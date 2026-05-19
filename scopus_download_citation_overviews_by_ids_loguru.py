import dotenv_switch.auto

from datetime import date
import json
import sys

from loguru import logger

from pyrsistent import m
from returns.result import Success, Failure

from experts.api import scopus
from experts.api.scopus import \
    Client, \
    CitationMaybeMultiRecord, \
    CitationRequestSuccess, \
    CitationRequestResponseValidationError, \
    CitationRequestResponseDefunct, \
    CitationRequestResponseFailure, \
    CitationRequestNonresponseFailure, \
    ScopusIds

#logger.add(sys.stderr, format="{message} | {extra}")
logger.remove()
logger.add(
    #sys.stderr,
    'scopus-etl-citations.ljson',
    level='INFO',
    serialize=True,
    rotation='1 day',
    retention='1 year',
)

@logger.catch
def main():
    # Multiple Scopus IDs must be comma-separated:
    #scopus_ids_query_param = sys.argv[1]

    scopus_ids, invalid_scopus_ids = ScopusIds.factory([
        #'84876222028',
        #'33644930319',
        #'85199124578',

        '85092720354',

        '85095828686',
        '85095839902',
        '85096116393',
        '85096207053',
        '85096232030',
        '85089785260',
        '85089889020',
        '85090308374',
        '85090375462',
        '85091035672',
        '85091387957',
        '85096288920',
        '85091468363',
        '85092575216',
        '85095805311',
        '85095943588',
        '85096142542',
        '85096367294',
        '85096386717',
        '85096436653',
        '85096545136',
        '85096549674',
        '85096702213',
        '85097005893',
        '85097033339',
        '85097042400',
    ])

    # Defunct socpus IDs:
    #scopus_ids = [
    #    '0004149691',
    #    '0142190895',
    #    '85159914383',
    #]

    scopus_ids_query_param = ','.join(scopus_ids)

    with scopus.Client() as client:
        fancy_result = None
        result = client.get(f'abstract/citations', params=m(citation='exclude-self', scopus_id=scopus_ids_query_param))
            # Logic copied from experts.api.scopus.get_citations_by_scopus_ids()
        match result:
            case Success(response):
                match response.status_code:
                    case 200:
                        match CitationMaybeMultiRecord.factory(response.json()):
                            case Success(record):
                                fancy_result = Success(
                                    CitationRequestSuccess(
                                        requested_scopus_ids=scopus_ids,
                                        response=response,
                                        record=record,
                                    )
                                )
                            case Failure(exception):
                                fancy_result = Failure(
                                    CitationRequestResponseValidationError(
                                        requested_scopus_ids=scopus_ids,
                                        response=response,
                                        exception=exception,
                                    )
                                )
                    case 404:
                        fancy_result = Failure(
                            CitationRequestResponseDefunct(
                                requested_scopus_ids=scopus_ids,
                                response=response,
                            )
                        )
                    case _:
                        fancy_result = Failure(
                            CitationRequestResponseFailure(
                                requested_scopus_ids=scopus_ids,
                                response=response,
                            )
                        )
            case Failure(exception):
                fancy_result = Failure(
                    CitationRequestNonresponseFailure(
                        requested_scopus_ids=scopus_ids,
                        exception=exception,
                    )
                )
           
        match fancy_result:
            case Failure(failure):
                logger.error('request failed', error=failure.serialize()) 

if __name__ == "__main__":
    main()
