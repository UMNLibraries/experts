import dotenv_switch.auto

from datetime import date
import json
import importlib
import os

from pyrsistent import m, pmap
from returns.pipeline import is_successful

from experts.api.scopus import \
    Client, \
    ResponseParser as r_parser, \
    AbstractResponseBodyParser as ar_parser
    
#    OffsetResponseBodyParser as or_parser, \
#    TokenResponseBodyParser as tr_parser, \
#    ResponseBodyParser
#
#items_pipe = ResponseBodyParser.items_pipe


with Client() as session:
    #params = m(view='FULL')
    params = m(view='META')
    umn_scopus_id = '0020362344'
    umn_result = session.get(f'abstract/scopus_id/{umn_scopus_id}', params=params)
    
    if not is_successful(umn_result):
        raise umn_result.failure()
    print(json.dumps(umn_result.unwrap().json(), indent=2))
