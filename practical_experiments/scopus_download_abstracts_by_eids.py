import dotenv_switch.auto

from datetime import date
import json
import sys

from pyrsistent import m
from returns.pipeline import is_successful

from experts.api.scopus import \
    Client, \
    ResponseParser as r_parser, \
    AbstractResponseBodyParser as ar_parser
    
eid = sys.argv[1]

with Client() as session:
    # Scopus Search API
    params = m(view='complete', query=f'EID({eid})')
    result = session.get(f'search/scopus', params=params)

    if not is_successful(result):
        raise result.failure()
    response = result.unwrap()
    #print(f'{response.headers=}')
    response_json = response.json()
    print(json.dumps(response_json, indent=2))
