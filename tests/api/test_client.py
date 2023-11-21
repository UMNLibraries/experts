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
def test_get_with_pure_ws(pure_ws_session):
    session = pure_ws_session
    parser = pure_ws_context.OffsetResponseParser
    params = m(offset=0, size=1000)

    total_result = session.get('persons', params=params)

    if not is_successful(total_result):
        raise total_result.failure()
    total = parser.total_items(
        total_result.unwrap().json()
    )

    assert sum(
        len(parser.items(response)) for response in (
            session.all_responses_by_offset(get, 'persons', params=params)
        )
    ) == total
    
    assert sum(
        [1 for item in session.all_items_by_offset(
            session.all_responses_by_offset(get, 'persons', params=params)
        )]
    ) == total

    assert sum(
        [1 for item in session.all_items(get, 'persons', params=params)]
    ) == total

@pytest.mark.integration
def test_post_with_pure_ws(pure_ws_session):
    session = pure_ws_session
    parser = pure_ws_context.OffsetResponseParser
    params = pmap({
        'offset': 0,
        'size': 200,
        'forJournals': {
          'uuids': [ '830a7383-b7a2-445c-8ff5-34816b6eadee' ] # Nature
        }
    })

    total_result = session.post('research-outputs', params=params)

    if not is_successful(total_result):
        raise total_result.failure()
    total = parser.total_items(
        total_result.unwrap().json()
    )

    assert sum(
        len(parser.items(response)) for response in (
            session.all_responses_by_offset(post, 'research-outputs', params=params)
        )
    ) == total
    
    assert sum(
        [1 for item in session.all_items_by_offset(
            session.all_responses_by_offset(post, 'research-outputs', params=params)
        )]
    ) == total

    assert sum(
        [1 for item in session.all_items(post, 'research-outputs', params=params)]
    ) == total

