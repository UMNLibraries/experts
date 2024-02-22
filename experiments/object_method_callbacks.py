import attrs
from attrs import Factory, field, frozen, validators

@frozen(kw_only=True)
class CallbackTester:
    foo: str
    bar: str

    def callback(self, object_name: str):
        print(self.foo, self.bar, object_name)

ct1 = CallbackTester(foo='manchu', bar='stool')
ct2 = CallbackTester(foo='kung', bar='luchador')

def callback_runner(callback, object_name):
    callback(object_name)

callback_runner(ct1.callback, 'ct1')
callback_runner(ct2.callback, 'ct2')

some_obj = SomeClass()

def some_function(obj, callback):
    obj.callback()

partial_some_function = partial(some_function, some_obj)
partial_some_function(callback)

some_obj.some_function(callback)
