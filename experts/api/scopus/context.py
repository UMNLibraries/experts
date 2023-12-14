# See https://peps.python.org/pep-0655/#usage-in-python-3-11
from __future__ import annotations
from typing_extensions import NotRequired, TypedDict

import os

from typing import Callable, Iterable, Iterator, List, Mapping, Tuple

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
        return params.get('count')
    
    @staticmethod
    def offset(params:OffsetRequestParams) -> int:
        return params.get('start')

    @staticmethod
    def update_offset(params:OffsetRequestParams, new_offset:int) -> OffsetRequestParams:
        return params.set('start', new_offset)
    
OffsetSearchResults = TypedDict(
    'SearchResults', {
        # Values for the next three keys are ints represented as strs:
        'opensearch:totalResults': str,
        'opensearch:startIndex': str,
        'opensearch:itemsPerPage': str,
        'opensearch:Query': Mapping,
        'link': Iterable,
        'entry': NotRequired[Iterable[Mapping]],
    }
)
OffsetResponse = TypedDict('OffsetResponse', {'search-results': OffsetSearchResults})

class OffsetResponseParser:
    @staticmethod
    def total_items(response:OffsetResponse) -> int:
        return int(response['search-results']['opensearch:totalResults'])
    
    @staticmethod
    def items_per_page(response:OffsetResponse) -> int:
        return int(response['search-results']['opensearch:itemsPerPage'])

    @staticmethod
    def offset(response:OffsetResponse) -> int:
        return int(response['search-results']['opensearch:startIndex'])

    @staticmethod
    def items(response:OffsetResponse) -> Iterator[Mapping]:
        return [] if 'entry' not in response['search-results'] else response['search-results']['entry']

TokenCursor = TypedDict(
    'TokenCursor', {
        '@current': str,
        '@next': str,
    }
)

TokenSearchResults = TypedDict(
    'TokenSearchResults', {
        # Values for the next two keys are ints represented as strs:
        'opensearch:totalResults': str,
        'opensearch:itemsPerPage': str,
        'opensearch:Query': Mapping,
        'cursor': TokenCursor,
        'link': Iterable,
        'entry': NotRequired[Iterable[Mapping]],
    }
)
TokenResponse = TypedDict('TokenResponse', {'search-results': TokenSearchResults})

class TokenResponseParser:
    @staticmethod
    def more_items(response:TokenResponse) -> bool:
        # We know for sure there are no more items when the '@current' and '@next' tokens are equal
        # (and there is no 'entry' element in 'search-results').
        return (response['search-results']['cursor']['@next'] != response['search-results']['cursor']['@current'])

    @staticmethod
    def items_per_page(response:TokenResponse) -> int:
        return int(response['search-results']['opensearch:itemsPerPage'])

    @staticmethod
    def total_items(response:TokenResponse) -> int:
        return int(response['search-results']['opensearch:totalResults'])

    @staticmethod
    def token(response:TokenResponse) -> int:
        return response['search-results']['cursor']['@next']

    @staticmethod
    def items(response:TokenResponse) -> list[Mapping]:
        return [] if 'entry' not in response['search-results'] else response['search-results']['entry']

def update_token(token: str, resource_path: str, params: PMap):
    return resource_path, params.set('cursor', token)

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

    timeout: httpx.Timeout = httpx.Timeout(10.0, connect=3.0, read=60.0)
    '''httpx client timeouts. Default: ``httpx.Timeout(10.0, connect=3.0, read=60.0)``.'''

    max_attempts: int = 10
    '''An integet maximum number of times to retry a request. Required. Default: ``10``.'''

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

    #version: str = '524'
    '''Pure Web Services version, without the decimal point. For example, ``524`` for version 5.24.
    The final and only valid version is now 5.24.'''

    affiliation_id: str = field(
        default=os.environ.get('SCOPUS_API_AFFILIATION_ID'),
        validator=validators.instance_of(str)
    )
    '''Scopus affiliation ID for our organization. Required. Default: environment variable SCOPUS_API_AFFILIATION_ID'''

    key: str = field(
        default=os.environ.get('SCOPUS_API_KEY'),
        validator=validators.instance_of(str)
    )
    '''Scopus API key. Required. Default: environment variable SCOPUS_API_KEY'''

    headers: PMap = pmap({
        'Accept': 'application/json',
        'Accept-Charset': 'utf-8',
    })
    '''HTTP headers to be sent on every request. The constructor automatically adds
    an ``api-key`` header, using the value of the ``key`` attribute.'''

    records_per_request: int = 200
    '''An integer number of records to return for each request of many records.'''

    offset_request_params_parser = OffsetRequestParamsParser

    offset_response_parser = OffsetResponseParser
    token_response_parser = TokenResponseParser

    update_token: Callable = update_token

    def __attrs_post_init__(self) -> None:
        object.__setattr__(
            self,
            'httpx_client',
            httpx.Client(
                base_url=f'https://{self.domain}/{self.base_path}/',
                headers={
                    **thaw(self.headers),
                    'X-ELS-APIKey': self.key,
                }
            )
        )
