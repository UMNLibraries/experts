import dotenv_switch.auto

from datetime import datetime
import json
import importlib
import os

from pyrsistent import m, pmap
from returns.pipeline import is_successful

import experts.api.client as client
from experts.api.client import get, post
import experts.api.scopus.context as context

with client.session(context.Context()) as session:
    #params = m(cursor='*', count=200, query=f'af-id({session.context.affiliation_id})')
    #params = m(count=200, query=f'af-id({session.context.affiliation_id}) AND key(kidney carcinoma)')
    #params = m(count=200, query=f'au-id(7004512648)')
    params = m(cursor='*', count=200, query=f'au-id(7004512648)')

    total_result = session.get('search/scopus', params=params)
    if not is_successful(total_result):
        raise total_result.failure()
    print(total_result.unwrap().headers)

    #total_result_json = total_result.unwrap().json()
    #print(json.dumps(total_result_json))

    #for response in session.all_responses_by_token(get, 'search/scopus', token='*', params=params):
        #continue
        #print(total_result.unwrap().headers)
        #print(json.dumps(response)) 

# Request for a single record by unique ID:
#    result = session.get('abstract/scopus_id/85173160883', params=m(view='REF'))
#    if not is_successful(result):
#        # TODO: A 404 did not cause a failure!
#        raise result.failure()
#    print(json.dumps(result.unwrap().json()))


