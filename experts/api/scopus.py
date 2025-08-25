# See https://peps.python.org/pep-0655/#usage-in-python-3-11
from __future__ import annotations
from itertools import batched
from typing_extensions import NotRequired, TypedDict
from datetime import date, datetime
from functools import reduce, partial
import os
import re
from typing import Any, Callable, Iterable, Iterator, Mapping, MutableMapping, Sequence, Self
import uuid

import attrs
from attrs import Factory, field, frozen, validators

import dateutil

import httpx
import jsonpath_ng.ext as jp
from pipe import Pipe

from pycific.validated import ValidatedPMap, ValidatedStr

from pyrsistent import CheckedPMap, CheckedPSet, PRecord, field as pfield, freeze, thaw, m, pmap, s, v, pvector
from pyrsistent.typing import PMap, PSet

import returns
from returns.pipeline import is_successful
from returns.result import Result

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

# Would like to make these types more specific at some point:
CitationResponseBody = ResponseBody
CitationSubrecordBody = dict # ResponseBody would work, but seems misleading in this case.
AbstractResponseBody = ResponseBody
#class AbstractResponseBody(TypedDict):
#    ...
#    Would like to have this class, but the Scopus data we need is so deeply
#    nested, and Python's TypedDicts are so strict, that the costs outweigh
#    any documentation and type annotation benefits we would get from it.

Json = dict
#ScopusId = int # Are these always 11 digits?
#ScopusId = str # Are these always 11 digits? No!

class ScopusId(ValidatedStr):
    '''Are these always 11 digits? No! What we've seen as of 2025-08-25:
    min abstract: 84946606937
    max abstract: 105009540344
    min citation: 1842737537
    max citation: 105011990601
    The shortest Scopus ID we've seen is 10 characters, so 5 seems like a safe minimum.
    '''
    def _validate(self) -> Self:
        if not re.match(r'^\d{5,}$', self):
            raise ValueError(f'ScopusId value {self} is invalid: must be at least five characters, all digits')
        return self

class ScopusIds(CheckedPSet):
    '''Used for sets of defunct scopus records, etc'''
    __type__ = ScopusId

def iterable_to_scopus_ids(scopus_ids:Iterable[int|str|ScopusId]) -> ScopusIds:
    if isinstance(scopus_ids, ScopusIds):
        return scopus_ids
    return ScopusIds([
        ScopusId(scopus_id) for scopus_id in scopus_ids
    ])

class CitationRequestScopusIds(CheckedPSet):
    '''A set of Scopus IDs to include in a Citation Overview API request. Do not
    instantiate this class direcetly. Instead, use the citation_request_scopus_ids
    factory function'''
    __type__ = ScopusId

    def query_param_string(self):
        '''Scopus API requires multiple identifiers to be comma-separated'''
        return ','.join(self)

CITATION_OVERVIEW_MAX_IDENTIFIERS = 25

def citation_request_scopus_ids(scopus_ids:Iterable[int|str|ScopusId]) -> CitationRequestScopusIds:
    '''Factory function to create instances of CitationRequestScopusIds, which provides set size validation,
    because its base clase does not allow custom constructors or whole-set validation'''
    if len(scopus_ids) > CITATION_OVERVIEW_MAX_IDENTIFIERS:
        raise ValueError(f'Scopus Citation Overview API accepts no more than {CITATION_OVERVIEW_MAX_IDENTIFIERS} identifiers per request. {len(scopus_ids)} received')
    if len(scopus_ids) == 0:
        raise ValueError(f'Scopus Citation Overview API requires at least one identifier per request. 0 received')
    return CitationRequestScopusIds(iterable_to_scopus_ids(scopus_ids))

def scopus_ids_to_citation_request_subsets(scopus_ids:Iterable[int|str|ScopusId]) -> Sequence[CitationRequestScopusIds]:
    # TODO: Can we return a tuple, pset, or pvector here?
    return [
        citation_request_scopus_ids(batch)
        for batch in list(batched(scopus_ids, CITATION_OVERVIEW_MAX_IDENTIFIERS))
    ]

