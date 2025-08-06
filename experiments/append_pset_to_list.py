from itertools import batched

from pyrsistent import s, CheckedPSet

TestId = str

class TestSet(CheckedPSet):
    __type__ = TestId

test_set_1 = TestSet(['foo','bar'])
test_set_2 = TestSet(('baz','luhrman'))
test_set_3 = TestSet(['kung'])

scalar = 'perl'
#if isinstance(scalar, TestId):
#    print('any str is an instance of TestId')
#else:
#    print(f'{scalar=} is not an instance of TestId')
#
#scalar_to_list = list(scalar)
#print(f'{scalar_to_list=}')

append_if_str = []
if isinstance(scalar, TestId):
    append_if_str.append(scalar)
append_if_str += list(test_set_1)
print(f'{append_if_str=}')

#set_list = []
#str_list = []
#
#set_list.append(test_set_1)
#set_list.append(test_set_2)
#set_list.append(test_set_3)
#print(f'{set_list=}')
#
#str_list += list(test_set_1)
#str_list += list(test_set_2)
#str_list += list(test_set_3)
#print(f'{str_list=}')
