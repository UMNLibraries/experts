from collections import namedtuple
from types import MappingProxyType
from typing import Any, ClassVar, Generic, Iterable, Iterator, Mapping, Protocol, TypedDict, TypeVar, Union

from attrs import define, frozen
from pyrsistent import freeze, thaw, m, pmap, v, pvector
from pyrsistent.typing import PMap, PVector

class RequestPageParamsParser(Protocol):
    @staticmethod
    def size(params:PMap) -> int:
        ...

    @staticmethod
    def offset(params:PMap) -> int:
        ...

    @staticmethod
    def update_offset(params:PMap, new_offset:int) -> PMap:
        ...

class PureRequestPageParamsParser:
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
    
class ScopusRequestPageParamsParser:
    @staticmethod
    def size(params:PMap) -> int:
        return params.count
    
    @staticmethod
    def offset(params:PMap) -> int:
        return params.start

    @staticmethod
    def update_offset(params:PMap, new_offset:int) -> PMap:
        # This returns a new PMap:
        return params.set('start', new_offset)
    
# WSDataSetListResult in the Pure Web Services Swagger JSON schema
class PureResponsePage(TypedDict):
    count: int
    pageInformation: Mapping
    navigationLinks: Iterable
    items: Iterable[Mapping]

ScopusSearchResults = TypedDict(
    'ScopusSearchResults', {
        # Values for the next three keys are ints represented as strs:
        'opensearch:totalResults': str,
        'opensearch:startIndex': str,
        'opensearch:itemsPerPage': str,
        'opensearch:Query': Mapping,
        'link': Iterable,
        'entry': Iterable[Mapping],
    }
)
ScopusResponsePage = TypedDict('ScopusResponsePage', {'search-results': ScopusSearchResults})

ResponsePage_contra = TypeVar('ResponsePage_contra', PureResponsePage, ScopusResponsePage, contravariant=True)

class ResponsePageParser(Protocol, Generic[ResponsePage_contra]):
    @staticmethod
    def count(response:ResponsePage_contra) -> int:
        ...

    @staticmethod
    def items(response:ResponsePage_contra) -> Iterator[Mapping]:
        ...

class PureResponsePageParser:
    @staticmethod
    def count(response:PureResponsePage) -> int:
        return response['count']
    
    @staticmethod
    def items(response:PureResponsePage) -> Iterator[Mapping]:
        for item in response['items']:
            yield item

class ScopusResponsePageParser:
    @staticmethod
    def count(response:ScopusResponsePage) -> int:
        return int(response['search-results']['opensearch:totalResults'])
    
    @staticmethod
    def items(response:ScopusResponsePage) -> Iterator[Mapping]:
        for item in response['search-results']['entry']:
            yield item

def parse_params(parser:RequestPageParamsParser, params:PMap):
    size_fn = parser.size
    size = size_fn(params)
    print(f'{size=}')

    offset_fn = parser.offset
    offset = offset_fn(params)
    print(f'{offset=}')

    update_offset_fn = parser.update_offset
    #updated_params = update_offset_fn(params, 17)
    updated_params = parser.update_offset(params, 17)
    print('after updating offset:')
    print(f'{params=}')
    print(f'{updated_params=}')

print('Scopus params:')
sparams = pmap({'count': 10, 'start': 0, 'sort': 'pubyear', 'foo': ['bar','baz']})
parse_params(ScopusRequestPageParamsParser, sparams)

print('\nPure params:')
pparams = pmap({'size': 100, 'offset': 3, 'kung': 'foo'})
parse_params(PureRequestPageParamsParser, pparams)

def parse_response(parser:ResponsePageParser, response:ResponsePage_contra):
    #count = parser.count(response)
    count_fn = parser.count
    count = count_fn(response)
    print(f'{count=}')

    #for item in parser.items(response):
    items_fn = parser.items
    for item in items_fn(response):
        print(f'{item=}')

print('\nScopus response:')
sresponse:ScopusResponsePage = {
  'search-results': {
    'opensearch:totalResults': '8767488',
    'opensearch:startIndex': '0',
    'opensearch:itemsPerPage': '10',
    'opensearch:Query': {},
    'link': [],
    'entry': [
        {'kung': 'fu'},
        {'foo': 'manchu'},
    ],
  },
}
print(sresponse)
parse_response(ScopusResponsePageParser, sresponse)

print('\nPure response:')
presponse:PureResponsePage = {
    'count': 3,
    'pageInformation': {},
    'navigationLinks': [],
    'items': [
        {'foo': 'bar'},
        {'baz': 'luhrmann'},
    ],
}
print(presponse)
parse_response(PureResponsePageParser, presponse)
