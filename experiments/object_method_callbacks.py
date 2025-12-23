import attrs
from attrs import Factory, field, frozen, validators

@frozen(kw_only=True)
class CallbackTester:
    foo: str
    bar: str

    def default_callback(self, object_name: str):
        print(f'Default callback! {object_name=}')
        print(self.foo, self.bar, object_name)

# This doesn't work!
# Generates 'missing required positional argument errors, due to missing class/object context.
#    def method_with_callback(self, object_name, callback=callback):
#        return callback(object_name)
#
#ct1.method_with_callback('ct1')
#def callback_override(object_name: str):
#    print(f'Callback override! {object_name=}')
#ct2.method_with_callback('ct1', callback=callback_override)

# This works...
#    def callback_override(self, object_name: str):
#        print(f'Callback override! {object_name=}')

    def method_with_callback(self, object_name, callback=None):
        if not callback:
            callback = self.default_callback
        return callback(object_name)

# ... and so does this:
def callback_override(object_name: str):
    print(f'Callback override! {object_name=}')

ct1 = CallbackTester(foo='manchu', bar='stool')
ct2 = CallbackTester(foo='kung', bar='luchador')

ct1.method_with_callback('ct1')
#ct2.method_with_callback('ct2', callback=ct2.callback_override)
ct2.method_with_callback('ct2', callback=callback_override)

def callback_runner(callback, object_name):
    callback(object_name)

callback_runner(ct1.default_callback, 'ct1')
callback_runner(callback_override, 'ct2')

some_obj = SomeClass()

def some_function(obj, callback):
    obj.callback()

partial_some_function = partial(some_function, some_obj)
partial_some_function(callback)

some_obj.some_function(callback)
