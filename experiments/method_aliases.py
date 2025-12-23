from pyrsistent import field, PRecord

class ParentClass(PRecord):
    foo = field(type=str)
    bar = field(type=str)

    def both(self):
        return self.foo + ' ' + self.bar

class ChildClass(ParentClass):
    both_alias = ParentClass.both

    # NameError: name 'ChildClass' is not defined
    #both_alias = ChildClass.both

pc = ParentClass(foo='manchu', bar='none')
print(f'{pc.both()=}')

# AttributeError: ParentClass has no attribute 'both_alias'
#print(f'{pc.both_alias()=}')

cc = ChildClass(foo='kung', bar='fu')
print(f'{cc.both()=}')
print(f'{cc.both_alias()=}')
