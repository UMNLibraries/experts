import dotenv_switch.auto

import importlib
import os

import pytest
from pyrsistent import m, pmap
import returns
from returns.pipeline import is_successful

import experts.api.client as client
from experts.api.client import get, post
import experts.api.pure.web_services.context as pure_ws_context
import experts.api.scopus.context as scopus_context

@pytest.mark.integration
def test_pure_ws():
    parser = pure_ws_context.OffsetResponseParser
    with client.session(pure_ws_context.Context()) as session:

        total_persons : int
        total_persons_received : int = 0
        person_params = m(offset=0, size=1000)

        for result in session.all_responses_by_offset(get, 'persons', params=person_params):
            if is_successful(result):
                response = result.unwrap().json()
                if parser.offset(response) == 0:
                    total_persons = parser.total_items(response)
                total_persons_received += len(parser.items(response))
        assert total_persons_received == total_persons

        total_person_items_received : int = 0
        for item in session.all_items_by_offset(get, 'persons', params=person_params):
            total_person_items_received += 1
        assert total_person_items_received == total_persons

        total_ros : int
        total_ros_received : int = 0
        ro_params = pmap({
            'offset': 0,
            'size': 200,
            'forJournals': {
              'uuids': [ '830a7383-b7a2-445c-8ff5-34816b6eadee' ] # Nature
            }
        })

        for result in session.all_responses_by_offset(post, 'research-outputs', params=ro_params):
            if is_successful(result):
                response = result.unwrap().json()
                if parser.offset(response) == 0:
                    total_ros = parser.total_items(response)
                total_ros_received += len(parser.items(response))
        assert total_ros_received == total_ros

        total_ro_items_received : int = 0
        for item in session.all_items_by_offset(post, 'research-outputs', params=ro_params):
            total_ro_items_received += 1
        assert total_ro_items_received == total_ros

