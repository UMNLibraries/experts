# See https://peps.python.org/pep-0655/#usage-in-python-3-11
from __future__ import annotations
from typing_extensions import NotRequired, TypedDict

from collections import namedtuple
import concurrent.futures
from contextlib import contextmanager
from functools import partial
from inspect import getmembers, getmodule, isfunction, signature
import math
import os
import threading
import time
#from collections.abc import Iterator # Causes this error: TypeError: 'ABCMeta' object is not subscriptable
from typing import Callable, Generator, Generic, Iterable, Iterator, List, Mapping, MutableMapping, Protocol, Tuple, Type, TypeVar, Union
import uuid

import addict
import attr
import attrs
from attrs import Factory, field, frozen

from pyrsistent import freeze, thaw, m, pmap, v, pvector
from pyrsistent.typing import PMap, PVector

import requests
from requests import PreparedRequest, Response
from requests.exceptions import RequestException, HTTPError, ConnectionError, ConnectTimeout, ReadTimeout

import httpx

import returns
from returns.pipeline import is_successful
from returns.result import Result, Success, Failure, safe
from returns.trampolines import Trampoline, trampoline

from experts.pureapi import response
from experts.pureapi.common import default_version, valid_collection, valid_version, PureAPIInvalidCollectionError, PureAPIInvalidVersionError
from experts.pureapi.exceptions import PureAPIException

class RequestPageParamsParser:
    @staticmethod
    def size(params:PMap) -> int:
        return params.size
    
    @staticmethod
    def offset(params:PMap) -> int:
        return params.offset
    
    @staticmethod
    def update_offset(params:PMap, new_offset:int) -> PMap:
        # This returns a new PMap:
        return params.set('offset', new_offset)
    
# WSDataSetListResult in the Pure Web Services Swagger JSON schema
# TODO: Will this be true for both API and Web Services?
class ResponsePage(TypedDict):
    count: int
    pageInformation: Mapping
    navigationLinks: Iterable
    items: Iterable[Mapping]

class ResponsePageParser:
    @staticmethod
    def count(response:ResponsePage) -> int:
        return response['count']
    
    @staticmethod
    def items(response:ResponsePage) -> Iterator[Mapping]:
        for item in response['items']:
            yield item

env_key_varname: str = 'PURE_API_KEY'
'''Environment variable name for a Pure API key. Defaults to PURE_API_KEY.
Used by ``env_key()``.
'''

def env_key() -> str:
    '''Returns the value of environment variable env_key_varname, or None if undefined.
    See Config for more details.
    '''
    return os.environ.get(env_key_varname)

def default_protocol() -> str:
    '''Returns 'https'. See Config for more details.'''
    return 'https'

def default_base_path() -> str:
    '''Returns 'ws/api'. See Config for more details.'''
    return 'ws/api'

def default_headers() -> MutableMapping:
    '''See Config for more details.

    Returns:
        {
            'Accept': 'application/json',
            'Accept-Charset': 'utf-8',
        }
    '''
    return {
        'Accept': 'application/json',
        'Accept-Charset': 'utf-8',
    }

def default_records_per_request() -> int:
    '''Returns an integer number of records to return for each request of many records.'''
    return 1000

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
            retryable_errors=(ConnectionError, ConnectTimeout, ReadTimeout),
        )

def default_next_wait_interval(wait_interval: int):
    return wait_interval**2

class PureAPIClientException(PureAPIException):
    '''Base class for exceptions specific to pureapi.client.'''
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

env_domain_varname: str = 'PURE_API_DOMAIN'
'''Environment variable name for a Pure API domain. Defaults to PURE_API_DOMAIN.
Used by env_domain().
'''

def env_domain() -> str:
    '''Returns the value of environment variable env_domain_varname, or None if undefined.
    See Config for more details.
    '''
    return os.environ.get(env_domain_varname)

def _get_collection_from_resource_path(resource_path: str, version: str) -> str:
    '''Extracts the collection name from a Pure API URL resource path.

    Args:
        resource_path: URL path, without the base URL, to a Pure API resource.
        config: Instance of pureapi.client.Config.

    Returns:
        The name of the collection.

    Raises:
        common.PureAPIInvalidCollectionError: If the extracted collection is
            invalid for the given API version.
    '''
    collection = resource_path.split('/')[0]
    if not valid_collection(collection=collection, version=version):
        raise PureAPIInvalidCollectionError(collection=collection, version=version)
    return collection

