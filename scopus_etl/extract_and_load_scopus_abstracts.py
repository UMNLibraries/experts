import dotenv_switch.auto

from datetime import datetime
import json
from functools import reduce
#from itertools import batched

from experts_dw import db, scopus_json
from experts_dw.scopus_json_collection_meta import \
    get_collection_meta_by_local_name

from experts.api import scopus
from experts.api.scopus import \
    ScopusIds

scopus_ids_to_download_sql = 'SELECT scopus_id FROM scopus_abstract_to_download'

with db.cx_oracle_connection() as db_session, scopus.Client() as scopus_client:
    select_cursor = db_session.cursor()

    meta = get_collection_meta_by_local_name(
        cursor=select_cursor,
        local_name='abstract',
    )

    select_cursor.execute(scopus_ids_to_download_sql)
    # cx_Oracle columns definition:
    columns = [col[0] for col in select_cursor.description]
    # oracledb columns definition:
    #columns = [col.name for col in select_cursor.description]
    select_cursor.rowfactory = lambda *args: dict(zip(columns, args))
    scopus_ids, invalid_scopus_ids = ScopusIds.factory(
        [str(row['SCOPUS_ID']) for row in select_cursor.fetchall()]
    )
    # TODO: Handle any invalid_scopus_ids

    insert_cursor = db_session.cursor()

    # Initialize this to a number higher than it would ever be, because
    # we want to find the minimum, excluding this starting value:
    ratelimit_remaining = 1000000

    for assorted_results in scopus_client.get_assorted_abstracts_by_scopus_id(scopus_ids):    

        ratelimit_remaining = reduce(
            lambda smallest, current: smallest if (smallest < current) else current,
            # Hope that using list() below will resolve this error:
            # pyrsistent._checked_types.CheckedValueTypeError: Type AbstractSuccessResults can only be used with ('AbstractRequestSuccess',), not AbstractRequestResponseDefunct
            [result.ratelimit_remaining for result in list(assorted_results.success) + list(assorted_results.defunct)] + [ratelimit_remaining]
        )
        print(f'{ratelimit_remaining=}')

        documents_to_insert = [
            {
                'scopus_id': result.scopus_id,
                'scopus_created': result.date_created,
                'scopus_modified': result.last_modified,
                'inserted': datetime.now(),
                'updated': datetime.now(),
                'json_document': result.record.text,
            }
            for result in assorted_results.success
        ]
    
        scopus_json.insert_documents(
           insert_cursor,
           # TODO: Do we need list() here? Isn't it already a list?
           #documents=list(documents_to_insert),
           documents=documents_to_insert,
           meta=meta,
           staging=True,
        )

        scopus_json.insert_defunct_scopus_ids(
            insert_cursor,
            scopus_ids=assorted_results.defunct.scopus_ids,
            meta=meta,
        )

        # log errors for scopus ids in error list
        # TODO: Where to log these? Log file, db, or both?
        for result in assorted_results.error:
            # TODO: Update the following to handle different types of errors:
            print(f'{result.requested_scoppus_id=}: {result.error=}')

        db_session.commit()

    scopus_json.load_documents_from_staging(
        insert_cursor,
        meta=meta,
    )

    # remove scopus ids in scopus_json_abstract and scopus_abstract_defunct from scopus_abstract_to_download

    db_session.commit()

    print(f'{ratelimit_remaining=}')