# In the classes below, setting a value type of Request Result caused an infinite loop
# in pyrsistent:
#
#Traceback (most recent call last):
#  File "/home/naughton/github.com/UMNLibraries/experts/./scopus_results_assorter.py", line 5, in <module>
#    from experts.api.scopus import \
#  File "/home/naughton/github.com/UMNLibraries/experts/experts/api/scopus.py", line 76, in <module>
#    class AbstractRequestResult(CheckedPMap):
#  File "/home/naughton/github.com/UMNLibraries/experts/.venv/lib/python3.12/site-packages/pyrsistent/_checked_types.py", line 434, in __new__
#    _store_types(dct, bases, '_checked_value_types', '__value_type__')
#  File "/home/naughton/github.com/UMNLibraries/experts/.venv/lib/python3.12/site-packages/pyrsistent/_checked_types.py", line 102, in _store_types
#    maybe_types = maybe_parse_many_user_types([
#                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#  File "/home/naughton/github.com/UMNLibraries/experts/.venv/lib/python3.12/site-packages/pyrsistent/_checked_types.py", line 98, in maybe_parse_many_user_types
#    return maybe_parse_user_type(ts)
#           ^^^^^^^^^^^^^^^^^^^^^^^^^
#  File "/home/naughton/github.com/UMNLibraries/experts/.venv/lib/python3.12/site-packages/pyrsistent/_checked_types.py", line 87, in maybe_parse_user_type
#    return tuple(e for t in ts for e in maybe_parse_user_type(t))
#           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#  File "/home/naughton/github.com/UMNLibraries/experts/.venv/lib/python3.12/site-packages/pyrsistent/_checked_types.py", line 87, in <genexpr>
#    return tuple(e for t in ts for e in maybe_parse_user_type(t))
#           ^^^^^^^^^^^^^^^^^^^^^^^^^
#  File "/home/naughton/github.com/UMNLibraries/experts/.venv/lib/python3.12/site-packages/pyrsistent/_checked_types.py", line 87, in maybe_parse_user_type
#    return tuple(e for t in ts for e in maybe_parse_user_type(t))
#           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#  File "/home/naughton/github.com/UMNLibraries/experts/.venv/lib/python3.12/site-packages/pyrsistent/_checked_types.py", line 87, in <genexpr>
#    return tuple(e for t in ts for e in maybe_parse_user_type(t))
# ...
#
#  File "/home/naughton/.anyenv/envs/pyenv/versions/3.12.11/lib/python3.12/typing.py", line 1458, in __iter__
#    yield Unpack[self]
#          ~~~~~~^^^^^^
#  File "/home/naughton/.anyenv/envs/pyenv/versions/3.12.11/lib/python3.12/typing.py", line 395, in inner
#    return _caches[func](*args, **kwds)
#           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#  File "/home/naughton/.anyenv/envs/pyenv/versions/3.12.11/lib/python3.12/typing.py", line 1286, in __hash__
#    return hash((self.__origin__, self.__args__))
#           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
#  File "/home/naughton/.anyenv/envs/pyenv/versions/3.12.11/lib/python3.12/typing.py", line 1286, in __hash__
#    return hash((self.__origin__, self.__args__))
#           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
# ...

class AbstractRequestResult(PRecord):
    scopus_id = pfield(type=ScopusId, mandatory=True)
    result = pfield(type=Result, mandatory=True)
    # For some unknown reason, pyrsistent can't handle the RequestResult type.
    # The following results in an infinite loop:
    #result = pfield(type=RequestResult, mandatory=True)

    def kv(self) -> tuple[ScopusId, Result]:
        return (self.scopus_id, self.result)

class CitationRequestResult(PRecord):
    scopus_ids = pfield(type=CitationRequestScopusIds, mandatory=True)
    result = pfield(type=Result, mandatory=True)

    def kv(self) -> tuple[CitationRequestScopusIds, Result]:
        return (self.scopus_ids, self.result)

ScopusIdRequestResult = AbstractRequestResult | CitationRequestResult

class SuccessResponse(PRecord):
    headers = pfield(type=httpx.Headers)
    body = pfield(type=Json)

