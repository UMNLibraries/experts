from collections import namedtuple
from types import MappingProxyType
from typing import Any, ClassVar, Generic, Iterable, Iterator, Mapping, Protocol, TypedDict, TypeVar, Union

from attrs import define, frozen
from pyrsistent import freeze, thaw, m, pmap, v, pvector
from pyrsistent.typing import PMap, PVector

class RequestPageParams(Protocol):
    # Use of a pyrsistent.pmap will satisfy this:
    def set(self, key:str, value:Any):
        ...

# Even with PMap in the TypeVar's bound=Union[...] below, mypy throws this error, unless we include RequestPageParams above:
# "ScopusRequestPageParams" has no attribute "set"  [attr-defined]
#class ScopusRequestPageParams(Protocol):
class ScopusRequestPageParams(RequestPageParams, Protocol):
    start: int
    count: int

# Even with PMap in the TypeVar's bound=Union[...] below, mypy throws this error, unless we include RequestPageParams above:
# "PureRequestPageParams" has no attribute "set"  [attr-defined]
#class PureRequestPageParams(Protocol):
class PureRequestPageParams(RequestPageParams, Protocol):
    offset: int
    size: int

# Without PMap in the bound=Union[...], mypy throws this error:
# Value of type variable "RequestPageParams_contra" of "parse_params" cannot be "PMap[str, object]"  [type-var]
#RequestPageParams_co = TypeVar('RequestPageParams_co', bound=Union[PureRequestPageParams, ScopusRequestPageParams], covariant=True)
#RequestPageParams_contra = TypeVar('RequestPageParams_contra', bound=Union[PureRequestPageParams, ScopusRequestPageParams], contravariant=True)
RequestPageParams_co = TypeVar('RequestPageParams_co', bound=Union[PureRequestPageParams, ScopusRequestPageParams, PMap], covariant=True)
RequestPageParams_contra = TypeVar('RequestPageParams_contra', bound=Union[PureRequestPageParams, ScopusRequestPageParams, PMap], contravariant=True)

#class RequestPageParamsParser(Protocol, Generic[RequestPageParams_contra]):
#class RequestPageParamsParser(Protocol, Generic[RequestPageParams_co, RequestPageParams_contra]):
class RequestPageParamsParser(Protocol):
    @staticmethod
    #def size(params:RequestPageParams_contra) -> int:
    def size(params:PMap) -> int:
        ...

    @staticmethod
    #def offset(params:RequestPageParams_contra) -> int:
    def offset(params:PMap) -> int:
        ...

    @staticmethod
    #def update_offset(params:RequestPageParams_contra) -> RequestPageParams_contra:
    #def update_offset(params:RequestPageParams_contra, new_offset:int) -> RequestPageParams_co:
    def update_offset(params:PMap, new_offset:int) -> PMap:
        ...

class PureRequestPageParamsParser:
    @staticmethod
    #def size(params:PureRequestPageParams) -> int:
    def size(params:PMap) -> int:
        return params.size
    
    @staticmethod
    #def offset(params:PureRequestPageParams) -> int:
    def offset(params:PMap) -> int:
        return params.offset
    
    @staticmethod
    #def update_offset(params:PureRequestPageParams, new_offset:int) -> PureRequestPageParams:
    def update_offset(params:PMap, new_offset:int) -> PMap:
        # This returns a new PMap:
        return params.set('offset', new_offset)
    
class ScopusRequestPageParamsParser:
    @staticmethod
    #def size(params:ScopusRequestPageParams) -> int:
    def size(params:PMap) -> int:
        return params.count
    
    @staticmethod
    #def offset(params:ScopusRequestPageParams) -> int:
    def offset(params:PMap) -> int:
        return params.start

    @staticmethod
    #def update_offset(params:ScopusRequestPageParams, new_offset:int) -> ScopusRequestPageParams:
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
# Without contravariant=True, we get this mypy error:
# Invariant type variable "ResponsePage_contra" used in protocol where contravariant one is expected
#ResponsePage_contra = TypeVar('ResponsePage_contra', PureResponsePage, ScopusResponsePage)

class ResponsePageParser(Protocol, Generic[ResponsePage_contra]):
# Without Generic[ResponsePage_contra], we get mypy errors like this:
# Argument 1 to "parse_response" has incompatible type "type[ScopusResponsePageParser]"; expected "ResponsePageParser"
#class ResponsePageParser(Protocol):
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

#def parse_params(parser:RequestPageParamsParser, params:RequestPageParams_contra):
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
# The following causes this error:
# Value of type variable "RequestPageParams_contra" of "parse_params" cannot be "PMap[str, object]"
sparams = pmap({'count': 10, 'start': 0, 'sort': 'pubyear', 'foo': ['bar','baz']})
#sparams = pmap({'count': 10, 'start': 0, 'foo': 100})
#sparams = pmap({'count': 10, 'start': 0})
parse_params(ScopusRequestPageParamsParser, sparams)

print('\nPure params:')
pparams = pmap({'size': 100, 'offset': 3, 'kung': 'foo'})
# This passes type-checking, even though it's missing the required size key!
#pparams = pmap({'offset': 3, 'kung': 'foo'})
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
#sresponse:ScopusResponsePage = pmap({
#sresponse:ScopusResponsePage = MappingProxyType({
#sresponse:Mapping = {
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
#)
print(sresponse)
parse_response(ScopusResponsePageParser, sresponse)

print('\nPure response:')
#presponse:PureResponsePage = pmap({
#presponse:PureResponsePage = MappingProxyType({
#presponse:Mapping = {
presponse:PureResponsePage = {
    'count': 3,
    'pageInformation': {},
    'navigationLinks': [],
    'items': [
        {'foo': 'bar'},
        {'baz': 'luhrmann'},
    ],
}
#)
print(presponse)
parse_response(PureResponsePageParser, presponse)
