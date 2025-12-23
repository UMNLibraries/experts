import pytest

from experts.api.pure.ws import \
    OffsetResponseBodyParser, \
    TokenResponseBodyParser

def test_offset_response_body_parser():
    response = {
        'count': 1271,
        'pageInformation': {
            'offset': 0,
            'size': 10,
        },
        'items': [
            {'foo': 1},
            {'bar': 2},
            {'baz': 3},
        ]
    }        
    parser = OffsetResponseBodyParser
    assert parser.total_items(response) == response['count']
    assert parser.offset(response) == response['pageInformation']['offset']
    assert parser.items_per_page(response) == response['pageInformation']['size']
    assert parser.items(response) == response['items']

def test_token_response_body_parser():
    parser = TokenResponseBodyParser
    response1 = {
        "count": 3,
        "resumptionToken": "eyJzZXF1ZW5jZU51bWJlciI6MTk0MTM1MzcyfQ==",
        "moreChanges": True,
        "items": [
            {
                "uuid": "d09e017d-4e1d-403c-a703-6c3d11b039b4",
                "changeType": "UPDATE",
                "family": "dk.atira.pure.api.shared.contentimport.model.ImportResult",
                "familySystemName": "ImportResult",
                "version": -1
            },
            {
                "uuid": "d09e017d-4e1d-403c-a703-6c3d11b039b4",
                "changeType": "UPDATE",
                "family": "dk.atira.pure.api.shared.contentimport.model.ImportResult",
                "familySystemName": "ImportResult",
                "version": -1
            },
            {
                "uuid": "d09e017d-4e1d-403c-a703-6c3d11b039b4",
                "changeType": "UPDATE",
                "family": "dk.atira.pure.api.shared.contentimport.model.ImportResult",
                "familySystemName": "ImportResult",
                "version": -1
            },
        ],
        "navigationLinks": [
            {
                "ref": "next",
                "href": "https://experts.umn.edu/ws/api/516/changes/eyJzZXF1ZW5jZU51bWJlciI6MTk0MTM1MzcyfQ=="
            },
        ],
    }
    assert parser.items_per_page(response1) == response1['count']
    assert parser.token(response1) == response1['resumptionToken']
    assert parser.more_items(response1) == response1['moreChanges']
    assert parser.more_items(response1) == True
    assert parser.items(response1) == response1['items']

    response2 = {
        "count": 0,
        "resumptionToken": "eyJzZXF1ZW5jZU51bWJlciI6MTk0MTM1NDcyfQ==",
        "moreChanges": True,
        "navigationLinks": [
            {
                "ref": "next",
                "href": "https://experts.umn.edu/ws/api/516/changes/eyJzZXF1ZW5jZU51bWJlciI6MTk0MTM1NDcyfQ=="
            }
        ]
    }
    assert parser.items_per_page(response2) == response2['count']
    assert parser.token(response2) == response2['resumptionToken']
    assert parser.more_items(response2) == response2['moreChanges']
    assert parser.more_items(response2) == True
    assert parser.items(response2) == []

    response3 = {
        "count": 3,
        "resumptionToken": "eyJzZXF1ZW5jZU51bWJlciI6MTk0MTM1NzcyfQ==",
        "moreChanges": False,
        "items": [
            {
                "uuid": "67073a6c-e84a-470f-9b45-d780cfe0d7cc",
                "changeType": "UPDATE",
                "family": "dk.atira.pure.api.shared.model.researchoutput.ResearchOutput",
                "familySystemName": "ResearchOutput",
                "version": 3
            },
            {
                "uuid": "960c880e-4835-4850-9461-d0415c57abd4",
                "changeType": "UPDATE",
                "family": "dk.atira.pure.api.shared.model.researchoutput.ResearchOutput",
                "familySystemName": "ResearchOutput",
                "version": 7
            },
            {
                "uuid": "35890d58-587a-4b59-a258-c7a70a1e49dd",
                "changeType": "UPDATE",
                "family": "dk.atira.pure.api.shared.model.researchoutput.ResearchOutput",
                "familySystemName": "ResearchOutput",
                "version": 2
            },
        ],
        "navigationLinks": [
            {
                "ref": "next",
                "href": "https://experts.umn.edu/ws/api/516/changes/eyJzZXF1ZW5jZU51bWJlciI6MTk0MTM1NzcyfQ=="
            },
        ],
    }
    assert parser.items_per_page(response3) == response3['count']
    assert parser.token(response3) == response3['resumptionToken']
    assert parser.more_items(response3) == response3['moreChanges']
    assert parser.more_items(response3) == False
    assert parser.items(response3) == response3['items']
