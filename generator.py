def to10():
    n = 1
    while True:
        yield n
        n = n+1
        if n > 10:
            #break
            return

for n in to10():
    print(n)
