from datetime import date
import json

import pytest

from experts.api.scopus import AbstractRecord

def load_data(scopus_id:str) -> tuple[dict, dict]:
    parent_path = f'tests/api/scopus/data/abstract/{scopus_id}'
    with open(f'{parent_path}/body.json') as body_file, open(f'{parent_path}/body_ref_scopus_ids.json') as ref_scopus_ids_file:
        return [json.load(body_file), json.load(ref_scopus_ids_file)]

def test_special_properties():
    scopus_id = '75149190029'
    body_dict, reference_scopus_ids = load_data(scopus_id)

    # The constructor validates the types returned by the special property methods...
    record = AbstractRecord(body_dict)

    # ...so we just verify the values themselves for an extra sanity check:

    assert record.scopus_id == scopus_id
    assert record.eid == '2-s2.0-75149190029' \
        == body_dict['abstracts-retrieval-response']['coredata']['eid']

    assert record.date_created == date.fromisoformat('2009-10-15')

    assert record.refcount == 103 \
        == int(body_dict['abstracts-retrieval-response']['item']['bibrecord']['tail']['bibliography']['@refcount'])

    # We compare to a set made up of body_dict reference_reference_scopus_ids, because
    # the record reference_scopus_ids are a set, and the original record json
    # contains a duplicate (32144434430).
    assert record.reference_scopus_ids == set(reference_scopus_ids)

def test_parser_mixed_reference_itemid_values():
    '''The abstract under test here contains reference itemids that are mix of list and non-list values.'''
    scopus_id = '84924664029'
    body_dict, reference_scopus_ids = load_data(scopus_id)
    record = AbstractRecord(body_dict)

    assert record.scopus_id == scopus_id
    assert record.eid == '2-s2.0-84924664029' \
        == body_dict['abstracts-retrieval-response']['coredata']['eid']

    assert record.date_created == date.fromisoformat('2021-09-27')

    assert record.refcount == 60 \
        == int(body_dict['abstracts-retrieval-response']['item']['bibrecord']['tail']['bibliography']['@refcount'])

    assert record.reference_scopus_ids == set(reference_scopus_ids)

def test_parser_no_references():
    scopus_id = '49949145584'
    body_dict, reference_scopus_ids = load_data(scopus_id)
    record = AbstractRecord(body_dict)

    assert record.scopus_id == scopus_id
    assert record.eid == '2-s2.0-49949145584' \
        == body_dict['abstracts-retrieval-response']['coredata']['eid']

    assert record.date_created == date.fromisoformat('2017-09-18')

    assert record.refcount == 0
    assert record.reference_scopus_ids == set(reference_scopus_ids)
