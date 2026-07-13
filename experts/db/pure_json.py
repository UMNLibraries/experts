from datetime import datetime
import functools
import json
import time
from typing import Any, Callable, MutableMapping, Tuple, TypeVar, cast

import logging
import importlib
importlib.reload(logging)

logging.basicConfig(format='%(asctime)s %(levelname)s: %(message)s', level=logging.DEBUG, datefmt='%I:%M:%S')

from experts.db.exceptions import ExpertsDbException

iso_8601_format = '%Y-%m-%dT%H:%M:%S.%f%z'

@functools.lru_cache(maxsize=None)
def api_versions(cursor):
    """Returns all known Pure API versions from collection metadata.

    Args:
        cursor: Database cursor used to execute metadata queries.

    Returns:
        A list of distinct API version values.
    """
    cursor.execute('SELECT DISTINCT(api_version) FROM pure_json_collection_meta')
    return [row[0] for row in cursor.fetchall()]

class MissingApiVersion(ValueError, ExpertsDbException):
    '''Raised when a Pure API version is expected but missing.'''
    def __init__(self, *args, **kwargs):
        super().__init__(f'No api_version found in kwargs', *args, **kwargs)

class InvalidApiVersion(ValueError, ExpertsDbException):
    '''Raised when a Pure API version is unrecognized.'''
    def __init__(self, api_version, *args, **kwargs):
        super().__init__(f'Invalid api_version "{api_version}"', *args, **kwargs)

F = TypeVar('F', bound=Callable[..., Any])

def function_call_logger(func: F) -> F:
    """Decorator that logs function calls and return values in debug mode.

    Args:
        func: Function to wrap.

    Returns:
        Wrapped function with debug call logging.
    """
    @functools.wraps(func)
    def wrapper_function_call_logger(*args, **kwargs):
        if __debug__:
            logging.debug(f'Invoking {func.__name__}:')
            logging.debug(f'  args: {args}')
            logging.debug(f'  kwargs: {kwargs}')
        result = func(*args, **kwargs)
        if __debug__:
            logging.debug(f'  returned: {result}')
        return result
    return cast(F, wrapper_function_call_logger)

def function_time_logger(func: F) -> F:
    """Decorator that logs function execution time in debug mode.

    Args:
        func: Function to wrap.

    Returns:
        Wrapped function with debug timing logging.
    """
    @functools.wraps(func)
    def wrapper_function_time_logger(*args, **kwargs):
        if __debug__:
            start_time = time.perf_counter()
        result = func(*args, **kwargs)
        if __debug__:
            end_time = time.perf_counter()
            duration = (end_time - start_time) * 1000
            logging.debug(f'  time: {duration:0.4f} ms')
        return result
    return cast(F, wrapper_function_time_logger)

def validate_api_version(func: F) -> F:
    '''A decorator wrapper that validates a kwarg Pure API version.

    Args:
        func: The function to be wrapped.

    Returns:
        The wrapped function.

    Raises:
        MissingApiVersion: If the ``api_version`` kwarg is missing or
            the value is None.
        InvalidApiVersion: If the ``api_version`` is unrecognized.
    '''
    @functools.wraps(func)
    def wrapper_validate_api_version(*args, **kwargs):
        cursor = args[0]
        if 'api_version' in kwargs and kwargs['api_version'] is not None:
            if kwargs['api_version'] not in api_versions(cursor):
                raise InvalidApiVersion(kwargs['api_version'])
        if ('api_version' not in kwargs) or (kwargs['api_version'] is None):
            raise MissingApiVersion()
        return func(*args, **kwargs)
    return cast(F, wrapper_validate_api_version)

@functools.lru_cache(maxsize=None)
@validate_api_version
def collection_local_names_for_api_version(cursor, *, api_version):
    """Returns valid local collection names for a Pure API version.

    Args:
        cursor: Database cursor used to execute metadata queries.
        api_version: Pure API version identifier.

    Returns:
        Local collection names for the requested API version.
    """
    cursor.execute(
        'SELECT DISTINCT(local_name) FROM pure_json_collection_meta where api_version = :api_version',
        {'api_version': api_version}
    )
    return [row[0] for row in cursor.fetchall()]

@functools.lru_cache(maxsize=None)
@validate_api_version
def collection_family_system_names_for_api_version(cursor, *, api_version):
    """Returns valid family system collection names for an API version.

    Args:
        cursor: Database cursor used to execute metadata queries.
        api_version: Pure API version identifier.

    Returns:
        Family system names for the requested API version.
    """
    cursor.execute(
        'SELECT DISTINCT(family_system_name) FROM pure_json_collection_meta where api_version = :api_version',
        {'api_version': api_version}
    )
    return [row[0] for row in cursor.fetchall()]

@functools.lru_cache(maxsize=None)
@validate_api_version
def collection_api_names_for_api_version(cursor, *, api_version):
    """Returns valid API collection names for a Pure API version.

    Args:
        cursor: Database cursor used to execute metadata queries.
        api_version: Pure API version identifier.

    Returns:
        API collection names for the requested API version.
    """
    cursor.execute(
        'SELECT DISTINCT(api_name) FROM pure_json_collection_meta where api_version = :api_version',
        {'api_version': api_version}
    )
    return [row[0] for row in cursor.fetchall()]

@functools.lru_cache(maxsize=None)
@validate_api_version
def collection_local_name_for_api_name(cursor, *, collection_api_name, api_version):
    """Resolves local collection name from an API collection name.

    Args:
        cursor: Database cursor used to execute metadata queries.
        collection_api_name: API collection name.
        api_version: Pure API version identifier.

    Returns:
        Matching local collection name, or None when no match exists.
    """
    cursor.execute(
        'SELECT local_name FROM pure_json_collection_meta WHERE api_name = :api_name AND api_version = :api_version',
        {'api_name': collection_api_name, 'api_version': api_version}
    )
    result = cursor.fetchone()
    if result is None:
        return result
    else:
        return result[0] # Result will be a tuple

