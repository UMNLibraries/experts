class Static():
    @staticmethod
    def foo(x):
        print(x)

    @staticmethod
    def bar(y):
        Static.foo(y)

    @classmethod
    def baz(cls, z):
        cls.foo(z)

Static.bar('hello')
Static.baz('luhrman')

s = Static()
s.baz('lol')

s.bar('bash')
