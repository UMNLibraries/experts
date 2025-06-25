import dotenv_switch.auto

from datetime import date
import json
import importlib
import os

from pyrsistent import m, pmap
from returns.pipeline import is_successful

from experts.api.common import bodies_pipe
from experts.api.pure.ws.client import \
    Client, \
    OffsetResponseBodyParser as or_parser, \
    TokenResponseBodyParser as tr_parser, \
    ResponseBodyParser

items_pipe = ResponseBodyParser.items_pipe


with Client() as session:
    params = m(offset=0, size=1000)
    total_result = session.get('persons', params=params)
    
    if not is_successful(total_result):
        raise total_result.failure()
    total_response_json = total_result.unwrap().json()
    total = or_parser.total_items(
        total_response_json
    )
    print(f'{total=}')
    response_item_count = len(or_parser.items(total_response_json))
    print(f'{response_item_count=}')
    response_items_per_page = or_parser.items_per_page(total_response_json)
    print(f'{response_items_per_page=}')

#    for response in session.request_many_by_offset(session.get, 'persons', params=params):
#        print(response)
#
#    for body in session.request_many_by_offset(session.get, 'persons', params=params) | bodies_pipe:
#        print(body['pageInformation']['offset'])
#    
#    count = 0
#    for item in session.request_many_by_offset(session.get, 'persons', params=params) | bodies_pipe | items_pipe:
#        print(item['uuid'])
#        count = count + 1
#        if count > 10:
#            break

#    item_count = len(list(session.request_many_by_offset(session.get, 'persons', params=params) | bodies_pipe | items_pipe))
#    print(item_count)

#    # Ugly! Is there a way to make this prettier? Do we even need it?
#    json_response = list(session.request_many_by_offset(session.get, 'persons', params=m(offset=55000, size=1000), first_offset=55000) | response_json)[0]
#    print(json_response['pageInformation']['offset'])

    token = date.today().isoformat()
    for body in session.request_many_by_token(session.get, 'changes', token=token) | bodies_pipe:
        # The response parser should always return values of these types:
        items_count = tr_parser.items_per_page(body)
        assert (isinstance(items_count, int) and items_count >= 0)
        assert isinstance(tr_parser.items(body), list)
        assert isinstance(tr_parser.more_items(body), bool)
        assert isinstance(tr_parser.token(body), str)

