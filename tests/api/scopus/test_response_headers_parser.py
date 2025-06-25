from datetime import date, datetime
from importlib import import_module

from dateutil.tz import tzutc
import httpx
import pytest

from experts.api.scopus import ResponseHeadersParser as parser

all_scopus_ids = [
    '49949145584',
    '75149190029',
    '84924664029',
]
headers_inputs = {
    scopus_id: import_module(f'..data.abstract.{scopus_id}.headers', package=__name__)
    for scopus_id in all_scopus_ids
}

@pytest.fixture(params=all_scopus_ids)
def httpx_headers(request):
    yield httpx.Headers(headers_inputs[request.param].headers)

def test_parser(httpx_headers):
    assert isinstance(parser.ratelimit(httpx_headers), int)
    assert isinstance(parser.ratelimit_remaining(httpx_headers), int)
    assert isinstance(parser.ratelimit_reset(httpx_headers), datetime)
    assert isinstance(parser.last_modified(httpx_headers), datetime)

def test_parser_specific_values():
    httpx_headers = httpx.Headers(headers_inputs['49949145584'].headers)
    assert parser.ratelimit(httpx_headers) == 100000
    assert parser.ratelimit_remaining(httpx_headers) == 99861
    assert parser.ratelimit_reset(httpx_headers) == datetime(2024, 7, 23, 1, 33, 21)
    assert parser.last_modified(httpx_headers) == datetime(2020, 5, 17, 16, 47, 3, tzinfo=tzutc())
