from datetime import date
import json

import pytest
from returns.result import Success, Failure

from experts.api.scopus import \
    ScopusId, \
    ScopusIds, \
    CitationRequestScopusIds

def test_scopus_id():
    valid_scopus_id = '84924664029'
    match ScopusId.factory(valid_scopus_id):
        case Success(scopus_id):
            assert scopus_id == valid_scopus_id
            assert isinstance(scopus_id, ScopusId)
        case Failure(exception_should_not_happen):
            raise exception_should_not_happen

    bogus_scopus_id = 'bogus'
    match ScopusId.factory(bogus_scopus_id):
        case Success(should_not_happen):
            raise Exception(f'Attempt to instantiate a ScopusId with invalid value {bogus_scopus_id} should have failed')
        case Failure(exception):
            assert isinstance(exception, ValueError)

def test_scopus_ids():
    valid_scopus_ids_list = ['84924664029','84876222028','33644930319','85199124578']
    valid_scopus_ids, empty_invalid_scopus_ids = ScopusIds.factory(valid_scopus_ids_list)
    assert valid_scopus_ids == set(valid_scopus_ids_list)
    assert isinstance(valid_scopus_ids, ScopusIds)
    assert len(empty_invalid_scopus_ids) == 0

    invalid_scopus_ids_list = ['bogus','invalid']
    mixed_scopus_ids_set = set(valid_scopus_ids_list + invalid_scopus_ids_list)
    only_valid_scopus_ids, only_invalid_scopus_ids = ScopusIds.factory(mixed_scopus_ids_set)
    assert only_valid_scopus_ids == set(valid_scopus_ids_list)
    assert isinstance(only_valid_scopus_ids, ScopusIds)
    assert only_invalid_scopus_ids == set(invalid_scopus_ids_list)

    empty_valid_scopus_ids, invalid_scopus_ids = ScopusIds.factory(invalid_scopus_ids_list)
    assert len(empty_valid_scopus_ids) == 0
    assert invalid_scopus_ids == set(invalid_scopus_ids_list)

def test_citation_request_scopus_ids():
    start = 10000
    last_set_length = 13
    other_set_length = CitationRequestScopusIds.max_scopus_ids_per_request()
    end = start + (other_set_length *3) + last_set_length
    valid_scopus_ids_list = list(range(start, end))

    valid_scopus_ids_sets, empty_invalid_scopus_ids = CitationRequestScopusIds.factory(valid_scopus_ids_list)
    assert len(empty_invalid_scopus_ids) == 0
    last_set = valid_scopus_ids_sets.pop()
    assert len(last_set) == last_set_length
    assert isinstance(last_set, CitationRequestScopusIds)
    for other_set in valid_scopus_ids_sets:
        assert len(other_set) == other_set_length
        assert isinstance(other_set, CitationRequestScopusIds)

    invalid_scopus_ids_list = ['bogus','invalid']
    scopus_id_objects_list = [ScopusId(scopus_id) for scopus_id in valid_scopus_ids_list]
    mixed_scopus_ids_set = set(scopus_id_objects_list + invalid_scopus_ids_list)
    scopus_ids_sets_from_objects, invalid_scopus_ids = CitationRequestScopusIds.factory(mixed_scopus_ids_set)
    assert invalid_scopus_ids == set(invalid_scopus_ids_list)
    assert len(scopus_ids_sets_from_objects) > 0
    for set_from_objects in scopus_ids_sets_from_objects:
        assert isinstance(set_from_objects, CitationRequestScopusIds)
        assert len(set_from_objects) <= CitationRequestScopusIds.max_scopus_ids_per_request()
