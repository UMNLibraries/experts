# See https://peps.python.org/pep-0655/#usage-in-python-3-11
from __future__ import annotations

from itertools import batched
from datetime import date, datetime
from functools import cached_property, reduce, partial
import os
import re

# Previously we imported Self from typing, but we don't need it since we import annotations from __future__.
from typing import Any, Callable, Iterable, Iterator, Mapping, MutableMapping, Sequence

import uuid

import attrs
from attrs import Factory, field, frozen, validators

import dateutil

import httpx
import jsonpath_ng.ext as jp

from pycific.validated import ValidatedPMap, ValidatedPMapSpec, ValidatedStr

from pyrsistent import CheckedPMap, CheckedPSet, CheckedPVector, PRecord, field as pfield, freeze, thaw, m, pmap, s, v, pvector
from pyrsistent.typing import PMap, PSet

import returns
from returns.result import Result, Success, Failure, safe

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

class AbstractRecordValidated(ValidatedPMapSpec):
    eid: str
    scopus_id: ScopusId
    date_created: date
    refcount: int
    reference_scopus_ids: ScopusIds

class AbstractRecord(ValidatedPMap):
    def _validate(self) -> AbstractRecordValidated:
        return AbstractRecordValidated(
            eid=self.eid,
            scopus_id=self.scopus_id,
            date_created=self.date_created,
            refcount=self.refcount,
            reference_scopus_ids=self.reference_scopus_ids,
        )

    @cached_property
    def eid(self) -> str:
        # There should always be exactly one of these:
        return jp.parse("$..coredata.eid").find(
            # We need to thaw the self pmap, because jsonpath needs a dict:
            thaw(self)
        )[0].value

    @cached_property
    def scopus_id(self) -> ScopusId:
        return ScopusId(
            re.search(r'-(\d+)$', self.eid).group(1)
        )

    @cached_property
    def date_created(self) -> date:
        year, month, day = [
            jp.parse(f"$..item-info.history.date-created['@{date_part}']").find(
                # We need to thaw the self pmap, because jsonpath needs a dict:
                thaw(self)
            )[0].value
            for date_part in ['year','month','day']
        ]
        return date.fromisoformat(f'{year}-{month}-{day}')

    @cached_property
    def refcount(self) -> int:
        refcount_expr = jp.parse("$..['@refcount']")
        matches = refcount_expr.find(
            # We need to thaw the self pmap, because jsonpath needs a dict:
            thaw(self)
        )
        if matches:
            return int(matches[0].value)
        else:
            return 0

    @cached_property
    def reference_scopus_ids(self) -> ScopusIds:
        if self.refcount == 0:
            return ScopusIds([])
        scopus_ids, invalid_scopus_ids = ScopusIds.factory([
            itemid['$'] for itemid in filter(
                lambda itemid: itemid['@idtype'] == 'SGR',
                flatten_mixed_match_values(
                    jp.parse("$..reference[*].ref-info.refd-itemidlist.itemid").find(
                        # We need to thaw the self pmap, because jsonpath needs a dict:
                        thaw(self)
                    )
                )
            )
        ])
        if len(invalid_scopus_ids) > 0:
            raise ValueError(f'Parsing of abstract with Scopus ID {self.scopus_id} returned some invalid reference Scopus IDs: {invalid_scopus_ids}')
        return scopus_ids

#    # Not sure we'll need this, but keeping it here and commented out for now.
#    def issn(self) -> str:
#        if 'issn' not in self['abstracts-retrieval-response']['item']['bibrecord']['head']['source']:
#            print('scopus id:', self.scopus_id())
#            print(self['abstracts-retrieval-response']['item']['bibrecord']['head']['source'])
#            # TODO: Fix the line below!
#            return None
#        return self['abstracts-retrieval-response']['item']['bibrecord']['head']['source']['issn']['$']

class CitationRecordMixin():
    @cached_property
    def _identifier_subrecords(self) -> Iterable[dict]:
        return list(flatten_mixed_match_values(
            jp.parse('$..identifier-legend.identifier').find(
                # We need to thaw the self pmap, because jsonpath needs a dict:
                thaw(self)
            )
        ))

    @cached_property
    def _cite_info_subrecords(self) -> Iterable[dict]:
        return list(flatten_mixed_match_values(
            jp.parse('$..citeInfoMatrix.citeInfoMatrixXML.citationMatrix.citeInfo').find(
                # We need to thaw the self pmap, because jsonpath needs a dict:
                thaw(self)
            )
        ))

    @cached_property
    def _column_heading(self) -> Iterable[dict]:
        return jp.parse('$..citeColumnTotalXML.citeCountHeader.columnHeading').find(
            # We need to thaw the self pmap, because jsonpath needs a dict:
            thaw(self)
        )[0].value

