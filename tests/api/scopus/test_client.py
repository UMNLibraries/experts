from datetime import datetime
import importlib
import os

import pytest
from pyrsistent import m, pmap
from returns.pipeline import is_successful

from experts.api.client import get, post
import experts.api.scopus.context as context

'''
@pytest.mark.integration
def test_get_all_responses_by_token(session):
    parser = context.TokenResponseParser

    token = datetime.now().isoformat()

    for response in session.all_responses_by_token(get, 'changes', token=token):
        # The response parser should always return values of these types:
        items_count = parser.items_per_page(response)
        assert (isinstance(items_count, int) and items_count >= 0)
        assert isinstance(parser.items(response), list)
        assert isinstance(parser.more_items(response), bool)
        assert isinstance(parser.token(response), str)
    
    item_elements_present_counts = {
        'uuid': 0,
        'changeType': 0,
        'family': 0,
        'familySystemName': 0,
        'version': 0,
    }
    item_elements_missing_counts = {
        'uuid': 0,
        'changeType': 0,
        'family': 0,
        'familySystemName': 0,
        'version': 0,
    }
    for item in session.all_items(get, 'changes', token=token):
        for element in item_elements_present_counts:
            if element in item:
                item_elements_present_counts[element] += 1
            else:
                item_elements_missing_counts[element] += 1

    for element in item_elements_present_counts:
        # Some items will not have some elements, but most items should have all of them:
        assert item_elements_present_counts[element] > 0
        assert item_elements_present_counts[element] > item_elements_missing_counts[element]
'''

@pytest.mark.integration
def test_get_all_responses_by_offset(session):
    parser = context.OffsetResponseParser
    params = m(start=0, count=200, query='af-id(60029445)')

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
    
'''
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
