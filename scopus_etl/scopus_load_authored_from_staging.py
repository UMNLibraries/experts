import dotenv_switch.auto

from datetime import datetime
import json

from experts_dw import db, scopus_json

with db.cx_oracle_connection() as db_session:
    cursor = db_session.cursor()
    scopus_json.load_documents_from_staging(
        cursor,
        collection_local_name='abstract',
        relation='authored'
    )
    db_session.commit()
