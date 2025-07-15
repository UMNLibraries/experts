from datetime import date
import json
import pytest

from experts.api.scopus import \
    CitationOverviewResponseBodyParser as parser

def load_response_body(scopus_ids: str):
    with open(f'tests/api/scopus/data/citation_overview/{scopus_ids}.json') as body_file:
        return json.load(body_file)

def test_parser():
    scopus_ids_to_expected_citations = {
        '84876222028': {
            'column_heading': [{'$': '2023'}, {'$': '2024'}, {'$': '2025'}],
            'identifiers': {'@_fa': 'true', 'dc:identifier': 'SCOPUS_ID:84876222028', 'prism:doi': '10.1016/j.cell.2013.03.036', 'pii': 'S0092867413003930', 'scopus_id': '84876222028'},
            'cite_info': {'@_fa': 'true', 'dc:identifier': 'SCOPUS_ID:84876222028', 'prism:url': 'https://api.elsevier.com/content/abstract/scopus_id/84876222028', 'dc:title': 'Selective inhibition of tumor oncogenes by disruption of super-enhancers', 'author': [{'@_fa': 'true', 'initials': None, 'index-name': None, 'surname': None, 'authid': None, 'author-url': 'https://api.elsevier.com/content/author/author_id/'}], 'citationType': {'@code': 'ar', '$': 'Article'}, 'sort-year': '2013', 'sortTitle': 'Cell', 'prism:volume': '153', 'prism:issueIdentifier': '2', 'prism:startingPage': '320', 'prism:endingPage': '334', 'prism:issn': '0092-8674', 'pcc': '1671', 'cc': [{'$': '202'}, {'$': '175'}, {'$': '93'}], 'lcc': '0', 'rangeCount': '470', 'rowTotal': '2141'},
        },
        '33644930319': {
            'column_heading': [{'$': '2023'}, {'$': '2024'}, {'$': '2025'}],
            'identifiers': {'@_fa': 'true', 'dc:identifier': 'SCOPUS_ID:33644930319', 'prism:doi': '10.1007/s00217-005-0147-2', 'pii': None, 'scopus_id': '33644930319'},
            'cite_info': {'@_fa': 'true', 'dc:identifier': 'SCOPUS_ID:33644930319', 'prism:url': 'https://api.elsevier.com/content/abstract/scopus_id/33644930319', 'dc:title': 'Antihypertensive effect of alcalase generated mung bean protein hydrolysates in spontaneously hypertensive rats', 'author': [{'@_fa': 'true', 'initials': None, 'index-name': None, 'surname': None, 'authid': None, 'author-url': 'https://api.elsevier.com/content/author/author_id/'}], 'citationType': {'@code': 'ar', '$': 'Article'}, 'sort-year': '2006', 'sortTitle': 'European Food Research and Technology', 'prism:volume': '222', 'prism:issueIdentifier': '5-6', 'prism:startingPage': '733', 'prism:endingPage': '736', 'prism:issn': '1438-2377', 'pcc': '49', 'cc': [{'$': '3'}, {'$': '5'}, {'$': '1'}], 'lcc': '0', 'rangeCount': '9', 'rowTotal': '58'},
        },
        '85199124578': {
            'column_heading': [{'$': '2023'}, {'$': '2024'}, {'$': '2025'}],
            'identifiers': {'@_fa': 'true', 'dc:identifier': 'SCOPUS_ID:85199124578', 'prism:doi': '10.7326/M23-2865', 'pii': None, 'scopus_id': '85199124578'},
            'cite_info': {'@_fa': 'true', 'dc:identifier': 'SCOPUS_ID:85199124578', 'prism:url': 'https://api.elsevier.com/content/abstract/scopus_id/85199124578', 'dc:title': 'Computer-Aided Diagnosis for Leaving Colorectal Polyps In Situ A Systematic Review and Meta-analysis', 'author': [{'@_fa': 'true', 'initials': None, 'index-name': None, 'surname': None, 'authid': None, 'author-url': 'https://api.elsevier.com/content/author/author_id/'}], 'citationType': {'@code': 're', '$': 'Review'}, 'sort-year': '2024', 'sortTitle': 'Annals of Internal Medicine', 'prism:volume': '177', 'prism:issueIdentifier': '7', 'prism:startingPage': '919', 'prism:endingPage': '928', 'prism:issn': '0003-4819', 'pcc': '0', 'cc': [{'$': '0'}, {'$': '2'}, {'$': '6'}], 'lcc': '0', 'rangeCount': '8', 'rowTotal': '8'},
        },
    }

    # Verify that parsing a single record response body is successful, and store the
    # results for comparison below:
    downloaded_single_record_bodies = {}
    for scopus_id, expected_citation in scopus_ids_to_expected_citations.items():
        body = load_response_body(scopus_id)
        assert parser.column_heading(body) == expected_citation['column_heading']
        assert next(parser.identifier_subrecords(body)) == expected_citation['identifiers']
        assert next(parser.cite_info_subrecords(body)) == expected_citation['cite_info']
        downloaded_single_record_bodies[scopus_id] = body

    # Parse single records out of a multiple record response body, to reconstruct the equivalents
    # of single record response bodies:
    scopus_ids_string = ','.join(scopus_ids_to_expected_citations.keys())
    downloaded_multiple_record_body = load_response_body(scopus_ids_string)
    reconstructed_single_record_bodies = {}
    for body in parser.subrecords(downloaded_multiple_record_body):
        identifiers = next(parser.identifier_subrecords(body))
        reconstructed_single_record_bodies[identifiers['scopus_id']] = body

    # Verify that we have successfully reconstructed single records from a multiple record response body:
    assert downloaded_single_record_bodies == reconstructed_single_record_bodies
