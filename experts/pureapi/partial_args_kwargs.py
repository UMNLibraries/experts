from functools import partial

from pyrsistent import freeze, thaw, m, pmap, v, pvector
from pyrsistent.typing import PMap, PVector

def get(resource_path:str, params:PMap=m(), config:PMap=m()):
    print(f'{resource_path=}, {params=}, {config=}')

def post(resource_path:str, answer:int, params:PMap=m(), json:PMap=m(), config:PMap=m()):
    print(f'{resource_path=}, {answer=}, {params=}, {json=}, {config=}')

def build_request_by_offset(request_function, resource_path, *args, params:PMap, **kwargs):
    partial_request = partial(request_function, resource_path, *args, **kwargs)
    def request_by_offset(offset:int):
        return partial_request(params=params.update({'offset':offset}))
    return request_by_offset

get_by_offset = build_request_by_offset(get, 'persons', params=m(size=100), config=m(foo='bar'))
get_by_offset(10)
# resource_path='persons', params=pmap({'offset': 10, 'size': 100}), config=pmap({'foo': 'bar'})

post_by_offset = build_request_by_offset(post, 'research-outputs', 42, params=m(size=1000), json=m(search='naughton'), config=m(kung='foo'))
post_by_offset(0)
# resource_path='research-outputs', answer=42, params=pmap({'offset': 0, 'size': 1000}), json=pmap({'search': 'naughton'}), config=pmap({'kung': 'foo'})