@functools.lru_cache(maxsize=None)
@validate_api_version
def collection_local_name_for_family_system_name(cursor, *, collection_family_system_name, api_version):
    """Resolves local collection name from a family system name.

    Args:
        cursor: Database cursor used to execute metadata queries.
        collection_family_system_name: Family system collection name.
        api_version: Pure API version identifier.

    Returns:
        Matching local collection name, or None when no match exists.
    """
    cursor.execute(
        'SELECT local_name FROM pure_json_collection_meta WHERE family_system_name = :family_system_name AND api_version = :api_version',
        {'family_system_name': collection_family_system_name, 'api_version': api_version}
    )
    result = cursor.fetchone()
    if result is None:
        return result
    else:
        return result[0] # Result will be a tuple

@functools.lru_cache(maxsize=None)
@validate_api_version
def collection_family_system_name_for_local_name(cursor, *, collection_local_name, api_version):
    """Resolves family system name from a local collection name.

    Args:
        cursor: Database cursor used to execute metadata queries.
        collection_local_name: Local collection name.
        api_version: Pure API version identifier.

    Returns:
        Matching family system name, or None when no match exists.
    """
    cursor.execute(
        'SELECT family_system_name FROM pure_json_collection_meta WHERE local_name = :local_name AND api_version = :api_version',
        {'local_name': collection_local_name, 'api_version': api_version}
    )
    result = cursor.fetchone()
    if result is None:
        return result
    else:
        return result[0] # Result will be a tuple

@functools.lru_cache(maxsize=None)
@validate_api_version
def collection_api_name_for_local_name(cursor, *, collection_local_name, api_version):
    """Resolves API collection name from a local collection name.

    Args:
        cursor: Database cursor used to execute metadata queries.
        collection_local_name: Local collection name.
        api_version: Pure API version identifier.

    Returns:
        Matching API collection name, or None when no match exists.
    """
    cursor.execute(
        'SELECT api_name FROM pure_json_collection_meta WHERE local_name = :local_name AND api_version = :api_version',
        {'local_name': collection_local_name, 'api_version': api_version}
    )
    result = cursor.fetchone()
    if result is None:
        return result
    else:
        return result[0] # Result will be a tuple

class MissingCollectionName(ValueError, ExpertsDbException):
    '''Raised when a Pure collection name is expected but missing.'''
    def __init__(self, *args, **kwargs):
        super().__init__(
            'No collection_local_name, collection_api_name, or collection_family_system_name found in kwargs',
            *args,
            **kwargs
        )

class InvalidCollectionLocalName(ValueError, ExpertsDbException):
    '''Raised when a local collection name is invalid for a given Pure API version.'''
    def __init__(self, *args, collection_local_name, api_version, **kwargs):
        super().__init__(
            f'Invalid collection_local_name "{collection_local_name}" for api_version "{api_version}"',
            *args,
            **kwargs
        )

class InvalidCollectionApiName(ValueError, ExpertsDbException):
    '''Raised when a Pure API collection name is invalid for a given API version.'''
    def __init__(self, *args, collection_api_name, api_version, **kwargs):
        super().__init__(
            f'Invalid collection_api_name "{collection_api_name}" for api_version "{api_version}"',
            *args,
            **kwargs
        )

class InvalidCollectionFamilySystemName(ValueError, ExpertsDbException):
    '''Raised when a Pure API family system name is invalid for a given API version.'''
    def __init__(self, *args, collection_family_system_name, api_version, **kwargs):
        super().__init__(
            f'Invalid collection_family_system_name "{collection_family_system_name}" for api_version "{api_version}"',
            *args,
            **kwargs
        )

def validate_collection_names(func: F) -> F:
    '''A decorator wrapper that ensures that collection_local_name,
    collection_api_name, and collection_family_system_name all exist in kwargs, are valid,
    and consistent with each other.

    Args:
        func: The function to be wrapped.

    Returns:
        The wrapped function.

    Raises:
        MissingCollectionName: If none of the various ``collection_*`` names
            is in kwargs.
        InvalidCollectionLocalName: If the ``collection_local_name`` is not
            found for the given ``api_version``.
        InvalidCollectionApiName: If the ``collection_api_name`` is not found
            for the given ``api_version``.
        InvalidCollectionFamilySystemName: If the ``collection_family_system_name``
            is not found for the given ``api_version``.
    '''
    @functools.wraps(func)
    def wrapper_validate_collection_names(*args, **kwargs):
        cursor = args[0]
        api_version = kwargs['api_version']
        if 'collection_local_name' in kwargs and kwargs['collection_local_name'] is not None:
            if kwargs['collection_local_name'] not in collection_local_names_for_api_version(cursor, api_version=api_version):
                raise InvalidCollectionLocalName(
                    collection_local_name=kwargs['collection_local_name'],
                    api_version=api_version
                )
        elif 'collection_api_name' in kwargs and kwargs['collection_api_name'] is not None:
            kwargs['collection_local_name'] = collection_local_name_for_api_name(
                cursor,
                collection_api_name=kwargs['collection_api_name'],
                api_version=api_version
            )
            if kwargs['collection_local_name'] is None:
                raise InvalidCollectionApiName(
                    collection_api_name=kwargs['collection_api_name'],
                    api_version=api_version
                )
        elif 'collection_family_system_name' in kwargs and kwargs['collection_family_system_name'] is not None:
            kwargs['collection_local_name'] = collection_local_name_for_family_system_name(
                cursor,
                collection_family_system_name=kwargs['collection_family_system_name'],
                api_version=api_version
            )
            if kwargs['collection_local_name'] is None:
                raise InvalidCollectionFamilySystemName(
                    collection_family_system_name=kwargs['collection_family_system_name'],
                    api_version=api_version
                )
        if ('collection_local_name' not in kwargs) or (kwargs['collection_local_name'] is None):
            raise MissingCollectionName()
        kwargs['collection_family_system_name'] = collection_family_system_name_for_local_name(
            cursor,
            collection_local_name=kwargs['collection_local_name'],
            api_version=api_version
        )
        kwargs['collection_api_name'] = collection_api_name_for_local_name(
            cursor,
            collection_local_name=kwargs['collection_local_name'],
            api_version=api_version
        )
        return func(*args, **kwargs)
    return cast(F, wrapper_validate_collection_names)

