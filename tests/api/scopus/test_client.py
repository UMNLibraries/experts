from datetime import date, datetime

from functools import reduce
import importlib

import httpx
import pytest
from pyrsistent import m, pmap
from returns.result import Result, Success, Failure

from experts.api.scopus import \
    AbstractAssortedResults, \
    AbstractRequestResult, \
    AbstractRequestSuccess, \
    AbstractRequestFailure, \
    AbstractRequestResponseDefunct, \
    AbstractRecord, \
    CitationAssortedResults, \
    CitationRequestResult, \
    CitationRequestSuccess, \
    CitationRequestFailure, \
    CitationRequestResponseDefunct, \
    CitationMaybeMultiRecord, \
    CitationSingleRecord, \
    ScopusId, \
    ScopusIds, \
    CitationRequestScopusIds

@pytest.mark.integration
def test_low_level_abstract_retrieval(client):
    scopus_id = '84924664029'
    params = m(content='core', view='FULL')

    match client.get(f'abstract/scopus_id/{scopus_id}', params=params):
        case Success(response):
            assert response.status_code == 200
        case Failure(exception_should_not_happen):
            raise exception_should_not_happen

    match AbstractRecord.factory(response.json()):
        case Success(record):
            assert record.scopus_id == scopus_id
            assert record.refcount > 50 # Should actually be 60, unless the metadata changes
        case Failure(exception_should_not_happen):
            raise exception_should_not_happen

    bogus_scopus_id = '000000000000' # Just guessed that this ID doesn't exist, which appears to be correct
    match client.get(f'abstract/scopus_id/{bogus_scopus_id}', params=params):
        case Success(response_for_nonexistent_scopus_id):
            assert response_for_nonexistent_scopus_id.status_code == 404
        case Failure(unexpected_failure):
            raise Exception(f'This is not the expected failure result for a non-existent Scopus ID: {unexpected_failure}')

@pytest.mark.integration
def test_get_abstract_by_scopus_id(client):
    scopus_id = ScopusId('84924664029')

    #abstract_request_result = client.get_abstract_by_scopus_id(scopus_id)
    #assert isinstance(abstract_request_result, AbstractRequestResult)
    # The above commented-out code generates the following error:
    # TypeError: Subscripted generics cannot be used with class and instance checks
    #match abstract_request_result:

    match client.get_abstract_by_scopus_id(scopus_id):
        #case Success(AbstractRequestSuccess(result)):
        # The above commented-out code generates the following error:
        # TypeError: AbstractRequestSuccess() accepts 0 positional sub-patterns (1 given) 

        #case Success(AbstractRequestSuccess()) as result:
        # The above commented-out code generates the following error:
        # AttributeError: 'Success' object has no attribute 'ratelimit'

        # The following does not work: No cases match!
        #case AbstractRequestSuccess() as result:

        # The following works!
        case Success(AbstractRequestSuccess() as result):
            assert result.response.status_code == 200

            # Not sure we really need these...
            assert isinstance(result.ratelimit, int)
            assert isinstance(result.ratelimit_remaining, int)
            assert isinstance(result.ratelimit_reset, datetime)
            assert isinstance(result.last_modified, datetime)

            assert isinstance(result.record, AbstractRecord)
            assert result.requested_scopus_id == result.record.scopus_id == scopus_id
            assert result.record.refcount > 50 # Should actually be 60, unless the metadata changes
        case Failure(AbstractRequestFailure() as should_not_happen):
            raise Exception(f'Request for Scopus ID {scopus_id} failed: {should_not_happen}')
        case _:
            raise Exception(f'WTF? The above two cases should be the only possible cases.')

    bogus_scopus_id = ScopusId('000000000000') # Just guessed that this ID doesn't exist, which appears to be correct
    match client.get_abstract_by_scopus_id(bogus_scopus_id):
        case Success(AbstractRequestSuccess() as should_not_exist):
            raise Exception(f'Request for non-existent Scopus ID {bogus_scopus_id} successfully returned a result: {should_not_exist}')
        case Failure(AbstractRequestResponseDefunct() as defunct_result):
            assert defunct_result.response.status_code == 404
            assert defunct_result.requested_scopus_id == bogus_scopus_id
        case Failure(AbstractRequestFailure() as unexpected_failure):
            raise Exception(f'This is not the expected failure result for a non-existent Scopus ID: {unexpected_failure}')