class CitationMaybeMultiRecordValidated(ValidatedPMapSpec):
    _identifier_subrecords: Iterable[dict]
    _cite_info_subrecords: Iterable[dict]
    _column_heading: Iterable[dict]
    scopus_ids: ScopusIds
    single_records: Iterable[CitationSingleRecord]

class CitationMaybeMultiRecord(ValidatedPMap, CitationRecordMixin):
    def _validate(self) -> CitationMaybeMultiRecordValidated:
        return CitationMaybeMultiRecordValidated(
            _column_heading=self._column_heading,
            _identifier_subrecords=self._identifier_subrecords,
            _cite_info_subrecords=self._cite_info_subrecords,
            scopus_ids=self.scopus_ids,
            single_records=self.single_records,
        )

    @property
    def scopus_ids(self) -> ScopusIds:
        scopus_ids, invalid_scopus_ids = ScopusIds.factory(
            map(lambda subrecord: subrecord['scopus_id'], self._identifier_subrecords)
        )
        if len(invalid_scopus_ids) > 0:
            raise ValueError(f'Parsing of a citation overview returned some invalid Scopus IDs: {invalid_scopus_ids}')
        return scopus_ids

    @cached_property
    def single_records(self) -> list[CitationSingleRecord]:
        return [
            CitationSingleRecord({
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
                            'columnHeading': self._column_heading,
                            'laterColumnHeading': 'later',
                            'prevColumnTotal': cite_info['pcc'],
                            'columnTotal': cite_info['cc'],
                            'laterColumnTotal': cite_info['lcc'],
                            'rangeColumnTotal': cite_info['rangeCount'],
                            'grandTotal': cite_info['rowTotal'],
                        },
                    },
                },
            })
            for identifiers, cite_info in list(zip(
                self._identifier_subrecords,
                self._cite_info_subrecords,
            ))
        ]

class CitationSingleRecordValidated(ValidatedPMapSpec):
    scopus_id: ScopusId
    sort_year: datetime
    _identifier_subrecords: Iterable[dict]
    _cite_info_subrecords: Iterable[dict]
    _column_heading: Iterable[dict]

class CitationSingleRecord(ValidatedPMap, CitationRecordMixin):
    def _validate(self) -> CitationSingleRecordValidated:
        return CitationSingleRecordValidated(
            scopus_id=self.scopus_id,
            sort_year=self.sort_year,
            _column_heading=self._column_heading,
            _identifier_subrecords=self._identifier_subrecords,
            _cite_info_subrecords=self._cite_info_subrecords,
        )

    @cached_property
    def scopus_id(self) -> ScopusId:
        # There should be only one identifier dict in a single record:
        return ScopusId(
            # We avoid the complex, repetitious, commented-out code below by using a mixin property method:
            #jp.parse('$..identifier-legend.identifier[0].scopus_id').find(thaw(self))[0].value
            self._identifier_subrecords[0]['scopus_id']
        )

    @cached_property
    def sort_year(self) -> datetime:
        # There should be only one cite info dict in a single record:
        return datetime.strptime(
            # We avoid the complex, repetitious, commented-out code below by using a mixin property method:
            #jp.parse('$..citeInfoMatrix.citeInfoMatrixXML.citationMatrix.citeInfo[0].sort-year').find(thaw(self))[0].value, '%Y'
            self._cite_info_subrecords[0]['sort-year'], '%Y'
        )

    # TODO: Add issn()?

class ScopusId(ValidatedStr):
    '''Are these always 11 digits? No! What we've seen as of 2025-08-25:
    min abstract: 84946606937
    max abstract: 105009540344
    min citation: 1842737537
    max citation: 105011990601
    The shortest Scopus ID we've seen is 10 characters, so 5 seems like a safe minimum.
    TODO: Do any Scopus IDs start with a leading zero, though? That could be a problem
    for storing these as integers, especially in a database.
    '''
    def _validate(self) -> ScopusId:
        if not re.match(r'^\d{5,}$', self):
            raise ValueError(f'ScopusId value {self} is invalid: must be at least five characters, all digits')
        return self

