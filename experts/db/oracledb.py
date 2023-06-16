from contextlib import contextmanager
import oracledb
import os

@contextmanager
def connection():
    # Note that this approach to making a connection should not
    # require a tnsnames.ora config file.
    u=os.environ.get('EXPERTS_DB_USER')
    p=os.environ.get('EXPERTS_DB_PASS')
    cs=f'{os.environ.get("EXPERTS_DB_HOSTNAME")}/{os.environ.get("EXPERTS_DB_SERVICE_NAME")}'
    yield oracledb.connect(user=u,password=p,dsn=cs)