# Notice that this function has no validation. We recommend calling it only
# from other functions in this module that do have parameter validation.
def get_change_table_name(*, api_version, history=False):
    """Builds the Pure JSON change table name for an API version.

    Args:
        api_version: Pure API version identifier.
        history: Whether to return the corresponding history table name.

    Returns:
        Change table name, optionally suffixed with _history.
    """
    change_table_name = f'pure_json_change_{api_version}'
    if history:
        return change_table_name + '_history'
    return change_table_name

# Notice that this function has no validation. We recommend calling it only
# from other functions in this module that do have parameter validation.
def get_collection_table_name(*, api_version, collection_local_name, staging=False):
    """Builds a Pure JSON collection table name.

    Args:
        api_version: Pure API version identifier.
        collection_local_name: Local collection name segment.
        staging: Whether to return the staging table name.

    Returns:
        Collection table name, optionally suffixed with _staging.
    """
    collection_table_name = f'pure_json_{collection_local_name}_{api_version}'
    if staging:
        return collection_table_name + '_staging'
    return collection_table_name

@validate_api_version
@validate_collection_names
def document_exists(
    cursor,
    *,
    uuid,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None,
    staging=False
):
    """Checks whether a document UUID exists in a target collection table.

    Args:
        cursor: Database cursor used to execute queries.
        uuid: Document UUID to look up.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.
        staging: Whether to check the staging collection table.

    Returns:
        True when at least one matching document exists; otherwise False.
    """
    collection_table_name = get_collection_table_name(
        api_version=api_version,
        collection_local_name=collection_local_name,
        staging=staging
    )
    cursor.execute(
        f'SELECT count(*) FROM {collection_table_name} WHERE uuid = :uuid',
        {'uuid': uuid}
    )
    document_count = cursor.fetchone()[0] # Result will be a tuple
    if document_count > 0:
        return True
    else:
        return False

@validate_api_version
@validate_collection_names
def insert_sql(
    cursor,
    *,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None,
    staging=False
):
    """Builds insert SQL for a collection table with duplicate-key ignore hint.

    Args:
        cursor: Database cursor used for validation context.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.
        staging: Whether to target the staging collection table.

    Returns:
        Parameterized Oracle insert SQL string.
    """
    collection_table_name = get_collection_table_name(
        api_version=api_version,
        collection_local_name=collection_local_name,
        staging=staging
    )
    primary_key_column_names = 'uuid'
    primary_key_predicate = 'uuid = :uuid'
    if staging:
        primary_key_column_names = primary_key_column_names + ', pure_modified'
        primary_key_predicate = primary_key_predicate + ' AND pure_modified = :pure_modified'
    return f'''
        INSERT /*+ ignore_row_on_dupkey_index({collection_table_name}({primary_key_column_names})) */ 
        INTO {collection_table_name}
        (
          uuid,
          pure_created,
          pure_modified,
          inserted,
          updated,
          json_document
        ) VALUES (
          :uuid,
          :pure_created,
          :pure_modified,
          :inserted,
          :updated,
          :json_document
        )
    '''

@validate_api_version
@validate_collection_names
def insert_document(
    cursor,
    *,
    document,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None,
    staging=False
):
    """Inserts one document into the resolved collection table.

    Args:
        cursor: Database cursor used to execute statements.
        document: Single document bind mapping.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.
        staging: Whether to insert into the staging table.
    """
    sql = insert_sql(
        cursor,
        collection_local_name=collection_local_name,
        api_version=api_version,
        staging=staging
    )
    cursor.execute(sql, document)

@validate_api_version
@validate_collection_names
def insert_documents(
    cursor,
    *,
    documents,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None,
    staging=False
):
    """Bulk-inserts many documents into the resolved collection table.

    Args:
        cursor: Database cursor used to execute statements.
        documents: Iterable of document bind mappings.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.
        staging: Whether to insert into the staging table.
    """
    sql = insert_sql(
        cursor,
        collection_local_name=collection_local_name,
        api_version=api_version,
        staging=staging
    )
    cursor.executemany(sql, documents)

@validate_api_version
def max_change_history_inserted_date(
    cursor,
    *,
    api_version
):
    """Returns the most recent inserted timestamp in change history.

    Args:
        cursor: Database cursor used to execute queries.
        api_version: Pure API version identifier.

    Returns:
        Maximum inserted timestamp from the change history table.
    """
    change_history_table_name = get_change_table_name(
        api_version=api_version,
        history=True
    )
    cursor.execute(
        f'SELECT MAX(inserted) FROM {change_history_table_name}'
    )
    return cursor.fetchone()[0] # Result will be a tuple

@validate_api_version
def max_change_inserted_date(
    cursor,
    *,
    api_version
):
    """Returns the most recent inserted timestamp in change staging.

    Args:
        cursor: Database cursor used to execute queries.
        api_version: Pure API version identifier.

    Returns:
        Maximum inserted timestamp from the change table.
    """
    change_table_name = get_change_table_name(
        api_version=api_version
    )
    cursor.execute(
        f'SELECT MAX(inserted) FROM {change_table_name}'
    )
    return cursor.fetchone()[0] # Result will be a tuple

