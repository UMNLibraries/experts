import dotenv_switch.auto

from datetime import datetime
import json

from experts_dw import db, scopus_json
from experts_dw.scopus_json_collection_meta import \
    get_collection_meta_by_local_name

from experts.api import scopus
from experts.api.scopus import \
    ScopusIds

scopus_ids_sql = 'SELECT scopus_id FROM scopus_citation_to_download'

with db.cx_oracle_connection() as db_session, scopus.Client() as scopus_client:
    select_cursor = db_session.cursor()

    meta = get_collection_meta_by_local_name(
        cursor=select_cursor,
        local_name='citation',
    )
    select_cursor.execute(scopus_ids_sql)

    # cx_Oracle columns definition:
    columns = [col[0] for col in select_cursor.description]
    # oracledb columns definition:
    #columns = [col.name for col in select_cursor.description]
    select_cursor.rowfactory = lambda *args: dict(zip(columns, args))
    scopus_ids, invalid_scopus_ids = ScopusIds.factory(
        [str(row['SCOPUS_ID']) for row in select_cursor.fetchall()]
    )
    # TODO: Handle any invalid_scopus_ids

    insert_cursor = db_session.cursor()

    for assorted_results in client.get_assorted_citations_by_scopus_ids(scopus_ids):

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

        scopus_json.insert_documents(
           insert_cursor,
           # TODO: Do we need list() here? Isn't it already a list?
           #documents=list(documents_to_insert),
           documents=documents_to_insert,
           meta=meta,
           staging=True,
        )

        # remove scopus ids in citation staging from citation to-download list: can do in sql
        # Note: This may leave some defunct scopus ids in the to-download list. Verify later
        # by attempting to download them one-by-one.

        # add defunct abstract scopus ids to defunct abstract list
        insert_defunct_scopus_ids_sql = f'''
            INSERT /*+ ignore_row_on_dupkey_index(scopus_abstract_defunct(scopus_id)) */
            INTO scopus_citation_defunct
            (
              scopus_id,
              inserted
            ) VALUES (
              :scopus_id,
              :inserted
            )
        '''
        defunct_scopus_ids = [
            {
                'scopus_id': scopus_id,
                'inserted': datetime.now(),
            }
            for scopus_id in assorted_results.defunct.scopus_ids
        ]
        insert_cursor.executemany(insert_defunct_scopus_ids_sql, defunct_scopus_ids)

        # remove scopus ids in defunct abstract list from abstract to-download list: can do in sql

        # TODO: Where to log these? Log file, db, or both?
        for result in assorted_results.error:
            # TODO: Update the following to handle different types of errors:
            print(f'{list(result.requested_scopus_ids)=}: {error=}')

        # TODO: Handle result.probably_defunct_scopus_ids

        db_session.commit()
