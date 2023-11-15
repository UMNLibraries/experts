from functools import partial
from typing import Callable, Generic, Iterator, Mapping, Protocol, Tuple, Type, TypeVar, Union

import httpx

from pyrsistent import v
from pyrsistent.typing import PMap, PVector

import returns
from returns.pipeline import is_successful
from returns.result import Result

OffsetRequestParams = PMap

class OffsetRequestParamsParser(Protocol):
    @staticmethod
    def items_per_page(params:OffsetRequestParams) -> int:
        ...

    @staticmethod
    def offset(params:OffsetRequestParams) -> int:
        ...

    @staticmethod
    def update_offset(params:OffsetRequestParams, new_offset:int) -> OffsetRequestParams:
        ...

OffsetResponse = Mapping
OffsetResponse_contra = TypeVar('OffsetResponsee_contra', bound=OffsetResponse, contravariant=True)

class OffsetResponseParser(Protocol, Generic[OffsetResponse_contra]):
    @staticmethod
    def total_items(response:OffsetResponse_contra) -> int:
        ...

    @staticmethod
    def items_per_page(response:OffsetResponse_contra) -> int:
        ...

    @staticmethod
    def offset(response:OffsetResponse_contra) -> int:
        ...

    @staticmethod
    def items(response:OffsetResponse_contra) -> Iterator[Mapping]:
        ...

def retryable(
    result:Result,
    retryable_status_codes:PVector[int],
    retryable_errors:Tuple[Type[Exception]],
) -> bool:
    if is_successful(result):
        response = result.unwrap()
        if (response.status_code in retryable_status_codes):
            return True
        else:
            return False
    else:
       exc = result.failure()
       if isinstance(exc, retryable_errors):
           return True
       else:
           return False

def default_retryable():
       return partial(
            retryable,
            retryable_status_codes=v(429, 500, 502, 503, 504),
            retryable_errors=(httpx.NetworkError, httpx.TimeoutException),
        )

def default_next_wait_interval(wait_interval: int):
    return wait_interval**2

class Context(Protocol):
    '''Common client configuration settings. Used by most functions.
    '''

    @property
    def httpx_client(self) -> httpx.Client: ...
    '''An httpx.Client object.'''

    @property
    def timeout(self) -> Tuple[int, int]: ...
    '''A (connect timeout, read timeout) tuple. Required.'''

    @property
    def max_attempts(self) -> int: ...
    '''An integet maximum number of times to retry a request. Required.'''

    # TODO: Make a protocol for this function
    @property
    def retryable(self) -> Callable: ...
    '''A function that takes a returns.Result and returns a boolean. Required. Default: Return value of ``default_retryable``.'''

    # TODO: Make a protocol for this function
    @property
    def next_wait_interval(self) -> Callable: ...
    '''A function that takes an integer number of seconds to wait and returns a new interval. Required. Default: Return value of ``default_next_wait_interval``.'''

    @property
    def domain(self) -> str: ...
    '''Domain of a Pure API server. Required.'''

    @property
    def base_path(self) -> str: ...
    # TODO: Improve this documentation
    '''Base path of the Pure API URL entry point, without the version number segment. '''

    # TODO: We may not need this or want to require it for APIs other than Pure's
    @property
    def version(self) -> str: ...
    '''Pure API version, without the decimal point. For example, ``517`` for version 5.17.
    Default: Return value of ``default_version()``.'''

    @property
    def key(self) -> str: ...
    '''API key. Required.'''

    @property
    def headers(self) -> PMap: ...
    '''HTTP headers. The constructor automatically adds an ``api-key`` header, using the value of
    the ``key`` attribute.'''

    #records_per_request: int

    @property
    def offset_request_params_parser(self) -> OffsetRequestParamsParser: ...

    @property
    def offset_response_parser(self) -> OffsetResponseParser: ...

    @property
    def base_url(self) -> str: ...
    '''Pure API entrypoint URL. Should not be included in constructor
    parameters. The constructor generates this automatically based on
    other attributes.'''
