import dotenv_switch.auto

from datetime import datetime
import json

from experts_dw import db, scopus_json
from experts_dw.scopus_json_collection_meta import \
    get_collection_meta_by_local_name

from experts.api.scopus import \
    Client as scopus_client, \
    ScopusIds, \
    CitationRequestResultAssorter as c_assorter, \
    CitationResponseBodyParser as crb_parser, \
    CitationSubrecordBodyParser as csb_parser

scopus_ids_sql = 'SELECT scopus_id FROM scopus_citation_to_download'

with db.cx_oracle_connection() as db_session, scopus_client() as scopus_session:
    select_cursor = db_session.cursor()

    meta = get_collection_meta_by_local_name(
        cursor=select_cursor,
        local_name='citation',
    )
    select_cursor.execute(scopus_ids_sql)
    columns = [col[0] for col in select_cursor.description]
    select_cursor.rowfactory = lambda *args: dict(zip(columns, args))

    insert_cursor = db_session.cursor()
    while True:
        rows = select_cursor.fetchmany(1000)
        if not rows:
            break
        # Our ScopusId type requires a string, but we store them as ints in Oracle:
        scopus_ids = [str(row['SCOPUS_ID']) for row in rows]
        
        # TODO: This needs work for citations!
        assorted_citation_results = c_assorter.assort(
            scopus_session.get_many_citations_by_scopus_ids(scopus_ids)
        )

        documents_to_insert = [
            {
                'scopus_id': csb_parser.scopus_id(subrecord),
                'scopus_created': csb_parser.sort_year(subrecord),
                'scopus_modified': csb_parser.sort_year(subrecord),
                'inserted': datetime.now(),
                'updated': datetime.now(),
                'json_document': json.dumps(subrecord),
            }
            for subrecord in assorted_citation_results.success_subrecords.values()
        ]
    
        scopus_json.insert_documents(
           insert_cursor,
           documents=list(documents_to_insert),
           meta=meta,
           staging=True,
        )

        # remove scopus ids in citation staging from citation to-download list: can do in sql
        # Note: This may leave some defunct scopus ids in the to-download list. Verify later
        # by attempting to download them one-by-one.

        # add defunct abstract scopus ids to defunct abstract list 
        insert_defunct_citation_scopus_ids_sql = f'''
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
        defunct_citation_scopus_ids = [
            {
                'scopus_id': scopus_id,
                'inserted': datetime.now(),
            }
            for scopus_id in list(assorted_citation_results.defunct_scopus_ids())
        ]
        insert_cursor.executemany(insert_defunct_citation_scopus_ids_sql, defunct_citation_scopus_ids)

        # remove scopus ids in defunct abstract list from abstract to-download list: can do in sql

        # log errors for scopus ids in error list
        for scopus_ids, error in assorted_citation_results.error.items():
            print(f'{list(scopus_ids)=}: {error=}')

        db_session.commit()
