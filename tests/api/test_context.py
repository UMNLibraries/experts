from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

import importlib
import os

import pytest
from pyrsistent import m, pmap

#from pureapi import common
import experts.api.pure.web_services.context as pure_ws_context
import experts.api.scopus.context as scopus_context

def test_pure_ws_offset_request_params_parser():
    params = m(size=1000, offset=0)
    pure_ws_params_parser = pure_ws_context.OffsetRequestParamsParser
    assert pure_ws_params_parser.items_per_page(params) == params.get('size')
    assert pure_ws_params_parser.offset(params) == params.get('offset')

    empty_params = m()
    assert pure_ws_params_parser.items_per_page(empty_params) == None
    assert pure_ws_params_parser.offset(empty_params) == None

    new_offset = 10

    updated_params = pure_ws_params_parser.update_offset(empty_params, new_offset)
    assert pure_ws_params_parser.offset(updated_params) == new_offset
    assert updated_params.get('offset') == new_offset

    # Original params should be unchanged:
    assert pure_ws_params_parser.offset(empty_params) == None
    assert empty_params.get('offset') == None

def test_scopus_offset_request_params_parser():
    params = m(count=1000, start=0)
    scopus_params_parser = scopus_context.OffsetRequestParamsParser
    assert scopus_params_parser.items_per_page(params) == params.get('count')
    assert scopus_params_parser.offset(params) == params.get('start')

    empty_params = m()
    assert scopus_params_parser.items_per_page(empty_params) == None
    assert scopus_params_parser.offset(empty_params) == None

    new_offset = 10

    updated_params = scopus_params_parser.update_offset(empty_params, new_offset)
    assert scopus_params_parser.offset(updated_params) == new_offset
    assert updated_params.get('start') == new_offset

    # Original params should be unchanged:
    assert scopus_params_parser.offset(empty_params) == None
    assert empty_params.get('start') == None

        

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