@validate_api_version
def max_pure_version_for_change_history_uuid(
    cursor,
    *,
    uuid,
    api_version
):
    """Returns the highest pure_version for a UUID in change history.

    Args:
        cursor: Database cursor used to execute queries.
        uuid: Document UUID.
        api_version: Pure API version identifier.

    Returns:
        Highest pure_version value for the UUID in history.
    """
    change_history_table_name = get_change_table_name(
        api_version=api_version,
        history=True
    )
    cursor.execute(
        f'SELECT MAX(pure_version) FROM {change_history_table_name} WHERE uuid = :uuid',
        {'uuid': uuid}
    )
    return cursor.fetchone()[0] # Result will be a tuple

@validate_api_version
def max_pure_version_for_change_uuid(
    cursor,
    *,
    uuid,
    api_version
):
    """Returns the highest pure_version for a UUID in the change table.

    Args:
        cursor: Database cursor used to execute queries.
        uuid: Document UUID.
        api_version: Pure API version identifier.

    Returns:
        Highest pure_version value for the UUID.
    """
    change_table_name = get_change_table_name(
        api_version=api_version
    )
    cursor.execute(
        f'SELECT MAX(pure_version) FROM {change_table_name} WHERE uuid = :uuid',
        {'uuid': uuid}
    )
    return cursor.fetchone()[0] # Result will be a tuple

@validate_api_version
def change_document_exists(
    cursor,
    *,
    uuid,
    pure_version,
    api_version
):
    """Checks whether a UUID/version change row exists.

    Args:
        cursor: Database cursor used to execute queries.
        uuid: Document UUID.
        pure_version: Pure object version.
        api_version: Pure API version identifier.

    Returns:
        True when a matching change row exists; otherwise False.
    """
    change_table_name = get_change_table_name(
        api_version=api_version
    )
    cursor.execute(
        f'SELECT count(*) FROM {change_table_name} WHERE uuid = :uuid AND pure_version = :pure_version',
        {'uuid': uuid, 'pure_version': pure_version}
    )
    document_count = cursor.fetchone()[0] # Result will be a tuple
    if document_count > 0:
        return True
    else:
        return False

@validate_api_version
def change_history_exists(
    cursor,
    *,
    uuid,
    pure_version,
    api_version
):
    """Checks whether a UUID/version history row exists.

    Args:
        cursor: Database cursor used to execute queries.
        uuid: Document UUID.
        pure_version: Pure object version.
        api_version: Pure API version identifier.

    Returns:
        True when a matching history row exists; otherwise False.
    """
    change_history_table_name = get_change_table_name(
        api_version=api_version,
        history=True
    )
    cursor.execute(
        f'SELECT count(*) FROM {change_history_table_name} WHERE uuid = :uuid AND pure_version = :pure_version',
        {'uuid': uuid, 'pure_version': pure_version}
    )
    history_count = cursor.fetchone()[0] # Result will be a tuple
    if history_count > 0:
        return True
    else:
        return False

@validate_api_version
def insert_change_sql(
    cursor,
    *,
    api_version
):
    """Builds insert SQL for the change table.

    Args:
        cursor: Database cursor used for validation context.
        api_version: Pure API version identifier.

    Returns:
        Parameterized Oracle insert SQL string for change rows.
    """
    change_table_name = get_change_table_name(
        api_version=api_version
    )
    return f'''
        INSERT /*+ ignore_row_on_dupkey_index({change_table_name}(uuid, pure_version)) */ 
        INTO {change_table_name}
        (
          uuid,
          pure_version,
          change_type,
          family_system_name,
          inserted,
          json_document
        ) VALUES (
          :uuid,
          :pure_version,
          :change_type,
          :family_system_name,
          :inserted,
          :json_document
        )
    '''

@validate_api_version
def insert_change_documents(
    cursor,
    *,
    documents,
    api_version
):
    """Bulk-inserts change rows into the change table.

    Args:
        cursor: Database cursor used to execute statements.
        documents: Iterable of change bind mappings.
        api_version: Pure API version identifier.
    """
    sql = insert_change_sql(
        cursor,
        api_version=api_version
    )
    cursor.executemany(sql, documents)

@validate_api_version
@validate_collection_names
def delete_documents_based_on_changes_sql(
    cursor,
    *,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None,
    staging=False
):
    """Builds SQL to delete collection documents marked as DELETE changes.

    Args:
        cursor: Database cursor used for validation context.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.
        staging: Unused compatibility parameter.

    Returns:
        Delete SQL that removes rows matching DELETE changes.
    """
    # Not bothering to check for max(pure_version) here because historically
    # DELETEs have always been the max version.
    collection_table_name = get_collection_table_name(
        api_version=api_version,
        collection_local_name=collection_local_name
    )
    change_table_name = get_change_table_name(
        api_version=api_version
    )
    return f'''
        DELETE FROM {collection_table_name}
        WHERE uuid IN (
          SELECT uuid FROM {change_table_name}
          WHERE change_type = 'DELETE'
          AND family_system_name = '{collection_family_system_name}'
        )
    '''

@validate_api_version
@validate_collection_names
@function_call_logger
@function_time_logger
def delete_documents_based_on_changes(
    cursor,
    *,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None,
    staging=False
):
    """Deletes collection rows whose UUIDs are marked as DELETE changes.

    Args:
        cursor: Database cursor used to execute statements.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.
        staging: Unused compatibility parameter.
    """
    sql = delete_documents_based_on_changes_sql(
        cursor,
        collection_local_name=collection_local_name,
        api_version=api_version
    )
    cursor.execute(sql)

