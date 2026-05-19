import dotenv_switch.auto

from datetime import datetime
import sys
from typing import Iterable

import cx_Oracle

from experts.api import scopus
from experts.api.scopus import ScopusIds
from experts_dw import db, scopus_json
from experts_dw.scopus_json_collection_meta import \
    CollectionMeta, \
    get_collection_meta_by_local_name
    
scopus_ids_filename = sys.argv[1]

with open(scopus_ids_filename) as scopus_ids_file, db.cx_oracle_connection() as db_session, scopus.Client() as client:
    scopus_ids, invalid_scopus_ids = ScopusIds.factory(
        [line.rstrip() for line in scopus_ids_file]
    )

    cursor = db_session.cursor()
    meta = get_collection_meta_by_local_name(
        cursor=cursor,
        local_name='citation',
    )

    all_assorted_scopus_ids = {
        'success': [],
        'defunct': [],
        'probably_defunct': [],
        'error': [],
    }
    for assorted_results in client.get_assorted_citations_by_scopus_ids(scopus_ids):
        # Insert the successes into staging (size before insert: 0 rows):
        documents_to_insert = [
            {
                'scopus_id': record.scopus_id,
                'scopus_created': record.sort_year,
                'scopus_modified': record.sort_year,
                'inserted': datetime.now(),
                'updated': datetime.now(),
                'json_document': record.json_dumps(),
            }
            for record in assorted_results.success.single_records
        ]
        if len(documents_to_insert) > 0:
            scopus_json.insert_documents(
               cursor,
               # TODO: Do we need list() here? Isn't it already a list?
               #documents=list(documents_to_insert),
               documents=documents_to_insert,
               meta=meta,
               staging=True,
            )

        all_assorted_scopus_ids['success'] += list(assorted_results.success.returned_scopus_ids)
        all_assorted_scopus_ids['defunct'] += list(assorted_results.defunct.requested_scopus_ids)
        all_assorted_scopus_ids['probably_defunct'] += list(assorted_results.success.probably_defunct_scopus_ids)
        all_assorted_scopus_ids['error'] += list(assorted_results.error.requested_scopus_ids)

    # Download probably defunct Scopus IDs one-by-one, to ensure they really are defunct:
    probably_defunct_scopus_ids, _ = ScopusIds.factory(
        all_assorted_scopus_ids['probably_defunct']
    )
    for assorted_results in client.get_assorted_citations_by_scopus_ids(probably_defunct_scopus_ids, batch_size=1):
        all_assorted_scopus_ids['success'] += list(assorted_results.success.returned_scopus_ids)
        all_assorted_scopus_ids['defunct'] += list(assorted_results.defunct.requested_scopus_ids)
        all_assorted_scopus_ids['error'] += list(assorted_results.error.requested_scopus_ids)

        # Should be none of these, since we requested Scopus IDs one-by-one:
        #all_assorted_scopus_ids['probably_defunct'] += list(assorted_results.success.probably_defunct_scopus_ids)

    # Remove Scopus IDs we no know to be defunct from the probably defunct list:
    all_assorted_scopus_ids['probably_defunct'] = list(
        set(all_assorted_scopus_ids['probably_defunct']) - set(all_assorted_scopus_ids['defunct'])
    )

    # size before insert: 23451 rows
    if len(all_assorted_scopus_ids['defunct']) > 0:
        scopus_json.insert_defunct_scopus_ids(
            cursor, 
            scopus_ids=all_assorted_scopus_ids['defunct'],
            meta=meta,
        )

    for list_name, scopus_ids_list in all_assorted_scopus_ids.items():
        print(f'{list_name}: {len(scopus_ids_list)}')
        print(f'  {scopus_ids_list}')

    scopus_json.load_documents_from_staging(
        cursor,
        meta=meta,
    )

    db_session.commit()
