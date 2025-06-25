import dotenv_switch.auto

from datetime import date
import json
import importlib
import os

from pyrsistent import m, pmap
from returns.pipeline import is_successful

from experts.api.pure.ws import \
    Client, \
    ResponseParser

responses_to_items = ResponseParser.responses_to_items

with Client() as session:
    params = m(offset=0, size=1000)
    result = session.get('research-outputs', params=params)
    scopus_ids = []
    for ro in [result.unwrap()] | responses_to_items:
        if 'externalIdSource' in ro and ro['externalIdSource'] == 'Scopus':
            scopus_ids.append(ro['externalId'])

print(f'{len(scopus_ids)=}')
