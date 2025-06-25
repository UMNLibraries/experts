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
    params = m(content='core', view='FULL')
    #umn_scopus_id = '75149190029'
    #umn_scopus_id = '85150001360'
    #umn_scopus_id = '49949145584'
    #umn_scopus_id = '84924664029'
    #umn_scopus_id = '85159902125'
    umn_scopus_id = '85113927644'
    umn_result = session.get(f'abstract/scopus_id/{umn_scopus_id}', params=params)
    
    #cited_scopus_id = '1342299174'
#1442349426
#1542448662
#2442557820
#2542585403
#2942701077
#3042556767
#3042607342
#3042649996
#3042692563
    #umn_result = session.get(f'abstract/scopus_id/{cited_scopus_id}', params=params)

    if not is_successful(umn_result):
        raise umn_result.failure()
    umn_response = umn_result.unwrap()
    print(f'{umn_response.headers=}')
    umn_response_json = umn_response.json()
    print(umn_response_json)

## issn function is commented out in AbstractResponseBodyParser:
##   umn_issn = ar_parser.issn(umn_response_json)
##   print(f'{umn_issn=}')
#
#    umn_refcount = ar_parser.refcount(umn_response_json)
#    print(f'{umn_refcount=}')
#    umn_reference_scopus_ids = ar_parser.reference_scopus_ids(umn_response_json)
#    print(f'{len(umn_reference_scopus_ids)=}')
#
##   reference_scopus_ids_2_issns = {}
##   for body in session.request_many_by_id(session.get, 'abstract', id_type='scopus_id', ids=umn_reference_scopus_ids, params=params) | r_parser.responses_to_bodies:
##       print(ar_parser.scopus_id(body), body['abstracts-retrieval-response']['item']['bibrecord']['head']['source'])
##       #reference_scopus_ids_2_issns[ar_parser.scopus_id(body)] = ar_parser.issn(body)
#
#    for response in session.request_many_by_id(session.get, 'abstract', id_type='scopus_id', ids=umn_reference_scopus_ids, params=params):
#        print(f'{response.headers}')
#        body = r_parser.body(response)
#        print(ar_parser.scopus_id(body), body['abstracts-retrieval-response']['item']['bibrecord']['head']['source'])
#
#    #print(f'{len(reference_scopus_ids)=}')
#
