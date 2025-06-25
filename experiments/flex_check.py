from collections import abc

from _pvarrecord import PVarRecord
from pyrsistent import field, PMap

class PVFooInt(PVarRecord):
    foo = field(type=int, mandatory=True)

class PVBaz(PVarRecord):
    baz = field(type=str, mandatory=True)

#good_pvfoo = PVFooInt(foo=1, bar='baz')
#good_pvfoo = PVFooInt(**{'foo': 1, 'bar': {'baz': 'bam'}})
good_pvfoo = PVFooInt(**{'foo': 1, 'bar': PVBaz(baz='bam')})
print(f'{good_pvfoo=}')
print(f'{good_pvfoo.bar=}')
print(f'{good_pvfoo.bar["baz"]=}')
print(f'{good_pvfoo.bar.baz=}')
print(dir(good_pvfoo))
print(type(good_pvfoo))
for typ in (PVarRecord, PMap, abc.Mapping):
    assert isinstance(good_pvfoo, typ), f'good_pvfoo is not in instance of {typ}'

for k, v in good_pvfoo.items():
    print(f'{k=}, {v=}')

# Works!
#bad_pvfoo = PVFooInt(**{'bar': 'baz'})
#print(f'{bad_pvfoo=}')

good_pvfoo['foo'] = 2
print(f'{good_pvfoo=}')
