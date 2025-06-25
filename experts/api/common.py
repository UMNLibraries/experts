from collections import namedtuple
import concurrent.futures
from contextlib import contextmanager
from functools import partial
import importlib
from inspect import getmembers, getmodule, isfunction, signature
import os
import threading
import time
from typing import Callable, Generic, Iterator, Mapping, Protocol, Type, TypeVar
import uuid

import attrs
from attrs import Factory, field, frozen

from pipe import Pipe

from pyrsistent import thaw, m, pmap, v, pvector
from pyrsistent.typing import PMap, PVector

import httpx

import returns
from returns.pipeline import is_successful
from returns.result import Result, Success, Failure, safe

import immutable
immutable.module(__name__)

RequestParams = PMap
RequestResult = Result[httpx.Response, Exception]
ResponseBody = Mapping
ResponseBodyItem = Mapping

OffsetResponseBody = Mapping
OffsetResponseBody_contra = TypeVar('OffsetResponseBody_contra', bound=OffsetResponseBody, contravariant=True)

class OffsetResponseBodyParser(Protocol, Generic[OffsetResponseBody_contra]):
    @staticmethod
    def total_items(response:OffsetResponseBody_contra) -> int:
        ...

    @staticmethod
    def items_per_page(response:OffsetResponseBody_contra) -> int:
        ...

    @staticmethod
    def offset(response:OffsetResponseBody_contra) -> int:
        ...

    @staticmethod
    def items(response:OffsetResponseBody_contra) -> list[Mapping]:
        ...

# Do we need the Generic in this case?
#class OffsetResponseParser(Protocol, Generic[httpxResponse_contra]):
class OffsetResponseParser(Protocol):
    @staticmethod
    def total_items(response:httpx.Response) -> int:
        ...

    @staticmethod
    def items_per_page(response:httpx.Response) -> int:
        ...

    @staticmethod
    def offset(response:httpx.Response) -> int:
        ...

    @staticmethod
    def items(response:httpx.Response) -> list[ResponseBodyItem]:
        ...

TokenResponseBody = Mapping
TokenResponseBody_contra = TypeVar('TokenResponseeBody_contra', bound=TokenResponseBody, contravariant=True)

class TokenResponseBodyParser(Protocol, Generic[TokenResponseBody_contra]):
# Not all APIs have this:
#    @staticmethod
#    def total_items(response:TokenResponseBody_contra) -> int:
#        ...

    @staticmethod
    def items_per_page(response:TokenResponseBody_contra) -> int:
        ...

    @staticmethod
    def token(response:TokenResponseBody_contra) -> str:
        ...

    def more_items(response:TokenResponseBody_contra) -> bool:
        ...

    @staticmethod
    def items(response:TokenResponseBody_contra) -> list[ResponseBodyItem]:
        ...

# Do we need the Generic in this case?
#class TokenResponseParser(Protocol, Generic[httpxResponse_contra]):
class TokenResponseParser(Protocol):
    @staticmethod
    def items_per_page(response:httpx.Response) -> int:
        ...

    @staticmethod
    def token(response:httpx.Response) -> str:
        ...

    def more_items(response:httpx.Response) -> bool:
        ...

    @staticmethod
    def items(response:httpx.Response) -> list[ResponseBodyItem]:
        ...

default_max_attempts: int = 10

class Client(Protocol):
    '''Common client configuration settings. Used by most functions.
    '''

    @property
    def httpx_client(self) -> httpx.Client: ...
    '''An httpx.Client object.'''

    @property
    def timeout(self) -> httpx.Timeout: ...
    '''httpx client timeouts'''

    @property
    def max_attempts(self) -> int: ...
    '''An integet maximum number of times to retry a request. Required.'''

    # TODO: Make a protocol for this function
    @property
    def retryable(self) -> Callable: ...
    '''A function that takes a RequestResult and returns a boolean. Required. Default: Return value of ``default_retryable``.'''

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

    # TODO: Add more methods? See experts.api.pure.ws

