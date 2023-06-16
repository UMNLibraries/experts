from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from experts.db import oracledb

def test_connection():
    with oracledb.connection() as connection:
        # Execute sql to test that we have a connection and get results
        cur = connection.cursor()
        result = cur.execute(
            "SELECT COUNT(*) FROM UMN_DEPT_PURE_ORG"
        )
        assert result
