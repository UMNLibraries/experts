from datetime import date
import json
import pytest

from experts.api.scopus import \
    AbstractResponseBodyParser as abstract_parser, \
    CitationOverviewResponseBodyParser as citation_overview_parser

def load_abstract_data(scopus_id: str):
    with open(f'tests/api/scopus/data/abstract/{scopus_id}/body.json') as body_file, open(f'tests/api/scopus/data/abstract/{scopus_id}/body_ref_scopus_ids.json') as ref_scopus_ids_file:
        return [json.load(body_file), json.load(ref_scopus_ids_file)]

def test_abstract_response_body_parser():
    scopus_id = '75149190029'
    body, reference_scopus_ids = load_abstract_data(scopus_id)

    assert abstract_parser.scopus_id(body) == scopus_id
    assert isinstance(abstract_parser.scopus_id(body), str)
    assert abstract_parser.eid(body) == body['abstracts-retrieval-response']['coredata']['eid']
    assert isinstance(abstract_parser.eid(body), str)

    assert abstract_parser.date_created(body) == date.fromisoformat('2009-10-15')

    assert abstract_parser.refcount(body) == int(body['abstracts-retrieval-response']['item']['bibrecord']['tail']['bibliography']['@refcount'])
    assert isinstance(abstract_parser.refcount(body), int)
    assert sorted(abstract_parser.reference_scopus_ids(body)) == sorted(reference_scopus_ids)

def test_abstract_response_body_parser_mixed_reference_itemid_values():
    '''The abstract under test here contains reference itemids that are mix of list and non-list values.'''
    scopus_id = '84924664029'
    body, reference_scopus_ids = load_abstract_data(scopus_id)

    assert abstract_parser.scopus_id(body) == scopus_id
    assert isinstance(abstract_parser.scopus_id(body), str)
    assert abstract_parser.eid(body) == body['abstracts-retrieval-response']['coredata']['eid']
    assert isinstance(abstract_parser.eid(body), str)

    assert abstract_parser.date_created(body) == date.fromisoformat('2021-09-27')

    assert sorted(abstract_parser.reference_scopus_ids(body)) == sorted(reference_scopus_ids)

def test_abstract_response_body_parser_no_references():
    scopus_id = '49949145584'
    body, reference_scopus_ids = load_abstract_data(scopus_id)

    assert abstract_parser.scopus_id(body) == scopus_id
    assert isinstance(abstract_parser.scopus_id(body), str)
    assert abstract_parser.eid(body) == body['abstracts-retrieval-response']['coredata']['eid']
    assert isinstance(abstract_parser.eid(body), str)

    assert abstract_parser.date_created(body) == date.fromisoformat('2017-09-18')

    assert abstract_parser.refcount(body) == 0
    assert isinstance(abstract_parser.refcount(body), int)
    assert sorted(abstract_parser.reference_scopus_ids(body)) == sorted(reference_scopus_ids)

def load_citation_overview_data(scopus_ids: str):
    with open(f'tests/api/scopus/data/citation_overview/{scopus_ids}.json') as body_file:
        return json.load(body_file)


