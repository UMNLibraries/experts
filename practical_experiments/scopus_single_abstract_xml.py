import dotenv_switch.auto

import json
import sys

from pyrsistent import m, pmap
from returns.pipeline import is_successful

from experts.api.scopus import Client

scopus_id = sys.argv[1]
view = sys.argv[2]

xml_headers = pmap({
    #'Accept': 'application/xml',
    'Accept': 'text/xml',
    'Accept-Charset': 'utf-8',
})

with Client(headers=xml_headers) as session:
    result = session.get(f'abstract/scopus_id/{scopus_id}', params=m(view=view))
    if not is_successful(result):
        raise result.failure()
    response = result.unwrap()
    print(response.headers)
    print(response.text)
