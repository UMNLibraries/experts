import pytest

from experts.api.pure.ws import Client

@pytest.fixture(scope="module")
def client():
    with Client() as client:
        yield client
