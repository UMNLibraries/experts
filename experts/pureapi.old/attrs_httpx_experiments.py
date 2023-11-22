from attrs import frozen, field, validators
import httpx
from pyrsistent import pmap, thaw
from pyrsistent.typing import PMap, PVector

def default_bar():
    return 'baz'
    #return None

@frozen(kw_only=True)
class Context:
    baz: PMap = pmap({'a': 1, 'b': 2})
    kung: str = field(init=False)
    foo: str
    bar: str = field(
        #factory=default_bar,
        #factory=lambda: 'baz',
        default=default_bar(),
        validator=validators.instance_of(str)
    )
    httpx_client: httpx.Client = httpx.Client()

    def __attrs_post_init__(self) -> None:
        object.__setattr__(self, 'kung', 'fu')

#cx = Context(foo='bar', kung='foo')
cx = Context(foo='bar')
r = cx.httpx_client.get('https://google.com')
print(r.status_code)
print(f'{cx=}')

cx2 = Context(foo='manchoo', bar='overridden')
print(f'{cx2=}')

print(thaw(cx2.baz))

# This should fail:
#cx.foo = 'baz'