class PureAPIHTTPError(HTTPError, PureAPIClientException):
    '''Raised in case of an HTTP error response.'''
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class PureAPIRequestException(RequestException, PureAPIClientException):
    '''Raised in case of an HTTP-request-related exception that is something
    other than an HTTP error status code.'''
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

@frozen(kw_only=True)
class Config:
    '''Common client configuration settings. Used by most functions.

    Most attributes have defaults and are not required. Only ``domain`` and
    ``key`` are required, and both can be set with environment variables as
    well as constructor parameters.

    Config instances are immutable. To use different configurations for different
    function calls, pass different Config objects.

    Examples:
        >>> from pureapi import client
        >>> client.Config(domain='example.com', key='123-abc')
        Config(protocol='https', domain='example.com', base_path='ws/api', version='517', key='123-abc', headers={'Accept': 'application/json', 'Accept-Charset': 'utf-8', 'api-key': '123-abc'}, retryer=<Retrying object at 0x7fec3af4c278 (stop=<tenacity.stop._stop_never object at 0x7fec34a76908>, wait=<tenacity.wait.wait_exponential object at 0x7fec3af4c208>, sleep=<built-in function sleep>, retry=<tenacity.retry.retry_if_exception_type object at 0x7fec34a82ba8>, before=<function before_nothing at 0x7fec34a6d950>, after=<function after_nothing at 0x7fec34a85378>)>, base_url='https://example.com/ws/api/517/')

        >>> client.Config(domain='test.example.com', key='456-def', version='518')
        Config(protocol='https', domain='test.example.com', base_path='ws/api', version='518', key='456-def', headers={'Accept': 'application/json', 'Accept-Charset': 'utf-8', 'api-key': '456-def'}, retryer=<Retrying object at 0x7fec3454d828 (stop=<tenacity.stop._stop_never object at 0x7fec34a76908>, wait=<tenacity.wait.wait_exponential object at 0x7fec3454d860>, sleep=<built-in function sleep>, retry=<tenacity.retry.retry_if_exception_type object at 0x7fec34a82ba8>, before=<function before_nothing at 0x7fec34a6d950>, after=<function after_nothing at 0x7fec34a85378>)>, base_url='https://test.example.com/ws/api/518/')
    '''

    requests_session: Callable = default_requests_session
    '''A requests.Session object. Default: ``requests.Session()``.'''

    httpx_client: httpx.Client = httpx.Client()
    '''An httpx.Client object. Default: ``httpx.Client()``.'''

    timeout: Tuple[int, int] = (3, 60)
    '''A (connect timeout, read timeout) tuple. Required. Default: ``(3, 60)``.'''

    max_attempts: int = 10
    '''An integet maximum number of times to retry a request. Required. Default: ``10``.'''

    retryable: Callable = Factory(default_retryable)
    '''A function that takes a returns.Result and returns a boolean. Required. Default: Return value of ``default_retryable``.'''

    next_wait_interval: Callable = default_next_wait_interval
    '''A function that takes an integer number of seconds to wait and returns a new interval. Required. Default: Return value of ``default_next_wait_interval``.'''

    protocol: str = field(
        factory=default_protocol,
        validator=[
            attrs.validators.instance_of(str),
            attr.validators.in_(['http','https']),
        ]
    )
    '''HTTP protocol. Must be either ``https`` or ``http``. Default: ``https``'''

    domain: str = Factory(env_domain)
    '''Domain of a Pure API server. Required. Default: Return value of ``env_domain()``.'''

    base_path: str = Factory(default_base_path)
    '''Base path of the Pure API URL entry point, without the version number segment.
    Default: Return value of ``default_base_path()``.'''

    version: str = field(factory=default_version)
    '''Pure API version, without the decimal point. For example, ``517`` for version 5.17.
    Default: Return value of ``default_version()``.'''
    @version.validator
    def validate_version(self, attribute: str, value: str) -> None:
        if not valid_version(value):
            raise PureAPIInvalidVersionError(value)

    key: str = Factory(env_key)
    '''Pure API key. Required. Default: Return value of ``env_key()``.'''

    headers: MutableMapping = Factory(default_headers)
    '''HTTP headers. Default: Return value of ``default_headers()``. The
    constructor automatically adds an ``api-key`` header, using the value of
    the ``key`` attribute.'''

    records_per_request: int = Factory(default_records_per_request)

    request_page_params_parser: RequestPageParamsParser = PureRequestPageParamsParser

    response_page_parser: ResponsePageParser = PureResponsePageParser

    base_url: str = field(init=False)
    '''Pure API entrypoint URL. Should not be included in constructor
    parameters. The constructor generates this automatically based on
    other attributes.'''

    def __attrs_post_init__(self) -> None:
        self.headers['api-key'] = self.key
        object.__setattr__(self, 'base_url', f'{self.protocol}://{self.domain}/{self.base_path}/{self.version}/')

    @contextmanager
    def session(self):
        configured_functions = {
            function_name: partial(function, config=self)
            for (function_name, function) in getmembers(getmodule(self), isfunction)
            if (function.__module__ == getmodule(self).__name__ and
                'config' in signature(function).parameters
            )
        }
        Session = namedtuple('Session', configured_functions.keys())
        try:
            yield Session(**configured_functions)
        finally:
            # TODO: Does this make sense anymore?
            self.requests_session().close()
            self.httpx_client.close()

