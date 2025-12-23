from functools import reduce

from pyrsistent import CheckedPMap, CheckedPSet, PRecord, field, pset

SetElem = str

class SetKey(CheckedPSet):
    __type__ = SetElem

class MapWithSetKeys(CheckedPMap):
    __key_type__ = SetKey
    __value_type__ = str

# Initialize with tuple:
setkey1 = SetKey(('foo','bar','baz'))
# Initialize with list:
setkey2 = SetKey(['kung','foo','yung'])

print(f'{setkey1=}')
print(f'{setkey2=}')

mwsk = MapWithSetKeys({
    setkey1: 'set key 1',
    setkey2: 'set key 2',
})
print(f'{mwsk=}')
