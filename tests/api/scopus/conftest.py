import pytest

import experts.api.client as client
import experts.api.scopus.context as context

@pytest.fixture(scope="module")
def session():
    with client.session(context.Context()) as session:
        yield session
