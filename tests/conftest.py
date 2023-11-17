from pathlib import Path
import pytest
import sys

import dotenv_switch.auto

package_path = Path(__file__).parents[1]
sys.path.append(str(package_path))

import experts.api.client as client
import experts.api.pure.web_services.context as pure_ws_context
import experts.api.scopus.context as scopus_context

@pytest.fixture(scope="module")
def pure_ws_session():
    with client.session(pure_ws_context.Context()) as session:
        yield session

def pytest_addoption(parser):
    parser.addoption(
        '--integration',
        action='store_true',
        default=False,
        help='Run integration tests. Requires env var config. See README.'
    )

def pytest_configure(config):
    config.addinivalue_line('markers', 'integration: mark test as an integration test')

def pytest_collection_modifyitems(config, items):
    if config.getoption('--integration'):
        # --integration given in cli: do not skip integration tests
        return
    skip_integration = pytest.mark.skip(reason='need --integration option to run')
    for item in items:
        if 'integration' in item.keywords:
            item.add_marker(skip_integration)