# This type alias is just to make our code self-documenting
InvalidScopusId = Any

class ScopusIds(CheckedPSet):
    '''Used for sets of defunct scopus records, etc'''
    __type__ = ScopusId

    @classmethod
    def union(cls, *scopus_ids:Iterable[ScopusId]) -> ScopusIds:
        # The built-in set().union function doesn't seem to work with CheckedPSets
        # and multiple set arguments, so we make it work here as a class method.
        # Each argument after `cls` must be an iterable containing validated
        # instances of ScopusID.
        return ScopusIds(
            set().union(*scopus_ids)
        )

    @classmethod
    def validate_scopus_ids(cls, scopus_ids:Iterable[int|str|ScopusId]) -> tuple[set[ScopusId], set[InvalidScopusId]]:
        valid_scopus_ids = set()
        invalid_scopus_ids = set()
        for scopus_id in scopus_ids:
            match ScopusId.factory(scopus_id):
                case Success(valid_scopus_id):
                    valid_scopus_ids.add(valid_scopus_id)
                case Failure(Exception):
                    invalid_scopus_ids.add(scopus_id)
        return (valid_scopus_ids, invalid_scopus_ids)

    @classmethod
    def factory(cls, scopus_ids:Iterable[int|str|ScopusId]) -> tuple[ScopusIds, set[InvalidScopusId]]:
        if isinstance(scopus_ids, cls):
            return (scopus_ids, set())
        valid_scopus_ids, invalid_scopus_ids = cls.validate_scopus_ids(scopus_ids)
        return (cls(valid_scopus_ids), invalid_scopus_ids)

# We set this as a python "constant" in case we ever want to support
# identifiers other than Scopus IDs:
CITATION_OVERVIEW_REQUEST_MAX_IDENTIFIERS = 25

class CitationRequestScopusIds(CheckedPSet):
    '''A set of Scopus IDs to include in a Citation Overview API request. Do not
    instantiate this class direcetly. Instead, use CitationRequestScopusIds.factory()
    '''
    __type__ = ScopusId

    #@property
    # Update: Using this generates this error:
    # TypeError: 'property' object cannot be interpreted as an integer
    @classmethod
    def max_scopus_ids_per_request(cls):
        return CITATION_OVERVIEW_REQUEST_MAX_IDENTIFIERS

    @classmethod
    def factory(cls, scopus_ids:Iterable[int|str|ScopusId]) -> tuple[list[CitationRequestScopusIds], set[InvalidScopusId]]:
        if isinstance(scopus_ids, cls):
            return (scopus_ids, set())
        valid_scopus_ids, invalid_scopus_ids = ScopusIds.validate_scopus_ids(scopus_ids)
        citation_request_scopus_ids = [
            cls(batch)
            for batch in list(batched(valid_scopus_ids, cls.max_scopus_ids_per_request()))
        ]
        return (citation_request_scopus_ids, invalid_scopus_ids)

    def query_param_string(self):
        '''Scopus API requires multiple identifiers to be comma-separated'''
        return ','.join(self)

class RequestResponse(PRecord):
    response = pfield(type=httpx.Response, mandatory=True)

#    @property
#    def response_text(self) -> str:
#        return self.response.text
#
#    @property
#    def response_json(self) -> dict:
#        return self.response.json()

class RequestResponseWithRatelimit(RequestResponse):
    # If we try to use @cached_property, we get:
    # "TypeError: No '__dict__' attribute on 'AbstractSuccessResponse' instance to cache 'ratelimit' property."
    @property
    def ratelimit(self) -> int:
        return int(self.response.headers['x-ratelimit-limit'])

    @property
    def ratelimit_remaining(self) -> int:
        return int(self.response.headers['x-ratelimit-remaining'])

    @property
    def ratelimit_reset(self) -> datetime:
        return datetime.fromtimestamp(int(self.response.headers['x-ratelimit-reset']))

class AbstractRequestSuccess(RequestResponseWithRatelimit):
    requested_scopus_id = pfield(type=ScopusId, mandatory=True)
    #status_code = pfield(invariant=lambda x: (x==200, 'HTTP OK'), mandatory=True)
    record = pfield(type=AbstractRecord, mandatory=True)

    # These seem like overkill:
    #record_str = RequestResponse.response_text
    #record_json = RequestResponse.response_json

    @property
    def date_created(self) -> date:
        return self.record.date_created

    @property
    def last_modified(self) -> datetime:
        return dateutil.parser.parse(self.response.headers['last-modified'])

