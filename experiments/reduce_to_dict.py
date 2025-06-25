from functools import reduce

from pyrsistent import CheckedPMap, PRecord, field

ValueId = str

class Letters(CheckedPMap):
    __key_type__ = ValueId
    __value_type__ = str

class Numbers(CheckedPMap):
    __key_type__ = ValueId
    __value_type__ = int

class Separated(PRecord):
    letters = field(type=Letters)
    numbers = field(type=Numbers)

    def value_ids(self):
        return list(self.letters.keys()) + list(self.numbers.keys())

nl = [('id1', 'a'), ('id2', 1), ('id3', 'b'), ('id4', 2)]

def separate(accum, value_tuple):
    print(f'{value_tuple=}')
    value_id, value = value_tuple
    if isinstance(value, str):
        print('value is a letter')
        accum['letters'][value_id] = value
    elif isinstance(value, int):
        print('value is a number')
        accum['numbers'][value_id] = value
    print(f'{accum=}')
    return accum

separated_dict = reduce(separate, nl, {'letters': {}, 'numbers': {}})
separated = Separated(
    letters=Letters(separated_dict['letters']), 
    numbers=Numbers(separated_dict['numbers']), 
)
print(separated)
print(separated.value_ids())

