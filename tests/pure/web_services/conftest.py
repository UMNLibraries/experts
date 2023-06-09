import pytest
from experts.pure.web_services import common

@pytest.fixture(params=common.versions)
def version(request):
    return request.param
