import dotenv_switch.auto

from datetime import date
import json
import sys

from pyrsistent import m
from returns.result import Success, Failure

from experts.api import scopus
from experts.api.scopus import \
    Client, \
    CitationMaybeMultiRecord
    
# Multiple Scopus IDs must be comma-separated:
scopus_ids_query_param = sys.argv[1]

#scopus_ids = [
#    #'84876222028',
#    #'33644930319',
#    #'85199124578',
#
#    '85092720354',
#
#    '85095828686',
#    '85095839902',
#    '85096116393',
#    '85096207053',
#    '85096232030',
#    '85089785260',
#    '85089889020',
#    '85090308374',
#    '85090375462',
#    '85091035672',
#    '85091387957',
#    '85096288920',
#    '85091468363',
#    '85092575216',
#    '85095805311',
#    '85095943588',
#    '85096142542',
#    '85096367294',
#    '85096386717',
#    '85096436653',
#    '85096545136',
#    '85096549674',
#    '85096702213',
#    '85097005893',
#    '85097033339',
#    '85097042400',
#]

# Defunct socpus IDs:
#scopus_ids = [
#    '0004149691',
#    '0142190895',
#    '85159914383',
#]

with scopus.Client() as client:
    match client.get(f'abstract/citations', params=m(citation='exclude-self', scopus_id=scopus_ids_query_param)):
        case Success(response):
            print(json.dumps(response.json(), indent=2))
        case Failure(exception):
            raise exception
