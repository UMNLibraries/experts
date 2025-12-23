import dotenv_switch.auto

from datetime import datetime
import json, sys

from experts_dw import db, scopus_json
from experts_dw.scopus_json_collection_meta import \
    get_collection_meta_by_local_name

# 'abstract' or 'citation'
collection_local_name = sys.argv[1]

with db.cx_oracle_connection() as db_session:
    cursor = db_session.cursor()

    meta = get_collection_meta_by_local_name(
        cursor,
        local_name=collection_local_name,
    )

    scopus_json.merge_documents_from_staging(
       cursor,
       meta=meta,
    )

    db_session.commit()
