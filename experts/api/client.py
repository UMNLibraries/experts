from collections import namedtuple
import concurrent.futures
from contextlib import contextmanager
from functools import partial
import importlib
from inspect import getmembers, getmodule, isfunction, signature
import os
import threading
import time
from typing import Callable, Iterator
import uuid

import attrs
from attrs import Factory, field, frozen

from pyrsistent import thaw, m, pmap, v, pvector
from pyrsistent.typing import PMap, PVector

import httpx

import returns
from returns.pipeline import is_successful
from returns.result import Result, Success, Failure, safe

# Is there a better way to do this when all we went is the Context type?
from experts.api.context import Context

@contextmanager
def session(context: Context):
    configured_functions = {
        function_name: partial(function, context=context)
        for (function_name, function) in getmembers(importlib.import_module(__name__), isfunction)
        if (function.__module__ == __name__ and
            'context' in signature(function).parameters
        )
    }
    Session = namedtuple('Session', configured_functions.keys())
    try:
        yield Session(**configured_functions)
    finally:
        context.httpx_client.close()

@safe
def attempt_request(
    httpx_client: httpx.Client,
    prepared_request: httpx.Request,
) -> Result[httpx.Response, Exception]:
    return httpx_client.send(prepared_request)

def manage_request_attempts(
    prepared_request: httpx.Request,
    attempts_id: str,
    context: Context,
    wait_interval: int = 2,
    attempt_number: int = 1
) -> Result[httpx.Response, Exception]:
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
 
    result = attempt_request(context.httpx_client, prepared_request)
 
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

    if context.retryable(result) and attempt_number < context.max_attempts:
        time.sleep(wait_interval)
        return manage_request_attempts(
            prepared_request=prepared_request,
            attempts_id=attempts_id,
            wait_interval=context.next_wait_interval(wait_interval),
            attempt_number=attempt_number+1,
            context=context
        )
    else:
        return result       

def get(resource_path: str, context: Context, params: PMap = m()) -> Result[httpx.Response, Exception]:
    '''Makes an HTTP GET request for Pure API resources.

    Args:
        resource_path: URL path to a Pure API resource, to be appended to the
            ``Config.base_url``. Do not include a leading forward slash (``/``).
        params: A PMap representing URL query string params. Default: ``{}``.
        context: An instance of an experts.api.context.Context.

    Returns:
        An Result object, which may contain either a Response or an error/exception.
    '''
    prepared_request = context.httpx_client.build_request(
        'GET',
        resource_path,
        params=thaw(params),
        timeout=context.timeout
    )
    return manage_request_attempts(
        prepared_request,
        attempts_id=uuid.uuid4(),
        context=context
    )

def post(resource_path: str, context: Context, params: PMap = m()) -> Result[httpx.Response, Exception]:
    '''Makes an HTTP POST request for Pure API resources.

    Args:
        resource_path: URL path to a Pure API resource, to be appended to the
            ``Config.base_url``. Do not include a leading forward slash (``/``).
        params: A PMap representing payload data. Default: ``{}``.
        context: An instance of experts.api.context.Context.

    Returns:
        An Result object, which may contain either a Response or an error/exception.
    '''
    prepared_request = context.httpx_client.build_request(
        'POST',
        resource_path,
        json=thaw(params),
        timeout=context.timeout
    )
    return manage_request_attempts(
        prepared_request,
        attempts_id=uuid.uuid4(),
        context=context
    )

def request_pages_by_offset(
    request_by_offset_function,
    item_count: int,
    start_item_offset: int = 0,
    items_per_page: int = 1000,
    max_workers: int = 4
) -> Iterator[Result[httpx.Response, Exception]]:
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

def build_request_by_offset_function(
    request_function: Callable,
    resource_path: str, *args,
    params: PMap,
    context: Context,
    **kwargs
):
    partial_request = partial(
        request_function,
        resource_path,
        *args,
        context=context,
        **kwargs
    )
    def request_by_offset(offset: int):
        return partial_request(
            params=context.request_page_params_parser.update_offset(
                params,
                new_offset=offset
            )
        )
    return request_by_offset

