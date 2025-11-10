import dotenv_switch.auto

from datetime import datetime
import json

from experts_dw import db, scopus_json
from experts_dw.scopus_json_collection_meta import \
    get_collection_meta_by_local_name

from experts.api import scopus
from experts.api.scopus import \
    ScopusIds

#scopus_ids_sql = '''
#SELECT
#  rojt.scopus_id
#FROM
#  pure_json_research_output_524 ro,
#  JSON_TABLE(ro.json_document, '$'
#    COLUMNS (
#      scopus_id        PATH '$.externalId',
#      uuid             PATH '$.uuid',
#      external_source  PATH '$.externalIdSource',
#      ro_title         PATH '$.title.value',
#      ro_type          PATH '$.type.uri',
#      NESTED PATH '$.publicationStatuses[*]'
#        COLUMNS (
#          ro_year PATH '$.publicationDate.year',
#          ro_current PATH '$.current',
#          ro_status PATH '$.publicationStatus.uri'
#        )
#    )) rojt
#WHERE JSON_EXISTS(ro.json_document, '$.uuid')
#  AND rojt.external_source = 'Scopus'
#  AND rojt.ro_type LIKE '/dk/atira/pure/researchoutput/researchoutputtypes/contributiontojournal/%'
#  AND rojt.ro_current = 'true'
#  AND TO_DATE(rojt.ro_year, 'YYYY') > ADD_MONTHS(SYSDATE, - (12 * 3)) -- current date minus three years
#  AND rojt.ro_status = '/dk/atira/pure/researchoutput/status/published'
# '''

scopus_ids_to_download_sql = 'SELECT scopus_id FROM scopus_abstract_to_download'

with db.cx_oracle_connection() as db_session, scopus.Client() as scopus_client:
    select_cursor = db_session.cursor()

    meta = get_collection_meta_by_local_name(
        cursor=select_cursor,
        local_name='abstract',
    )

    select_cursor.execute(scopus_ids_to_download_sql)
    # cx_Oracle columns definition:
    #columns = [col[0] for col in select_cursor.description]
    # oracledb columns definition:
    columns = [col.name for col in select_cursor.description]
    select_cursor.rowfactory = lambda *args: dict(zip(columns, args))
    scopus_ids, invalid_scopus_ids = ScopusIds.factory(
        [str(row['SCOPUS_ID']) for row in select_cursor.fetchall()]
    )
    # TODO: Handle any invalid_scopus_ids

    insert_cursor = db_session.cursor()

    for assorted_results in client.get_assorted_abstracts_by_scopus_id(scopus_ids):    

        documents_to_insert = [
            {
                'scopus_id': result.scopus_id,
                'scopus_created': result.date_created,
                'scopus_modified': result.last_modified,
                'inserted': datetime.now(),
                'updated': datetime.now(),
                'json_document': result.record.text,
            }
            for result in assorted_results.success
        ]
    
        scopus_json.insert_documents(
           insert_cursor,
           # TODO: Do we need list() here? Isn't it already a list?
           #documents=list(documents_to_insert),
           documents=documents_to_insert,
           meta=meta,
           staging=True,
        )

        # remove scopus ids in abstract staging from abstract to-download list: can do in sql
        # Note: This may leave some defunct scopus ids in the to-download list. Verify later
        # by attempting to download them one-by-one.

        # add defunct abstract scopus ids to defunct abstract list 
        insert_defunct_scopus_ids_sql = f'''
            INSERT /*+ ignore_row_on_dupkey_index(scopus_abstract_defunct(scopus_id)) */
            INTO scopus_abstract_defunct
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

        # log errors for scopus ids in error list
        # TODO: Where to log these? Log file, db, or both?
        for result in assorted_results.error:
            # TODO: Update the following to handle different types of errors:
            print(f'{result.requested_scoppus_id=}: {result.error=}')

        db_session.commit()