@pytest.mark.integration
def test_get_many_abstracts_by_scopus_id(client):
    # These should all be validly formatted Scopus IDs, but the last one does not exist:
    bogus_scopus_id = '000000000000'
    scopus_ids, invalid_scopus_ids = ScopusIds.factory(['84924664029','84876222028','33644930319','85199124578',bogus_scopus_id])
    # Others to include?
#        '75149190029',
#        '85150001360',
#        '49949145584',
#        '84924664029',
#        '85159902125',

    for result in client.get_many_abstracts_by_scopus_id(scopus_ids):
        match result:
            case Failure(AbstractRequestResponseDefunct() as defunct_result):
                assert defunct_result.response.status_code == 404
                assert defunct_result.requested_scopus_id == bogus_scopus_id
            case Success(AbstractRequestSuccess() as success_result):
                assert success_result.response.status_code == 200
                assert success_result.requested_scopus_id == success_result.record.scopus_id

@pytest.mark.integration
def test_low_level_citation_retrieval(client):
    scopus_ids = ['84876222028','33644930319','85199124578']
    params = m(citation='exclude-self')

    match client.get(f'abstract/citations', params=params.set('scopus_id', ','.join(scopus_ids))):
        case Success(response):
            assert response.status_code == 200
        case Failure(exception):
            raise exception

    match CitationMaybeMultiRecord.factory(response.json()):
        case Success(record):
            assert record.scopus_ids == set(scopus_ids)
            assert len(record.single_records) == len(scopus_ids)
        case Failure(exception):
            raise exception

    bogus_scopus_ids = ['000000000000','000000000001','000000000002'] # Just guessed that these IDs don't exist, which appears to be correct
    match client.get(f'abstract/citations', params=params.set('scopus_id', ','.join(bogus_scopus_ids))):
        case Success(should_not_exist):
            assert should_not_exist.status_code == 404
        case Failure(unexpected_failure):
            raise Exception(f'This is not the expected failure result for non-existent Scopus IDs: {unexpected_failure}')

@pytest.mark.integration
def test_get_citations_by_scopus_ids(client):
    scopus_ids_sets, invalid_scopus_ids = CitationRequestScopusIds.factory(['84876222028','33644930319','85199124578'])
    assert len(invalid_scopus_ids) == 0
    # Should be only one of these, since the list is so short:
    scopus_ids = scopus_ids_sets[0]
    assert isinstance(scopus_ids, CitationRequestScopusIds)

    match client.get_citations_by_scopus_ids(scopus_ids):
        case Success(CitationRequestSuccess() as result):
            assert result.response.status_code == 200
            assert isinstance(result.record, CitationMaybeMultiRecord)
            assert result.requested_scopus_ids == result.record.scopus_ids == scopus_ids
        case Failure(CitationRequestFailure() as should_not_happen):
            raise Exception(f'Request for Scopus IDs {scopus_ids} failed: {should_not_happen}')
        case _:
            raise Exception(f'WTF? The above two cases should be the only possible cases.')

    bogus_scopus_ids_sets, _ = CitationRequestScopusIds.factory(['000000000000','000000000001','000000000002']) # Just guessed that this ID doesn't exist, which appears to be correct
    bogus_scopus_ids = bogus_scopus_ids_sets[0]
    match client.get_citations_by_scopus_ids(bogus_scopus_ids):
        case Success(CitationRequestSuccess() as should_not_happen):
            raise Exception(f'Request for non-existent Scopus IDs {bogus_scopus_ids} successfully returned a result: {should_not_happen}')
        case Failure(CitationRequestResponseDefunct() as defunct_result):
            assert defunct_result.response.status_code == 404
            assert defunct_result.requested_scopus_ids == bogus_scopus_ids
        case Failure(CitationRequestFailure() as unexpected_failure):
            raise Exception(f'This is not the expected failure result for non-existent Scopus IDs: {unexpected_failure}')

