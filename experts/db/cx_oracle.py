from contextlib import contextmanager
import cx_Oracle
import os

# If a path to the Oracle client libraries was defined, pass to cx_Oracle with init method
oracle_libs_path = os.environ.get('ORACLE_CLIENT_LIBRARIES_PATH')
if oracle_libs_path:
     cx_Oracle.init_oracle_client(lib_dir=oracle_libs_path)

@contextmanager
def connection():
    # Note that this approach to making a connection should not
    # require a tnsnames.ora config file.
    yield cx_Oracle.connect(
        os.environ.get('EXPERTS_DB_USER'),
        os.environ.get('EXPERTS_DB_PASS'),
        f'{os.environ.get("EXPERTS_DB_HOSTNAME")}:{os.environ.get("EXPERTS_DB_PORT")}/{os.environ.get("EXPERTS_DB_SERVICE_NAME")}',
        encoding='UTF-8'
    )
