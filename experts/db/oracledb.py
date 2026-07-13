from contextlib import contextmanager
import oracledb
import os

@contextmanager
def connection():
    """Yields an Oracle DB connection using environment-based credentials.

    This connection strategy does not require a tnsnames.ora configuration file.

    Yields:
        An open oracledb connection.
    """
    # Note that this approach to making a connection should not
    # require a tnsnames.ora config file.
    un=os.environ.get('EXPERTS_DB_USER')
    pw=os.environ.get('EXPERTS_DB_PASS')
    cs=f'{os.environ.get("EXPERTS_DB_HOSTNAME")}/{os.environ.get("EXPERTS_DB_SERVICE_NAME")}'
    yield oracledb.connect(user=un,password=pw,dsn=cs)
