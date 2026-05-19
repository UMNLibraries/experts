# See https://peps.python.org/pep-0655/#usage-in-python-3-11
from __future__ import annotations
from typing_extensions import NotRequired, TypedDict

from datetime import date, datetime
import dateutil
from itertools import batched
from functools import cached_property, reduce, partial

import json
import os
from pathlib import Path
import re
from typing import Any, Callable, Iterable, Iterator, Mapping, Tuple

from uuid import uuid4, UUID

import attrs
from attrs import Factory, field, frozen, validators

import httpx

from pipe import Pipe

from pydantic import Field
from pyrsistent import field as pfield, freeze, thaw, m, pmap, v, CheckedPSet, PRecord, pvector, PVector, CheckedPVector
#from pyrsistent.typing import PMap, PVector

import returns # This doesn't appear to be used directly
from returns.result import Result, Success, Failure, safe # safe appears to be unused

from pycific.validated import ValidatedPMap, ValidatedPMapSpec, ValidatedStr

from experts.api import common
from experts.api.common import \
    default_max_attempts, \
    default_retryable, \
    default_next_wait_interval, \
    manage_request_attempts, \
    RequestResult

class Version(ValidatedStr):
    def _validate(self) -> Self:
        if not bool(re.match(r'^\d+$', self)):
            raise ValueError(f'Value {self} is invalid: a Pure WS Version must be numeric')
        return self

class Versions(CheckedPVector):
    __type__ = Version

class UUIDStr(ValidatedStr):
    def _validate(self) -> Self:
        try:
            UUID(self)
        except Exception as e:
            raise ValueError(f'Attempt to validate input "{value}" failed during UUIDStr instantiation')
        return self

# This type alias is just to make our code self-documenting
InvalidUUIDStr = Any

class UUIDStrs(CheckedPSet):
    '''Used for sets of defunct records, etc'''
    __type__ = UUIDStr

    @classmethod
    def union(cls, *uuids:Iterable[UUIDStr]) -> UUIDStrs:
        # The built-in set().union function doesn't seem to work with CheckedPSets
        # and multiple set arguments, so we make it work here as a class method.
        # Each argument after `cls` must be an iterable containing validated
        # instances of ScopusID.
        return UUIDStrs(
            set().union(*uuids)
        )

    @classmethod
    def validate_uuids(cls, uuids:Iterable[str|UUIDStr]) -> tuple[set[UUIDStr], set[InvalidUUIDStr]]:
        valid_uuids = set()
        invalid_uuids = set()
        for uuid in uuids:
            match UUIDStr.factory(uuid):
                case Success(valid_uuid):
                    valid_uuids.add(valid_uuid)
                case Failure(Exception):
                    invalid_uuids.add(uuid)
        return (valid_uuids, invalid_uuids)

    @classmethod
    def factory(cls, uuids:Iterable[str|UUIDStr]) -> tuple[UUIDStrs, set[InvalidUUIDStr]]:
        if isinstance(uuids, cls):
            return (uuids, set())
        valid_uuids, invalid_uuids = cls.validate_uuids(uuids)
        return (cls(valid_uuids), invalid_uuids)

class Versions(CheckedPVector):
    __type__ = Version

class CollectionName(ValidatedStr):
    def _validate(self) -> Self:
        if not bool(re.match(r'^[-a-z]+$', self)):
            raise ValueError(f'Value {self} is invalid: a Pure WS CollectionName may contain only lower-case letters and hyphens')
        return self

class CollectionNames(CheckedPVector):
    __type__ = CollectionName

class SchemaValidated(ValidatedPMapSpec):
    collection_names: CollectionNames
    version: Version

class CollectionNameNotFound(ValueError):
    '''Raised when a Pure WS collection name is unrecognized.'''
    def __init__(self, collection_name, version, *args, **kwargs):
        super().__init__(f'Unable to find collection name {collection_name} in schema version "{version}"', *args, **kwargs)

