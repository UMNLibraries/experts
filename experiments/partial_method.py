from functools import partial

from attrs import frozen

@frozen(kw_only=True)
class Foo:
    bar: str
    kung: str

    def hello(self, someone: str):
        print(f'Hello, {someone}!')
        print(f'{self.bar=}, {self.kung=}')

fu = Foo(bar='Luhrman', kung='fu')
hello_partial = partial(fu.hello)
hello_partial('manchu')


foo = Foo(bar='baz', kung='foo')
hello_partial = partial(foo.hello)
hello_partial('fighters')
