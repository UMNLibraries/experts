def to10():
    n = 1
    while True:
        yield n
        n = n+1
        if n > 10:
            return

for n in to10():
    print(n)

def two_way(token):
    print('Starting server...')
    while True:
        token = yield f'{token=}'
        print(f'Received request {token}')

c = two_way(None)
next(c)
tokens = ['2023-11-20'] + list(range(1,11))
for token in tokens:
    print(f'Sending request: {token}')
    response = c.send(token)
    print(f'Response: {response}')
