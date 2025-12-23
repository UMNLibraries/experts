from collections import namedtuple
from types import MappingProxyType
from typing import Any, ClassVar, Generic, Iterable, Iterator, Mapping, Protocol, TypedDict, TypeVar, Union

from attrs import define, frozen
#from pyrsistent import freeze, thaw, m, pmap, v, pvector
import pyrsistent
from pyrsistent.typing import PMap, PVector

class ValidatedPMap(pyrsistent.PMap):
    def __init__(self, *args, **kwargs):
        print('in ValidatedPMap.__init__')
        print(f'{self=}')
        print(f'{args=}')
        print(f'{kwargs=}')
        super().__init__()

def _turbo_mapping(initial, pre_size):
    if pre_size:
        size = pre_size
    else:
        try:
            size = 2 * len(initial) or 8
        except Exception:
            # Guess we can't figure out the length. Give up on length hinting,
            # we can always reallocate later.
            size = 8

    buckets = size * [None]

    if not isinstance(initial, Mapping):
        # Make a dictionary of the initial data if it isn't already,
        # that will save us some job further down since we can assume no
        # key collisions
        initial = dict(initial)

    for k, v in initial.items():
        h = hash(k)
        index = h % size
        bucket = buckets[index]

        if bucket:
            bucket.append((k, v))
        else:
            buckets[index] = [(k, v)]

    return ValidatedPMap(len(initial), pyrsistent.pvector().extend(buckets))

#_EMPTY_PMAP = _turbo_mapping({}, 0)

def pmap(initial={}, pre_size=0):
    """
    Create new persistent map, inserts all elements in initial into the newly created map.
    The optional argument pre_size may be used to specify an initial size of the underlying bucket vector. This
    may have a positive performance impact in the cases where you know beforehand that a large number of elements
    will be inserted into the map eventually since it will reduce the number of reallocations required.

    >>> pmap({'a': 13, 'b': 14}) == {'a': 13, 'b': 14}
    True
    """
    if not initial and pre_size == 0:
        #return _EMPTY_PMAP
        return _turbo_mapping({}, 0)

    return _turbo_mapping(initial, pre_size)


def m(**kwargs):
    """
    Creates a new persistent map. Inserts all key value arguments into the newly created map.

    >>> m(a=13, b=14) == {'a': 13, 'b': 14}
    True
    """
    return pmap(kwargs)

class IntSet(pyrsistent.CheckedPSet):
    __type__ = int

int_set = IntSet([1,2,'a'])

#m1 = ValidatedPMap({'a': 1, 'b': 2})
#m1 = ValidatedPMap.pmap({'a': 1, 'b': 2})
m1 = pmap({'a': 1, 'b': 2})
print(m1)
print(type(m1))
if isinstance(m1, pyrsistent.PMap):
    print('m1 is an instance of pyrsistent.PMap')
m2 = m1.set('a', 3)
print(type(m2))
