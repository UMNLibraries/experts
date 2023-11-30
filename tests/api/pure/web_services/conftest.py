import pytest

import experts.api.client as client
import experts.api.pure.web_services.context as context

@pytest.fixture(scope="module")
def session():
    with client.session(context.Context()) as session:
        yield session
