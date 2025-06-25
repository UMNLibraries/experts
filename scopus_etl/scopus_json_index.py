import dotenv_switch.auto

from experts_dw import db, scopus_json

with db.cx_oracle_connection() as db_session:
    cur = db_session.cursor()
    sql = scopus_json.insert_sql(
       cur,
       collection_api_name='abstract',
    )
    print(sql)

