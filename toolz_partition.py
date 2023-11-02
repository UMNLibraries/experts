from time import sleep
from toolz import partition

def slow_list():
    for i in [1, 2, 3, 4, 5, 6, 7, 8]:
        sleep(2)
        yield i

a = [1, 2, 3, 4, 5, 6, 7, 8]
for l in partition(5, a, pad=None):
    print(l)

for l in partition(5, slow_list(), pad=None):
    print(l)
