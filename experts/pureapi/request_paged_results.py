import dotenv_switch.auto
import client
from client import get

from pyrsistent import m
import returns
from returns.pipeline import is_successful
from returns.result import Result, Success, Failure, safe

with client.Config().session() as session:
    #for result in session.request_pages_by_offset('persons', offset_start=0, size=10, count=100):
    for result in session.all_responses_by_offset(get, 'persons', params=m(offset=0, size=1000)):
        print(result)
        if is_successful(result):
            response = result.unwrap()
            response_json = response.json()
            print(response_json['pageInformation'])
