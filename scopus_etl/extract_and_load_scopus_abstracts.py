import dotenv_switch.auto

from datetime import datetime
import json
from functools import reduce
from threading import Thread
from queue import Queue

from experts_dw import db, scopus_json, pure_json_collection_meta
from experts_dw.scopus_json_collection_meta import \
    get_collection_meta_by_local_name

from experts.api import scopus
from experts.api.scopus import \
    ScopusIds

def producer(queue: Queue, scopus_client: scopus.Client, scopus_ids: ScopusIds) -> None:
    for assorted_results in scopus_client.get_assorted_abstracts_by_scopus_id(scopus_ids):
        queue.put(assorted_results)

def consumer(queue: Queue, db_session) -> None:
    select_cursor = db_session.cursor()
    meta = get_collection_meta_by_local_name(
        cursor=select_cursor,
        local_name='abstract',
    )
    insert_cursor = db_session.cursor()

    while True:
        assorted_results = queue.get()

        documents_to_insert = [
            {
                'scopus_id': result.requested_scopus_id, # or result.record.scopus_id
                'scopus_created': result.date_created,
                'scopus_modified': result.last_modified,
                'inserted': datetime.now(),
                'updated': datetime.now(),
                'json_document': result.response.text, # or result.record.json_dumps()
            }
            for result in assorted_results.success
        ]

        scopus_json.insert_documents(
           insert_cursor,
           documents=documents_to_insert,
           meta=meta,
           staging=True,
        )

        scopus_json.insert_defunct_scopus_ids(
            insert_cursor,
            scopus_ids=assorted_results.defunct.requested_scopus_ids,
            meta=meta,
        )

        # log errors for scopus ids in error list
        # TODO: Where to log these? Log file, db, or both?
        for result in assorted_results.error:
            # TODO: Maybe update the following to handle different types of errors?
            print(f'{result=}')

        db_session.commit()

        queue.task_done()

with db.cx_oracle_connection() as db_session, scopus.Client() as scopus_client:
    select_cursor = db_session.cursor()
    abstract_meta = get_collection_meta_by_local_name(
        cursor=select_cursor,
        local_name='abstract',
    )
    citation_meta = get_collection_meta_by_local_name(
        cursor=select_cursor,
        local_name='citation',
    )
    pure_ro_meta = pure_json_collection_meta.get_collection_meta_by_local_name(
        cursor=select_cursor,
        api_version='524',
        local_name='research_output',
    )

    insert_cursor = db_session.cursor()
    scopus_json.update_abstract_to_download(
        cursor=insert_cursor,
        abstract_meta=abstract_meta,
        citation_meta=citation_meta,
        pure_ro_meta=pure_ro_meta,
    )

    scopus_ids, invalid_scopus_ids = ScopusIds.factory(
        scopus_json.scopus_ids_to_download(
            select_cursor,
            meta=abstract_meta,
        ),
    )
    # TODO: Handle any invalid_scopus_ids

    queue = Queue()
    # The consumer loads raw json abstracts into the staging table...
    consumer = Thread(target=consumer, args=(queue, db_session), daemon=True)
    consumer.start()

    # ... which are fed to the consumer from the producer, which downloads abstracts
    # using the scopus api:
    producer = Thread(target=producer, args=(queue, scopus_client, scopus_ids))
    producer.start()

    producer.join()
    queue.join()

    scopus_json.load_documents_from_staging(
        insert_cursor,
        meta=abstract_meta,
    )

    db_session.commit()
