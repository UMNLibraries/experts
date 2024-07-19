from datetime import date, datetime
import importlib

import httpx
import pytest
from pyrsistent import m, pmap
from returns.pipeline import is_successful

from experts.api.scopus import \
    ResponseParser as r_parser, \
    ResponseHeadersParser as rh_parser, \
    AbstractResponseBodyParser as arb_parser

@pytest.mark.integration
def test_basic_abstract_retrieval_and_parsing(session):
    umn_article_scopus_id = '84924664029'

    # Test more generic functions first:

    params = m(content='core', view='FULL')
    result = session.get(f'abstract/scopus_id/{umn_article_scopus_id}', params=params)
    if not is_successful(result):
        raise result.failure()
    umn_article_body = r_parser.body(result.unwrap())

    # A few sanity check assertions while we gather some data:
    assert arb_parser.scopus_id(umn_article_body) == umn_article_scopus_id
    refcount = arb_parser.refcount(umn_article_body)
    assert refcount > 50 # Should actually be 60, unless the metadata changes
    reference_scopus_ids = sorted(arb_parser.reference_scopus_ids(umn_article_body))
    assert len(reference_scopus_ids) == refcount

    downloaded_reference_scopus_ids = []
    for headers, body in session.request_many_by_id(
        session.get,
        'abstract',
        id_type='scopus_id',
        ids=reference_scopus_ids,
        params=params
    ) | r_parser.responses_to_headers_bodies:
        assert isinstance(headers, httpx.Headers)
        scopus_id = arb_parser.scopus_id(body)
        assert scopus_id in reference_scopus_ids
        downloaded_reference_scopus_ids.append(scopus_id)

    assert len(downloaded_reference_scopus_ids) <= refcount
    # This _should_ be true; should be about 59. We don't test for equality because
    # some cited articles are unavailable via the API.
    assert len(downloaded_reference_scopus_ids) > (refcount - 5)

    # Test abstract-specific functions making the same requests:

    abstract_specific_result = session.get_abstract_by_scopus_id(umn_article_scopus_id)
    if not is_successful(abstract_specific_result):
        raise abstract_specific_result.failure()
    abstract_specific_body = r_parser.body(abstract_specific_result.unwrap())

    assert abstract_specific_body == umn_article_body

    downloaded_abstract_specific_reference_scopus_ids = []
    for body in session.get_many_abstracts_by_scopus_id(
        scopus_ids=reference_scopus_ids,
    ) | r_parser.responses_to_bodies:
        downloaded_abstract_specific_reference_scopus_ids.append(
            arb_parser.scopus_id(body)
        )

    assert sorted(downloaded_abstract_specific_reference_scopus_ids) == sorted(downloaded_reference_scopus_ids)

def test_abstract_specific_pipes(session):
    umn_article_scopus_ids = [
        '84924664029',
        '75149190029',
        '49949145584',
    ]
    # Based on previously downloaded records in data/:
    total_reference_scopus_ids = 167

    two_pipe_multi_umn_article_reference_scopus_ids = list(
        session.get_many_abstracts_by_scopus_id(
            scopus_ids=umn_article_scopus_ids,
        )
        | r_parser.responses_to_bodies
        | arb_parser.bodies_to_reference_scopus_ids
    )

    one_pipe_multi_umn_article_reference_scopus_ids = list(
        session.get_many_abstracts_by_scopus_id(
            scopus_ids=umn_article_scopus_ids,
        )
        | arb_parser.responses_to_reference_scopus_ids
    )

    assert sorted(one_pipe_multi_umn_article_reference_scopus_ids) == sorted(two_pipe_multi_umn_article_reference_scopus_ids)
    assert len(one_pipe_multi_umn_article_reference_scopus_ids) <= total_reference_scopus_ids
    # This _should_ be true. We don't test for equality because some cited articles are unavailable via the API.
    assert len(one_pipe_multi_umn_article_reference_scopus_ids) > (total_reference_scopus_ids - 10)
