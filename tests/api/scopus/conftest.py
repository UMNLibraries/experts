import pytest

from experts.api import scopus

@pytest.fixture(scope="module")
def client():
    with scopus.Client() as client:
        yield client
