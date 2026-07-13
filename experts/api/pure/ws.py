# See https://peps.python.org/pep-0655/#usage-in-python-3-11
from __future__ import annotations
from typing_extensions import NotRequired, TypedDict

from functools import partial

import os
from typing import Callable, Iterable, Iterator, Mapping, Tuple

import uuid

import attrs
from attrs import Factory, field, frozen, validators

import httpx

from pipe import Pipe

from pyrsistent import freeze, thaw, m, pmap, v, pvector
from pyrsistent.typing import PMap, PVector

from experts.api import common
from experts.api.common import \
    default_max_attempts, \
    default_retryable, \
    default_next_wait_interval, \
    manage_request_attempts, \
    ResponseBody, \
    ResponseBodyItem

class ResponseBodyParser:
    @staticmethod
    # TODO: Create a better type!
    def items(body:ResponseBody) -> list[ResponseBodyItem]:
        """Extracts the top-level items list from a response body.

        Args:
            body: Parsed Pure WS response body mapping.

        Returns:
            The items list when present; otherwise an empty list.
        """
        return body['items'] if 'items' in body else []

    @Pipe
    def bodies_to_items(bodies: Iterator[ResponseBody]) -> Iterator[ResponseBodyItem]:
        """Flattens a stream of response bodies into item records.

        Args:
            bodies: Parsed response bodies.

        Yields:
            Individual items from each body.
        """
        for body in bodies:
            for item in ResponseBodyParser.items(body):
                yield item

class ResponseParser:
    @staticmethod
    def body(response:httpx.Response) -> ResponseBody:
        """Parses an HTTP response body as JSON.

        Args:
            response: HTTP response from Pure WS.

        Returns:
            Parsed response body mapping.
        """
        return response.json()

    @staticmethod
    def items(response:httpx.Response) -> list[ResponseBodyItem]:
        """Extracts item records from an HTTP response.

        Args:
            response: HTTP response from Pure WS.

        Returns:
            Item records contained in the parsed response body.
        """
        return ResponseBodyParser.items(
            ResponseParser.body(response)
        )

    @Pipe
    def responses_to_bodies(responses: Iterator[httpx.Response]) -> Iterator[ResponseBody]:
        """Converts a stream of HTTP responses into parsed bodies.

        Args:
            responses: HTTP responses to parse.

        Yields:
            Parsed response body mappings.
        """
        for response in responses:
            yield ResponseParser.body(response)

    @Pipe
    def responses_to_items(responses: Iterator[httpx.Response]) -> Iterator[ResponseBodyItem]:
        """Converts a stream of HTTP responses into individual items.

        Args:
            responses: HTTP responses to parse.

        Yields:
            Individual item records from each response body.
        """
        for item in responses | ResponseParser.responses_to_bodies | ResponseBodyParser.bodies_to_items:
            yield item

OffsetRequestParams = PMap

class PageInformation(TypedDict):
    size: int
    offset: int

# WSDataSetListResult in the Pure Web Services Swagger JSON schema
class OffsetResponseBody(TypedDict):
    count: int
    pageInformation: PageInformation
    navigationLinks: Iterable[Mapping]
    items: NotRequired[Iterable[Mapping]]

class OffsetResponseBodyParser(ResponseBodyParser):
    @staticmethod
    def total_items(body:OffsetResponseBody) -> int:
        """Extracts total available items for offset pagination.

        Args:
            body: Parsed offset-paginated response body.

        Returns:
            Total count of available items.
        """
        return body['count']

    @staticmethod
    def items_per_page(body:OffsetResponseBody) -> int:
        """Extracts page size for offset pagination.

        Args:
            body: Parsed offset-paginated response body.

        Returns:
            Number of items returned per page.
        """
        return int(body['pageInformation']['size'])

    @staticmethod
    def offset(body:OffsetResponseBody) -> int:
        """Extracts current offset for offset pagination.

        Args:
            body: Parsed offset-paginated response body.

        Returns:
            Current offset value.
        """
        return int(body['pageInformation']['offset'])

class OffsetResponseParser(ResponseParser):
    @staticmethod
    def total_items(response:httpx.Response) -> int:
        """Extracts total available items from an offset response."""
        return OffsetResponseBodyParser.total_items(
            ResponseParser.body(response)
        )

    @staticmethod
    def items_per_page(response:httpx.Response) -> int:
        """Extracts page size from an offset response."""
        return OffsetResponseBodyParser.items_per_page(
            ResponseParser.body(response)
        )

    @staticmethod
    def offset(response:httpx.Response) -> int:
        """Extracts current offset from an offset response."""
        return OffsetResponseBodyParser.offset(
            ResponseParser.body(response)
        )

