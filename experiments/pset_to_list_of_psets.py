from itertools import batched

from pyrsistent import s, CheckedPSet

class TestSet(CheckedPSet):
    __type__ = str

total_set = ['foo','bar','baz','luhrman','kung']
# Works:
#total_set = TestSet(['foo','bar','baz','luhrman','kung'])
# Works:
#total_set = s('foo','bar','baz','luhrman','kung')

# Fails, because pyrsistent doesn't allow this argument to the pset constructor:
#total_set = s(['foo','bar','baz','luhrman','kung'])

subsets = list(batched(total_set, 2))
print(f'{subsets=}')