class SuccessResponses(CheckedPMap):
    # The following type union  triggers an error from pyrsistent:
    # "TypeError: Type specifications must be types or strings. Input: str | experts.api.scopus.CitationRequestScopusIds"
    #__key_type__ = ScopusIdEnigma (This was a union type of either ScopusId or CitationRequestScopusIds
    __key_type__ = ScopusId
    __value_type__ = SuccessResponse

class AbstractSuccessResponses(CheckedPMap):
    __key_type__ = ScopusId
    __value_type__ = SuccessResponse

class CitationSuccessResponses(CheckedPMap):
    __key_type__ = CitationRequestScopusIds # Notice that this is a set!
    __value_type__ = SuccessResponse

    def scopus_ids(self) -> ScopusIds:
        return iterable_to_scopus_ids(
            list(
                reduce(
                    # Calling list() on a set returns a list of the elements in the set,
                    # which we recursively concatenate to reduce them into a single list
                    # of scopus Ids:
                    lambda set_a, set_b: list(set_a) + list(set_b),

                    # CheckedPMap keys() are a set, and each key is itself a set of type
                    # CitationRequestScopusIds, so we have sets of sets. We unpack
                    # each set of keys into its elements using the asterisk operator,
                    # to produce a single list of sets:
                    list(self.keys()),
                    []
                )
            )
        )

class CitationSuccessSubrecords(CheckedPMap):
    __key_type__ = ScopusId
    __value_type__ = CitationSubrecordBody

    def scopus_ids(self) -> ScopusIds:
        return iterable_to_scopus_ids(
            list(self.keys())
        )

class ErrorResult(PRecord):
    exception = pfield(type=(Exception, type(None)))
    response = pfield(type=(httpx.Response, type(None)))

class ErrorResults(CheckedPMap):
    #__key_type__ = ScopusIdEnigma
    __key_type__ = ScopusId
    __value_type__ = ErrorResult

class AbstractErrorResults(CheckedPMap):
    __key_type__ = ScopusId
    __value_type__ = ErrorResult

class CitationErrorResults(CheckedPMap):
    __key_type__ = CitationRequestScopusIds # Notice that this is a set!
    __value_type__ = ErrorResult

    def scopus_ids(self) -> ScopusIds:
        return iterable_to_scopus_ids(
            list(
                reduce(
                    # Calling list() on a set returns a list of the elements in the set,
                    # which we recursively concatenate to reduce them into a single list
                    # of scopus Ids:
                    lambda set_a, set_b: list(set_a) + list(set_b),

                    # CheckedPMap keys() are a set, and each key is itself a set of type
                    # CitationRequestScopusIds, so we have sets of sets. We unpack
                    # each set of keys into its elements using the asterisk operator,
                    # to produce a single list of sets:
                    list(self.keys()),
                    []
                )
            )
        )

# Final data structure of multiple results, e.g. concurrent requests for 1000 abstracts:
class AssortedResults(PRecord):
    success = pfield(type=SuccessResponses)
    defunct = pfield(type=ErrorResults)
    error = pfield(type=ErrorResults)

    def scopus_ids(self):
        return iterable_to_scopus_ids(
            list(self.success.keys()) + list(self.defunct.keys()) + list(self.error.keys())
        )

# Final data structure of multiple results, e.g. concurrent requests for 1000 abstracts:
class AbstractAssortedResults(PRecord):
    success = pfield(type=AbstractSuccessResponses)
    defunct = pfield(type=AbstractErrorResults)
    error = pfield(type=AbstractErrorResults)

    def scopus_ids(self) -> ScopusIds:
        return iterable_to_scopus_ids(
            # CheckedPMap keys() are a set, and each set contains scopus Ids. We unpack
            # each set into a list of its elements using the asterisk operator, then combine
            # those scopus ID elements into a single list:
            [*self.success.keys(), *self.defunct.keys(), *self.error.keys()]
        )

        # Another way to accomplish what we did above:
        #return ScopusIds(
        #    list(self.success.keys()) + list(self.defunct.keys()) + list(self.error.keys())
        #)


