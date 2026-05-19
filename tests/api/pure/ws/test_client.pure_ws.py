from datetime import date
import importlib

import pytest
from pyrsistent import m, pmap
from returns.pipeline import is_successful

from experts.api.pure.ws import \
    ResponseBodyParser, \
    ResponseParser, \
    OffsetResponseBodyParser, \
    TokenResponseBodyParser, \
    OffsetResponseParser, \
    TokenResponseParser

responses_to_items = ResponseParser.responses_to_items

@pytest.mark.integration
def test_request_many_by_token(session):
    token = date.today().isoformat()

    parser = TokenResponseParser
    result = session.get(f'changes/{token}')
    if not is_successful(result):
        raise result.failure()
    response = result.unwrap()

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

    for item in session.request_many_by_token(session.get, 'changes', token=token) | responses_to_items:
        for element in item_elements_present_counts:
            if element in item:
                item_elements_present_counts[element] += 1
            else:
                item_elements_missing_counts[element] += 1

    for element in item_elements_present_counts:
        # Some items will not have some elements, but most items should have all of them:
        assert item_elements_present_counts[element] > 0
        assert item_elements_present_counts[element] > item_elements_missing_counts[element]

@pytest.mark.integration
def test_request_many_by_offset_get(session):
    #parser = OffsetResponseBodyParser
    parser = OffsetResponseParser
    params = m(offset=0, size=1000)

    result = session.get('persons', params=params)
    if not is_successful(result):
        raise result.failure()
    total_items = parser.total_items(
        result.unwrap()
    )

    assert len(
        list(session.request_many_by_offset(session.get, 'persons', params=params) | responses_to_items)
    ) == total_items

@pytest.mark.integration
def test_request_many_by_offset_post(session):
    #parser = OffsetResponseBodyParser
    parser = OffsetResponseParser
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
        total_result.unwrap()
    )

    assert len(
        list(session.request_many_by_offset(session.post, 'research-outputs', params=params) | responses_to_items)
    ) == total
