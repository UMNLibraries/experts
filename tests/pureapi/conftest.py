import pytest
from experts.pureapi import common

@pytest.fixture(params=common.versions)
def version(request):
    return request.param
