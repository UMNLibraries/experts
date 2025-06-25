import dotenv_switch.auto

import json
import sys

citation_overview_filename = sys.argv[1]

from experts.api.scopus import \
    CitationOverviewResponseBodyParser as parser

with open(citation_overview_filename) as file:
    body = json.load(file)
    print(f'{parser.column_heading(body)=}')
    for identifiers in parser.identifier_subrecords(body):
        print(f'{identifiers=}')
    for cite_info in parser.cite_info_subrecords(body):
        print(f'{cite_info=}')
    for subrecord in parser.subrecords(body):
        print(f'{subrecord=}')