def all_responses_by_offset(
    request_function: Callable,
    resource_path: str,
    *args,
    params: PMap = m(),
    context: Context,
    **kwargs
) -> Iterator[Result[httpx.Response, Exception]]:
    first_result = request_function(
        resource_path,
        *args,
        params=params,
        context=context,
        **kwargs
    )
    yield first_result
    if not is_successful(first_result):
        return
    item_count = context.response_page_parser.count(
        first_result.unwrap().json()
    )
    items_per_page = context.request_page_params_parser.size(params)
    if item_count <= items_per_page:
        return
    request_by_offset_function = build_request_by_offset_function(
        request_function,
        resource_path,
        *args,
        params=params,
        context=context,
        **kwargs
    )
    yield from request_pages_by_offset(
        request_by_offset_function,
        item_count=item_count,
        start_item_offset=items_per_page,
        items_per_page=items_per_page
    )

def all_items_by_offset(
    request_function: Callable,
    resource_path: str,
    *args,
    params: PMap = m(),
    context: Context,
    **kwargs
) -> Iterator[Result[httpx.Response, Exception]]:
    for result in all_responses_by_offset(
        request_function,
        resource_path,
        *args,
        params=params,
        context=context,
        **kwargs
    ):
        if is_successful(result):
            for item in context.response_page_parser.items(
                result.unwrap().json()
            ):
                yield item
        else:
            # log failure
            print(f'Failed! {result}')
            continue

