import dotenv_switch.auto

import jsonpath_ng.ext as jp
from pyrsistent import pmap

pure_json = pmap({'uuid': 'd21976c7-6ddb-4832-93a4-30b993197ad2'})
uuid = jp.parse('$.uuid').find(pure_json)[0].value
print(f'{uuid=}')
