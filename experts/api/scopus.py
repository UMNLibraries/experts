# See https://peps.python.org/pep-0655/#usage-in-python-3-11
"""Scopus API client, response parsers, and result classification helpers."""

from __future__ import annotations
from typing_extensions import NotRequired, TypedDict
from datetime import date, datetime
from functools import reduce, partial
import os
import re
from typing import Callable, Iterable, Iterator, Mapping
import uuid

import attrs
from attrs import Factory, field, frozen, validators

import dateutil

import httpx
import jsonpath_ng.ext as jp
from pipe import Pipe

from pyrsistent import CheckedPMap, CheckedPSet, PRecord, field as pfield, freeze, thaw, m, pmap, v, pvector
from pyrsistent.typing import PMap, PSet

import returns
from returns.pipeline import is_successful

from experts.api import common
from experts.api.common import \
    default_max_attempts, \
    default_retryable, \
    default_next_wait_interval, \
    manage_request_attempts, \
    RequestParams, \
    RequestResult, \
    ResponseBody, \
    ResponseBodyItem

from experts.helpers.jsonpath import flatten_mixed_match_values

Json = dict
ScopusId = str # Are these always 11 digits?
ScopusIdRequestResult = tuple[ScopusId, RequestResult]

class SuccessResponse(PRecord):
    """Container for a successful Scopus response payload and headers."""

    headers = pfield(type=httpx.Headers)
    body = pfield(type=Json)

class SuccessResponses(CheckedPMap):
    """Mapping of Scopus ID to successful response payload."""

    __key_type__ = ScopusId
    __value_type__ = SuccessResponse

class ScopusIds(CheckedPSet):
    '''Used for sets of defunct scopus records, etc'''
    __type__ = ScopusId

class ErrorResult(PRecord):
    """Container for request exception or non-success HTTP response."""

    exception = pfield(type=(Exception, type(None)))
    response = pfield(type=(httpx.Response, type(None)))

class ErrorResults(CheckedPMap):
    """Mapping of Scopus ID to request error information."""

    __key_type__ = ScopusId
    __value_type__ = ErrorResult

# Final data structure of multiple results, e.g. concurrent requests for 1000 abstracts:
class AssortedResults(PRecord):
    """Final grouped result set for many Scopus abstract requests."""

    success = pfield(type=SuccessResponses)
    defunct = pfield(type=ScopusIds)
    error = pfield(type=ErrorResults)

    def scopus_ids(self):
        """Returns all Scopus IDs represented in this result set.

        Returns:
            A set-like ScopusIds collection containing IDs from successful,
            defunct, and error buckets.
        """
        return ScopusIds(list(self.success.keys()) + list(self.defunct) + list(self.error.keys()))

class ScopusIdRequestResultAssorter:
    """Utility for grouping Scopus request results into typed buckets."""

    @staticmethod
    def classify(accumulator: dict, request_result: ScopusIdRequestResult) -> dict:
        """Classifies one Scopus request result into aggregation buckets.

        Args:
            accumulator: A mutable dict containing success, defunct, and error
                collections.
            request_result: A tuple of (scopus_id, request result).

        Returns:
            The same accumulator after classifying the request outcome.
        """
        scopus_id, result = request_result
        if is_successful(result):
            response = result.unwrap()
            if response.status_code == 200:
                accumulator['success'][scopus_id] = SuccessResponse(headers=response.headers, body=response.json())
            elif response.status_code == 404:
                accumulator['defunct'].append(scopus_id)
            else:
                accumulator['error'][scopus_id] = ErrorResult(exception=None, response=response)
        else:
            accumulator['error'][scopus_id] = ErrorResult(exception=result.failure(), response=None)
        return accumulator

    @staticmethod
    def assort(results: Iterator[ScopusIdRequestResult]) -> AssortedResults:
        """Aggregates many Scopus request results into typed result groups.

        Args:
            results: An iterator of (scopus_id, request result) tuples.

        Returns:
            An AssortedResults record containing success, defunct, and error
            groupings.
        """
        assorted = reduce(
            ScopusIdRequestResultAssorter.classify,
            results,
            {'success': {}, 'defunct': [], 'error': {}}
        )
        return AssortedResults(
            success=SuccessResponses(assorted['success']),
            defunct=ScopusIds(assorted['defunct']),
            error=ErrorResults(assorted['error']),
        )