## old functions from here to the end:
#
#def get_all(resource_path:str, params:PMap=m(), config:Config=Config()) -> Iterator[Result[Response, Exception]]:
#    '''Makes as many HTTP GET requests as necessary to get all resources in a
#    collection, possibly restricted by the ``params``.
#
#    Conveniently calculates the offset for each request, based on the desired
#    number of records per request, as given by ``params['size']``.
#
#    Args:
#        resource_path: URL path to a Pure API resource, to be appended to the
#            ``Config.base_url``. Do not include a leading forward slash (``/``).
#        params: A mapping representing URL query string params. Default:
#            ``{'size': 100}``
#        config: An instance of Config. If not provided, this function attempts
#            to automatically instantiate a Config based on environment variables
#            and default values.
#
#    Yields:
#        Result objects, which may contain either a requests.Response or an error/exception.
#    '''
#    count_params = params.update({'size':0, 'offset':0})
#    result = get(resource_path, count_params, config)
#
#    if not is_successful(result):
#        return result
#    record_count = int(result.unwrap().json()['count'])
#    window_size = int(params.get('size', 100))
#    window_count = int(math.ceil(float(record_count) / window_size))
#
#    for window_number in range(0, window_count):
#        window_params = params.update({
#            'offset': window_number * window_size,
#            'size': window_size,
#        })
#        yield get(resource_path, window_params, config)
#
#def get_all_transformed(
#    resource_path:str,
#    params:PMap=m(),
#    config:Config=Config()
#) -> Iterator[addict.Dict]:
#    '''Like ``get_all()``, but with the added convenience of yielding
#    individual records, transformed from raw JSON into ``addict.Dict`` objects,
#    for easier access to deeply nested fields.
#
#    Args:
#        resource_path: URL path to a Pure API resource, to be appended to the
#            ``Config.base_url``. Do not include a leading forward slash (``/``).
#        params: A mapping representing URL query string params. Default:
#            ``{'size': 100}``
#        config: An instance of Config. If not provided, this function attempts
#            to automatically instantiate a Config based on environment variables
#            and default values.
#
#    Yields:
#        Individual records.
#
#    Raises:
#        common.PureAPIInvalidCollectionError: If the collection, the first
#            segment in the resource_path, is invalid for the given API version.
#        PureAPIHTTPError: If the response includes an HTTP error code, possibly
#            after multiple retries.
#        PureAPIRequestException: If the request generated some error unrelated
#            to any HTTP error status.
#        PureAPIClientException: Some unexpected exception that is none of the
#            above.
#    '''
#    collection = _get_collection_from_resource_path(resource_path, config.version)
#    for r in get_all(resource_path, params, config):
#        for item in r.json()['items']:
#            yield response.transform(collection, item, version=config.version)
#
#def get_all_changes(start_date:str, params:PMap=m(), config:Config=Config()) -> Iterator[Response]:
#    '''Makes as many HTTP GET requests as necessary to get all resources from
#    the changes collection, from a start date forward.
#
#    Conveniently finds resumption tokens and automatically adds them to each
#    subsequent request. Note that there is no default ``size`` for number of
#    records per request. Though the Pure API documentation includes support
#    for that parameter, it seems to be ignored. The Pure API may actually
#    ignore all parameters for this collection.
#
#    Args:
#        start_date: Date in ISO 8601 format, YYYY-MM-DD.
#        params: A mapping representing URL query string params. Default: ``{}``
#        config: An instance of Config. If not provided, this function attempts
#            to automatically instantiate a Config based on environment variables
#            and default values.
#
#    Yields:
#        HTTP response objects.
#
#    Raises:
#        common.PureAPIInvalidCollectionError: If the collection, the first
#            segment in the resource_path, is invalid for the given API version.
#        PureAPIHTTPError: If the response includes an HTTP error code, possibly
#            after multiple retries.
#        PureAPIRequestException: If the request generated some error unrelated
#            to any HTTP error status.
#        PureAPIClientException: Some unexpected exception that is none of the
#            above.
#    '''
#    next_token_or_date = start_date
#    while(True):
#        r = get('changes/' + next_token_or_date, params, config)
#        json = r.json()
#
#        if json['moreChanges'] is True:
#            next_token_or_date = str(json['resumptionToken'])
#            if int(json['count']) == 0 or 'items' not in json:
#                # We skip these responses, under the assumption that a caller wanting all changes will
#                # have no use for a response that contains no changes.
#                # The "count" in changes responses has different semantics from all other endpoints.
#                # While for all others "count" is the total number of records that matched the request,
#                # for changes it is the number of records in the current response. According to Elsevier,
#                # "In an extreme scenario the count can be 0 while moreChanges is true, if for example
#                # all 100 changes are on confidential content"
#                # -- https://support.pure.elsevier.com/browse/PURESUPPORT-63657?focusedCommentId=560888&page=com.atlassian.jira.plugin.system.issuetabpanels:comment-tabpanel#comment-560888
#                # We have seen counts of 0, sometimes in multiple, consecutive responses. When "count"
#                # is zero, there will be no "items", so we check for that, too, for some extra protection.
#                continue
#        else:
#            break
#
#        yield r
#
#def get_all_changes_transformed(
#    start_date:str,
#    params:PMap=m(),
#    config:Config=Config()
#) -> Iterator[addict.Dict]:
#    '''Like ``get_all_changes()``, but with the added convenience of yielding
#    individual records, transformed from raw JSON into ``addict.Dict`` objects,
#    for easier access to deeply nested fields.
#
#    Args:
#        start_date: Date in ISO 8601 format, YYYY-MM-DD.
#        params: A mapping representing URL query string params. Default:
#            ``{'size': 100}``
#        config: An instance of Config. If not provided, this function attempts
#            to automatically instantiate a Config based on environment variables
#            and default values.
#
#    Yields:
#        Individual records.
#
#    Raises:
#        common.PureAPIInvalidCollectionError: If the collection, the first
#            segment in the resource_path, is invalid for the given API version.
#        PureAPIHTTPError: If the response includes an HTTP error code, possibly
#            after multiple retries.
#        PureAPIRequestException: If the request generated some error unrelated
#            to any HTTP error status.
#        PureAPIClientException: Some unexpected exception that is none of the
#            above.
#    '''
#    for r in get_all_changes(start_date, params, config):
#        for item in r.json()['items']:
#            yield response.transform('changes', item, version=config.version)
#
#def filter(resource_path:str, payload:PMap=m(), config:Config=Config()) -> Response:
#    '''Makes an HTTP POST request for Pure API resources, filtered according to
#        the ``payload``.
#
#    Note that many collections likely contain more resources than can be
#    practically downloaded in a single request. To retrieve all filtered
#    resources in a collection, see ``filter_all()``.
#
#    Args:
#        resource_path: URL path to a Pure API resource, to be appended to the
#            ``Config.base_url``. Do not include a leading forward slash (``/``).
#        payload: A PMap representing JSON filters of the collection. Default: ``{}``
#        config: An instance of Config. If not provided, this function attempts
#            to automatically instantiate a Config based on environment variables
#            and default values.
#
#    Returns:
#        An HTTP response object.
#
#    Raises:
#        common.PureAPIInvalidCollectionError: If the collection, the first
#            segment in the resource_path, is invalid for the given API version.
#        PureAPIHTTPError: If the response includes an HTTP error code, possibly
#            after multiple retries.
#        PureAPIRequestException: If the request generated some error unrelated
#            to any HTTP error status.
#        PureAPIClientException: Some unexpected exception that is none of the
#            above.
#    '''
#    collection = _get_collection_from_resource_path(resource_path, config.version)
#    with requests.Session() as s:
#        prepped = s.prepare_request(requests.Request('POST', config.base_url + resource_path, json=thaw(payload)))
#        prepped.headers = {**prepped.headers, **config.headers}
#
#        try:
#            r = config.retryer(s.send, prepped)
#            r.raise_for_status()
#            return r
#        except HTTPError as http_exc:
#            raise PureAPIHTTPError(
#                f'POST request for resource path {resource_path} with payload {payload} returned HTTP status {http_exc.response.status_code}',
#                request=http_exc.request,
#                response=http_exc.response
#            ) from http_exc
#        except RequestException as req_exc:
#            raise PureAPIRequestException(
#                f'Failed POST request for resource path {resource_path} with payload {payload}',
#                request=req_exc.request,
#                response=req_exc.response
#            ) from req_exc
#        except Exception as e:
#            raise PureAPIClientException(
#                f'Unexpected exception for POST request for resource path {resource_path} with payload {payload}'
#            ) from e
#
#def filter_all(resource_path:str, payload:PMap=m(), config:Config=Config()) -> Iterator[Response]:
#    '''Makes as many HTTP POST requests as necessary to retrieve all resources in
#    a collection, filtered according to the ``payload``.
#
#    Conveniently calculates the offset for each request, based on the desired
#    number of records per request, as given by ``payload['size']``.
#
#    Args:
#        resource_path: URL path to a Pure API resource, to be appended to the
#            ``Config.base_url``. Do not include a leading forward slash (``/``).
#        payload: A PMap representing JSON filters of the collection. Default:
#            ``pmap({'size': 100})``
#        config: An instance of Config. If not provided, this function attempts
#            to automatically instantiate a Config based on environment variables
#            and default values.
#
#    Yields:
#        HTTP response objects.
#
#    Raises:
#        common.PureAPIInvalidCollectionError: If the collection, the first
#            segment in the resource_path, is invalid for the given API version.
#        PureAPIHTTPError: If the response includes an HTTP error code, possibly
#            after multiple retries.
#        PureAPIRequestException: If the request generated some error unrelated
#            to any HTTP error status.
#        PureAPIClientException: Some unexpected exception that is none of the
#            above.
#    '''
#    count_payload = payload.update({'size':0, 'offset':0})
#    r = filter(resource_path, count_payload, config)
#    json = r.json()
#    record_count = int(json['count'])
#
#    # TODO: This needs work. Replace with custom params/payload type.
#    window_size = int(payload.get('size', 100))
#    if window_size <= 0:
#        window_size = 100
#    # TODO: Since we're now using PMap, this won't work:
#    #payload['size'] = window_size
#    window_count = int(math.ceil(float(record_count) / window_size))
#
#    for window in range(0, window_count):
#        window_payload = payload.update({
#            'offset': window * window_size,
#            'size': window_size
#        })
#        yield filter(resource_path, window_payload, config)
#
#def _group_items(items:PVector=v(), items_per_group:int=100) -> Iterator[List]:
#    '''Groups a list of items into multiple, smaller groups, each with no more
#    items than ``items_per_group``.
#
#    Args:
#        items: Items to group into smaller sub-groups.
#        items_per_group: Number of items in each sub-group.
#
#    Yields:
#        Sub-group with <= ``items_per_group`` items.
#    '''
#    items_per_group = int(items_per_group)
#    if items_per_group <= 0:
#        items_per_group = default_items_per_group
#    start = 0
#    end = items_per_group
#    # TODO: This may need work for PVector compatibility
#    while start < len(items):
#        yield items[start:end]
#        start += items_per_group
#        end += items_per_group
#
#def filter_all_by_uuid(
#    resource_path:str,
#    payload:PMap=m(),
#    uuids:PVector=(),
#    uuids_per_request:int=100,
#    config:Config=Config()
#) -> Iterator[Response]:
#    '''Like ``filter_all()``, but with added convenience for requesting a set of
#    records by uuid.
#
#    Args:
#        resource_path: URL path to a Pure API resource, to be appended to the
#            ``Config.base_url``. Do not include a leading forward slash (``/``).
#        payload: A PMap representing JSON filters, in addition to the uuids,
#            of the collection. Default: ``pmap({})``
#        uuids: The list of uuids to retrieve. Default: ``[]``
#        uuids_per_request: The number of records to retrieve in each request.
#          Default: 100
#        config: An instance of Config. If not provided, this function attempts
#            to automatically instantiate a Config based on environment variables
#            and default values.
#
#    Yields:
#        HTTP response objects.
#
#    Raises:
#        common.PureAPIInvalidCollectionError: If the collection, the first
#            segment in the resource_path, is invalid for the given API version.
#        PureAPIHTTPError: If the response includes an HTTP error code, possibly
#            after multiple retries.
#        PureAPIRequestException: If the request generated some error unrelated
#            to any HTTP error status.
#        PureAPIClientException: Some unexpected exception that is none of the
#            above.
#    '''
#    # TODO: May need work for PVector compatibility
#    for uuid_group in _group_items(items=uuids, items_per_group=uuids_per_request):
#        group_payload = payload.update({
#            'uuids': uuid_group,
#            'size': len(uuid_group),
#        })
#        yield filter(resource_path, group_payload, config)
#
#def filter_all_by_id(
#    resource_path:str,
#    payload:PMap=m(),
#    ids:PVector=v(),
#    ids_per_request:int=100,
#    config:Config=Config()
#) -> Iterator[Response]:
#    '''Like ``filter_all()``, but with added convenience for requesting a set of
#    records by some non-uuid identifier.
#
#    Args:
#        resource_path: URL path to a Pure API resource, to be appended to the
#            ``Config.base_url``. Do not include a leading forward slash (``/``).
#        payload: A PMap representing JSON filters, in addition to the uuids,
#            of the collection. Default: ``pmap({})``
#        ids: The list of ids to retrieve. Default: ``[]``
#        ids_per_request: The number of records to retrieve in each request.
#          Default: 100
#        config: An instance of Config. If not provided, this function attempts
#            to automatically instantiate a Config based on environment variables
#            and default values.
#
#    Yields:
#        HTTP response objects.
#
#    Raises:
#        common.PureAPIInvalidCollectionError: If the collection, the first
#            segment in the resource_path, is invalid for the given API version.
#        PureAPIHTTPError: If the response includes an HTTP error code, possibly
#            after multiple retries.
#        PureAPIRequestException: If the request generated some error unrelated
#            to any HTTP error status.
#        PureAPIClientException: Some unexpected exception that is none of the
#            above.
#    '''
#    # TODO: May need work for PVector compatibility
#    for id_group in _group_items(items=ids, items_per_group=ids_per_request):
#        group_payload = payload.update({
#            'ids': id_group,
#            'size': len(id_group),
#        })
#        yield filter(resource_path, group_payload, config)
#
#def filter_all_transformed(
#    resource_path:str,
#    payload:PMap=m(),
#    config:Config=Config()
#) -> Iterator[addict.Dict]:
#    '''Like ``filter_all()``, but with the added convenience of yielding
#    individual records, transformed from raw JSON into ``addict.Dict`` objects,
#    for easier access to deeply nested fields.
#
#    Args:
#        resource_path: URL path to a Pure API resource, to be appended to the
#            ``Config.base_url``. Do not include a leading forward slash (``/``).
#        payload: A PMap representing JSON filters of the collection. Default:
#            ``pmap({'size': 100})``
#        config: An instance of Config. If not provided, this function attempts
#            to automatically instantiate a Config based on environment variables
#            and default values.
#
#    Yields:
#        Individual records.
#
#    Raises:
#        common.PureAPIInvalidCollectionError: If the collection, the first
#            segment in the resource_path, is invalid for the given API version.
#        PureAPIHTTPError: If the response includes an HTTP error code, possibly
#            after multiple retries.
#        PureAPIRequestException: If the request generated some error unrelated
#            to any HTTP error status.
#        PureAPIClientException: Some unexpected exception that is none of the
#            above.
#    '''
#    collection = _get_collection_from_resource_path(resource_path, config.version)
#    for r in filter_all(resource_path, payload, config):
#        for item in r.json()['items']:
#            yield response.transform(collection, item, version=config.version)
#
#def filter_all_by_uuid_transformed(
#    resource_path:str,
#    payload:PMap=m(),
#    uuids:PVector=v(),
#    uuids_per_request:int=100,
#    config:Config=Config()
#) -> Iterator[addict.Dict]:
#    '''Like ``filter_all_by_uuid()``, but with the added convenience of yielding
#    individual records, transformed from raw JSON into ``addict.Dict`` objects,
#    for easier access to deeply nested fields.
#
#    Args:
#        resource_path: URL path to a Pure API resource, to be appended to the
#            ``Config.base_url``. Do not include a leading forward slash (``/``).
#        payload: A PMap representing JSON filters, in addition to the uuids,
#            of the collection. Default: ``pmap({})``
#        uuids: The list of uuids to retrieve. Default: ``[]``
#        uuids_per_request: The number of records to retrieve in each request.
#          Default: 100
#        config: An instance of Config. If not provided, this function attempts
#            to automatically instantiate a Config based on environment variables
#            and default values.
#
#    Yields:
#        Individual records.
#
#    Raises:
#        common.PureAPIInvalidCollectionError: If the collection, the first
#            segment in the resource_path, is invalid for the given API version.
#        PureAPIHTTPError: If the response includes an HTTP error code, possibly
#            after multiple retries.
#        PureAPIRequestException: If the request generated some error unrelated
#            to any HTTP error status.
#        PureAPIClientException: Some unexpected exception that is none of the
#            above.
#    '''
#    # TODO: May need work for PVector compatibility
#    collection = _get_collection_from_resource_path(resource_path, config.version)
#    for r in filter_all_by_uuid(
#        resource_path,
#        payload=payload,
#        uuids=uuids,
#        uuids_per_request=uuids_per_request,
#        config=config
#    ):
#        for item in r.json()['items']:
#            yield response.transform(collection, item, version=config.version)
#
#def filter_all_by_id_transformed(
#    resource_path:str,
#    payload:PMap=m(),
#    ids:PVector=v(),
#    ids_per_request:int=100,
#    config:Config=Config()
#) -> Iterator[addict.Dict]:
#    '''Like ``filter_all_by_id()``, but with the added convenience of yielding
#    individual records, transformed from raw JSON into ``addict.Dict`` objects,
#    for easier access to deeply nested fields.
#
#    Args:
#        resource_path: URL path to a Pure API resource, to be appended to the
#            ``Config.base_url``. Do not include a leading forward slash (``/``).
#        payload: A PMap representing JSON filters, in addition to the uuids,
#            of the collection. Default: ``pmap({})``
#        ids: The list of ids to retrieve. Default: ``[]``
#        ids_per_request: The number of records to retrieve in each request.
#          Default: 100
#        config: An instance of Config. If not provided, this function attempts
#            to automatically instantiate a Config based on environment variables
#            and default values.
#
#    Yields:
#        Individual records.
#
#    Raises:
#        common.PureAPIInvalidCollectionError: If the collection, the first
#            segment in the resource_path, is invalid for the given API version.
#        PureAPIHTTPError: If the response includes an HTTP error code, possibly
#            after multiple retries.
#        PureAPIRequestException: If the request generated some error unrelated
#            to any HTTP error status.
#        PureAPIClientException: Some unexpected exception that is none of the
#            above.
#    '''
#    # TODO: May need work for PVector compatibility
#    collection = _get_collection_from_resource_path(resource_path, config.version)
#    for r in filter_all_by_id(
#        resource_path,
#        payload=payload,
#        ids=ids,
#        ids_per_request=ids_per_request,
#        config=config
#    ):
#        for item in r.json()['items']:
#            yield response.transform(collection, item, version=config.version)