class AbstractRequestFailure(PRecord):
    requested_scopus_id = pfield(type=ScopusId, mandatory=True)

AbstractRequestResult = Result[AbstractRequestSuccess, AbstractRequestFailure]

class AbstractRequestResponseFailure(AbstractRequestFailure, RequestResponse):
    pass
    # These seem like overkill:
    #error_message_str = RequestResponse.response_text
    #error_message_json = RequestResponse.response_json

class AbstractRequestResponseValidationError(AbstractRequestResponseFailure, RequestResponseWithRatelimit):
    #status_code = pfield(invariant=lambda x: (x==200, 'HTTP OK'), mandatory=True)
    validation_error = pfield(type=Exception, mandatory=True)

class AbstractRequestResponseDefunct(AbstractRequestResponseFailure, RequestResponseWithRatelimit):
    #status_code = pfield(invariant=lambda x: (x==404, 'HTTP Not Found'), mandatory=True)
    pass

class AbstractRequestNonresponseFailure(AbstractRequestFailure):
    exception = pfield(type=Exception, mandatory=True)

class CitationRequestSuccess(RequestResponse):
    requested_scopus_ids = pfield(type=CitationRequestScopusIds, mandatory=True)
    record = pfield(type=CitationMaybeMultiRecord, mandatory=True)

    # These seem like overkill:
    #record_str = RequestResponse.response_text
    #record_json = RequestResponse.response_json

class CitationRequestFailure(PRecord):
    requested_scopus_ids = pfield(type=ScopusIds, mandatory=True)

CitationRequestResult = Result[CitationRequestSuccess, CitationRequestFailure]

class CitationRequestResponseFailure(CitationRequestFailure, RequestResponse):
    pass
    # These seem like overkill:
    #error_message_str = RequestResponse.response_text
    #error_message_json = RequestResponse.response_json

class CitationRequestResponseValidationError(CitationRequestResponseFailure):
    #status_code = pfield(invariant=lambda x: (x==200, 'HTTP OK'), mandatory=True)
    validation_error = pfield(type=Exception, mandatory=True)

class CitationRequestResponseDefunct(CitationRequestResponseFailure):
    #status_code = pfield(invariant=lambda x: (x==404, 'HTTP Not Found'), mandatory=True)
    pass

class CitationRequestNonresponseFailure(CitationRequestFailure):
    exception = pfield(type=Exception, mandatory=True)

class AbstractResultsMixin:
    @property
    def requested_scopus_ids(self) -> ScopusIds:
        return ScopusIds(
            [result.requested_scopus_id for result in self]
        )

class AbstractSuccessResults(CheckedPVector, AbstractResultsMixin):
    __type__ = AbstractRequestSuccess

    @property
    def cited_scopus_ids(self) -> ScopusIds:
        return ScopusIds.union(
            *[result.record.reference_scopus_ids for result in self]
        )

class AbstractDefunctResults(CheckedPVector, AbstractResultsMixin):
    __type__ = AbstractRequestResponseDefunct

class AbstractErrorResults(CheckedPVector, AbstractResultsMixin):
    __type__ = AbstractRequestFailure

class CitationResultsMixin:
    @property
    def requested_scopus_ids(self) -> ScopusIds:
        return ScopusIds.union(
            *[result.requested_scopus_ids for result in self]
        )

class CitationSuccessResults(CheckedPVector, CitationResultsMixin):
    __type__ = CitationRequestSuccess

    @property
    def single_records(self) -> list[CitationSingleRecord]:
        return reduce(
            lambda list1, list2: list1 + list2,
            # Each call to single_records will return a list, so we need to
            # reduce the following list of lists into a single list:
            [result.record.single_records for result in self],
            []
        )
        
    @property
    def single_record_scopus_ids(self) -> ScopusIds:
        return ScopusIds(
            [record.scopus_id for record in self.single_records]
        )
        
    returned_scopus_ids = single_record_scopus_ids

    @property
    def probably_defunct_scopus_ids(self) -> ScopusIds:
        '''If there are some defunct Scopus IDs in the set of those requested,
        they will not appear in the response. We capture those here, so we can
        identify them, maybe test them to ensure the Scopus API returns a 404.
        '''
        return ScopusIds(
            self.requested_scopus_ids - self.returned_scopus_ids
        )