def preconfig(config:Config, *args:Callable) -> PVector[Callable]:
    '''Preconfigures functions that require a Config parameter.

    When using more than one function that requires configuration, or
    calling such functions multiple times, this function helps avoid
    repetition, allowing multiple functions to be configured only once,
    then re-used multiple times.

    Example:
        get, get_all = client.preconfig(Config(), client.get, client.get_all)

    Args:
        config: An instance of Config.
        *args: A list of functions that accept a config=Config parameter.

    Returns:
        A list of preconfigured functions.
    '''
    return pvector(partial(function, config=config) for function in args)

@safe
def attempt_request(
    httpx_client: httpx.Client,
    prepared_request: httpx.Request,
) -> Result[httpx.Response, Exception]:
    return httpx_client.send(prepared_request)

def manage_request_attempts(
    prepared_request:httpx.Request,
    attempts_id:str,
    wait_interval:int=2,
    attempt_number:int=1,
    config:Config=Config()
) -> Result[Response, Exception]:
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
 
    result = attempt_request(config.httpx_client, prepared_request)
 
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

    if config.retryable(result) and attempt_number < config.max_attempts:
        time.sleep(wait_interval)
        return manage_request_attempts(
            prepared_request=prepared_request,
            attempts_id=attempts_id,
            wait_interval=config.next_wait_interval(wait_interval),
            attempt_number=attempt_number+1,
            config=config
        )
    else:
        return result       

def get(resource_path:str, params:PMap=m(), config:Config=Config()) -> Result[httpx.Response, Exception]:
    '''Makes an HTTP GET request for Pure API resources.

    Args:
        resource_path: URL path to a Pure API resource, to be appended to the
            ``Config.base_url``. Do not include a leading forward slash (``/``).
        params: A PMap representing URL query string params. Default: ``{}``.
        config: An instance of Config. If not provided, this function attempts
            to automatically instantiate a Config based on environment variables
            and default values.

    Returns:
        An Result object, which may contain either a Response or an error/exception.
    '''
    prepared_request = config.httpx_client.build_request(
        'GET', config.base_url + resource_path, params=thaw(params), timeout=config.timeout, headers=config.headers
    )
    return manage_request_attempts(prepared_request, attempts_id=uuid.uuid4(), config=config)

