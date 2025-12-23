import sys
from types import ModuleType
from typing import Any

class ImmutableModule(ModuleType):
    def __setattr__(module: ModuleType, attribute_name: str, value: Any):
        msg: str = (
            f'Attempt to modify attribute "{attribute_name}" of immutable module "{module.__name__}"'
            if hasattr(module, attribute_name) else
            f'Attempt to add attribute "{attribute_name}" to immutable module "{module.__name__}"' 
        )
        raise AttributeError(msg)

    def __delattr__(module: ModuleType, attribute_name: str):
        msg: str = (
            f'Attempt to delete attribute "{attribute_name}" from immutable module "{module.__name__}"'
            if hasattr(module, attribute_name) else
            f'Attempt delete non-existent attribute "{attribute_name}" from immutable module "{module.__name__}"' 
        )
        raise AttributeError(msg)

def module(module_name: str):
    sys.modules[module_name].__class__ = ImmutableModule