def retryable(
    result:RequestResult,
    retryable_status_codes:PVector[int],
    retryable_errors:tuple[Type[Exception]],
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

# TODO: This needs work. Need to remove the context, at least.
#class RequestFunction(Protocol):
#    '''Request functions defined by this module, e.g., ``get`` and ``post``.'''
#    def __call__(resource_path: str, context: Context, params: RequestParams = m()) -> RequestResult:
#        ...

@safe
def attempt_request(
    httpx_client: httpx.Client,
    prepared_request: httpx.Request,
) -> RequestResult:
    return httpx_client.send(prepared_request)

def manage_request_attempts(
    httpx_client: httpx.Client,
    prepared_request: httpx.Request,
    retryable: Callable = default_retryable,
    next_wait_interval: Callable = default_next_wait_interval,
    max_attempts: int = default_max_attempts,
    attempts_id: str = uuid.uuid4(),
    attempt_number: int = 1,
    wait_interval: int = 2,
) -> RequestResult:
    start_time = time.perf_counter()
    if __debug__:
        print({
            'attempts_id': attempts_id,
            'attempt_number': attempt_number,
            'attempt_stage': 'start',
            'time': start_time,
            'method': prepared_request.method,
            'url': prepared_request.url,
            #'params': params,
        })
 
    result = attempt_request(httpx_client, prepared_request)
 
    end_time = time.perf_counter()
    if __debug__:
        print({
            'attempts_id': attempts_id,
            'attempt_number': attempt_number,
            'attempt_stage': 'end',
            'time': end_time,
            'elapsed_time': end_time - start_time,
            'result': result,
        })

    if retryable(result) and attempt_number < max_attempts:
        time.sleep(wait_interval)
        return manage_request_attempts(
            httpx_client = httpx_client,
            prepared_request = prepared_request,
            retryable = retryable,
            next_wait_interval = next_wait_interval,
            wait_interval=next_wait_interval(wait_interval),
            attempts_id=attempts_id,
            attempt_number=attempt_number+1,
            max_attempts = max_attempts,
        )
    else:
        return result       

def request_many_by_identifier(
    request_by_identifier_function,
    identifiers: Iterator,
    max_workers: int = 4
) -> Iterator[RequestResult]:
    '''
    '''

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = [
            executor.submit(
                request_by_identifier_function,
                identifier
            ) for identifier in identifiers
        ]
        for future in concurrent.futures.as_completed(results):
            yield future.result()

def request_many_by_offset(
    request_by_offset_function: Callable,
    response_parser: OffsetResponseParser,
    first_offset: int = 0,
) -> Iterator[httpx.Response]:
    first_result = request_by_offset_function(first_offset)
    if not is_successful(first_result):
        # TODO: log failure. Maybe pass in a logger?
        print(f'Failed! {result}')
        return
    first_response = first_result.unwrap()
    yield first_response

    total_items = response_parser.total_items(first_response)
    items_per_page = response_parser.items_per_page(first_response)

    # The following assumes an ascending order of offsets,
    # in which case increasing the offset will result in 
    # zero items in the next response:
    if total_items <= items_per_page or total_items <= first_offset:
        return

    # In the first_result above, we got items first_offset through items_per_page - 1
    second_offset = first_offset + items_per_page
    remaining_offsets = range(second_offset, total_items, items_per_page)

    for result in request_many_by_identifier(
        request_by_offset_function,
        identifiers=remaining_offsets
    ):
        if is_successful(result):
            yield result.unwrap()
        else:
        # TODO: log failure. Maybe pass in a logger?
            print(f'Failed! {result}')
            continue

def request_many_by_token(
    request_by_token_function: Callable,
    response_parser: TokenResponseParser,
    token: str,
) -> Iterator[httpx.Response]:
    while(True):
        result = request_by_token_function(token)
        if not is_successful(result):
            # TODO: log failure, probably relying on context
            print(f'Failed! {result}')
            return

        response = result.unwrap()
        yield response

        if not response_parser.more_items(response):
            return
        # Hate this ugly resetting of token!
        token = response_parser.token(response)
