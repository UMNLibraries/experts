from functools import partial
from pyrsistent import freeze, thaw, m, pmap, v, pvector
from pyrsistent.typing import PMap, PVector

def get(resource_path:str, params:PMap=m()):
    print(resource_path, params)

def curry_offset_get(resource_path, params, size):
    partial_get = partial(get, resource_path=resource_path)
    def offset_get(offset:int=0):
        return partial_get(params=params.update({'size':size, 'offset':offset}))
    return offset_get

curried_get = curry_offset_get(resource_path='persons', params=m(), size=10)
for offset in pvector(range(0, 100, 10)):
    curried_get(offset)
