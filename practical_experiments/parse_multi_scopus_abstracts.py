import dotenv_switch.auto

from datetime import date
import json
import importlib
import os

from pyrsistent import m, pmap
from returns.pipeline import is_successful

import experts.api.pure.ws as pure_ws
import experts.api.scopus as scopus

with pure_ws.Client() as pure_session, scopus.Client() as scopus_session:
    result = pure_session.get('research-outputs', params=m(offset=0, size=1000))
    pure_scopus_ids = set() 
    for ro in [result.unwrap()] | pure_ws.ResponseParser.responses_to_items:
        if 'externalIdSource' in ro and ro['externalIdSource'] == 'Scopus':
            pure_scopus_ids.add(ro['externalId'])
    print(f'{len(pure_scopus_ids)=}')

    r_parser = scopus.ResponseParser
    ar_parser = scopus.AbstractResponseBodyParser
    scopus_ids = set()
    eids = set()
    reference_scopus_ids = set()
    for body in scopus_session.request_many_by_id(
        scopus_session.get,
        'abstract',
        id_type='scopus_id',
        ids=pure_scopus_ids,
        params=m(content='core', view='FULL')
    ) | r_parser.responses_to_bodies:
        eid = ar_parser.eid(body)
        eids.add(eid)
        scopus_id = ar_parser.scopus_id(body)
        scopus_ids.add(scopus_id)
        try:
            reference_scopus_ids.update(ar_parser.reference_scopus_ids(body))
        except Exception as e:
            print(f'{scopus_id=}')
            print(e)

    print(f'{len(eids)=}')
    print(f'{len(scopus_ids)=}')
    print(f'{len(reference_scopus_ids)=}')
    print(f'{pure_scopus_ids.difference(scopus_ids)=}')
