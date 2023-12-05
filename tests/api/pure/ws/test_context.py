#import importlib
#import os

import pytest
from pyrsistent import m

#from pureapi import common
import experts.api.pure.ws.context as context

def test_offset_request_params_parser():
    params = m(size=1000, offset=0)
    parser = context.OffsetRequestParamsParser
    assert parser.items_per_page(params) == params.get('size')
    assert parser.offset(params) == params.get('offset')

    empty_params = m()
    assert parser.items_per_page(empty_params) == None
    assert parser.offset(empty_params) == None

    new_offset = 10

    updated_params = parser.update_offset(empty_params, new_offset)
    assert parser.offset(updated_params) == new_offset
    assert updated_params.get('offset') == new_offset

    # Original params should be unchanged:
    assert parser.offset(empty_params) == None
    assert empty_params.get('offset') == None

def test_offset_response_parser():
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
    parser = context.OffsetResponseParser
    assert parser.total_items(response) == response['count']
    assert parser.offset(response) == response['pageInformation']['offset']
    assert parser.items_per_page(response) == response['pageInformation']['size']
    assert parser.items(response) == response['items']

def test_token_response_parser():
    parser = context.TokenResponseParser
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

#def test_valid_version():
#    versions = common.versions
#    assert len(versions) > 0
#    assert all(common.valid_version(version) for version in versions)
#    assert not common.valid_version('bogus')
#
#def test_default_version():
#    assert common.default_version() in common.versions
#    assert common.valid_version(common.default_version())
#
#def test_latest_version():
#    assert common.latest_version in common.versions
#    assert common.valid_version(common.latest_version)
#
#@pytest.mark.forked
#def test_env_version_is_none():
#    if common.env_version_varname in os.environ:
#        os.environ.pop(common.env_version_varname)
#        importlib.reload(common)
#
#    assert common.env_version() is None
#    assert common.default_version() == common.latest_version
#
#@pytest.mark.forked
#def test_env_version_is_not_none():
#    os.environ[common.env_version_varname] = common.latest_version
#    importlib.reload(common)
#
#    assert common.env_version() == os.environ.get(common.env_version_varname)
#    assert common.env_version() == common.latest_version
#    assert common.default_version() == common.env_version()
#
#@pytest.mark.forked
#def test_default_version_override():
#    if common.oldest_version != common.latest_version:
#        os.environ[common.env_version_varname] = common.oldest_version
#        importlib.reload(common)
#
#        assert common.env_version() == os.environ.get(common.env_version_varname)
#        assert common.env_version() == common.oldest_version
#        assert common.default_version() == common.env_version()
#
#def test_schemas_for_all_versions():
#    assert all(len(common.schema_for(version=version)) for version in common.versions)
#    with pytest.raises(common.PureAPIInvalidVersionError):
#        schema = common.schema_for(version='bogus')
#
#def test_collections_for_all_versions():
#    for version in common.versions:
#        collections = common.collections_for(version=version)
#        assert len(collections) > 0
#        for collection in collections:
#            assert common.valid_collection(collection=collection, version=version)
#        assert not common.valid_collection(collection='bogus', version=version)
#        with pytest.raises(common.PureAPIInvalidVersionError):
#            collections = common.collections_for(version='bogus')