class ResponseParser:
    """Helpers that parse Scopus HTTP responses into iterable-friendly shapes."""

    @staticmethod
    def body(response:httpx.Response) -> ResponseBody:
        """Parses a Scopus HTTP response body as JSON.

        Args:
            response: An HTTP response from the Scopus API.

        Returns:
            The decoded response body mapping.
        """
        return response.json()

    @Pipe
    def responses_to_bodies(responses: Iterator[httpx.Response]) -> Iterator[ResponseBody]:
        """Converts a stream of responses to response bodies.

        Args:
            responses: HTTP responses to parse.

        Yields:
            Parsed response bodies.
        """
        for response in responses:
            yield ResponseParser.body(response)

    @Pipe
    def responses_to_headers_bodies(responses: Iterator[httpx.Response]) -> Iterator[tuple[httpx.Headers, ResponseBody]]:
        """Converts responses to (headers, body) tuples.

        Args:
            responses: HTTP responses to parse.

        Yields:
            Tuples of response headers and parsed body mappings.
        """
        for response in responses:
            yield (response.headers, response.json())

class ResponseHeadersParser:
    """Helpers that parse Scopus rate-limit and metadata response headers."""

    def ratelimit(headers:httpx.Headers) -> int:
        """Extracts the rate-limit ceiling from response headers.

        Args:
            headers: HTTP response headers.

        Returns:
            The integer value of x-ratelimit-limit.
        """
        return int(headers.get('x-ratelimit-limit'))

    def ratelimit_remaining(headers:httpx.Headers) -> int:
        """Extracts remaining requests from response headers.

        Args:
            headers: HTTP response headers.

        Returns:
            The integer value of x-ratelimit-remaining.
        """
        return int(headers.get('x-ratelimit-remaining'))

    def ratelimit_reset(headers:httpx.Headers) -> datetime:
        """Extracts the reset timestamp as a datetime.

        Args:
            headers: HTTP response headers.

        Returns:
            Reset time parsed from x-ratelimit-reset (unix seconds).
        """
        return datetime.fromtimestamp(int(headers.get('x-ratelimit-reset')))

    @staticmethod
    def last_modified(headers:httpx.Headers) -> datetime:
        """Parses the last-modified timestamp from headers.

        Args:
            headers: HTTP response headers.

        Returns:
            The parsed last-modified datetime value.
        """
        return dateutil.parser.parse(headers.get('last-modified'))

#class AbstractResponseBody(TypedDict):
#    ...
#    Would like to have this class, but the Scopus data we need is so deeply
#    nested, and Python's TypedDicts are so strict, that the costs outweigh
#    any documentation and type annotation benefits we would get from it.

