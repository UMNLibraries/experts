import dotenv_switch.auto

import json
import sys

citation_overview_filename = sys.argv[1]

from experts.api.scopus import \
    CitationResponseBodyParser as crb_parser, \
    CitationSubrecordBodyParser as csb_parser

with open(citation_overview_filename) as file:
    body = json.load(file)
    print(f'{crb_parser.column_heading(body)=}')
    for identifiers in crb_parser.identifier_subrecords(body):
        print(f'{identifiers=}')
    for cite_info in crb_parser.cite_info_subrecords(body):
        print(f'{cite_info=}')
    for subrecord in crb_parser.subrecords(body):
        print(f'{subrecord=}')
        scopus_id = csb_parser.scopus_id(subrecord)
        sort_year = csb_parser.sort_year(subrecord)
        print(f'subrecord: {scopus_id=}, {sort_year=}')
