import dotenv_switch.auto

from datetime import date
import json
import sys

from pyrsistent import m
from returns.result import Success, Failure

from experts.api import scopus
from experts.api.scopus import \
    ScopusId, \
    AbstractRequestSuccess, \
    AbstractRequestFailure 
    
scopus_id = sys.argv[1]

with scopus.Client() as client:
    # Abstract Retrieval API
    # content='core' excludes dummy records (404s), but not when retrieving
    # abstracts by scopus ID, apparently.
    #params = m(content='core', view='FULL')

    #params = m(view='FULL')
    #params = m(content='core', view='REF')
    #result = client.get(f'abstract/scopus_id/{scopus_id}', params=params)

    match client.get_abstract_by_scopus_id(ScopusId(scopus_id)):
        case Success(AbstractRequestSuccess() as result):
            print(json.dumps(result.response.json(), indent=2))
        case Failure(AbstractRequestFailure() as should_not_happen):
            raise Exception(f'Request for Scopus ID {scopus_id} failed: {should_not_happen}')
        case _:
            raise Exception(f'WTF? The above two cases should be the only possible cases.')
