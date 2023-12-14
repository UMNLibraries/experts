from datetime import datetime
import importlib
import os

import pytest
from pyrsistent import m, pmap
from returns.pipeline import is_successful

from experts.api.client import get, post
import experts.api.scopus.context as context

@pytest.mark.integration
def test_get_all_responses_by_token(session):
    parser = context.TokenResponseParser
    params = m(count=200, query=f'af-id({session.context.affiliation_id}) AND key(kidney carcinoma)')

    total_result = session.get('search/scopus', params=params.set('cursor', '*'))

    if not is_successful(total_result):
        raise total_result.failure()
    total = parser.total_items(
        total_result.unwrap().json()
    )

    assert total > 0

    assert sum(
        len(parser.items(response)) for response in (
            session.all_responses_by_token(get, 'search/scopus', token='*', params=params)
        )
    ) == total
    
    assert sum(
        [1 for item in session.all_items(get, 'search/scopus', token='*', params=params)]
    ) == total
'''
@pytest.mark.integration
def test_get_all_responses_by_offset(session):
    parser = context.OffsetResponseParser
    params = m(start=0, count=200, query='af-id({session.context.affiliation_id})')

    total_result = session.get('search/scopus', params=params)

    if not is_successful(total_result):
        raise total_result.failure()
    total = parser.total_items(
        total_result.unwrap().json()
    )

    assert total > 0

    assert sum(
        len(parser.items(response)) for response in (
            session.all_responses_by_offset(get, 'search/scopus', params=params)
        )
    ) == total
    
    assert sum(
        [1 for item in session.all_items(get, 'persons', params=params)]
    ) == total
'''
'''
@pytest.mark.integration
def test_post_all_responses_by_offset(pure_ws_session):
    parser = context.OffsetResponseParser
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
        [1 for item in session.all_items(post, 'research-outputs', params=params)]
    ) == total
'''