@validate_api_version
@validate_collection_names
def insert_change_deletes_history_sql(
    cursor,
    *,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None,
    staging=False
):
    """Builds SQL to merge DELETE change rows into change history.

    Args:
        cursor: Database cursor used for validation context.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.
        staging: Unused compatibility parameter.

    Returns:
        Merge SQL for history insertion of DELETE change rows.
    """
    change_table_name = get_change_table_name(
        api_version=api_version
    )
    change_history_table_name = get_change_table_name(
        api_version=api_version,
        history=True
    )
    return f'''
        MERGE INTO {change_history_table_name} pjh
        USING (
          SELECT
            uuid,
            pure_version,
            family_system_name,
            change_type,
            inserted
          FROM {change_table_name}
          WHERE
            change_type = 'DELETE'
            AND pj.family_system_name = '{collection_family_system_name}'
        )
        ON (pj.uuid = pjh.uuid AND pj.pure_version = pjh.pure_version)
        WHEN NOT MATCHED THEN
          INSERT (pjh.uuid, pjh.pure_version, pjh.family_system_name, pjh.change_type, pjh.inserted)
          VALUES (pj.uuid, pj.pure_version, pj.family_system_name, pj.change_type, pj.inserted)
    '''

@validate_api_version
@validate_collection_names
@function_call_logger
@function_time_logger
def insert_change_deletes_history(
    cursor,
    *,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None,
    staging=False
):
    """Merges DELETE change rows into the change history table.

    Args:
        cursor: Database cursor used to execute statements.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.
        staging: Unused compatibility parameter.
    """
    sql = insert_change_deletes_history_sql(
        cursor,
        collection_local_name=collection_local_name,
        api_version=api_version
    )
    cursor.execute(sql)

@validate_api_version
@validate_collection_names
def delete_change_deletes_sql(
    cursor,
    *,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None
):
    """Builds SQL to remove DELETE rows from the change table.

    Args:
        cursor: Database cursor used for validation context.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.

    Returns:
        Delete SQL for change rows of type DELETE.
    """
    change_table_name = get_change_table_name(
        api_version=api_version
    )
    return f'''
        DELETE FROM {change_table_name}
        WHERE change_type = 'DELETE'
        AND family_system_name = '{collection_family_system_name}'
    '''

@validate_api_version
@validate_collection_names
@function_call_logger
@function_time_logger
def delete_change_deletes(
    cursor,
    *,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None,
    staging=False
):
    """Deletes DELETE rows from the change table.

    Args:
        cursor: Database cursor used to execute statements.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.
        staging: Unused compatibility parameter.
    """
    sql = delete_change_deletes_sql(
        cursor,
        collection_local_name=collection_local_name,
        api_version=api_version
    )
    cursor.execute(sql)

@validate_api_version
@validate_collection_names
def process_change_deletes(
    cursor,
    *,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None
):
    """Processes DELETE changes in one transaction.

    This removes affected documents, archives DELETE changes to history, and
    then removes processed DELETE rows from the change table.

    Args:
        cursor: Database cursor used to execute statements.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.

    Raises:
        Exception: Re-raises any exception after rolling back the transaction.
    """
    connection = cursor.connection
    connection.begin()

    try:
        delete_documents_based_on_changes(
            cursor,
            collection_local_name=collection_local_name,
            api_version=api_version
        )

        insert_change_deletes_history(
            cursor,
            collection_family_system_name=collection_family_system_name,
            api_version=api_version
        )

        delete_change_deletes(
            cursor,
            collection_family_system_name=collection_family_system_name,
            api_version=api_version
        )
    except Exception as e:
        connection.rollback()
        raise e

    connection.commit()

@validate_api_version
@validate_collection_names
def insert_change_history_matching_previous_uuids_sql(
    cursor,
    *,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None
):
    """Builds SQL to archive changes matching previous UUID references.

    Args:
        cursor: Database cursor used for validation context.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.

    Returns:
        Merge SQL that copies matching change rows into history.
    """
    change_table_name = get_change_table_name(
        api_version=api_version
    )
    change_history_table_name = get_change_table_name(
        api_version=api_version,
        history=True
    )
    collection_table_name = get_collection_table_name(
        api_version=api_version,
        collection_local_name=collection_local_name
    )
    return f'''
        MERGE INTO {change_history_table_name} pjh
        USING (
          SELECT
            uuid,
            pure_version,
            family_system_name,
            change_type,
            inserted
          FROM {change_table_name}
          WHERE uuid IN (
            SELECT jt.previous_uuid
            FROM {collection_table_name},
              JSON_TABLE(json_document, '$'
                COLUMNS (
                  uuid VARCHAR2(36) PATH '$.uuid',
                  NESTED PATH '$.info.previousUuids[*]'
                    COLUMNS (
                      previous_uuid VARCHAR2(36) PATH '$'
                    )
                )
              )
              AS jt
              WHERE JSON_EXISTS(json_document, '$.info.previousUuids') AND jt.previous_uuid IS NOT NULL
          )
        ) pj
        ON (pj.uuid = pjh.uuid AND pj.pure_version = pjh.pure_version)
        WHEN NOT MATCHED THEN
          INSERT (pjh.uuid, pjh.pure_version, pjh.family_system_name, pjh.change_type, pjh.inserted)
          VALUES (pj.uuid, pj.pure_version, pj.family_system_name, pj.change_type, pj.inserted)
    '''

@validate_api_version
@validate_collection_names
@function_call_logger
@function_time_logger
def insert_change_history_matching_previous_uuids(
    cursor,
    *,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None
):
    """Archives changes whose UUIDs match previous UUID links in documents.

    Args:
        cursor: Database cursor used to execute statements.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.
    """
    sql = insert_change_history_matching_previous_uuids_sql(
        cursor,
        collection_local_name=collection_local_name,
        api_version=api_version
    )
    cursor.execute(sql)

