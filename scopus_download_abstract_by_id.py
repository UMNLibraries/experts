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
    
request_scopus_id = sys.argv[1]

with Client() as session:
    # Abstract Retrieval API
    # content='core' excludes dummy records (404s), but not when retrieving
    # abstracts by scopus ID, apparently.
    #params = m(content='core', view='FULL')

    #params = m(view='FULL')
    #params = m(content='core', view='REF')
    #result = session.get(f'abstract/scopus_id/{scopus_id}', params=params)

    response_scopus_id, result = session.get_abstract_by_scopus_id(request_scopus_id)
    assert response_scopus_id == request_scopus_id

    if not is_successful(result):
        raise result.failure()
    response = result.unwrap()
    #print(f'{response.headers=}')
    response_json = response.json()
    print(json.dumps(response_json, indent=2))