class Schema(ValidatedPMap):
    def _validate(self) -> SchemaValidated:
        return SchemaValidated(
            collection_names=self.collection_names,
            version=self.version,
        )

    @cached_property
    def version(self) -> Version:
        return Version(self.info.version)

    @cached_property
    def collection_names(self) -> CollectionNames:
        return CollectionNames(map(lambda tag: CollectionName(tag.name), self.tags))

    def collection_name_exists(self, collection_name:str) -> bool:
        return (collection_name in self.collection_names)

# TODO: Make a PureWSException class?
#class VersionNotFound(ValueError, PureWSException):
class VersionNotFound(ValueError):
    '''Raised when a Pure WS version is unrecognized.'''
    def __init__(self, version, *args, **kwargs):
        super().__init__(f'Unable to find a schema for version "{version}"', *args, **kwargs)

default_schemas_path: Path = Path(__file__).parent / 'schemas'
'''Folder containing schema sub-folders, each named for its version, e.g., "524" for version 5.24.'''

@frozen(kw_only=True)
class Schemas:
    path: Path = field(
        default=default_schemas_path,
        validator=attrs.validators.instance_of(Path),
    )

    @cached_property
    def versions(self) -> Versions:
        return Versions(
            map(lambda item: Version(item.name),
                filter(lambda item: item.name if item.is_dir() else None, os.scandir(self.path))
            )
        )

    def version_exists(self, version:str) -> bool:
        return (version in self.versions)

    @cached_property
    def latest_version(self) -> Version:
        return Version(max([int(version) for version in self.versions]))

    def load(self, version:str) -> Schema:
        if version is None:
            version = self.latest_version
        if not self.version_exists(version):
            raise VersionNotFound(version)
        with open(self.path / version / 'swagger.json') as json_file:
            return Schema(json.load(json_file))

class RecordValidated(ValidatedPMapSpec):
    uuid_str: UUIDStr
    created_date: datetime
    modified_date: datetime

class Record(ValidatedPMap):
    def _validate(self) -> RecordValidated:
        return RecordValidated(
            uuid_str=self.uuid_str,
            created_date=self.created_date,
            modified_date=self.modified_date,
        )

    @cached_property
    def uuid_str(self) -> UUIDStr:
        return UUIDStr(self.uuid)

    @cached_property
    def created_date(self) -> datetime:
        return dateutil.parser.parse(self.info.createdDate)

    @cached_property
    def modified_date(self) -> datetime:
        return dateutil.parser.parse(self.info.modifiedDate)


class Records(CheckedPVector):
    __type__ = Record

class RequestResponse(PRecord):
    response = pfield(
        type=httpx.Response,
        mandatory=True,
        serializer=lambda _format, response: {
            'status_code': response.status_code,
            # May be nice to include headers, but these contain secrets:
            #'headers': dict(response.headers),
            'body': response.json(),
        }
    )

# Alias to help make code self-documenting:
RequestSuccess = RequestResponse

class GetByUUIDSuccess(RequestSuccess):
    requested_uuid = pfield(type=UUIDStr, mandatory=True)
    record = pfield(type=Record, mandatory=True)

class MultiRecordResultMixin:
    @property
    def records(self) -> Records:
        return Records(
            [Record(item) for item in self.response.body.items]
        )

    @property
    def returned_uuids(self) -> UUIDStrs:
        return UUIDStrs(
            [record.uuid_str for record in self.records]
        )
        

class GetManyRecordsByUUIDsSuccess(RequestSuccess, MultiRecordResultMixin):
    requested_uuids = pfield(type=UUIDStrs, mandatory=True)

    @property
    def probably_defunct_uuids(self) -> UUIDStrs:
        '''If there are some defunct UUIDs in the set of those requested,
        they will not appear in the response. We capture those here, so we can
        identify them, maybe test them to ensure the Pure WS API returns a 404.
        '''
        return UUIDStrs(
            self.requested_uuids - self.returned_uuids
        )