# Final data structure of multiple results, e.g. concurrent requests for 1000 citations:
class CitationAssortedResults(PRecord):
    success = pfield(type=CitationSuccessResponses)
    defunct = pfield(type=CitationErrorResults)
    error = pfield(type=CitationErrorResults)

    success_subrecords = pfield(type=CitationSuccessSubrecords)
    defunct_scopus_ids = pfield(type=ScopusIds)

    def scopus_ids(self) -> ScopusIds:
        return iterable_to_scopus_ids(
            list(
                reduce(
                    # Calling list() on a set returns a list of the elements in the set,
                    # which we recursively concatenate to reduce them into a single list
                    # of scopus Ids:
                    lambda set_a, set_b: list(set_a) + list(set_b),

                    # CheckedPMap keys() are a set, and each key is itself a set of type
                    # CitationRequestScopusIds, so we have sets of sets. We unpack
                    # each set of keys into its elements using the asterisk operator,
                    # to produce a single list of sets:
                    [*self.success.keys(), *self.defunct.keys(), *self.error.keys()],
                    []
                )
            )
        )

class ScopusIdRequestResultAssorter:
    @staticmethod
    def classify(accumulator: MutableMapping, request_result: AbstractRequestResult | CitationRequestResult) -> MutableMapping:
        # Note that ScopusIdRequestResult is a type union, such that the scopus ID(s)
        # associated with a request could be either a single scopus ID or a set of
        # scopus IDs, thus "enigma":
        scopus_id_enigma, result = request_result.kv()
        if is_successful(result):
            response = result.unwrap()
            if response.status_code == 200:
                accumulator['success'][scopus_id_enigma] = SuccessResponse(headers=response.headers, body=response.json())
            elif response.status_code == 404:
                accumulator['defunct'][scopus_id_enigma] = ErrorResult(exception=None, response=response)
            else:
                accumulator['error'][scopus_id_enigma] = ErrorResult(exception=None, response=response)
        else:
            accumulator['error'][scopus_id_enigma] = ErrorResult(exception=result.failure(), response=None)
        return accumulator

    @staticmethod
    def assort(results: Iterator[AbstractRequestResult | CitationRequestResult]) -> MutableMapping:
        #assorted = reduce(
        return reduce(
            ScopusIdRequestResultAssorter.classify,
            results,
            {'success': {}, 'defunct': {}, 'error': {}}
        )

class AbstractRequestResultAssorter:
    @staticmethod
    def assort(results: Iterator[AbstractRequestResult]) -> AbstractAssortedResults:
        assorted = ScopusIdRequestResultAssorter.assort(results)
        return AbstractAssortedResults(
            success=AbstractSuccessResponses(assorted['success']),
            defunct=AbstractErrorResults(assorted['defunct']),
            error=AbstractErrorResults(assorted['error']),
        )

class ResponseParser:
    @staticmethod
    def body(response:httpx.Response) -> ResponseBody:
        return response.json()

    @Pipe
    def responses_to_bodies(responses: Iterator[httpx.Response]) -> Iterator[ResponseBody]:
        for response in responses:
            yield ResponseParser.body(response)

    @Pipe
    def responses_to_headers_bodies(responses: Iterator[httpx.Response]) -> Iterator[tuple[httpx.Headers, ResponseBody]]:
        for response in responses:
            yield (response.headers, response.json())

class ResponseHeadersParser:
    def ratelimit(headers:httpx.Headers) -> int:
        return int(headers.get('x-ratelimit-limit'))

    def ratelimit_remaining(headers:httpx.Headers) -> int:
        return int(headers.get('x-ratelimit-remaining'))

    def ratelimit_reset(headers:httpx.Headers) -> datetime:
        return datetime.fromtimestamp(int(headers.get('x-ratelimit-reset')))

    @staticmethod
    def last_modified(headers:httpx.Headers) -> datetime:
        return dateutil.parser.parse(headers.get('last-modified'))

