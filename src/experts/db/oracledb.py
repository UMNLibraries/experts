from contextlib import contextmanager
import oracledb
import os

@contextmanager
def connection():
    # Note that this approach to making a connection should not
    # require a tnsnames.ora config file.
    un=os.environ.get('EXPERTS_DB_USER')
    pw=os.environ.get('EXPERTS_DB_PASS')
    cs=f'{os.environ.get("EXPERTS_DB_HOSTNAME")}/{os.environ.get("EXPERTS_DB_SERVICE_NAME")}'
    yield oracledb.connect(user=un,password=pw,dsn=cs)