class CitationDefunctResults(CheckedPVector, CitationResultsMixin):
    __type__ = CitationRequestResponseDefunct

class CitationErrorResults(CheckedPVector, CitationResultsMixin):
    __type__ = CitationRequestFailure

# Final data structure of multiple results, e.g. concurrent requests for 1000 abstracts:
class AbstractAssortedResults(PRecord):
    success = pfield(type=AbstractSuccessResults)
    defunct = pfield(type=AbstractDefunctResults)
    error = pfield(type=AbstractErrorResults)

    @property
    def requested_scopus_ids(self) -> ScopusIds:
        return ScopusIds.union(
            self.success.requested_scopus_ids, self.defunct.requested_scopus_ids, self.error.requested_scopus_ids
        )

# Final data structure of multiple results, e.g. concurrent requests for 1000 citations:
class CitationAssortedResults(PRecord):
    success = pfield(type=CitationSuccessResults)
    defunct = pfield(type=CitationDefunctResults)
    error = pfield(type=CitationErrorResults)

    # Doubt that we'll need this property, but we'll keep it anyway:
    @property
    def requested_scopus_ids(self) -> ScopusIds:
        return ScopusIds.union(
            self.success.requested_scopus_ids, self.defunct.requested_scopus_ids, self.error.requested_scopus_ids
        )

class AbstractRequestResultAssorter:
    @staticmethod
    def classify(accumulator: MutableMapping, result: AbstractRequestResult) -> MutableMapping:
        match result:
            case Success(AbstractRequestSuccess() as success_result):
                accumulator['success'].append(success_result)
            case Failure(AbstractRequestResponseDefunct() as defunct_result):
                accumulator['defunct'].append(defunct_result)
            case Failure(AbstractRequestFailure() as error_result):
                accumulator['error'].append(error_result)
        return accumulator

    @staticmethod
    def assort(results: Iterator[AbstractRequestResult]) -> AbstractAssortedResults:
        assorted = reduce(
            AbstractRequestResultAssorter.classify,
            results,
            {'success': [], 'defunct': [], 'error': []}
        )
        return AbstractAssortedResults(
            success=AbstractSuccessResults(assorted['success']),
            defunct=AbstractDefunctResults(assorted['defunct']),
            error=AbstractErrorResults(assorted['error']),
        )