class AbstractResponseBodyParser():
    @staticmethod
    def eid(body: AbstractResponseBody) -> str:
        # There should always be exactly one of these:
        return jp.parse("$..coredata.eid").find(body)[0].value

    @staticmethod
    def scopus_id(body: AbstractResponseBody) -> str:
        return re.search(r'-(\d+)$', AbstractResponseBodyParser.eid(body)).group(1)

    @staticmethod
    def date_created(body: AbstractResponseBody) -> date:
        year, month, day = [
            jp.parse(f"$..item-info.history.date-created['@{date_part}']").find(body)[0].value
            for date_part in ['year','month','day']
        ]
        return date.fromisoformat(f'{year}-{month}-{day}')

    @staticmethod
    def refcount(body: AbstractResponseBody) -> int:
        refcount_expr = jp.parse("$..['@refcount']")
        matches = refcount_expr.find(body)
        if matches:
            return int(matches[0].value)
        else:
            return 0

    @staticmethod
    def reference_scopus_ids(body: AbstractResponseBody) -> list:
        return [
            itemid['$'] for itemid in filter(
                lambda itemid: itemid['@idtype'] == 'SGR',
                flatten_mixed_match_values(
                    jp.parse("$..reference[*].ref-info.refd-itemidlist.itemid").find(body)
                )
            )
        ]

    @Pipe
    def bodies_to_reference_scopus_ids(bodies: Iterator[AbstractResponseBody]) -> Iterator[str]:
        for body in bodies:
            for scopus_id in AbstractResponseBodyParser.reference_scopus_ids(body):
                yield scopus_id

    @Pipe
    def responses_to_reference_scopus_ids(responses: Iterator[httpx.Response]) -> Iterator[str]:
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

def single_citation(*, identifiers, cite_info, column_heading):
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

class CitationResponseBodyParser():
    @staticmethod
    def identifier_subrecords(body: CitationResponseBody) -> Iterator:
        return flatten_mixed_match_values(
            jp.parse('$..identifier-legend.identifier').find(body)
        )

    @staticmethod
    def cite_info_subrecords(body: CitationResponseBody) -> Iterator:
        return flatten_mixed_match_values(
            jp.parse('$..citeInfoMatrix.citeInfoMatrixXML.citationMatrix.citeInfo').find(body)
        )

    @staticmethod
    def column_heading(body: CitationResponseBody) -> Iterator: # TODO: Find a better type for this!
        return jp.parse('$..citeColumnTotalXML.citeCountHeader.columnHeading').find(body)[0].value

    @staticmethod
    def subrecords(body: CitationResponseBody) -> Iterator:
        column_heading = CitationResponseBodyParser.column_heading(body)
        return [
            single_citation(
                identifiers=identifiers,
                cite_info=cite_info,
                column_heading=column_heading,
            )
            for identifiers, cite_info in list(zip(
                CitationResponseBodyParser.identifier_subrecords(body),
                CitationResponseBodyParser.cite_info_subrecords(body)
            ))
        ]

class CitationSubrecordBodyParser():
    @staticmethod
    def scopus_id(body: CitationSubrecordBody) -> ScopusId:
        # There should be only one identifier dict in a subrecord:
        return jp.parse('$..identifier-legend.identifier[0].scopus_id').find(body)[0].value

    @staticmethod
    def sort_year(body: CitationSubrecordBody) -> datetime:
        return datetime.strptime(    
            jp.parse('$..citeInfoMatrix.citeInfoMatrixXML.citationMatrix.citeInfo[0].sort-year').find(body)[0].value, '%Y'
        )

def parse_citation_success_responses(responses:Sequence[SuccessResponse]) -> CitationSuccessSubrecords:
    return CitationSuccessSubrecords({
        ScopusId(CitationSubrecordBodyParser.scopus_id(subrecord)): subrecord
        for subrecord in list(reduce(
            lambda list1, list2: list1 + list2,
            # Each call to subrecords will return a list, so we need to reduce the following
            # list of lists into a single list:
            [CitationResponseBodyParser.subrecords(response.body) for response in responses],
            []
        ))
    })

