from collections import namedtuple
from typing import ClassVar, Generic, Iterable, Iterator, Mapping, Protocol, TypedDict, TypeVar, Union

from dataclasses import dataclass, field
from dataclasses_json import config, dataclass_json, DataClassJsonMixin
from pyrsistent import freeze, thaw, m, pmap, v, pvector
from pyrsistent.typing import PMap, PVector

@dataclass
ScopusAPISearchResults(DataClassJsonMixin):

@dataclass
ScopusAPIResponse(DataClassJsonMixin):
    count:int = field(init=False)
    items:Iterable[Mapping] = field(init=False)
    search_results:

    def __post_init__(self):
        self.c = self.a + self.b