@validate_api_version
@validate_collection_names
def delete_changes_matching_previous_uuids_sql(
    cursor,
    *,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None
):
    """Builds SQL to delete changes matching previous UUID references.

    Args:
        cursor: Database cursor used for validation context.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.

    Returns:
        Delete SQL for matching change rows.
    """
    change_table_name = get_change_table_name(
        api_version=api_version
    )
    collection_table_name = get_collection_table_name(
        api_version=api_version,
        collection_local_name=collection_local_name
    )
    return f'''
        DELETE FROM {change_table_name}
        WHERE uuid IN (
          SELECT jt.previous_uuid
          FROM {collection_table_name},
            JSON_TABLE(json_document, '$'
              COLUMNS (
                uuid VARCHAR2(36) PATH '$.uuid',
                NESTED PATH '$.info.previousUuids[*]'
                  COLUMNS (
                    previous_uuid VARCHAR2(36) PATH '$'
                  )
              )
            )
            AS jt
            WHERE JSON_EXISTS(json_document, '$.info.previousUuids') AND jt.previous_uuid IS NOT NULL
        )
    '''

@validate_api_version
@validate_collection_names
@function_call_logger
@function_time_logger
def delete_changes_matching_previous_uuids(
    cursor,
    *,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None
):
    """Deletes changes that match previous UUID links in documents.

    Args:
        cursor: Database cursor used to execute statements.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.
    """
    sql = delete_changes_matching_previous_uuids_sql(
        cursor,
        collection_local_name=collection_local_name,
        api_version=api_version
    )
    cursor.execute(sql)

@validate_api_version
@validate_collection_names
def process_changes_matching_previous_uuids(
    cursor,
    *,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None
):
    """Archives then deletes changes matching previous UUID links.

    Args:
        cursor: Database cursor used to execute statements.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.

    Raises:
        Exception: Re-raises any exception after rolling back the transaction.
    """
    connection = cursor.connection
    connection.begin()

    try:
        insert_change_history_matching_previous_uuids(
            cursor,
            collection_local_name=collection_local_name,
            api_version=api_version
        )

        delete_changes_matching_previous_uuids(
            cursor,
            collection_local_name=collection_local_name,
            api_version=api_version
        )
    except Exception as e:
        connection.rollback()
        raise e

    connection.commit()

@validate_api_version
@validate_collection_names
def truncate_staging(
    cursor,
    *,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None
):
    """Truncates the staging table for the resolved collection.

    Args:
        cursor: Database cursor used to execute statements.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.
    """
    collection_staging_table_name = get_collection_table_name(
        api_version=api_version,
        collection_local_name=collection_local_name,
        staging=True
    )
    cursor.execute(f'TRUNCATE TABLE {collection_staging_table_name}')

@validate_api_version
@validate_collection_names
def distinct_change_uuids_for_collection(
    cursor,
    *,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None
):
    """Returns distinct change UUIDs for a specific collection family.

    Args:
        cursor: Database cursor used to execute queries.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.

    Returns:
        Distinct UUID values from the change table for the collection family.
    """
    change_table_name = get_change_table_name(
        api_version=api_version
    )
    cursor.execute(
        f'SELECT DISTINCT(uuid) FROM {change_table_name} WHERE family_system_name = :family_system_name',
        {'family_system_name': collection_family_system_name}
    )
    return [row[0] for row in cursor.fetchall()]

@validate_api_version
@validate_collection_names
def insert_change_history_matching_staging_sql(
    cursor,
    *,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None
):
    """Builds SQL to archive changes whose UUIDs are in staging.

    Args:
        cursor: Database cursor used for validation context.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.

    Returns:
        Merge SQL for archiving matching change rows.
    """
    change_table_name = get_change_table_name(
        api_version=api_version
    )
    change_history_table_name = get_change_table_name(
        api_version=api_version,
        history=True
    )
    collection_staging_table_name = get_collection_table_name(
        api_version=api_version,
        collection_local_name=collection_local_name,
        staging=True
    )
    return f'''
        MERGE INTO {change_history_table_name} pjh
        USING (
          SELECT
            uuid,
            pure_version,
            family_system_name,
            change_type,
            inserted
          FROM {change_table_name}
          WHERE uuid IN (
            SELECT uuid FROM {collection_staging_table_name}
          )
        ) pj
        ON (pj.uuid = pjh.uuid AND pj.pure_version = pjh.pure_version)
        WHEN NOT MATCHED THEN
          INSERT (pjh.uuid, pjh.pure_version, pjh.family_system_name, pjh.change_type, pjh.inserted)
          VALUES (pj.uuid, pj.pure_version, pj.family_system_name, pj.change_type, pj.inserted)
    '''

@validate_api_version
@validate_collection_names
@function_call_logger
@function_time_logger
def insert_change_history_matching_staging(
    cursor,
    *,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None
):
    """Archives changes whose UUIDs are present in staging.

    Args:
        cursor: Database cursor used to execute statements.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.
    """
    sql = insert_change_history_matching_staging_sql(
        cursor,
        collection_local_name=collection_local_name,
        api_version=api_version
    )
    cursor.execute(sql)

@validate_api_version
@validate_collection_names
def delete_changes_matching_staging_sql(
    cursor,
    *,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None
):
    """Builds SQL to delete changes whose UUIDs are in staging.

    Args:
        cursor: Database cursor used for validation context.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.

    Returns:
        Delete SQL for matching staged UUIDs.
    """
    change_table_name = get_change_table_name(
        api_version=api_version
    )
    collection_staging_table_name = get_collection_table_name(
        api_version=api_version,
        collection_local_name=collection_local_name,
        staging=True
    )
    return f'''
        DELETE FROM {change_table_name}
        WHERE uuid IN (
          SELECT uuid FROM {collection_staging_table_name}
        )
    '''

