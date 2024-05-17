from datetime import date
import json
import pytest

from experts.api.scopus import AbstractResponseBodyParser as parser

def load_data(scopus_id: str):
    with open(f'tests/api/scopus/data/abstract_{scopus_id}.json') as body_file, open(f'tests/api/scopus/data/abstract_{scopus_id}_ref_scopus_ids.json') as ref_scopus_ids_file:
        return [json.load(body_file), json.load(ref_scopus_ids_file)]

def test_abstract_response_body_parser():
    scopus_id = '75149190029'
    body, reference_scopus_ids = load_data(scopus_id)

    assert parser.scopus_id(body) == scopus_id
    assert isinstance(parser.scopus_id(body), str)
    assert parser.eid(body) == body['abstracts-retrieval-response']['coredata']['eid']
    assert isinstance(parser.eid(body), str)

    assert parser.date_created(body) == date.fromisoformat('2009-10-15')

    assert parser.refcount(body) == int(body['abstracts-retrieval-response']['item']['bibrecord']['tail']['bibliography']['@refcount'])
    assert isinstance(parser.refcount(body), int)
    assert sorted(parser.reference_scopus_ids(body)) == sorted(reference_scopus_ids)

def test_abstract_response_body_parser_mixed_reference_itemid_values():
    '''The abstract under test here contains reference itemids that are mix of list and non-list values.'''
    scopus_id = '84924664029'
    body, reference_scopus_ids = load_data(scopus_id)

    assert parser.scopus_id(body) == scopus_id
    assert isinstance(parser.scopus_id(body), str)
    assert parser.eid(body) == body['abstracts-retrieval-response']['coredata']['eid']
    assert isinstance(parser.eid(body), str)

    assert parser.date_created(body) == date.fromisoformat('2021-09-27')

    assert sorted(parser.reference_scopus_ids(body)) == sorted(reference_scopus_ids)

def test_abstract_response_body_parser_no_references():
    scopus_id = '49949145584'
    body, reference_scopus_ids = load_data(scopus_id)

    assert parser.scopus_id(body) == scopus_id
    assert isinstance(parser.scopus_id(body), str)
    assert parser.eid(body) == body['abstracts-retrieval-response']['coredata']['eid']
    assert isinstance(parser.eid(body), str)

    assert parser.date_created(body) == date.fromisoformat('2017-09-18')

    assert parser.refcount(body) == 0
    assert isinstance(parser.refcount(body), int)
    assert sorted(parser.reference_scopus_ids(body)) == sorted(reference_scopus_ids)
