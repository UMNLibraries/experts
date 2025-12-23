from pyrsistent import CheckedPVector

class CPV(CheckedPVector):
    __type__ = str

    def print_values(self):
        for value in self:
            print (f'{value=}')

cpv = CPV(['a','b','c'])
cpv.print_values()