class AbstractResponseBodyParser():
    """Extractors for key fields from Scopus abstract response bodies."""

    @staticmethod
    def eid(body: ResponseBody) -> str:
        """Extracts the EID from an abstract response body.

        Args:
            body: Parsed Scopus abstract response body.

        Returns:
            The EID value.
        """
        # There should always be exactly one of these:
        return jp.parse("$..coredata.eid").find(body)[0].value

    @staticmethod
    def scopus_id(body: ResponseBody) -> str:
        """Extracts the Scopus ID from an abstract response body.

        Args:
            body: Parsed Scopus abstract response body.

        Returns:
            The numeric Scopus ID parsed from the EID suffix.
        """
        return re.search(r'-(\d+)$', AbstractResponseBodyParser.eid(body)).group(1)

    @staticmethod
    def date_created(body: ResponseBody) -> date:
        """Extracts the record creation date from an abstract response body.

        Args:
            body: Parsed Scopus abstract response body.

        Returns:
            The created date as a date object.
        """
        year, month, day = [
            jp.parse(f"$..item-info.history.date-created['@{date_part}']").find(body)[0].value
            for date_part in ['year','month','day']
        ]
        return date.fromisoformat(f'{year}-{month}-{day}')

    @staticmethod
    def refcount(body: ResponseBody) -> int:
        """Extracts reference count from an abstract response body.

        Args:
            body: Parsed Scopus abstract response body.

        Returns:
            The integer reference count, or 0 if absent.
        """
        refcount_expr = jp.parse("$..['@refcount']")
        matches = refcount_expr.find(body)
        if matches:
            return int(matches[0].value)
        else:
            return 0

    @staticmethod
    def reference_scopus_ids(body: ResponseBody) -> list:
        """Extracts referenced Scopus IDs from an abstract response body.

        Args:
            body: Parsed Scopus abstract response body.

        Returns:
            A list of referenced Scopus IDs for SGR reference items.
        """
        return [
            itemid['$'] for itemid in filter(
                lambda itemid: itemid['@idtype'] == 'SGR',
                flatten_mixed_match_values(
                    jp.parse("$..reference[*].ref-info.refd-itemidlist.itemid").find(body)
                )
            )
        ]

    @Pipe
    def bodies_to_reference_scopus_ids(bodies: Iterator[ResponseBody]) -> Iterator[str]:
        """Flattens a stream of bodies into referenced Scopus IDs.

        Args:
            bodies: Parsed abstract response bodies.

        Yields:
            Referenced Scopus IDs from each body.
        """
        for body in bodies:
            for scopus_id in AbstractResponseBodyParser.reference_scopus_ids(body):
                yield scopus_id

    @Pipe
    def responses_to_reference_scopus_ids(responses: Iterator[httpx.Response]) -> Iterator[str]:
        """Flattens a stream of responses into referenced Scopus IDs.

        Args:
            responses: Abstract API responses.

        Yields:
            Referenced Scopus IDs from each response body.
        """
        for scopus_id in responses | ResponseParser.responses_to_bodies | AbstractResponseBodyParser.bodies_to_reference_scopus_ids:
            yield scopus_id


#    # Not sure we'll need this, but keeping it here and commented out for now.
#    def issn(body: ResponseBody) -> str:
#        if 'issn' not in body['abstracts-retrieval-response']['item']['bibrecord']['head']['source']:
#            print('scopus id:', AbstractResponseBodyParser.scopus_id(body))
#            print(body['abstracts-retrieval-response']['item']['bibrecord']['head']['source'])
#            # TODO: Fix the line below!
#            return None
#        return body['abstracts-retrieval-response']['item']['bibrecord']['head']['source']['issn']['$']

def single_citation_overview(*, identifiers, cite_info, column_heading):
    """Builds a normalized single citation-overview payload fragment.

    Args:
        identifiers: Identifier subrecord for a single overview row.
        cite_info: Citation metrics subrecord for the same row.
        column_heading: Column heading label shared across rows.

    Returns:
        A dict shaped like one abstract-citations-response unit.
    """
    return {
        'abstract-citations-response': {
            'h-index': '1',
            'identifier-legend': {
                'identifier': [identifiers],
            },
            'citeInfoMatrix': {
                'citeInfoMatrixXML': {
                    'citationMatrix': {
                        'citeInfo': [cite_info],
                    },
                },
            },
            'citeColumnTotalXML': {
                'citeCountHeader': {
                    'prevColumnHeading': 'previous',
                    'columnHeading': column_heading,
                    'laterColumnHeading': 'later',
                    'prevColumnTotal': cite_info['pcc'],
                    'columnTotal': cite_info['cc'],
                    'laterColumnTotal': cite_info['lcc'],
                    'rangeColumnTotal': cite_info['rangeCount'],
                    'grandTotal': cite_info['rowTotal'],
                },
            },
        },
    }