class GetManyRecordsByUUIDsFailure(RequestFailure):
    requested_uuids = pfield(type=UUIDStrs, mandatory=True)

GetManyRecordsByUUIDsResult = Result[GetManyRecordsByUUIDsSuccess, GetManyRecordsByUUIDsFailure]

class GetManyRecordsByUUIDsResponseFailure(GetManyRecordsByUUIDsFailure, RequestResponse):
    pass

class GetManyRecordsByUUIDsResponseValidationError(GetManyRecordsByUUIDsResponseFailure):
    exception = pfield(type=Exception, mandatory=True, serializer=exception_serializer)

class GetManyRecordsByUUIDsResponseDefunct(GetManyRecordsByUUIDsResponseFailure):
    pass

class GetManyRecordsByUUIDsNonresponseFailure(GetManyRecordsByUUIDsFailure):
    exception = pfield(type=Exception, mandatory=True, serializer=exception_serializer)


class GetManyRecordsByUUIDsResultsMixin:
    @property
    def requested_uuids(self) -> UUIDStrs:
        return UUIDStrs.union(
            *[result.requested_uuids for result in self]
        )

class GetManyRecordsByUUIDsSuccessResults(CheckedPVector, GetManyRecordsByUUIDsResultMixin):
    __type__ = GetManyrecordsByUUIDsSuccess

    @property
    def records(self) -> list[CitationSingleRecord]:
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


class GetManyRecordsByUUIDsDefunctResults(CheckedPVector, CitationResultsMixin):
    __type__ = GetManyRecordsByUUIDsResponseDefunct

class GetManyRecordsByUUIDsErrorResults(CheckedPVector, CitationResultsMixin):
    __type__ = GetManyRecordsByUUIDsFailure

class RequestFailure(PRecord):
    def serialize(self) -> dict:
        return {
            'type': type(self).__name__,
            **super().serialize(),
        }

# A serializer for PRecord exception fields:
exception_serializer = lambda _format, ex: {
    'type': type(ex).__name__,
    'message': str(ex),
    'traceback': traceback.format_exception(ex),
}

class GetByUUIDFailure(RequestFailure):
    requested_uuid = pfield(type=UUIDStr, mandatory=True)

GetByUUIDResult = Result[GetByUUIDSuccess, GetByUUIDFailure]

class GetByUUIDResponseFailure(GetByUUIDFailure, RequestResponse):
    pass

class GetByUUIDResponseValidationError(GetByUUIDResponseFailure):
    exception = pfield(type=Exception, mandatory=True, serializer=exception_serializer)

class GetByUUIDResponseDefunct(GetByUUIDResponseFailure):
    pass

class GetByUUIDNonresponseFailure(GetByUUIDFailure):
    exception = pfield(type=Exception, mandatory=True, serializer=exception_serializer)

# Alias to help make code self-documenting:
InvalidRequestByUUID = GetByUUIDNonresponseFailure

class GetByUUIDResultsMixin:
    @property
    def requested_uuids(self) -> UUIDStrs:
        return UUIDStrs(
            [result.requested_uuid for result in self]
        )

class GetByUUIDSuccessResults(CheckedPVector, GetByUUIDResultsMixin):
    __type__ = GetByUUIDSuccess

class GetByUUIDDefunctResults(CheckedPVector, GetByUUIDResultsMixin):
    __type__ = GetByUUIDResponseDefunct

class GetByUUIDErrorResults(CheckedPVector, GetByUUIDResultsMixin):
    __type__ = GetByUUIDFailure

# Final data structure of multiple results, e.g. concurrent requests for 1000 abstracts:
class GetByUUIDAssortedResults(PRecord):
    success = pfield(type=GetByUUIDSuccessResults)
    defunct = pfield(type=GetByUUIDDefunctResults)
    error = pfield(type=GetByUUIDErrorResults)

    @property
    def requested_uuids(self) -> UUIDStrs:
        return UUIDStrs.union(
            self.success.requested_uuids, self.defunct.requested_uuids, self.error.requested_uuids
        )

