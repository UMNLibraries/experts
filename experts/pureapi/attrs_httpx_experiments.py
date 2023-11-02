from attrs import frozen, field
import httpx

@frozen(kw_only=True)
class Context:
    foo: str
    httpx_client: httpx.Client = httpx.Client()

cx = Context(foo='bar')
r = cx.httpx_client.get('https://google.com')
print(r.status_code)
print(cx.foo)
cx.foo = 'baz'
