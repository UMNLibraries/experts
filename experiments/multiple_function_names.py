import inspect
import sys
from functools import partial

def request(foo, bar):
    print(f'{foo=}, {bar=}')
    print(f'{inspect.stack()[0][3]=}')
    print(f'{inspect.stack()[1][3]=}')
    #print(f'{inspect.stack()[0][0].f_code.co_name=}')
    #print(f'{inspect.currentframe().f_code.co_name=}')
    #print(f'{sys._getframe().f_code.co_name=}')

def get(*args, **kwargs):
    request(*args, **kwargs)

def post(*args, **kwargs):
    request(*args, **kwargs)

request(foo='request', bar='baz')
get(foo='get', bar='baz')
post(foo='post', bar='luhrman')

partial_get = partial(get, foo='partial_get')
partial_get(bar='baz')
partial_post = partial(post, foo='partial_post')
partial_post(bar='luhrman')