def post(resource_path:str, params:PMap=m(), config:Config=Config()) -> Result[httpx.Response, Exception]:
    '''Makes an HTTP POST request for Pure API resources.

    Args:
        resource_path: URL path to a Pure API resource, to be appended to the
            ``Config.base_url``. Do not include a leading forward slash (``/``).
        params: A PMap representing payload data. Default: ``{}``.
        config: An instance of Config. If not provided, this function attempts
            to automatically instantiate a Config based on environment variables
            and default values.

    Returns:
        An Result object, which may contain either a Response or an error/exception.
    '''
    prepared_request = config.httpx_client.build_request(
        'POST', config.base_url + resource_path, json=thaw(params), timeout=config.timeout, headers=config.headers
    )
    return manage_request_attempts(prepared_request, attempts_id=uuid.uuid4(), config=config)

def request_pages_by_offset(
    request_by_offset_function,
    item_count:int,
    start_item_offset:int=0,
    items_per_page:int=1000,
    max_workers:int=4
) -> Iterator[Result[Response, Exception]]:
    '''
    '''

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = [
            executor.submit(
                request_by_offset_function,
                offset
            ) for offset in range(start_item_offset, item_count, items_per_page)
        ]
        for future in concurrent.futures.as_completed(results):
            yield future.result()

def build_request_by_offset_function(request_function:Callable, resource_path:str, *args, params:PMap, config:Config, **kwargs):
    partial_request = partial(request_function, resource_path, *args, config=config, **kwargs)
    def request_by_offset(offset:int):
        return partial_request(params=config.request_page_params_parser.update_offset(params, new_offset=offset))
    return request_by_offset

def all_responses_by_offset(request_function:Callable, resource_path:str, *args, params:PMap=m(), config=Config(), **kwargs) -> Iterator[Result[Response, Exception]]:
    first_result = request_function(resource_path, *args, params=params, config=config, **kwargs)
    yield first_result
    if not is_successful(first_result):
        return
    item_count = config.response_page_parser.count(first_result.unwrap().json())
    items_per_page = config.request_page_params_parser.size(params)
    if item_count <= items_per_page:
        return
    request_by_offset_function = build_request_by_offset_function(request_function, resource_path, *args, params=params, config=config, **kwargs)
    yield from request_pages_by_offset(request_by_offset_function, item_count=item_count, start_item_offset=items_per_page, items_per_page=items_per_page)

def all_items_by_offset(request_function:Callable, resource_path:str, *args, params:PMap=m(), config=Config(), **kwargs) -> Iterator[Result[Response, Exception]]:
    for result in all_responses_by_offset(request_function, resource_path, *args, params=params, config=config, **kwargs):
        if is_successful(result):
            for item in config.response_page_parser.items(result.unwrap().json()):
                yield item
        else:
            # log failure
            print(f'Failed! {result}')
            continue

## old functions from here to the end:

def get_all(resource_path:str, params:PMap=m(), config:Config=Config()) -> Iterator[Result[Response, Exception]]:
    '''Makes as many HTTP GET requests as necessary to get all resources in a
    collection, possibly restricted by the ``params``.

    Conveniently calculates the offset for each request, based on the desired
    number of records per request, as given by ``params['size']``.

    Args:
        resource_path: URL path to a Pure API resource, to be appended to the
            ``Config.base_url``. Do not include a leading forward slash (``/``).
        params: A mapping representing URL query string params. Default:
            ``{'size': 100}``
        config: An instance of Config. If not provided, this function attempts
            to automatically instantiate a Config based on environment variables
            and default values.

    Yields:
        Result objects, which may contain either a requests.Response or an error/exception.
    '''
    count_params = params.update({'size':0, 'offset':0})
    result = get(resource_path, count_params, config)

    if not is_successful(result):
        return result
    record_count = int(result.unwrap().json()['count'])
    window_size = int(params.get('size', 100))
    window_count = int(math.ceil(float(record_count) / window_size))

    for window_number in range(0, window_count):
        window_params = params.update({
            'offset': window_number * window_size,
            'size': window_size,
        })
        yield get(resource_path, window_params, config)

