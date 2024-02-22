import attrs
from attrs import Factory, field, frozen, validators
from collections import namedtuple

import immutable
immutable.module(__name__)

max_attempts = 10

def function_to_import(foo):
    print(foo)

def build_namedtuple():
    def namedtuple_function(foo):
        print(foo)

    NT = namedtuple('NT', 'nt_function')    
    return NT(namedtuple_function)

@frozen(kw_only=True)
class ClassToImport:
    callable_attr_to_import = function_to_import

    def method_to_import(self, foo):
        print(foo)