class CitationOverviewResponseBodyParser():
    """Parsers for Scopus citation-overview response body subrecords."""

    @staticmethod
    def identifier_subrecords(body: ResponseBody) -> Iterator:
        """Extracts identifier subrecords from a citation overview body.

        Args:
            body: Parsed citation overview response body.

        Returns:
            Flattened identifier subrecords.
        """
        return flatten_mixed_match_values(
            jp.parse('$..identifier-legend.identifier').find(body)
        )

    @staticmethod
    def cite_info_subrecords(body: ResponseBody) -> Iterator:
        """Extracts cite-info subrecords from a citation overview body.

        Args:
            body: Parsed citation overview response body.

        Returns:
            Flattened cite-info subrecords.
        """
        return flatten_mixed_match_values(
            jp.parse('$..citeInfoMatrix.citeInfoMatrixXML.citationMatrix.citeInfo').find(body)
        )

    @staticmethod
    def column_heading(body: ResponseBody) -> Iterator: # TODO: Find a better type for this!
        """Extracts the column heading label from a citation overview body.

        Args:
            body: Parsed citation overview response body.

        Returns:
            The column heading string.
        """
        return jp.parse('$..citeColumnTotalXML.citeCountHeader.columnHeading').find(body)[0].value

    @staticmethod
    def subrecords(body: ResponseBody) -> Iterator:
        """Builds normalized citation-overview subrecords from a body.

        Args:
            body: Parsed citation overview response body.

        Returns:
            A list of normalized single citation-overview dicts.
        """
        column_heading = CitationOverviewResponseBodyParser.column_heading(body)
        return [
            single_citation_overview(
                identifiers=identifiers,
                cite_info=cite_info,
                column_heading=column_heading,
            )
            for identifiers, cite_info in list(zip(
                CitationOverviewResponseBodyParser.identifier_subrecords(body),
                CitationOverviewResponseBodyParser.cite_info_subrecords(body)
            ))
        ]

@frozen(kw_only=True)
class Client:
    """Configurable Scopus HTTP client with retry and bulk request helpers."""