# WSChangeListResult in the Pure Web Services Swagger JSON schema
class TokenResponseBody(TypedDict):
    count: int
    resumptionToken: str
    moreChanges: bool
    navigationLinks: Iterable[Mapping]
    items: NotRequired[Iterable[Mapping]]

class TokenResponseBodyParser(ResponseBodyParser):
    @staticmethod
    def items_per_page(body:TokenResponseBody) -> int:
        """Extracts item count for a token-page response body.

        Args:
            body: Parsed token-paginated response body.

        Returns:
            Number of items represented in the response.
        """
        return int(body['count'])

    @staticmethod
    def more_items(body:TokenResponseBody) -> bool:
        """Indicates whether additional token pages are available.

        Args:
            body: Parsed token-paginated response body.

        Returns:
            True when more pages are available.
        """
        return body['moreChanges']

    @staticmethod
    def token(body:TokenResponseBody) -> int:
        """Extracts the resumption token from a token-page response body.

        Args:
            body: Parsed token-paginated response body.

        Returns:
            The resumption token for the next request.
        """
        return body['resumptionToken']

class TokenResponseParser(ResponseParser):
    @staticmethod
    def items_per_page(response:httpx.Response) -> int:
        """Extracts item count from a token-based response."""
        return TokenResponseBodyParser.items_per_page(
            ResponseParser.body(response)
        )

    @staticmethod
    def more_items(response:httpx.Response) -> bool:
        """Indicates whether additional token-based pages are available."""
        return TokenResponseBodyParser.more_items(
            ResponseParser.body(response)
        )

    @staticmethod
    def token(response:httpx.Response) -> int:
        """Extracts the next resumption token from a token response."""
        return TokenResponseBodyParser.token(
            ResponseParser.body(response)
        )

@frozen(kw_only=True)
class Client:
    '''Common client configuration and behavior. Used by most functions.

    Most attributes have defaults and are not required. Only ``domain`` and
    ``key`` are required, and both can be set with environment variables as
    well as constructor parameters.

    Context instances are immutable. To use different configurations for different
    function calls, pass different Context objects.

    E
    '''

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

    def __attrs_post_init__(self) -> None:
        """Initializes the underlying httpx client with Pure WS settings."""
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
        """Issues a GET request against a Pure WS resource path.

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

    def post(self, resource_path, *args, params=m(), **kwargs):
        """Issues a POST request against a Pure WS resource path.

        Args:
            resource_path: Relative API path.
            params: JSON payload as an immutable map.

        Returns:
            A request result containing either a response or an exception.
        """
        prepared_request = self.httpx_client.build_request(
            'POST',
            resource_path,
            json=thaw(params),
            timeout=self.timeout
        )
        return self.request(*args, prepared_request=prepared_request, **kwargs)
    
    def request_many_by_offset(
        self,
        request_function: RequestFunction,
        resource_path: str,
        params: OffsetRequestParams = m(),
        first_offset: int = 0,
    ) -> Iterator[httpx.Response]:
        """Requests many pages for an offset-based endpoint.

        Args:
            request_function: Bound request method used to make calls.
            resource_path: Relative API path for the target endpoint.
            params: Base request parameters.
            first_offset: Initial offset.

        Returns:
            An iterator of successful paged responses.
        """
        partial_request = partial(
            request_function,
            resource_path,
        )
        def request_by_offset(offset: int):
            return partial_request(
                params=params.set('offset', offset)
            )

        return common.request_many_by_offset(
            request_by_offset_function = request_by_offset,
            response_parser = OffsetResponseParser,
            first_offset = first_offset
        )

    def request_many_by_token(
        self,
        request_function: RequestFunction,
        resource_path: str,
        token: str,
        params: RequestParams = m(),
    ) -> Iterator[httpx.Response]:
        """Requests many pages for a token-based endpoint.

        Args:
            request_function: Bound request method used to make calls.
            resource_path: Relative API path for the target endpoint.
            token: Initial resumption token.
            params: Base request parameters.

        Returns:
            An iterator of successful paged responses.
        """
        partial_request = partial(
            request_function,
            params=params,
        )
        def request_by_token(token: str):
            return partial_request(
                resource_path = resource_path + '/' + token
            )

        return common.request_many_by_token(
            request_by_token_function = request_by_token,
            response_parser = TokenResponseParser,
            token = token,
        )
    