def get_all_transformed(
    resource_path:str,
    params:PMap=m(),
    config:Config=Config()
) -> Iterator[addict.Dict]:
    '''Like ``get_all()``, but with the added convenience of yielding
    individual records, transformed from raw JSON into ``addict.Dict`` objects,
    for easier access to deeply nested fields.

    Args:
        resource_path: URL path to a Pure API resource, to be appended to the
            ``Config.base_url``. Do not include a leading forward slash (``/``).
        params: A mapping representing URL query string params. Default:
            ``{'size': 100}``
        config: An instance of Config. If not provided, this function attempts
            to automatically instantiate a Config based on environment variables
            and default values.

    Yields:
        Individual records.

    Raises:
        common.PureAPIInvalidCollectionError: If the collection, the first
            segment in the resource_path, is invalid for the given API version.
        PureAPIHTTPError: If the response includes an HTTP error code, possibly
            after multiple retries.
        PureAPIRequestException: If the request generated some error unrelated
            to any HTTP error status.
        PureAPIClientException: Some unexpected exception that is none of the
            above.
    '''
    collection = _get_collection_from_resource_path(resource_path, config.version)
    for r in get_all(resource_path, params, config):
        for item in r.json()['items']:
            yield response.transform(collection, item, version=config.version)

def get_all_changes(start_date:str, params:PMap=m(), config:Config=Config()) -> Iterator[Response]:
    '''Makes as many HTTP GET requests as necessary to get all resources from
    the changes collection, from a start date forward.

    Conveniently finds resumption tokens and automatically adds them to each
    subsequent request. Note that there is no default ``size`` for number of
    records per request. Though the Pure API documentation includes support
    for that parameter, it seems to be ignored. The Pure API may actually
    ignore all parameters for this collection.

    Args:
        start_date: Date in ISO 8601 format, YYYY-MM-DD.
        params: A mapping representing URL query string params. Default: ``{}``
        config: An instance of Config. If not provided, this function attempts
            to automatically instantiate a Config based on environment variables
            and default values.

    Yields:
        HTTP response objects.

    Raises:
        common.PureAPIInvalidCollectionError: If the collection, the first
            segment in the resource_path, is invalid for the given API version.
        PureAPIHTTPError: If the response includes an HTTP error code, possibly
            after multiple retries.
        PureAPIRequestException: If the request generated some error unrelated
            to any HTTP error status.
        PureAPIClientException: Some unexpected exception that is none of the
            above.
    '''
    next_token_or_date = start_date
    while(True):
        r = get('changes/' + next_token_or_date, params, config)
        json = r.json()

        if json['moreChanges'] is True:
            next_token_or_date = str(json['resumptionToken'])
            if int(json['count']) == 0 or 'items' not in json:
                # We skip these responses, under the assumption that a caller wanting all changes will
                # have no use for a response that contains no changes.
                # The "count" in changes responses has different semantics from all other endpoints.
                # While for all others "count" is the total number of records that matched the request,
                # for changes it is the number of records in the current response. According to Elsevier,
                # "In an extreme scenario the count can be 0 while moreChanges is true, if for example
                # all 100 changes are on confidential content"
                # -- https://support.pure.elsevier.com/browse/PURESUPPORT-63657?focusedCommentId=560888&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel#comment-560888
                # We have seen counts of 0, sometimes in multiple, consecutive responses. When "count"
                # is zero, there will be no "items", so we check for that, too, for some extra protection.
                continue
        else:
            break

        yield r

def get_all_changes_transformed(
    start_date:str,
    params:PMap=m(),
    config:Config=Config()
) -> Iterator[addict.Dict]:
    '''Like ``get_all_changes()``, but with the added convenience of yielding
    individual records, transformed from raw JSON into ``addict.Dict`` objects,
    for easier access to deeply nested fields.

    Args:
        start_date: Date in ISO 8601 format, YYYY-MM-DD.
        params: A mapping representing URL query string params. Default:
            ``{'size': 100}``
        config: An instance of Config. If not provided, this function attempts
            to automatically instantiate a Config based on environment variables
            and default values.

    Yields:
        Individual records.

    Raises:
        common.PureAPIInvalidCollectionError: If the collection, the first
            segment in the resource_path, is invalid for the given API version.
        PureAPIHTTPError: If the response includes an HTTP error code, possibly
            after multiple retries.
        PureAPIRequestException: If the request generated some error unrelated
            to any HTTP error status.
        PureAPIClientException: Some unexpected exception that is none of the
            above.
    '''
    for r in get_all_changes(start_date, params, config):
        for item in r.json()['items']:
            yield response.transform('changes', item, version=config.version)