#    '''Common client configuration and behavior. Used by most functions.
#
#    Most attributes have defaults and are not required. Only ``domain`` and
#    ``key`` are required, and both can be set with environment variables as
#    well as constructor parameters.
#
#    Context instances are immutable. To use different configurations for different
#    function calls, pass different Context objects.
#    '''

    httpx_client: httpx.Client = field(init=False)
    '''An httpx.Client object. Default: ``httpx.Client()``.'''

    timeout: httpx.Timeout = httpx.Timeout(10.0, connect=3.0, read=60.0)
    '''httpx client timeouts. Default: ``httpx.Timeout(10.0, connect=3.0, read=60.0)``.'''

    max_attempts: int = 10
    '''An integer maximum number of times to retry a request. Default: ``10``.'''

    retryable: Callable = Factory(default_retryable)
    '''A function that takes a returns.Result and returns a boolean. Required. Default: Return value of ``default_retryable``.'''

    next_wait_interval: Callable = default_next_wait_interval
    '''A function that takes an integer number of seconds to wait and returns a new interval. Required. Default: Return value of ``default_next_wait_interval``.'''

    domain: str = field(
        default=os.environ.get('SCOPUS_API_DOMAIN'),
        validator=validators.instance_of(str)
    )
    '''Domain of a Scopus API server. Required. Default: environment variable SCOPUS_API_DOMAIN'''

    base_path: str = field(
        default='content',
        validator=validators.instance_of(str)
    )
    '''Base path of the Scopus API URL entry point.'''

    key: str = field(
        default=os.environ.get('SCOPUS_API_KEY'),
        validator=validators.instance_of(str)
    )
    '''Scopus API key. Required. Default: environment variable SCOPUS_API_KEY'''

    inst_token: str = field(
        default=os.environ.get('SCOPUS_API_INST_TOKEN'),
        validator=validators.instance_of(str)
    )
    '''Scopus API institutional token. Required. Default: environment variable SCOPUS_INST_TOKEN'''

    headers: PMap = pmap({
        'Accept': 'application/json',
        'Accept-Charset': 'utf-8',
    })
    '''HTTP headers to be sent on every request. The constructor automatically adds
    an ``X-ELS-APIKey`` header, using the value of the ``key`` attribute, and the
    an ``X-ELS-Insttoken`` header, using the value of the ``inst_token`` attribute.
    '''

    def __attrs_post_init__(self) -> None:
        """Initializes the underlying httpx client with Scopus settings."""
        object.__setattr__(
            self,
            'httpx_client',
            httpx.Client(
                base_url=f'https://{self.domain}/{self.base_path}/',
                headers={
                    **thaw(self.headers),
                    'X-ELS-APIKey': self.key,
                    'X-ELS-Insttoken': self.inst_token,
                }
            )
        )

    def __enter__(self):
        """Returns this client for use as a context manager."""
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        """Closes the underlying httpx client on context manager exit."""
        # TODO: Do something with the other args?
        self.httpx_client.close()

    def request(
        self,
        *args,
        prepared_request,
        retyrable = default_retryable,
        next_wait_interval = default_next_wait_interval,
        max_attempts = default_max_attempts,
        **kwargs
    ): # -> TODO: Type?
        """Sends a prepared request using shared retry attempt management.

        Args:
            prepared_request: Fully prepared httpx request to execute.

        Returns:
            A request result containing either a response or an exception.
        """
        return manage_request_attempts(
            httpx_client = self.httpx_client,
            prepared_request = prepared_request,
            retryable = self.retryable,
            next_wait_interval = self.next_wait_interval,
            max_attempts = self.max_attempts,
            attempts_id = uuid.uuid4(),
        )

    def get(self, resource_path, *args, params=m(), **kwargs):
        """Issues a GET request against a Scopus resource path.

        Args:
            resource_path: Relative API path.
            params: Query parameters as an immutable map.

        Returns:
            A request result containing either a response or an exception.
        """
        prepared_request = self.httpx_client.build_request(
            'GET',
            resource_path,
            params=thaw(params),
            timeout=self.timeout # TODO: Change to default_timeout
        )
        return self.request(*args, prepared_request=prepared_request, **kwargs)

    def get_abstract_by_scopus_id(self, scopus_id: ScopusId, *args, params=m(content='core', view='FULL'), **kwargs) -> tuple[ScopusId, RequestResult]:
        """Fetches one abstract by Scopus ID.

        Args:
            scopus_id: Target Scopus ID.
            params: Query parameters for abstract retrieval.

        Returns:
            A tuple containing the original Scopus ID and its request result.
        """
        prepared_request = self.httpx_client.build_request(
            'GET',
            f'abstract/scopus_id/{scopus_id}',
            params=thaw(params),
            timeout=self.timeout # TODO: Change to default_timeout
        )
        #return self.request(*args, prepared_request=prepared_request, **kwargs)
        # Return a tuple with the scopus ID and the result of the request, so we can associate the two later:
        return (scopus_id, self.request(*args, prepared_request=prepared_request, **kwargs))

    def request_many_by_id(
        self,
        request_function: RequestFunction,
        collection: str,
        id_type: str,
        ids: Iterator,
        params: RequestParams = m(),
    ) -> Iterator[httpx.Response]:
        """Requests many resources by ID and yields successful responses.

        Args:
            request_function: Bound request method used to make calls.
            collection: API collection name.
            id_type: Identifier path segment type.
            ids: Identifiers to request.
            params: Request parameters passed to each call.

        Yields:
            Responses with status code 200.
        """
        partial_request = partial(
            request_function,
            params=params,
        )
        def request_by_id(identifier: str):
            # Pass an id-specific resource_path:
            return partial_request(
                f'{collection}/{id_type}/{identifier}'
            )

        for result in common.request_many_by_identifier(
            request_by_identifier_function = request_by_id,
            identifiers = ids,
        ):
            if is_successful(result):
                response = result.unwrap()
                if response.status_code == 200:
                    yield response
                else:
                    print(f'Failed! {result}')
                    continue
            else:
            # TODO: log failure. Maybe pass in a logger?
                print(f'Failed! {result}')
                continue

    def get_many_abstracts_by_scopus_id(
        self,
        scopus_ids: Iterator,
        params: RequestParams = m(content='core', view='FULL'),
    #) -> Iterator[httpx.Response]:
    ) -> Iterator[tuple[ScopusId, RequestResult]]:
        """Requests abstracts for many Scopus IDs.

        Args:
            scopus_ids: Scopus IDs to request.
            params: Query parameters for each abstract request.

        Yields:
            Tuples of (scopus_id, request result).
        """
        partial_request = partial(
            self.get_abstract_by_scopus_id,
            params=params,
        )
        def request_by_scopus_id(scopus_id: ScopusId):
            # Pass an id-specific resource_path:
            return partial_request(scopus_id)

        for scopus_id, result in common.request_many_by_identifier(
            request_by_identifier_function = request_by_scopus_id,
            identifiers = scopus_ids,
        ):
            yield (scopus_id, result)
#            if is_successful(result):
#                response = result.unwrap()
#                if response.status_code == 200:
#                    yield response
#                else:
#                    print(f'Failed! {result}')
#                    continue
#            else:
#            # TODO: log failure. Maybe pass in a logger?
#                print(f'Failed! {result}')
#                continue
