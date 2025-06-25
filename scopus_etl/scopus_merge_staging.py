import dotenv_switch.auto

from datetime import datetime
import json

from experts_dw import db, scopus_json

with db.cx_oracle_connection() as db_session:
    cursor = db_session.cursor()
    scopus_json.merge_documents_from_staging(
       cursor,
       collection_api_name='abstract',
       relation='cited',
    )
    db_session.commit()
