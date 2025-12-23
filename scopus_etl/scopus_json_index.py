import dotenv_switch.auto

from experts_dw import db, scopus_json
from experts_dw.scopus_json_collection_meta import \
    get_collection_meta_by_local_name

with db.cx_oracle_connection() as db_session:
    cursor = db_session.cursor()
    meta = get_collection_meta_by_local_name(
        cursor=cursor,
        local_name='abstract',
    )
    sql = scopus_json.insert_sql(
       cursor,
       meta=meta,
    )
    print(sql)