def filter(resource_path:str, payload:PMap=m(), config:Config=Config()) -> Response:
    '''Makes an HTTP POST request for Pure API resources, filtered according to
        the ``payload``.

    Note that many collections likely contain more resources than can be
    practically downloaded in a single request. To retrieve all filtered
    resources in a collection, see ``filter_all()``.

    Args:
        resource_path: URL path to a Pure API resource, to be appended to the
            ``Config.base_url``. Do not include a leading forward slash (``/``).
        payload: A PMap representing JSON filters of the collection. Default: ``{}``
        config: An instance of Config. If not provided, this function attempts
            to automatically instantiate a Config based on environment variables
            and default values.

    Returns:
        An HTTP response object.

    Raises:
        common.PureAPIInvalidCollectionError: If the collection, the first
            segment in the resource_path, is invalid for the given API version.
        PureAPIHTTPError: If the response includes an HTTP error code, possibly
            after multiple retries.
        PureAPIRequestException: If the request generated some error unrelated
            to any HTTP error status.
        PureAPIClientException: Some unexpected exception that is none of the
            above.
    '''
    collection = _get_collection_from_resource_path(resource_path, config.version)
    with requests.Session() as s:
        prepped = s.prepare_request(requests.Request('POST', config.base_url + resource_path, json=thaw(payload)))
        prepped.headers = {**prepped.headers, **config.headers}

        try:
            r = config.retryer(s.send, prepped)
            r.raise_for_status()
            return r
        except HTTPError as http_exc:
            raise PureAPIHTTPError(
                f'POST request for resource path {resource_path} with payload {payload} returned HTTP status {http_exc.response.status_code}',
                request=http_exc.request,
                response=http_exc.response
            ) from http_exc
        except RequestException as req_exc:
            raise PureAPIRequestException(
                f'Failed POST request for resource path {resource_path} with payload {payload}',
                request=req_exc.request,
                response=req_exc.response
            ) from req_exc
        except Exception as e:
            raise PureAPIClientException(
                f'Unexpected exception for POST request for resource path {resource_path} with payload {payload}'
            ) from e

def filter_all(resource_path:str, payload:PMap=m(), config:Config=Config()) -> Iterator[Response]:
    '''Makes as many HTTP POST requests as necessary to retrieve all resources in
    a collection, filtered according to the ``payload``.

    Conveniently calculates the offset for each request, based on the desired
    number of records per request, as given by ``payload['size']``.

    Args:
        resource_path: URL path to a Pure API resource, to be appended to the
            ``Config.base_url``. Do not include a leading forward slash (``/``).
        payload: A PMap representing JSON filters of the collection. Default:
            ``pmap({'size': 100})``
        config: An instance of Config. If not provided, this function attempts
            to automatically instantiate a Config based on environment variables
            and default values.

    Yields:
        HTTP response objects.

    Raises:
        common.PureAPIInvalidCollectionError: If the collection, the first
            segment in the resource_path, is invalid for the given API version.
        PureAPIHTTPError: If the response includes an HTTP error code, possibly
            after multiple retries.
        PureAPIRequestException: If the request generated some error unrelated
            to any HTTP error status.
        PureAPIClientException: Some unexpected exception that is none of the
            above.
    '''
    count_payload = payload.update({'size':0, 'offset':0})
    r = filter(resource_path, count_payload, config)
    json = r.json()
    record_count = int(json['count'])

    # TODO: This needs work. Replace with custom params/payload type.
    window_size = int(payload.get('size', 100))
    if window_size <= 0:
        window_size = 100
    # TODO: Since we're now using PMap, this won't work:
    #payload['size'] = window_size
    window_count = int(math.ceil(float(record_count) / window_size))

    for window in range(0, window_count):
        window_payload = payload.update({
            'offset': window * window_size,
            'size': window_size
        })
        yield filter(resource_path, window_payload, config)