class GetByUUIDResultAssorter:
    @staticmethod
    def classify(accumulator: MutableMapping, result: GetByUUIDResult) -> MutableMapping:
        match result:
            case Success(GetByUUIDSuccess() as success_result):
                accumulator['success'].append(success_result)
            case Failure(GetByUUIDResponseDefunct() as defunct_result):
                accumulator['defunct'].append(defunct_result)
            case Failure(GetByUUIDFailure() as error_result):
                accumulator['error'].append(error_result)
        return accumulator

    @staticmethod
    def assort(results: Iterator[GetByUUIDResult]) -> GetByUUIDAssortedResults:
        assorted = reduce(
            GetByUUIDResultAssorter.classify,
            results,
            {'success': [], 'defunct': [], 'error': []}
        )
        return GetByUUIDAssortedResults(
            success=GetByUUIDSuccessResults(assorted['success']),
            defunct=GetByUUIDDefunctResults(assorted['defunct']),
            error=GetByUUIDErrorResults(assorted['error']),
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

    schema: Schema = field(init=False)
    '''A Pure Web Services schema.'''

    schemas_path: Path = default_schemas_path
    ''''''

    httpx_client: httpx.Client = field(init=False)
    '''An httpx.Client object. Default: ``httpx.Client()``.'''

    timeout: httpx.Timeout = httpx.Timeout(10.0, connect=3.0, read=60.0)
    '''httpx client timeouts. Default: ``httpx.Timeout(10.0, connect=3.0, read=60.0)``.'''

    #max_attempts: int = 10
    max_attempts: int = 3 # TODO: This may be way too high, depending on the wait interval!
    '''An integer maximum number of times to retry a request. Default: ``10``.'''

    retryable: Callable = Factory(default_retryable)
    '''A function that takes a returns.Result and returns a boolean. Required. Default: Return value of ``default_retryable``.'''

    next_wait_interval: Callable = default_next_wait_interval
    '''A function that takes an integer number of seconds to wait and returns a new interval. Required. Default: Return value of ``default_next_wait_interval``.'''

    domain: str = field(
        default=os.environ.get('PURE_WS_DOMAIN'),
        validator=validators.instance_of(str)
    )
    '''Domain of a Pure Web Services server. Required. Default: environment variable PURE_WS_DOMAIN'''

    base_path: str = field(
        default='ws/api',
        validator=validators.instance_of(str)
    )
    '''Base path of the Pure Web Services URL entry point.'''

    version: Version = field(
        default=Version(os.environ.get('PURE_WS_VERSION')),
    )
    '''Pure Web Services version, without the decimal point. For example, ``524`` for version 5.24.'''

    key: str = field(
        default=os.environ.get('PURE_WS_KEY'),
        validator=validators.instance_of(str)
    )
    '''Pure Web Services key. Required. Default: environment variable PURE_WS_KEY'''

    headers: PMap = pmap({
        'Accept': 'application/json',
        'Accept-Charset': 'utf-8',
    })
    '''HTTP headers to be sent on every request. The constructor automatically adds
    an ``api-key`` header, using the value of the ``key`` attribute.
    '''

    def __attrs_post_init__(self) -> None:
        schemas = Schemas(path=self.schemas_path)
        object.__setattr__(
            self,
            'schema',
            schemas.load(self.version)
        )
        object.__setattr__(
            self,
            'httpx_client',
            httpx.Client(
                base_url=f'https://{self.domain}/{self.base_path}/{self.version}/',
                headers={
                    **thaw(self.headers),
                    'api-key': self.key,
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
            attempts_id = uuid4(),
        )

    def get(self, resource_path, *args, params=m(), **kwargs) -> RequestResult:
        prepared_request = self.httpx_client.build_request(
            'GET',
            resource_path,
            params=thaw(params),
            timeout=self.timeout,
        )
        return self.request(*args, prepared_request=prepared_request, **kwargs)

    def get_by_uuid(
        self,
        collection_name:str,
        *args,
        uuid:UUIDStr,
        # TODO: Should this be of type RequestParams?
        params=m(),
        **kwargs
    ) -> GetByUUIDResult:
        if not self.schema.collection_name_exists(collection_name):
            return Failure(
                InvalidRequestByUUID(
                    requested_uuid=uuid,
                    exception=CollectionNameNotFound(
                        collection_name=collection_name,
                        version=self.version,
                    ),
                )
            )

        match self.get(
            f'{collection_name}/{uuid}',
            *args,
            params=params,
            timeout=self.timeout,
            **kwargs,
        ):
            case Success(response):
                match response.status_code:
                    case 200:
                        match Record.factory(response.json()):
                            case Success(record):
                                return Success(
                                    GetByUUIDSuccess(
                                        requested_uuid=uuid,
                                        response=response,
                                        record=record,
                                    )
                                )
                            case Failure(exception):
                                return Failure(
                                    GetByUUIDResponseValidationError(
                                        requested_uuid=uuid,
                                        response=response,
                                        exception=exception,
                                    )
                                )
                    case 404:
                        return Failure(
                            GetByUUIDResponseDefunct(
                                requested_uuid=uuid,
                                response=response,
                            )
                        )
                    case _:
                        return Failure(
                            GetByUUIDResponseFailure(
                                requested_uuid=uuid,
                                response=response,
                            )
                        )
            case Failure(exception):
                return Failure(
                    GetByUUIDNonresponseFailure(
                        requested_uuid=uuid,
                        exception=exception,
                    )
                )

    def get_many_by_uuid(
        self,
        collection_name:str,
        uuids:UUIDStrs,
        params=m(),
    ) -> Iterator[GetByUUIDResult]:
        partial_request = partial(
            self.get_by_uuid,
            collection_name,
            params=params,
        )
        def request_by_uuid(uuid:UUIDStr):
            return partial_request(uuid=uuid)

        for result in common.request_many_by_identifier(
            request_by_identifier_function = request_by_uuid,
            identifiers = uuids,
        ):
            yield result

    def get_assorted_by_uuid_results(
        self,
        collection_name:str,
        uuids:UUIDStrs,
        params=m(),
        batch_size: int = 1000,
        assorter = GetByUUIDResultAssorter,
    ) -> Iterator[GetByUUIDAssortedResults]:
        for results in batched(
            self.get_many_by_uuid(
                collection_name,
                uuids=uuids,
                params=params,
            ),
            batch_size,
        ):
            yield assorter.assort(results)

#class ResponseBodyParser:
#    @staticmethod
#    # TODO: Create a better type!
#    def items(body:ResponseBody) -> list[ResponseBodyItem]:
#        return body['items'] if 'items' in body else []
#
#    @Pipe
#    def bodies_to_items(bodies: Iterator[ResponseBody]) -> Iterator[ResponseBodyItem]:
#        for body in bodies:
#            for item in ResponseBodyParser.items(body):
#                yield item
#
#class ResponseParser:
#    @staticmethod
#    def body(response:httpx.Response) -> ResponseBody:
#        return response.json()
#
#    @staticmethod
#    def items(response:httpx.Response) -> list[ResponseBodyItem]:
#        return ResponseBodyParser.items(
#            ResponseParser.body(response)
#        )
#
#    @Pipe
#    def responses_to_bodies(responses: Iterator[httpx.Response]) -> Iterator[ResponseBody]:
#        for response in responses:
#            yield ResponseParser.body(response)
#
#    @Pipe
#    def responses_to_items(responses: Iterator[httpx.Response]) -> Iterator[ResponseBodyItem]:
#        for item in responses | ResponseParser.responses_to_bodies | ResponseBodyParser.bodies_to_items:
#            yield item
#
#OffsetRequestParams = PMap
#
#class PageInformation(TypedDict):
#    size: int
#    offset: int
#
## WSDataSetListResult in the Pure Web Services Swagger JSON schema
#class OffsetResponseBody(TypedDict):
#    count: int
#    pageInformation: PageInformation
#    navigationLinks: Iterable[Mapping]
#    items: NotRequired[Iterable[Mapping]]
#
#class OffsetResponseBodyParser(ResponseBodyParser):
#    @staticmethod
#    def total_items(body:OffsetResponseBody) -> int:
#        return body['count']
#
#    @staticmethod
#    def items_per_page(body:OffsetResponseBody) -> int:
#        return int(body['pageInformation']['size'])
#
#    @staticmethod
#    def offset(body:OffsetResponseBody) -> int:
#        return int(body['pageInformation']['offset'])
#
#class OffsetResponseParser(ResponseParser):
#    @staticmethod
#    def total_items(response:httpx.Response) -> int:
#        return OffsetResponseBodyParser.total_items(
#            ResponseParser.body(response)
#        )
#
#    @staticmethod
#    def items_per_page(response:httpx.Response) -> int:
#        return OffsetResponseBodyParser.items_per_page(
#            ResponseParser.body(response)
#        )
#
#    @staticmethod
#    def offset(response:httpx.Response) -> int:
#        return OffsetResponseBodyParser.offset(
#            ResponseParser.body(response)
#        )
#
## WSChangeListResult in the Pure Web Services Swagger JSON schema
#class TokenResponseBody(TypedDict):
#    count: int
#    resumptionToken: str
#    moreChanges: bool
#    navigationLinks: Iterable[Mapping]
#    items: NotRequired[Iterable[Mapping]]
#
#class TokenResponseBodyParser(ResponseBodyParser):
#    @staticmethod
#    def items_per_page(body:TokenResponseBody) -> int:
#        return int(body['count'])
#
#    @staticmethod
#    def more_items(body:TokenResponseBody) -> bool:
#        return body['moreChanges']
#
#    @staticmethod
#    def token(body:TokenResponseBody) -> int:
#        return body['resumptionToken']
#
#class TokenResponseParser(ResponseParser):
#    @staticmethod
#    def items_per_page(response:httpx.Response) -> int:
#        return TokenResponseBodyParser.items_per_page(
#            ResponseParser.body(response)
#        )
#
#    @staticmethod
#    def more_items(response:httpx.Response) -> bool:
#        return TokenResponseBodyParser.more_items(
#            ResponseParser.body(response)
#        )
#
#    @staticmethod
#    def token(response:httpx.Response) -> int:
#        return TokenResponseBodyParser.token(
#            ResponseParser.body(response)
#        )
#
#@frozen(kw_only=True)
#class Client:
#    '''Common client configuration and behavior. Used by most functions.
#
#    Most attributes have defaults and are not required. Only ``domain`` and
#    ``key`` are required, and both can be set with environment variables as
#    well as constructor parameters.
#
#    Context instances are immutable. To use different configurations for different
#    function calls, pass different Context objects.
#
#    E
#    '''
#
#    httpx_client: httpx.Client = field(init=False)
#    '''An httpx.Client object. Default: ``httpx.Client()``.'''
#
#    timeout: httpx.Timeout = httpx.Timeout(10.0, connect=3.0, read=60.0)
#    '''httpx client timeouts. Default: ``httpx.Timeout(10.0, connect=3.0, read=60.0)``.'''
#
#    max_attempts: int = 10
#    '''An integer maximum number of times to retry a request. Default: ``10``.'''
#
#    retryable: Callable = Factory(default_retryable)
#    '''A function that takes a returns.Result and returns a boolean. Required. Default: Return value of ``default_retryable``.'''
#
#    next_wait_interval: Callable = default_next_wait_interval
#    '''A function that takes an integer number of seconds to wait and returns a new interval. Required. Default: Return value of ``default_next_wait_interval``.'''
#
#    domain: str = field(
#        default=os.environ.get('PURE_WS_DOMAIN'),
#        validator=validators.instance_of(str)
#    )
#    '''Domain of a Pure Web Services API server. Required. Default: environment variable PURE_WS_DOMAIN'''
#
#    base_path: str = field(
#        default='ws/api',
#        validator=validators.instance_of(str)
#    )
#    '''Base path of the Pure Web Services API URL entry point, without the version number segment.'''
#
#    version: str = '524'
#    '''Pure Web Services version, without the decimal point. For example, ``524`` for version 5.24.
#    The final and only valid version is now 5.24.'''
#
#    key: str = field(
#        default=os.environ.get('PURE_WS_KEY'),
#        validator=validators.instance_of(str)
#    )
#    '''Pure Web Services API key. Required. Default: environment variable PURE_WS_KEY'''
#
#    headers: PMap = pmap({
#        'Accept': 'application/json',
#        'Accept-Charset': 'utf-8',
#    })
#    '''HTTP headers to be sent on every request. The constructor automatically adds
#    an ``api-key`` header, using the value of the ``key`` attribute.'''
#
#    def __attrs_post_init__(self) -> None:
#        object.__setattr__(
#            self,
#            'httpx_client',
#            httpx.Client(
#                base_url=f'https://{self.domain}/{self.base_path}/{self.version}/',
#                headers={
#                    **thaw(self.headers),
#                    'api-key': self.key,
#                }
#            )
#        )
#
#    def __enter__(self):
#        return self
#
#    def __exit__(self, exc_type, exc_value, exc_tb):
#        # TODO: Do something with the other args?
#        self.httpx_client.close()
#
#    def request(
#        self,
#        *args,
#        prepared_request,
#        retyrable = default_retryable,
#        next_wait_interval = default_next_wait_interval,
#        max_attempts = default_max_attempts,
#        **kwargs
#    ): # -> TODO: Type?
#        return manage_request_attempts(
#            httpx_client = self.httpx_client,
#            prepared_request = prepared_request,
#            retryable = self.retryable,
#            next_wait_interval = self.next_wait_interval,
#            max_attempts = self.max_attempts,
#            attempts_id = uuid.uuid4(),
#        )
#
#    def get(self, resource_path, *args, params=m(), **kwargs):
#        prepared_request = self.httpx_client.build_request(
#            'GET',
#            resource_path,
#            params=thaw(params),
#            timeout=self.timeout # TODO: Change to default_timeout
#        )
#        return self.request(*args, prepared_request=prepared_request, **kwargs)
#
#    def post(self, resource_path, *args, params=m(), **kwargs):
#        prepared_request = self.httpx_client.build_request(
#            'POST',
#            resource_path,
#            json=thaw(params),
#            timeout=self.timeout
#        )
#        return self.request(*args, prepared_request=prepared_request, **kwargs)
#    
#    def request_many_by_offset(
#        self,
#        request_function: RequestFunction,
#        resource_path: str,
#        params: OffsetRequestParams = m(),
#        first_offset: int = 0,
#    ) -> Iterator[httpx.Response]:
#        partial_request = partial(
#            request_function,
#            resource_path,
#        )
#        def request_by_offset(offset: int):
#            return partial_request(
#                params=params.set('offset', offset)
#            )
#
#        return common.request_many_by_offset(
#            request_by_offset_function = request_by_offset,
#            response_parser = OffsetResponseParser,
#            first_offset = first_offset
#        )
#
#    def request_many_by_token(
#        self,
#        request_function: RequestFunction,
#        resource_path: str,
#        token: str,
#        params: RequestParams = m(),
#    ) -> Iterator[httpx.Response]:
#        partial_request = partial(
#            request_function,
#            params=params,
#        )
#        def request_by_token(token: str):
#            return partial_request(
#                resource_path = resource_path + '/' + token
#            )
#
#        return common.request_many_by_token(
#            request_by_token_function = request_by_token,
#            response_parser = TokenResponseParser,
#            token = token,
#        )
#    