class CitationRequestResultAssorter:
    @staticmethod
    def classify(accumulator: MutableMapping, result: CitationRequestResult) -> MutableMapping:
        match result:
            case Success(CitationRequestSuccess() as success_result):
                accumulator['success'].append(success_result)
            case Failure(CitationRequestResponseDefunct() as defunct_result):
                accumulator['defunct'].append(defunct_result)
            case Failure(CitationRequestFailure() as error_result):
                accumulator['error'].append(error_result)
        return accumulator

    @staticmethod
    def assort(results: Iterator[CitationRequestResult]) -> CitationAssortedResults:
        assorted = reduce(
            CitationRequestResultAssorter.classify,
            results,
            {'success': [], 'defunct': [], 'error': []}
        )
        return CitationAssortedResults(
            success=CitationSuccessResults(assorted['success']),
            defunct=CitationDefunctResults(assorted['defunct']),
            error=CitationErrorResults(assorted['error']),
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
        **kwargs,
    ) -> RequestResult:
        return manage_request_attempts(
            httpx_client = self.httpx_client,
            prepared_request = prepared_request,
            retryable = self.retryable,
            next_wait_interval = self.next_wait_interval,
            max_attempts = self.max_attempts,
            attempts_id = uuid.uuid4(),
        )

    def get(self, resource_path, *args, params=m(), **kwargs) -> RequestResult:
        prepared_request = self.httpx_client.build_request(
            'GET',
            resource_path,
            params=thaw(params),
            timeout=self.timeout,
        )
        return self.request(*args, prepared_request=prepared_request, **kwargs)

    def get_abstract_by_scopus_id(
        self,
        scopus_id:ScopusId,
        *args,
        params=m(view='FULL'),
        **kwargs
    ) -> AbstractRequestResult:
        match self.get(
            f'abstract/scopus_id/{scopus_id}',
            *args,
            params=params,
            timeout=self.timeout,
            **kwargs,
        ):
            case Success(response):
                match response.status_code:
                    case 200:
                        match AbstractRecord.factory(response.json()):
                            case Success(record):
                                return Success(
                                    AbstractRequestSuccess(
                                        requested_scopus_id=scopus_id,
                                        response=response,
                                        record=record,
                                    )
                                )
                            case Failure(exception):
                                return Failure(
                                    AbstractRequestResponseValidationError(
                                        requested_scopus_id=scopus_id,
                                        response=response,
                                        validation_error=exception,
                                    )
                                )
                    case 404:
                        return Failure(
                            AbstractRequestResponseDefunct(
                                requested_scopus_id=scopus_id,
                                response=response,
                            )
                        )
                    case _:
                        return Failure(
                            AbstractRequestResponseFailure(
                                requested_scopus_id=scopus_id,
                                response=response,
                            )
                        )
            case Failure(exception):
                return Failure(
                    AbstractRequestNonresponseFailure(
                        requested_scopus_id=scopus_id,
                        exception=exception,
                    )
                )

    def get_citations_by_scopus_ids(
        self,
        scopus_ids: CitationRequestScopusIds,
        *args,
        params: RequestParams = m(citation='exclude-self'),
        **kwargs,
    ) -> CitationRequestResult:
        match self.get(
            f'abstract/citations',
            *args,
            params=params.set('scopus_id', scopus_ids.query_param_string()),
            timeout=self.timeout,
            **kwargs,
        ):
            case Success(response):
                match response.status_code:
                    case 200:
                        match CitationMaybeMultiRecord.factory(response.json()):
                            case Success(record):
                                return Success(
                                    CitationRequestSuccess(
                                        requested_scopus_ids=scopus_ids,
                                        response=response,
                                        record=record,
                                    )
                                )
                            case Failure(exception):
                                return Failure(
                                    CitationRequestResponseValidationError(
                                        requested_scopus_ids=scopus_ids,
                                        response=response,
                                        validation_error=exception,
                                    )
                                )
                    case 404:
                        return Failure(
                            CitationRequestResponseDefunct(
                                requested_scopus_ids=scopus_ids,
                                response=response,
                            )
                        )
                    case _:
                        return Failure(
                            CitationRequestResponseFailure(
                                requested_scopus_ids=scopus_ids,
                                response=response,
                            )
                        )
            case Failure(exception):
                return Failure(
                    CitationRequestNonresponseFailure(
                        requested_scopus_ids=scopus_ids,
                        exception=exception,
                    )
                )

    def get_many_abstracts_by_scopus_id(
        self,
        scopus_ids: ScopusIds,
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
            identifiers = scopus_ids,
        ):
            yield result

    def get_assorted_abstracts_by_scopus_id(
        self,
        scopus_ids: ScopusIds,
        params: RequestParams = m(view='FULL'),
        batch_size: int = 1000,
        assorter = AbstractRequestResultAssorter,
    ) -> Iterator[AbstractAssortedResults]:
        for results in batched(
            self.get_many_abstracts_by_scopus_id(
                scopus_ids=scopus_ids,
                params=params,
            ),
            batch_size,
        ):
            yield assorter.assort(results)

    def get_many_citations_by_scopus_ids(
        self,
        scopus_ids: ScopusIds,
        params: RequestParams = m(citation='exclude-self'),
    ) -> Iterator[CitationRequestResult]:
        partial_request = partial(
            self.get_citations_by_scopus_ids,
            params=params,
        )
        def request_by_scopus_ids_set(scopus_ids_set: CitationRequestScopusIds):
            return partial_request(scopus_ids_set)

        # invalid_scopus_ids should be empty, because we require scopus_ids to be of type ScopusIds:
        citation_request_scopus_ids_sets, invalid_scopus_ids = CitationRequestScopusIds.factory(scopus_ids)

        for result in common.request_many_by_identifier(
            request_by_identifier_function = request_by_scopus_ids_set,
            identifiers = citation_request_scopus_ids_sets,
        ):
            yield result

    def get_assorted_citations_by_scopus_ids(
        self,
        scopus_ids: ScopusIds,
        params: RequestParams = m(citation='exclude-self'),
        batch_size: int = 40, # We request citations 25 at a time, so we divide 1000 by 25
        assorter = CitationRequestResultAssorter,
    ) -> Iterator[CitationAssortedResults]:
        for results in batched(
            self.get_many_citations_by_scopus_ids(
                scopus_ids=scopus_ids,
                params=params,
            ),
            batch_size,
        ):
            yield assorter.assort(results)