@validate_api_version
@validate_collection_names
@function_call_logger
@function_time_logger
def delete_changes_matching_staging(
    cursor,
    *,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None
):
    """Deletes changes whose UUIDs are present in staging.

    Args:
        cursor: Database cursor used to execute statements.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.
    """
    sql = delete_changes_matching_staging_sql(
        cursor,
        collection_local_name=collection_local_name,
        api_version=api_version
    )
    cursor.execute(sql)

@validate_api_version
@validate_collection_names
def process_changes_matching_staging(
    cursor,
    *,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None
):
    """Archives then deletes changes that match staging UUIDs.

    Args:
        cursor: Database cursor used to execute statements.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.

    Raises:
        Exception: Re-raises any exception after rolling back the transaction.
    """
    connection = cursor.connection
    connection.begin()

    try:
        insert_change_history_matching_staging(
            cursor,
            collection_local_name=collection_local_name,
            api_version=api_version
        )

        delete_changes_matching_staging(
            cursor,
            collection_local_name=collection_local_name,
            api_version=api_version
        )
    except Exception as e:
        connection.rollback()
        raise e

    connection.commit()

@validate_api_version
@validate_collection_names
def merge_documents_from_staging_sql(
    cursor,
    *,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None
):
    """Builds SQL to upsert latest staging documents into base collection.

    Args:
        cursor: Database cursor used for validation context.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.

    Returns:
        Merge SQL that updates newer rows and inserts missing rows.
    """
    collection_table_name = get_collection_table_name(
        api_version=api_version,
        collection_local_name=collection_local_name
    )
    collection_staging_table_name = get_collection_table_name(
        api_version=api_version,
        collection_local_name=collection_local_name,
        staging=True
    )
    return f'''
        MERGE INTO {collection_table_name} pj
        USING (
          SELECT uuid, inserted, json_document, updated, pure_created, pure_modified FROM ( 
            SELECT uuid, inserted, json_document, updated, pure_created, pure_modified,
              RANK() OVER (PARTITION BY uuid ORDER BY pure_modified DESC) latest
              FROM {collection_staging_table_name}
          ) where latest = 1
        ) pjs
        ON (pjs.uuid = pj.uuid)
        WHEN MATCHED
          THEN UPDATE SET
            pj.pure_modified = pjs.pure_modified,
            pj.updated = pjs.updated,
            pj.json_document = pjs.json_document
          WHERE
            pjs.pure_modified > pj.pure_modified
        WHEN NOT MATCHED
          THEN INSERT (pj.uuid, pj.inserted, pj.json_document, pj.updated, pj.pure_created, pj.pure_modified)
          VALUES (pjs.uuid, pjs.inserted, pjs.json_document, pjs.updated, pjs.pure_created, pjs.pure_modified)
    '''

@validate_api_version
@validate_collection_names
@function_call_logger
@function_time_logger
def merge_documents_from_staging(
    cursor,
    *,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None
):
    """Merges latest staging documents into the base collection table.

    Args:
        cursor: Database cursor used to execute statements.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.
    """
    sql = merge_documents_from_staging_sql(
        cursor,
        collection_local_name=collection_local_name,
        api_version=api_version
    )
    cursor.execute(sql)

@validate_api_version
@validate_collection_names
def delete_documents_matching_previous_uuids_sql(
    cursor,
    *,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None
):
    """Builds SQL to delete rows superseded by previous UUID links.

    Args:
        cursor: Database cursor used for validation context.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.

    Returns:
        Delete SQL for rows whose UUID appears in previousUuids.
    """
    collection_table_name = get_collection_table_name(
        api_version=api_version,
        collection_local_name=collection_local_name
    )
    return f'''
        DELETE FROM {collection_table_name}
        WHERE uuid IN (
          SELECT jt.previous_uuid
          FROM {collection_table_name},
            JSON_TABLE(json_document, '$'
              COLUMNS (
                uuid VARCHAR2(36) PATH '$.uuid',
                NESTED PATH '$.info.previousUuids[*]'
                  COLUMNS (
                    previous_uuid VARCHAR2(36) PATH '$'
                  )
              )
            )
            AS jt
            WHERE JSON_EXISTS(json_document, '$.info.previousUuids') AND jt.previous_uuid IS NOT NULL
        )
    '''

@validate_api_version
@validate_collection_names
@function_call_logger
@function_time_logger
def delete_documents_matching_previous_uuids(
    cursor,
    *,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None
):
    """Deletes rows whose UUID appears in any previousUuids array.

    Args:
        cursor: Database cursor used to execute statements.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.
    """
    sql = delete_documents_matching_previous_uuids_sql(
        cursor,
        collection_local_name=collection_local_name,
        api_version=api_version
    )
    cursor.execute(sql)

@validate_api_version
@validate_collection_names
def load_documents_from_staging(
    cursor,
    *,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None
):
    """Loads staging documents into base table in one transaction.

    This merges staged rows, removes rows matched by previous UUID links, and
    truncates the staging table.

    Args:
        cursor: Database cursor used to execute statements.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.

    Raises:
        Exception: Re-raises any exception after rolling back the transaction.
    """
    connection = cursor.connection
    connection.begin()

    try:
        merge_documents_from_staging(
            cursor,
            collection_local_name=collection_local_name,
            api_version=api_version
        )

        delete_documents_matching_previous_uuids(
            cursor,
            collection_local_name=collection_local_name,
            api_version=api_version
        )

        truncate_staging(
            cursor,
            collection_local_name=collection_local_name,
            api_version=api_version
        )

    except Exception as e:
        connection.rollback()
        raise e

    connection.commit()