def _group_items(items:PVector=v(), items_per_group:int=100) -> Iterator[List]:
    '''Groups a list of items into multiple, smaller groups, each with no more
    items than ``items_per_group``.

    Args:
        items: Items to group into smaller sub-groups.
        items_per_group: Number of items in each sub-group.

    Yields:
        Sub-group with <= ``items_per_group`` items.
    '''
    items_per_group = int(items_per_group)
    if items_per_group <= 0:
        items_per_group = default_items_per_group
    start = 0
    end = items_per_group
    # TODO: This may need work for PVector compatibility
    while start < len(items):
        yield items[start:end]
        start += items_per_group
        end += items_per_group

def filter_all_by_uuid(
    resource_path:str,
    payload:PMap=m(),
    uuids:PVector=(),
    uuids_per_request:int=100,
    config:Config=Config()
) -> Iterator[Response]:
    '''Like ``filter_all()``, but with added convenience for requesting a set of
    records by uuid.

    Args:
        resource_path: URL path to a Pure API resource, to be appended to the
            ``Config.base_url``. Do not include a leading forward slash (``/``).
        payload: A PMap representing JSON filters, in addition to the uuids,
            of the collection. Default: ``pmap({})``
        uuids: The list of uuids to retrieve. Default: ``[]``
        uuids_per_request: The number of records to retrieve in each request.
          Default: 100
        config: An instance of Config. If not provided, this function attempts
            to automatically instantiate a Config based on environment variables
            and default values.

    Yields:
        HTTP response objects.

    Raises:
        common.PureAPIInvalidCollectionError: If the collection, the first
            segment in the resource_path, is invalid for the given API version.
        PureAPIHTTPError: If the response includes an HTTP error code, possibly
            after multiple retries.
        PureAPIRequestException: If the request generated some error unrelated
            to any HTTP error status.
        PureAPIClientException: Some unexpected exception that is none of the
            above.
    '''
    # TODO: May need work for PVector compatibility
    for uuid_group in _group_items(items=uuids, items_per_group=uuids_per_request):
        group_payload = payload.update({
            'uuids': uuid_group,
            'size': len(uuid_group),
        })
        yield filter(resource_path, group_payload, config)

def filter_all_by_id(
    resource_path:str,
    payload:PMap=m(),
    ids:PVector=v(),
    ids_per_request:int=100,
    config:Config=Config()
) -> Iterator[Response]:
    '''Like ``filter_all()``, but with added convenience for requesting a set of
    records by some non-uuid identifier.

    Args:
        resource_path: URL path to a Pure API resource, to be appended to the
            ``Config.base_url``. Do not include a leading forward slash (``/``).
        payload: A PMap representing JSON filters, in addition to the uuids,
            of the collection. Default: ``pmap({})``
        ids: The list of ids to retrieve. Default: ``[]``
        ids_per_request: The number of records to retrieve in each request.
          Default: 100
        config: An instance of Config. If not provided, this function attempts
            to automatically instantiate a Config based on environment variables
            and default values.

    Yields:
        HTTP response objects.

    Raises:
        common.PureAPIInvalidCollectionError: If the collection, the first
            segment in the resource_path, is invalid for the given API version.
        PureAPIHTTPError: If the response includes an HTTP error code, possibly
            after multiple retries.
        PureAPIRequestException: If the request generated some error unrelated
            to any HTTP error status.
        PureAPIClientException: Some unexpected exception that is none of the
            above.
    '''
    # TODO: May need work for PVector compatibility
    for id_group in _group_items(items=ids, items_per_group=ids_per_request):
        group_payload = payload.update({
            'ids': id_group,
            'size': len(id_group),
        })
        yield filter(resource_path, group_payload, config)

