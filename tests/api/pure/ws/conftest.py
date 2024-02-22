import pytest

from experts.api.pure.ws import Client

@pytest.fixture(scope="module")
def session():
    with Client() as session:
        yield session