@validate_api_version
@validate_collection_names
def delete_documents_matching_uuids_sql(
    cursor,
    *,
    uuids,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None,
    staging=False
):
    """Builds SQL to delete collection rows matching explicit UUIDs.

    Args:
        cursor: Database cursor used for validation context.
        uuids: UUIDs to remove.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.
        staging: Unused compatibility parameter.

    Returns:
        Parameterized delete SQL with dynamic UUID bind variables.
    """
    collection_table_name = get_collection_table_name(
        api_version=api_version,
        collection_local_name=collection_local_name
    )
    bind_vars = ','.join(f':{i}' for i in range(len(uuids)))
    return f'''
        DELETE FROM {collection_table_name}
        WHERE uuid IN ({bind_vars})
    '''

@validate_api_version
@validate_collection_names
@function_call_logger
@function_time_logger
def delete_documents_matching_uuids(
    cursor,
    *,
    uuids,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None
):
    """Deletes collection rows matching explicit UUIDs.

    Args:
        cursor: Database cursor used to execute statements.
        uuids: UUIDs to remove.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.
    """
    sql = delete_documents_matching_uuids_sql(
        cursor,
        uuids=uuids,
        collection_local_name=collection_local_name,
        api_version=api_version
    )
    cursor.execute(sql, uuids)

@validate_api_version
@validate_collection_names
def insert_change_history_matching_uuids_sql(
    cursor,
    *,
    uuids,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None
):
    """Builds SQL to archive changes matching explicit UUIDs.

    Args:
        cursor: Database cursor used for validation context.
        uuids: UUIDs used to select change rows.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.

    Returns:
        Merge SQL for inserting matching rows into change history.
    """
    change_table_name = get_change_table_name(
        api_version=api_version
    )
    change_history_table_name = get_change_table_name(
        api_version=api_version,
        history=True
    )
    bind_vars = ','.join(f':{i}' for i in range(len(uuids)))
    return f'''
        MERGE INTO {change_history_table_name} pjh
        USING (
          SELECT
            uuid,
            pure_version,
            family_system_name,
            change_type,
            inserted
          FROM {change_table_name}
          WHERE uuid in ({bind_vars})
        ) pj
        ON (pj.uuid = pjh.uuid AND pj.pure_version = pjh.pure_version)
        WHEN NOT MATCHED THEN
          INSERT (pjh.uuid, pjh.pure_version, pjh.family_system_name, pjh.change_type, pjh.inserted)
          VALUES (pj.uuid, pj.pure_version, pj.family_system_name, pj.change_type, pj.inserted)
    '''

@validate_api_version
@validate_collection_names
@function_call_logger
@function_time_logger
def insert_change_history_matching_uuids(
    cursor,
    *,
    uuids,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None
):
    """Archives changes matching explicit UUIDs into history.

    Args:
        cursor: Database cursor used to execute statements.
        uuids: UUIDs used to select change rows.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.
    """
    sql = insert_change_history_matching_uuids_sql(
        cursor,
        uuids=uuids,
        collection_local_name=collection_local_name,
        api_version=api_version
    )
    cursor.execute(sql, uuids)

@validate_api_version
@validate_collection_names
def delete_changes_matching_uuids_sql(
    cursor,
    *,
    uuids,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None
):
    """Builds SQL to delete change rows matching explicit UUIDs.

    Args:
        cursor: Database cursor used for validation context.
        uuids: UUIDs used to select change rows.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.

    Returns:
        Parameterized delete SQL with dynamic UUID bind variables.
    """
    change_table_name = get_change_table_name(
        api_version=api_version
    )
    bind_vars = ','.join(f':{i}' for i in range(len(uuids)))
    return f'''
        DELETE FROM {change_table_name}
        WHERE uuid IN ({bind_vars})
    '''

@validate_api_version
@validate_collection_names
@function_call_logger
@function_time_logger
def delete_changes_matching_uuids(
    cursor,
    *,
    uuids,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None
):
    """Deletes change rows matching explicit UUIDs.

    Args:
        cursor: Database cursor used to execute statements.
        uuids: UUIDs used to select change rows.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.
    """
    sql = delete_changes_matching_uuids_sql(
        cursor,
        uuids=uuids,
        collection_local_name=collection_local_name,
        api_version=api_version
    )
    cursor.execute(sql, uuids)

@validate_api_version
@validate_collection_names
def delete_documents_and_changes_matching_uuids(
    cursor,
    *,
    uuids,
    api_version,
    collection_local_name=None,
    collection_api_name=None,
    collection_family_system_name=None
):
    """Deletes collection rows and corresponding change rows in one transaction.

    This deletes target collection documents, archives matching changes into
    history, and removes those changes from the change table.

    Args:
        cursor: Database cursor used to execute statements.
        uuids: UUIDs used to target documents and change rows.
        api_version: Pure API version identifier.
        collection_local_name: Local collection name.
        collection_api_name: API collection name alternative.
        collection_family_system_name: Family system name alternative.

    Raises:
        Exception: Re-raises any exception after rolling back the transaction.
    """
    connection = cursor.connection
    connection.begin()

    try:
        delete_documents_matching_uuids(
            cursor,
            uuids=uuids,
            collection_local_name=collection_local_name,
            api_version=api_version
        )

        insert_change_history_matching_uuids(
            cursor,
            uuids=uuids,
            collection_local_name=collection_local_name,
            api_version=api_version
        )

        delete_changes_matching_uuids(
            cursor,
            uuids=uuids,
            collection_local_name=collection_local_name,
            api_version=api_version
        )
    except Exception as e:
        connection.rollback()
        raise e

    connection.commit()
