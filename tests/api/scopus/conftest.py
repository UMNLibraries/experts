import pytest

from experts.api.scopus import Client

@pytest.fixture(scope="module")
def session():
    with Client() as session:
        yield session
