# experts

Integration applications for [Experts@Minnesota](https://experts.umn.edu)

## Testing

We use pytest, which can be run multiple ways given our use of poetry:
After first running `source .venv/bin/activate` or `poetry shell`, or as
arguments to `poetry run`.

There are multiple modules in this repository, some with tests that may
take a long time to finish. So it will be faster to run only tests for
certain modules and parts of the repository. The `tests` sub-directories
mirror the `experts` sub-directories. That makes it easy to run a subset
of tests, by running only the tests in a sub-directory.

For example, to run only the Scopus API tests:

`pytest tests/api/scopus/test_*.py`

Similarly, to run only the Pure Web Services tests:

`pytest tests/api/pure/web_services/test_*.py`

Or to run all tests: `pytest`

Note that some tests include integration tests do things like make requests
against a vendor API server. To run those tests, pass the `--integration` option
to pytest.

