from collections import namedtuple
from types import MappingProxyType
from typing import Any, ClassVar, Generic, Iterable, Iterator, Mapping, Protocol, TypedDict, TypeVar, Union

from attrs import define, frozen
#from pyrsistent import freeze, thaw, m, pmap, v, pvector
import pyrsistent
from pyrsistent import PRecord, field
from pyrsistent.typing import PMap, PVector

class ARecord(PRecord):
    x = field()

r = ARecord(x=3)
print(f"{r['x']=}")

for k, v in r.items():
    print(f'{k=}, {v=}')