def filter_all_transformed(
    resource_path:str,
    payload:PMap=m(),
    config:Config=Config()
) -> Iterator[addict.Dict]:
    '''Like ``filter_all()``, but with the added convenience of yielding
    individual records, transformed from raw JSON into ``addict.Dict`` objects,
    for easier access to deeply nested fields.

    Args:
        resource_path: URL path to a Pure API resource, to be appended to the
            ``Config.base_url``. Do not include a leading forward slash (``/``).
        payload: A PMap representing JSON filters of the collection. Default:
            ``pmap({'size': 100})``
        config: An instance of Config. If not provided, this function attempts
            to automatically instantiate a Config based on environment variables
            and default values.

    Yields:
        Individual records.

    Raises:
        common.PureAPIInvalidCollectionError: If the collection, the first
            segment in the resource_path, is invalid for the given API version.
        PureAPIHTTPError: If the response includes an HTTP error code, possibly
            after multiple retries.
        PureAPIRequestException: If the request generated some error unrelated
            to any HTTP error status.
        PureAPIClientException: Some unexpected exception that is none of the
            above.
    '''
    collection = _get_collection_from_resource_path(resource_path, config.version)
    for r in filter_all(resource_path, payload, config):
        for item in r.json()['items']:
            yield response.transform(collection, item, version=config.version)

def filter_all_by_uuid_transformed(
    resource_path:str,
    payload:PMap=m(),
    uuids:PVector=v(),
    uuids_per_request:int=100,
    config:Config=Config()
) -> Iterator[addict.Dict]:
    '''Like ``filter_all_by_uuid()``, but with the added convenience of yielding
    individual records, transformed from raw JSON into ``addict.Dict`` objects,
    for easier access to deeply nested fields.

    Args:
        resource_path: URL path to a Pure API resource, to be appended to the
            ``Config.base_url``. Do not include a leading forward slash (``/``).
        payload: A PMap representing JSON filters, in addition to the uuids,
            of the collection. Default: ``pmap({})``
        uuids: The list of uuids to retrieve. Default: ``[]``
        uuids_per_request: The number of records to retrieve in each request.
          Default: 100
        config: An instance of Config. If not provided, this function attempts
            to automatically instantiate a Config based on environment variables
            and default values.

    Yields:
        Individual records.

    Raises:
        common.PureAPIInvalidCollectionError: If the collection, the first
            segment in the resource_path, is invalid for the given API version.
        PureAPIHTTPError: If the response includes an HTTP error code, possibly
            after multiple retries.
        PureAPIRequestException: If the request generated some error unrelated
            to any HTTP error status.
        PureAPIClientException: Some unexpected exception that is none of the
            above.
    '''
    # TODO: May need work for PVector compatibility
    collection = _get_collection_from_resource_path(resource_path, config.version)
    for r in filter_all_by_uuid(
        resource_path,
        payload=payload,
        uuids=uuids,
        uuids_per_request=uuids_per_request,
        config=config
    ):
        for item in r.json()['items']:
            yield response.transform(collection, item, version=config.version)

def filter_all_by_id_transformed(
    resource_path:str,
    payload:PMap=m(),
    ids:PVector=v(),
    ids_per_request:int=100,
    config:Config=Config()
) -> Iterator[addict.Dict]:
    '''Like ``filter_all_by_id()``, but with the added convenience of yielding
    individual records, transformed from raw JSON into ``addict.Dict`` objects,
    for easier access to deeply nested fields.

    Args:
        resource_path: URL path to a Pure API resource, to be appended to the
            ``Config.base_url``. Do not include a leading forward slash (``/``).
        payload: A PMap representing JSON filters, in addition to the uuids,
            of the collection. Default: ``pmap({})``
        ids: The list of ids to retrieve. Default: ``[]``
        ids_per_request: The number of records to retrieve in each request.
          Default: 100
        config: An instance of Config. If not provided, this function attempts
            to automatically instantiate a Config based on environment variables
            and default values.

    Yields:
        Individual records.

    Raises:
        common.PureAPIInvalidCollectionError: If the collection, the first
            segment in the resource_path, is invalid for the given API version.
        PureAPIHTTPError: If the response includes an HTTP error code, possibly
            after multiple retries.
        PureAPIRequestException: If the request generated some error unrelated
            to any HTTP error status.
        PureAPIClientException: Some unexpected exception that is none of the
            above.
    '''
    # TODO: May need work for PVector compatibility
    collection = _get_collection_from_resource_path(resource_path, config.version)
    for r in filter_all_by_id(
        resource_path,
        payload=payload,
        ids=ids,
        ids_per_request=ids_per_request,
        config=config
    ):
        for item in r.json()['items']:
            yield response.transform(collection, item, version=config.version)
