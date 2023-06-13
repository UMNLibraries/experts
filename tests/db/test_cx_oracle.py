from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

from experts.db import cx_oracle

def test_connection():
    with cx_oracle.connection() as connection:
        # Execute sql to test that we have a connection and get results
        cur = connection.cursor()
        result = cur.execute(
            "SELECT COUNT(*) FROM UMN_DEPT_PURE_ORG"
        )
        assert result
