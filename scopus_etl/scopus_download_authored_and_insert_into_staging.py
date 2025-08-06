import dotenv_switch.auto

from datetime import datetime
import json

from experts_dw import db, scopus_json
from experts_dw.scopus_json_collection_meta import \
    get_collection_meta_by_local_name

from experts.api.scopus import \
    Client as scopus_client, \
    ScopusIds, \
    AbstractRequestResultAssorter as a_assorter, \
    ResponseParser as r_parser, \
    AbstractResponseBodyParser as arb_parser

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

with db.cx_oracle_connection() as db_session, scopus_client() as scopus_session:
    select_cursor = db_session.cursor()

    meta = get_collection_meta_by_local_name(
        cursor=select_cursor,
        local_name='abstract',
    )

    select_cursor.execute(scopus_ids_to_download_sql)
    columns = [col[0] for col in select_cursor.description]
    select_cursor.rowfactory = lambda *args: dict(zip(columns, args))

    insert_cursor = db_session.cursor()
    while True:
        rows = select_cursor.fetchmany(1000)
        if not rows:
            break
        scopus_ids = [row['SCOPUS_ID'] for row in rows]
        
        assorted_abstract_results = a_assorter.assort(
            scopus_session.get_many_abstracts_by_scopus_id(scopus_ids)
        )

        documents_to_insert = [
            {
                'scopus_id': arb_parser.scopus_id(response.body),
                'scopus_created': arb_parser.date_created(response.body),
                'scopus_modified': arb_parser.date_created(response.body),
                'inserted': datetime.now(),
                'updated': datetime.now(),
                'json_document': json.dumps(response.body),
            }
            for response in assorted_abstract_results.success.values()
        ]
    
        scopus_json.insert_documents(
           insert_cursor,
           documents=list(documents_to_insert),
           meta=meta,
           staging=True,
        )

        # remove scopus ids in abstract staging from abstract to-download list: can do in sql
        # Note: This may leave some defunct scopus ids in the to-download list. Verify later
        # by attempting to download them one-by-one.

        # add defunct abstract scopus ids to defunct abstract list 
        insert_defunct_abstract_scopus_ids_sql = f'''
            INSERT /*+ ignore_row_on_dupkey_index(scopus_abstract_defunct(scopus_id)) */
            INTO scopus_abstract_defunct
            (
              scopus_id
            ) VALUES (
              :scopus_id
            )
        '''
        defunct_abstract_scopus_is = [
            {'scopus_id': scopus_id}
            for scopus_id in assorted_abstract_results.defunct.keys()
        ]
        insert_cursor.executemany(insert_defunct_abstract_scopus_ids_sql, defunct_abstract_scopus_ids)

        # remove scopus ids in defunct abstract list from abstract to-download list: can do in sql

        # log errors for scopus ids in error list
        for scopus_id, error in assorted_abstract_results.error.items():
            print(f'{scopus_id=}: {error=}')

        db_session.commit()