class CitationRequestResultAssorter:
    @staticmethod
    def assort(results: Iterator[CitationRequestResult]) -> CitationAssortedResults:
        assorted = ScopusIdRequestResultAssorter.assort(results)

        # Because we may request multiple citations at a time, we need to do some
        # extra work to parse out individual subrecords and defunct scopus Ids:
        
        success_subrecords = parse_citation_success_responses(assorted['success'].values())

        success = CitationSuccessResponses(assorted['success'])
        defunct = CitationErrorResults(assorted['defunct'])

        defunct_scopus_ids = ScopusIds(
            list(success.scopus_ids() - success_subrecords.scopus_ids()) + list(defunct.scopus_ids())
        )

        return CitationAssortedResults(
            success=success,
            defunct=defunct,
            error=CitationErrorResults(assorted['error']),
            success_subrecords=success_subrecords,
            defunct_scopus_ids=defunct_scopus_ids,
        )

@frozen(kw_only=True)
class Client:
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
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
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
        return manage_request_attempts(
            httpx_client = self.httpx_client,
            prepared_request = prepared_request,
            retryable = self.retryable,
            next_wait_interval = self.next_wait_interval,
            max_attempts = self.max_attempts,
            attempts_id = uuid.uuid4(),
        )

    def get(self, resource_path, *args, params=m(), **kwargs):
        prepared_request = self.httpx_client.build_request(
            'GET',
            resource_path,
            params=thaw(params),
            timeout=self.timeout # TODO: Change to default_timeout
        )
        return self.request(*args, prepared_request=prepared_request, **kwargs)

    def get_abstract_by_scopus_id(
        self,
        scopus_id:ScopusId,
        *args,
        params=m(view='FULL'),
        **kwargs
    ) -> AbstractRequestResult:
        # Return a tuple with the scopus ID and the result of the request, so we can associate the two later:
        return AbstractRequestResult(
            scopus_id=scopus_id,
            result=self.get(
                f'abstract/scopus_id/{scopus_id}',
                *args,
                params=params,
                timeout=self.timeout, # TODO: Change to default_timeout
                **kwargs
            )
        )

    def get_citations_by_scopus_ids(
        self,
        scopus_ids:CitationRequestScopusIds,
        *args,
        params:RequestParms = m(citation='exclude-self'),
        **kwargs,
    ) -> CitationRequestResult:
        # Return a tuple with the scopus IDs and the result of the request, so we can associate the two later:
        return CitationRequestResult(
            scopus_ids=scopus_ids,
            result=self.get(
                f'abstract/citations',
                *args,
                params=params.set('scopus_id', scopus_ids.query_param_string()),
                timeout=self.timeout, # TODO: Change to default_timeout
                **kwargs
            )
        )

    def request_many_by_id(
        self,
        request_function: RequestFunction,
        collection: str,
        id_type: str,
        ids: Iterator,
        params: RequestParams = m(),
    ) -> Iterator[httpx.Response]:
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
        scopus_ids: Iteratable[int|str|ScopusId],
        params: RequestParams = m(view='FULL'),
    ) -> Iterator[AbstractRequestResult]:
        partial_request = partial(
            self.get_abstract_by_scopus_id,
            params=params,
        )
        def request_by_scopus_id(scopus_id: ScopusId):
            return partial_request(scopus_id)

        for result in common.request_many_by_identifier(
            request_by_identifier_function = request_by_scopus_id,
            identifiers = iterable_to_scopus_ids(scopus_ids),
        ):
            yield result

    def get_many_citations_by_scopus_ids(
        self,
        scopus_ids: Iterable[int|str|ScopusId],
        params: RequestParams = m(citation='exclude-self'),
    ) -> Iterator[CitationRequestResult]:
        partial_request = partial(
            self.get_citations_by_scopus_ids,
            params=params,
        )
        def request_by_scopus_ids(scopus_ids_set: CitationRequestScopusIds):
            return partial_request(scopus_ids_set)

        for result in common.request_many_by_identifier(
            request_by_identifier_function = request_by_scopus_ids,
            identifiers = scopus_ids_to_citation_request_subsets(scopus_ids),
        ):
            yield result
