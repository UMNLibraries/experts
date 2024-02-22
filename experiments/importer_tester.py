import module_to_import
from module_to_import import ClassToImport

import attrs
from attrs import Factory, field, frozen, validators

print(f'{module_to_import.max_attempts=}')
#module_to_import.max_attempts = 5 # AttributeError
#print(f'{module_to_import.max_attempts=}')

#del module_to_import.max_attempts # AttributeError
#delattr(module_to_import, 'max_attempts') # AttributeError

#module_to_import.new_attribute = 'foo' # AttributeError
#del module_to_import.new_attribute # AttributeError

#max_attempts = module_to_import.max_attempts
from module_to_import import max_attempts
max_attempts = 5 # Both of the above work...
print(f'{max_attempts=}')
print(f'{module_to_import.max_attempts=}') # ...and do not alter imported module's max_attempts

@frozen(kw_only=True)
class ImporterTester:
    # TypeError: function_to_import() takes 1 positional argument but 2 were given
    #function_to_import = module_to_import.function_to_import

    def __getattr__(self, attr):
        return getattr(module_to_import, attr)

it = ImporterTester()
it.function_to_import('bar')
#module_to_import.function_to_import = lambda x: print(f'Hello, {x}!')
#it.function_to_import('bar')

ClassToImport.callable_attr_to_import('baz')
ClassToImport.callable_attr_to_import = lambda x: print(f'Hello, {x}!')
ClassToImport.callable_attr_to_import('baz')

cti_obj = ClassToImport()
cti_obj.method_to_import('luhrman')
cti_obj.method_to_import = lambda x: print(f'Hello, {x}!') # error
#cti_obj.method_to_import('luhrman')

nt = module_to_import.build_namedtuple()
nt.nt_function('rashomon')
#nt.nt_function = lambda x: print(f'Hello, {x}!') # error
#module_to_import.build_namedtuple.namedtuple_function = lambda x: print(f'Hello, {x}!') # No error, but doesn't work
#from module_to_import.build_namedtuple import namedtuple_function
#namedtuple_function = lambda x: print(f'Hello, {x}!') # error: ModuleNotFoundError: No module named 'module_to_import.build_namedtuple'; 'module_to_import' is not a package
#nt2 = module_to_import.build_namedtuple()
#nt2.nt_function('rashomon')
