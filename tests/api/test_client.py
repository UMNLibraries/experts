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

        total_persons_result = session.get('persons', params=m(offset=0, size=1))
        if not is_successful(total_persons_result):
            raise total_persons_result.failure()
        total_persons= parser.total_items(
            total_persons_result.unwrap().json()
        )

        persons_params = m(offset=0, size=1000)

        assert sum(
            len(parser.items(response)) for response in (
                # This may fail, because we do not ensure a successful result:
                result.unwrap().json() for result in session.all_results_by_offset(get, 'persons', params=persons_params)
            )
        ) == total_persons
        
        assert sum(
            [1 for item in session.all_items(
                # This will not fail, because all_responses handles unsuccessful results:
                session.all_responses(
                    session.all_results_by_offset(get, 'persons', params=persons_params)
                )
            )]
        ) == total_persons

        ros_params = pmap({
            'offset': 0,
            'size': 200,
            'forJournals': {
              'uuids': [ '830a7383-b7a2-445c-8ff5-34816b6eadee' ] # Nature
            }
        })

        total_ros_result = session.post('research-outputs', params=ros_params)
        if not is_successful(total_ros_result):
            raise total_ros_result.failure()
        total_ros= parser.total_items(
            total_ros_result.unwrap().json()
        )

        assert sum(
            len(parser.items(response)) for response in (
                # This may fail, because we do not ensure a successful result:
                result.unwrap().json() for result in session.all_results_by_offset(post, 'research-outputs', params=ros_params)
            )
        ) == total_ros
        
        assert sum(
            [1 for item in session.all_items(
                # This will not fail, because all_responses handles unsuccessful results:
                session.all_responses(
                    session.all_results_by_offset(post, 'research-outputs', params=ros_params)
                )
            )]
        ) == total_ros
