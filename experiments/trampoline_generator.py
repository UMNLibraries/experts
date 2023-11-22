from typing import Union, List, Iterator
import returns
from returns.trampolines import Trampoline, trampoline

def continue_stepping(limit:int):
    if limit <=1:
        return False
    return True

def rest_of_the_steps(n:int, limit:int):
    for i in range(n, limit+1):
        yield i

#@trampoline
def step_by_one(
    n:int=1,
    limit:int=1500
) -> Iterator[int]:
#) -> Union[Iterator[int], Trampoline[Iterator[int]]]:
    yield n
    if n >= limit:
        return
    if continue_stepping(limit):
        for i in range(n, limit+1):
            yield i
        #yield from rest_of_the_steps(n=n+1, limit=limit)
    #yield from step_by_one(n=n+1, limit=limit)
    #yield from Trampoline(step_by_one, n=n+1, limit=limit)

for n in step_by_one():
    if n > 1495:
        print(n)
