from collections import namedtuple
from typing import ClassVar, Generic, Iterable, Iterator, Mapping, Protocol, TypedDict, TypeVar, Union

from attrs import define, frozen
from pyrsistent import freeze, thaw, m, pmap, v, pvector
from pyrsistent.typing import PMap, PVector

#class PureAPIResponse(Protocol):
# Called WSDataSetListResult in the Pure web services Swagger JSON schema
class PureAPIResponse(TypedDict):
    count: int
    pageInformation: Mapping
    navigationLinks: Iterable
    items: Iterable[Mapping]

ScopusAPISearchResults = TypedDict(
    'ScopusAPISearchResults', {
        # Values for the next three keys are ints represented as strs:
        'opensearch:totalResults': str,
        'opensearch:startIndex': str,
        'opensearch:itemsPerPage': str,
        'opensearch:Query': Mapping,
        'link': Iterable,
        'entry': Iterable[Mapping],
    }
)
ScopusAPIResponse = TypedDict('ScopusAPIResponse', {'search-results': ScopusAPISearchResults})

# Python TypeVars are invariant by default, but types used as function args/params must be contravariant.
# For details, see this answer (https://doc.pure.elsevier.com/pages/viewpage.action?pageId=167445970) to the
# Stack Overflow question, "How to use TypeVar for input and output of multiple generic Protocols in python?"
APIResponse_contra = TypeVar('APIResponse_contra', PureAPIResponse, ScopusAPIResponse, contravariant=True)

# These didn't work:
#APIResponse_co = TypeVar('APIResponse_co', PureAPIResponse, ScopusAPIResponse, covariant=True)
#APIResponse = TypeVar('APIResponse', PureAPIResponse, ScopusAPIResponse)
#APIResponse = Union[PureAPIResponse, ScopusAPIResponse]

# Turns out we don't need to define things this way to make a collection
# of functions that can be called without a class/self argument, i.e. functions
# that can be passed as callbacks. See the uncommented ResponseParser below.
#class ResponseCountParser(Protocol):
#    def __call__(self, response:APIResponse) -> int:
#        ...
#
#class ResponseItemsParser(Protocol):
#    def __call__(self, response:APIResponse) -> Iterator[Mapping]:
#        ...
#class ResponseParser(Protocol):
#    count:ResponseCountParser
#    items:ResponseItemsParser
#
#def pureapi_count(response:PureAPIResponse) -> int:
#    return response['count']
#
#def pureapi_items(response:PureAPIResponse) -> Iterator[Mapping]:
#    for item in response['items']:
#        yield item
#
#class PureAPIResponseParser:
#    count:ClassVar[ResponseCountParser] = pureapi_count
#    items:ClassVar[ResponseItemsParser] = pureapi_items
#    count:ResponseCountParser
#    items:ResponseItemsParser
#    count:ResponseCountParser = pureapi_count
#    items:ResponseItemsParser = pureapi_items
#    #count = pureapi_count
#    #items = pureapi_items
#
#def scopusapi_count(response:ScopusAPIResponse) -> int:
#    return int(response['search-results']['opensearch:totalResults'])
#
#def scopusapi_items(response:ScopusAPIResponse) -> Iterator[Mapping]:
#    for item in response['search-results']['entry']:
#        yield item
#
#class ScopusAPIResponseParser:
#    count:ResponseCountParser = scopusapi_count
#    items:ResponseItemsParser = scopusapi_items
#    #count = scopusapi_count
#    #items = scopusapi_items


# Doesn't work without the Generic type spec:
#class ResponseParser(Protocol):
# For more on why the Generic is necessary, see the Stack Overflow
# answer above.
class ResponseParser(Protocol, Generic[APIResponse_contra]):
    @staticmethod
    def count(response:APIResponse_contra) -> int:
    # These didn't work:
    #def count(response:APIResponse_co) -> int:
    #def count(response:APIResponse) -> int:
    #def count(response:Mapping) -> int:
        ...

    @staticmethod
    def items(response:APIResponse_contra) -> Iterator[Mapping]:
    # These didn't work:
    #def items(response:APIResponse_co) -> Iterator[Mapping]:
    #def items(response:APIResponse) -> Iterator[Mapping]:
    #def items(response:Mapping) -> Iterator[Mapping]:
        ...

# This didn't work:
#def response_parser(count:ResponseCountParser, items:ResponseItemsParser):
#    NTResponseParser = namedtuple('NTResponseParser', ['count','items'])
#    return NTResponseParser(count=count, items=items)
#sparser = response_parser(count=scopusapi_count, items=scopusapi_items)

# Don't need @frozen or @define from attrs, because these classes contain
# only static methods:
#@frozen
#@define
class PureAPIResponseParser:
    @staticmethod
    #def count(response:PureAPIResponse) -> int: # type: ignore[override] <- This didn't eliminate mypy errors
    def count(response:PureAPIResponse) -> int:
        return response['count']
    
    @staticmethod
    #def items(response:PureAPIResponse) -> Iterator[Mapping]: # type: ignore[override] <- This didn't eliminate mypy errors
    def items(response:PureAPIResponse) -> Iterator[Mapping]:
        for item in response['items']:
            yield item

# Don't need @frozen or @define from attrs, because these classes contain
# only static methods:
#@frozen
#@define
class ScopusAPIResponseParser:
#    count:ResponseCountParser = scopusapi_count
#    items:ResponseItemsParser = scopusapi_items
    #count = scopusapi_count
    #items = scopusapi_items

    @staticmethod
    def count(response:ScopusAPIResponse) -> int:
        return int(response['search-results']['opensearch:totalResults'])
    
    @staticmethod
    def items(response:ScopusAPIResponse) -> Iterator[Mapping]:
        for item in response['search-results']['entry']:
            yield item

#sparser:ResponseParser = ScopusAPIResponseParser()
sparser = ScopusAPIResponseParser()
#sparser = ScopusAPIResponseParser(count=scopusapi_count, items=scopusapi_items)
sresponse:ScopusAPIResponse = {
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

# Works to declare pparser as being of type (protocol) ResponseParser
pparser:ResponseParser = PureAPIResponseParser()
#pparser = PureAPIResponseParser()
#pparser = PureAPIResponseParser(count=pureapi_count, items=pureapi_items)
presponse:PureAPIResponse = {
    'count': 3,
    'pageInformation': {},
    'navigationLinks': [],
    'items': [
        {'foo': 'bar'},
        {'baz': 'luhrmann'},
    ],
}

def parse_response(parser:ResponseParser, response:APIResponse_contra):
    #count = parser.count(response)
    count_fn = parser.count
    count = count_fn(response)
    print(f'{count=}')

    #for item in parser.items(response):
    items_fn = parser.items
    for item in items_fn(response):
        print(f'{item=}')

#parse_response(sparser, sresponse)
#parse_response(pparser, presponse)
parse_response(ScopusAPIResponseParser, sresponse)
parse_response(PureAPIResponseParser, presponse)
