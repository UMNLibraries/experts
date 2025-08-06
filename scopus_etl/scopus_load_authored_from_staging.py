import dotenv_switch.auto

from datetime import datetime
import json

from experts_dw import db, scopus_json
from experts_dw.scopus_json_collection_meta import \
    get_collection_meta_by_local_name

with db.cx_oracle_connection() as db_session:
    cursor = db_session.cursor()

    meta = get_collection_meta_by_local_name(
        cursor=cursor,
        local_name='abstract',
    )

    scopus_json.load_documents_from_staging(
        cursor,
        meta=meta,
    )
    db_session.commit()
