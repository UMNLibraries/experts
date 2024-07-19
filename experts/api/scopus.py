# See https://peps.python.org/pep-0655/#usage-in-python-3-11
from __future__ import annotations
from typing_extensions import NotRequired, TypedDict
from datetime import date, datetime
from functools import partial
import os
import re
from typing import Callable, Iterable, Iterator, Mapping, Tuple
import uuid

import attrs
from attrs import Factory, field, frozen, validators

import dateutil

import httpx
import jsonpath_ng.ext as jp
from pipe import Pipe

from pyrsistent import freeze, thaw, m, pmap, v, pvector
from pyrsistent.typing import PMap, PVector

import returns
from returns.pipeline import is_successful

from experts.api import common
from experts.api.common import \
    default_max_attempts, \
    default_retryable, \
    default_next_wait_interval, \
    manage_request_attempts, \
    RequestParams, \
    ResponseBody, \
    ResponseBodyItem

from experts.helpers.jsonpath import flatten_mixed_match_values

class ResponseParser:
    @staticmethod
    def body(response:httpx.Response) -> ResponseBody:
        return response.json()

    @Pipe
    def responses_to_bodies(responses: Iterator[httpx.Response]) -> Iterator[ResponseBody]:
        for response in responses:
            yield ResponseParser.body(response)

    @Pipe
    def responses_to_headers_bodies(responses: Iterator[httpx.Response]) -> Iterator[Tuple[httpx.Headers, ResponseBody]]:
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

#class AbstractResponseBody(TypedDict):
#    ...
#    Would like to have this class, but the Scopus data we need is so deeply
#    nested, and Python's TypedDicts are so strict, that the costs outweigh
#    any documentation and type annotation benefits we would get from it.

class AbstractResponseBodyParser():
    @staticmethod
    def eid(body: ResponseBody) -> str:
        # There should always be exactly one of these:
        return jp.parse("$..coredata.eid").find(body)[0].value

    @staticmethod
    def scopus_id(body: ResponseBody) -> str:
        return re.search(r'-(\d+)$', AbstractResponseBodyParser.eid(body)).group(1)

    @staticmethod
    def date_created(body: ResponseBody) -> date:
        year, month, day = [
            jp.parse(f"$..item-info.history.date-created['@{date_part}']").find(body)[0].value
            for date_part in ['year','month','day']
        ]
        return date.fromisoformat(f'{year}-{month}-{day}')

    @staticmethod
    def refcount(body: ResponseBody) -> int:
        refcount_expr = jp.parse("$..['@refcount']")
        matches = refcount_expr.find(body)
        if matches:
            return int(matches[0].value)
        else:
            return 0

    @staticmethod
    def reference_scopus_ids(body: ResponseBody) -> list:
        return [
            itemid['$'] for itemid in filter(
                lambda itemid: itemid['@idtype'] == 'SGR',
                flatten_mixed_match_values(
                    jp.parse("$..reference[*].ref-info.refd-itemidlist.itemid").find(body)
                )
            )
        ]

    @Pipe
    def bodies_to_reference_scopus_ids(bodies: Iterator[ResponseBody]) -> Iterator[str]:
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

    def get_abstract_by_scopus_id(self, scopus_id, *args, params=m(content='core', view='FULL'), **kwargs):
        prepared_request = self.httpx_client.build_request(
            'GET',
            f'abstract/scopus_id/{scopus_id}',
            params=thaw(params),
            timeout=self.timeout # TODO: Change to default_timeout
        )
        return self.request(*args, prepared_request=prepared_request, **kwargs)

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
        scopus_ids: Iterator,
        params: RequestParams = m(content='core', view='FULL'),
    ) -> Iterator[httpx.Response]:
        partial_request = partial(
            self.get_abstract_by_scopus_id,
            params=params,
        )
        def request_by_scopus_id(scopus_id: str):
            # Pass an id-specific resource_path:
            return partial_request(scopus_id)

        for result in common.request_many_by_identifier(
            request_by_identifier_function = request_by_scopus_id,
            identifiers = scopus_ids,
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
