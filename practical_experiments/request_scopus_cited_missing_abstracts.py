import dotenv_switch.auto

from itertools import islice
import sys

from experts.api.scopus import \
    Client, \
    ScopusIds, \
    ScopusIdRequestResultAssorter as assorter, \
    AbstractResponseBodyParser as parser

scopus_ids_file = sys.argv[1]
with open(scopus_ids_file) as f:
    scopus_ids = f.read().splitlines()

with Client() as session:
    assorted_results = assorter.assort(
        session.get_many_abstracts_by_scopus_id(scopus_ids)
    )
    print(f'{assorted_results.success.keys()=}')
    print(f'{assorted_results.error.keys()=}')
    print(f'{assorted_results.defunct=}')
    #print(f'{assorted_results.scopus_ids()=}')
