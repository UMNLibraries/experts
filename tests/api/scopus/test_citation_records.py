from datetime import datetime
import json
import pytest

from pyrsistent import thaw

from experts.api.scopus import \
    CitationMaybeMultiRecord, \
    CitationSingleRecord, \
    ScopusId

def load_response_body(scopus_ids: str):
    with open(f'tests/api/scopus/data/citation/{scopus_ids}.json') as body_file:
        return json.load(body_file)

def test_parser():
    scopus_ids_to_expected_citation_values = {
        '84876222028': {
            'sort_year': datetime.strptime('2013', '%Y'),
            'column_heading': [{'$': '2023'}, {'$': '2024'}, {'$': '2025'}],
            'identifiers': {'@_fa': 'true', 'dc:identifier': 'SCOPUS_ID:84876222028', 'prism:doi': '10.1016/j.cell.2013.03.036', 'pii': 'S0092867413003930', 'scopus_id': '84876222028'},
            'cite_info': {'@_fa': 'true', 'dc:identifier': 'SCOPUS_ID:84876222028', 'prism:url': 'https://api.elsevier.com/content/abstract/scopus_id/84876222028', 'dc:title': 'Selective inhibition of tumor oncogenes by disruption of super-enhancers', 'author': [{'@_fa': 'true', 'initials': None, 'index-name': None, 'surname': None, 'authid': None, 'author-url': 'https://api.elsevier.com/content/author/author_id/'}], 'citationType': {'@code': 'ar', '$': 'Article'}, 'sort-year': '2013', 'sortTitle': 'Cell', 'prism:volume': '153', 'prism:issueIdentifier': '2', 'prism:startingPage': '320', 'prism:endingPage': '334', 'prism:issn': '0092-8674', 'pcc': '1671', 'cc': [{'$': '202'}, {'$': '175'}, {'$': '93'}], 'lcc': '0', 'rangeCount': '470', 'rowTotal': '2141'},
        },
        '33644930319': {
            'sort_year': datetime.strptime('2006', '%Y'),
            'column_heading': [{'$': '2023'}, {'$': '2024'}, {'$': '2025'}],
            'identifiers': {'@_fa': 'true', 'dc:identifier': 'SCOPUS_ID:33644930319', 'prism:doi': '10.1007/s00217-005-0147-2', 'pii': None, 'scopus_id': '33644930319'},
            'cite_info': {'@_fa': 'true', 'dc:identifier': 'SCOPUS_ID:33644930319', 'prism:url': 'https://api.elsevier.com/content/abstract/scopus_id/33644930319', 'dc:title': 'Antihypertensive effect of alcalase generated mung bean protein hydrolysates in spontaneously hypertensive rats', 'author': [{'@_fa': 'true', 'initials': None, 'index-name': None, 'surname': None, 'authid': None, 'author-url': 'https://api.elsevier.com/content/author/author_id/'}], 'citationType': {'@code': 'ar', '$': 'Article'}, 'sort-year': '2006', 'sortTitle': 'European Food Research and Technology', 'prism:volume': '222', 'prism:issueIdentifier': '5-6', 'prism:startingPage': '733', 'prism:endingPage': '736', 'prism:issn': '1438-2377', 'pcc': '49', 'cc': [{'$': '3'}, {'$': '5'}, {'$': '1'}], 'lcc': '0', 'rangeCount': '9', 'rowTotal': '58'},
        },
        '85199124578': {
            'sort_year': datetime.strptime('2024', '%Y'),
            'column_heading': [{'$': '2023'}, {'$': '2024'}, {'$': '2025'}],
            'identifiers': {'@_fa': 'true', 'dc:identifier': 'SCOPUS_ID:85199124578', 'prism:doi': '10.7326/M23-2865', 'pii': None, 'scopus_id': '85199124578'},
            'cite_info': {'@_fa': 'true', 'dc:identifier': 'SCOPUS_ID:85199124578', 'prism:url': 'https://api.elsevier.com/content/abstract/scopus_id/85199124578', 'dc:title': 'Computer-Aided Diagnosis for Leaving Colorectal Polyps In Situ A Systematic Review and Meta-analysis', 'author': [{'@_fa': 'true', 'initials': None, 'index-name': None, 'surname': None, 'authid': None, 'author-url': 'https://api.elsevier.com/content/author/author_id/'}], 'citationType': {'@code': 're', '$': 'Review'}, 'sort-year': '2024', 'sortTitle': 'Annals of Internal Medicine', 'prism:volume': '177', 'prism:issueIdentifier': '7', 'prism:startingPage': '919', 'prism:endingPage': '928', 'prism:issn': '0003-4819', 'pcc': '0', 'cc': [{'$': '0'}, {'$': '2'}, {'$': '6'}], 'lcc': '0', 'rangeCount': '8', 'rowTotal': '8'},
        },
    }

    downloaded_single_record_body_dicts = {}
    for scopus_id_str, expected_citation_values in scopus_ids_to_expected_citation_values.items():
        body_dict = load_response_body(scopus_id_str)
        # Store the body dict for later comparison:
        downloaded_single_record_body_dicts[scopus_id_str] = body_dict

        # Verify that parsing the body dict gives the expected values:

        single_record = CitationSingleRecord(body_dict)
        assert single_record.scopus_id == ScopusId(scopus_id_str)
        assert single_record.sort_year == expected_citation_values['sort_year']

        # There will be only one column heading, and it will be the same for all records
        # within a single- or multi-record citation response:
        assert single_record._column_heading == expected_citation_values['column_heading']

        # The identifier and cite_info subrecords are both lists of dicts, one dict for each single record.
        # Therefore, these lists will each have only one dict for a single-record response:
        assert len(single_record._identifier_subrecords) == 1
        assert single_record._identifier_subrecords[0] == expected_citation_values['identifiers']
        assert len(single_record._cite_info_subrecords) == 1
        assert single_record._cite_info_subrecords[0] == expected_citation_values['cite_info']


    # Parse single records out of a multi-record-response body dict, to reconstruct the equivalents
    # of single-record-response body dicts captured above:
    scopus_ids_str = ','.join(scopus_ids_to_expected_citation_values.keys())
    downloaded_multi_record_body_dict = load_response_body(scopus_ids_str)
    multi_record = CitationMaybeMultiRecord(downloaded_multi_record_body_dict)
    reconstructed_single_record_body_dicts = {
        single_record.scopus_id: thaw(single_record)
        for single_record in multi_record.single_records
    }

    # Verify that we have successfully reconstructed single records from a multiple-record-response body dict:
    assert downloaded_single_record_body_dicts == reconstructed_single_record_body_dicts
