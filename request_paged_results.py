import dotenv_switch.auto
import experts.api.client as client
from experts.api.client import get, post
from experts.api.pure.web_services.context import Context

from pyrsistent import m, pmap
import returns
from returns.pipeline import is_successful
from returns.result import Result, Success, Failure, safe

items_per_page = Context().offset_request_params_parser.items_per_page(m())
print(f'{items_per_page=}')
params = m()
new_params = params.set('offset', 10)
print(f'{new_params=}')

def report_result(result):
    print(result)
    if is_successful(result):
        response = result.unwrap()
        response_json = response.json()
        print('response data:')
        print(response_json['pageInformation'])
        print(len(response_json['items']), 'items')

with client.session(Context()) as session:
#    for result in session.all_responses_by_offset(get, 'persons', params=m(offset=0, size=1000)):
#        report_result(result)

    params = pmap({
        'offset': 0,
        'size': 200,
        'forJournals': {
          'uuids': [ '830a7383-b7a2-445c-8ff5-34816b6eadee' ] # Nature
        }
    })
##    for result in session.all_responses_by_offset(post, 'research-outputs', params=params):
##        report_result(result)
    returned_items_count = 0
    for item in session.all_items_by_offset(post, 'research-outputs', params=params):
        if returned_items_count == 0:
            print(item)
        returned_items_count += 1
    print(f'received {returned_items_count} items')
