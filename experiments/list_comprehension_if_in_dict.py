stuff = [ 
    {'name': 'foo'},
    {'name': 'bar'},
    {'bogus': 'man'},
]

names = [
    thing['name']
    for thing in stuff
    if 'name' in thing
]
print(names)