@pytest.mark.integration
def test_get_many_citations_by_scopus_ids(client):
    # These should all be validly formatted Scopus IDs
    scopus_ids, invalid_scopus_ids = ScopusIds.factory(['0018873523', '0033957644', '0018068188', '85099981690', '84939961237', '6044228166', '84983881625', '85100561827', '0000861325', '0343266523', '0037349974', '0019449167', '0017119520', '85159920478', '0000229676', '85082704352', '0017664068', '0001390371', '77956241535', '84857258987', '0018600670', '0029796506', '84930225727', '0041683074', '75149113747', '51049097278', '0025790578', '37249013057', '85122905075', '0031709570', '85102185869', '27644495679', '0028809235', '0002773005', '78650988594', '31344453213', '0142190895', '0020868654', '0017059521', '0023263192', '43049107998', '85056654979', '33748750527', '0020363237', '20644454642', '0004268574', '85103204629', '85122002920', '81155153943', '65649129982', '58149520312', '0030606673', '85159891516', '0035064106', '85098051712', '0027442756', '0030486803', '0036302694', '0017196510', '85159876368', '0016481815', '79960608008', '0842348566', '75149191551', '84872615699', '0001809347', '32344435383', '85055973966', '75149120759', '84887399153', '0036904545', '0021215560', '75149141059', '0032395508', '84922907673', '0018614873', '85088829812', '0008254515', '0021840653', '0023841222', '35348862011', '0004918111', '77957195151', '77956779075', '33747148101', '85159863404', '0032901676', '69749127975', '85079355692', '0038267769', '0022491873', '33644930319', '0009580310', '3543100683', '70349956437', '50649094650', '70849102291', '33746531279', '0025662256', '85159910655', '77749277164', '85082324832', '0035874457', '38249026510', '0042732573', '0024901172', '0019136209', '75149157713', '75149131091', '0031941559', '0022879443', '85122016198', '85159892537', '85159926163', '0026933670', '34548162029', '0021062922', '0037409169', '36849082448', '0028315524', '27744516236', '34147123803', '0035142087', '0033014549', '0003072959', '0018072125', '77950928423', '9644279954', '0030428626', '0032760778', '85033502968', '0033611305', '0004149691', '0000180578', '0017889854', '85159871688', '0029972849', '0022967349', '34249289704', '0028016014', '84859730867', '75149187080', '84855507947', '0037169297', '0019977566', '84996836170', '34548158293', '0020362344', '42949179459', '0029818885', '85118607522', '13844322374', '15444369213', '0022194091', '0028076991', '33747399034', '75149115900', '0036219595', '0019979314', '85020720099', '85074960570', '0017143229', '84991490282', '85099533415', '0021811872', '84929945600', '0029958113', '84894464378', '33646816054', '75149165376', '75149193597', '33745197770', '32144434430', '0025526283', '0030161855', '85159899372', '75149168974', '0017696932', '85047466505', '75149117921', '4243357029', '0344097508', '85010304030', '75149115438', '0034734223', '85068862130', '33748065305', '38549151817', '0002623019', '0032957934', '0031738098', '0030851358', '77954608798', '34547323478', '85052064874', '84872615091', '0026485521', '0032839807', '0042664072', '0028121297', '0016213578', '0019141927', '0024229763', '75149164504', '0030749526', '0003551413', '84875597801', '35649020642', '0025631108', '0019252614', '35449007166', '77956631921', '0020076423', '64349115740', '0342831714', '0023107578', '77952744201', '85070084692', '75149119880', '85018985501', '85159910700', '7244258916', '0031983817', '33846781508', '75149145191', '70349430938', '0036981085', '84985273189', '0030130380', '3242774456', '0026933666', '36549064699', '75149145647', '85103410127', '0027089368', '67949084933', '85131911910', '29844438773', '84868227548', '85091045623', '48749113401', '85045073928', '77957674664', '0031573198', '0027426080', '33750180429', '75149144078', '0029583178', '84873466383', '0019593384', '0003634702', '0021350233', '77952547324', '75149118394', '0027842945', '84987856231', '85150181204', '0019182431', '0029833141', '85159914383', '0031736808', '38749090899'])

    for result in client.get_many_citations_by_scopus_ids(scopus_ids):
        match result:
            case Success(CitationRequestSuccess() as success_result):
                assert success_result.response.status_code == 200
                assert isinstance(success_result.requested_scopus_ids, CitationRequestScopusIds)
                assert len(success_result.requested_scopus_ids) <= CitationRequestScopusIds.max_scopus_ids_per_request()
                for scopus_id in success_result.record.scopus_ids:
                    assert scopus_id in success_result.requested_scopus_ids
            case Failure(CitationRequestResponseDefunct() as defunct_result):
                # Unlikely to happen, but we test for it anyway:
                assert isinstance(defunct_result.requested_scopus_ids, CitationRequestScopusIds)
                assert len(defunct_result.requested_scopus_ids) <= CitationRequestScopusIds.max_scopus_ids_per_request()
                assert defunct_result.response.status_code == 404
            case Failure(CitationRequestFailure() as failure_result):
                # Even more unlikely to happen, but we test for it anyway...
                assert isinstance(failure_result.requested_scopus_ids, CitationRequestScopusIds)
                assert len(failure_result.requested_scopus_ids) <= CitationRequestScopusIds.max_scopus_ids_per_request()
                #...and also throw an exception, because we want to know what happened:
                raise Exception(f'Unexpected failure when requesting citation overview records for Scopus Ids {failure_result.requested_scopus_ids}: {CitationRequestFailure}')

