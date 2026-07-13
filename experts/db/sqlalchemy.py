from contextlib import contextmanager
import cx_Oracle
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy_mptt import mptt_sessionmaker

# If a path to the Oracle client libraries was defined, pass to cx_Oracle with init method
oracle_libs_path = os.environ.get('ORACLE_CLIENT_LIBRARIES_PATH')
if oracle_libs_path:
     cx_Oracle.init_oracle_client(lib_dir=oracle_libs_path)

default_db_name = 'hotel'

def url(db_name=default_db_name):
    """Builds the SQLAlchemy Oracle connection URL from environment variables.

    Args:
        db_name: Logical DB name placeholder retained for compatibility.

    Returns:
        An oracle+cx_oracle SQLAlchemy URL string.
    """
    # db_name must be the generic part of the service name,
    # without the (tst|prd).oit suffix, e.g. 'dwe' or 'hotel'.
    url = 'oracle+cx_oracle://{}:"{}"@{}:{}/?service_name={}'.format(
        os.environ.get('EXPERTS_DB_USER'),
        os.environ.get('EXPERTS_DB_PASS'),
        os.environ.get('EXPERTS_DB_HOSTNAME'),
        os.environ.get('EXPERTS_DB_PORT'),
        os.environ.get('EXPERTS_DB_SERVICE_NAME'),
    )
    return url

def engine(db_name=default_db_name):
    """Creates a SQLAlchemy engine for the configured Oracle service.

    Args:
        db_name: Logical DB name placeholder retained for compatibility.

    Returns:
        A configured SQLAlchemy Engine instance.
    """
    return create_engine(
        url(db_name),
        max_identifier_length=128
    )

@contextmanager
def cx_oracle_connection():
    """Yields a cx_Oracle connection using environment-based credentials.

    This connection strategy does not require a tnsnames.ora configuration file.

    Yields:
        An open cx_Oracle connection.
    """
    # Note that this approach to making a connection should not
    # require a tnsnames.ora config file.
    yield cx_Oracle.connect(
        os.environ.get('EXPERTS_DB_USER'),
        os.environ.get('EXPERTS_DB_PASS'),
        f'{os.environ.get("EXPERTS_DB_HOSTNAME")}:{os.environ.get("EXPERTS_DB_PORT")}/{os.environ.get("EXPERTS_DB_SERVICE_NAME")}',
        encoding='UTF-8'
    )

@contextmanager
def session(db_name=default_db_name):
    """Yields a transactional SQLAlchemy session and manages commit lifecycle.

    Args:
        db_name: Logical DB name placeholder retained for compatibility.

    Yields:
        An mptt-enabled SQLAlchemy session.

    Raises:
        Exception: Re-raises any exception after rolling back the session.
    """
    # Original:
    #Session = sessionmaker()
    # mptt docs:
    #Session = mptt_sessionmaker(sessionmaker(bind=engine))
    # This didn't work:
    #Session = mptt_sessionmaker(sessionmaker())

    Session = mptt_sessionmaker(sessionmaker(bind=engine(db_name)))
    session = Session()
    try:
        yield session
        session.commit()
    except:
        session.rollback()
        raise
    finally:
        session.close()
