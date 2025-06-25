import dotenv_switch.auto

from datetime import datetime
import json

from experts_dw import db, scopus_json

from experts.api.scopus import \
    Client as scopus_client, \
    ResponseParser as r_parser, \
    AbstractResponseBodyParser as arb_parser

scopus_ids_sql = 'SELECT scopus_id FROM scopus_cited_abstracts_to_download'

with db.cx_oracle_connection() as db_session, scopus_client() as scopus_session:
    select_cursor = db_session.cursor()
    select_cursor.execute(scopus_ids_sql)
    columns = [col[0] for col in select_cursor.description]
    select_cursor.rowfactory = lambda *args: dict(zip(columns, args))

    insert_cursor = db_session.cursor()
    while True:
        rows = select_cursor.fetchmany(1000)
        if not rows:
            break
        scopus_ids = [row['SCOPUS_ID'] for row in rows]
        
        documents_to_insert = [
            {
                'scopus_id': arb_parser.scopus_id(body),
                'scopus_created': arb_parser.date_created(body),
                'scopus_modified': arb_parser.date_created(body),
                'inserted': datetime.now(),
                'updated': datetime.now(),
                'json_document': json.dumps(body),
            }
            for body in scopus_session.get_many_abstracts_by_scopus_id(
                scopus_ids=scopus_ids,
            ) | r_parser.responses_to_bodies
        ]
    
        scopus_json.insert_documents(
           insert_cursor,
           documents=list(documents_to_insert),
           collection_api_name='abstract',
           relation='cited',
           staging=True,
        )
        db_session.commit()