@pytest.mark.integration
def test_get_assorted_results(client):
    # These should all be validly formatted Scopus IDs, but the last one does not exist:
    bogus_scopus_ids = ['000000000000']
    valid_scopus_ids = ['84924664029','84876222028','33644930319','85199124578']
    requested_scopus_ids = valid_scopus_ids + bogus_scopus_ids
    scopus_ids, invalid_scopus_ids = ScopusIds.factory(requested_scopus_ids)

    cited_scopus_ids_sets = []

    for assorted_results in client.get_assorted_abstracts_by_scopus_id(scopus_ids):
        assert isinstance(assorted_results, AbstractAssortedResults)
        assert assorted_results.requested_scopus_ids == set(requested_scopus_ids)


        assert len(assorted_results.success) == len(valid_scopus_ids)
        #assert assorted_results.success_scopus_ids == set(valid_scopus_ids)
        assert assorted_results.success.requested_scopus_ids == set(valid_scopus_ids)
        for success_result in assorted_results.success:
            assert success_result.response.status_code == 200
            assert success_result.requested_scopus_id == success_result.record.scopus_id

        assert len(assorted_results.defunct) == len(bogus_scopus_ids)
        #assert assorted_results.defunct_scopus_ids == set(bogus_scopus_ids)
        assert assorted_results.defunct.requested_scopus_ids == set(bogus_scopus_ids)
        for defunct_result in assorted_results.defunct:
            assert defunct_result.response.status_code == 404

        assert len(assorted_results.error) == 0

        cited_scopus_ids_sets.append(assorted_results.success.cited_scopus_ids)

    cited_scopus_ids = ScopusIds.union(*cited_scopus_ids_sets)
    assert len(cited_scopus_ids) > 0

    for assorted_results in client.get_assorted_citations_by_scopus_ids(cited_scopus_ids):
        assert isinstance(assorted_results, CitationAssortedResults)

        scopus_ids_sets = [
            assorted_results.success.requested_scopus_ids,
            assorted_results.defunct.requested_scopus_ids,
            assorted_results.error.requested_scopus_ids,
        ]
        for scopus_ids_set in scopus_ids_sets:
            assert isinstance(scopus_ids_set, ScopusIds)
        assert len(set().union(*scopus_ids_sets)) == len(assorted_results.requested_scopus_ids)
        assert len(assorted_results.success.requested_scopus_ids) > 0

        assert len(assorted_results.success.returned_scopus_ids | assorted_results.success.probably_defunct_scopus_ids) \
            == len(assorted_results.success.requested_scopus_ids)

        # We always seem to get a lot of these:
        assert len(assorted_results.success.probably_defunct_scopus_ids) > 0

        assert len(assorted_results.success) > 0
        for success_result in assorted_results.success:
            assert success_result.response.status_code == 200

            # We probably won't need these tests long-term, but they're
            # good sanity checks for now:
            assert isinstance(success_result.record, CitationMaybeMultiRecord)
            assert isinstance(success_result.requested_scopus_ids, CitationRequestScopusIds)
            assert len(assorted_results.success.single_records) > 0
            for single_record in assorted_results.success.single_records:
                assert isinstance(single_record, CitationSingleRecord)

        # We may not get any of these:
        for defunct_result in assorted_results.defunct:
            assert defunct_result.response.status_code == 404

        # If we get any of these, we should know so we can investigate:
        assert len(assorted_results.error) == 0
