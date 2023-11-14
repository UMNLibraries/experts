import os
from typing import Callable, Iterable, Iterator, List, Mapping, Tuple, TypedDict 

import attrs
from attrs import Factory, field, frozen, validators

import httpx

from pyrsistent import freeze, thaw, m, pmap, v, pvector
from pyrsistent.typing import PMap, PVector

from experts.api.context import default_retryable, default_next_wait_interval

OffsetRequestParams = PMap

class OffsetRequestParamsParser:
    @staticmethod
    def items_per_page(params:OffsetRequestParams) -> int:
        return params.count
    
    @staticmethod
    def offset(params:OffsetRequestParams) -> int:
        return params.start

    @staticmethod
    def update_offset(params:OffsetRequestParams, new_offset:int) -> OffsetRequestParams:
        return params.set('start', new_offset)
    
SearchResults = TypedDict(
    'SearchResults', {
        # Values for the next three keys are ints represented as strs:
        'opensearch:totalResults': str,
        'opensearch:startIndex': str,
        'opensearch:itemsPerPage': str,
        'opensearch:Query': Mapping,
        'link': Iterable,
        'entry': Iterable[Mapping],
    }
)
OffsetResponse = TypedDict('OffsetResponse', {'search-results': SearchResults})

class OffsetResponseParser:
    @staticmethod
    def total_items(response:OffsetResponse) -> int:
        return int(response['search-results']['opensearch:totalResults'])
    
    @staticmethod
    def items(response:OffsetResponse) -> Iterator[Mapping]:
        for item in response['search-results']['entry']:
            yield item

@frozen(kw_only=True)
class Context:
    '''Common client configuration and behavior. Used by most functions.

    Most attributes have defaults and are not required. Only ``domain`` and
    ``key`` are required, and both can be set with environment variables as
    well as constructor parameters.

    Context instances are immutable. To use different configurations for different
    function calls, pass different Context objects.

    Examples:
    '''

    httpx_client: httpx.Client = field(init=False)
    '''An httpx.Client object. Default: ``httpx.Client()``.'''

    timeout: Tuple[int, int] = (3, 60)
    '''A (connect timeout, read timeout) tuple. Required. Default: ``(3, 60)``.'''

    max_attempts: int = 10
    '''An integet maximum number of times to retry a request. Required. Default: ``10``.'''

    retryable: Callable = Factory(default_retryable)
    '''A function that takes a returns.Result and returns a boolean. Required. Default: Return value of ``default_retryable``.'''

    next_wait_interval: Callable = default_next_wait_interval
    '''A function that takes an integer number of seconds to wait and returns a new interval. Required. Default: Return value of ``default_next_wait_interval``.'''

    domain: str = field(
        default=os.environ.get('PURE_WS_DOMAIN'),
        validator=validators.instance_of(str)
    )
    '''Domain of a Pure Web Services API server. Required. Default: environment variable PURE_WS_DOMAIN'''

    base_path: str = field(
        default='ws/api',
        validator=validators.instance_of(str)
    )
    '''Base path of the Pure Web Services API URL entry point, without the version number segment.'''

    version: str = '524'
    '''Pure Web Services version, without the decimal point. For example, ``524`` for version 5.24.
    The final and only valid version is now 5.24.'''

    key: str = field(
        default=os.environ.get('PURE_WS_KEY'),
        validator=validators.instance_of(str)
    )
    '''Pure Web Services API key. Required. Default: environment variable PURE_WS_KEY'''

    headers: PMap = pmap({
        'Accept': 'application/json',
        'Accept-Charset': 'utf-8',
    })
    '''HTTP headers to be sent on every request. The constructor automatically adds
    an ``api-key`` header, using the value of the ``key`` attribute.'''

    records_per_request: int = 1000
    '''An integer number of records to return for each request of many records.'''

    offset_request_params_parser = OffsetRequestParamsParser

    offset_response_parser = OffsetResponseParser

    base_url: str = field(init=False)
    '''Pure Web Services API entrypoint URL. Should not be included in constructor
    parameters. The constructor generates this automatically based on
    other attributes.'''

    def __attrs_post_init__(self) -> None:
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
