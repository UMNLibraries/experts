from datetime import datetime
from threading import Thread
from queue import Queue

from loguru import logger

from experts_dw import db, scopus_json
from experts_dw.scopus_json_collection_meta import \
    get_collection_meta_by_local_name

from experts.api import scopus
from experts.api.scopus import ScopusIds

def producer(queue: Queue, scopus_client: scopus.Client, scopus_ids: ScopusIds) -> None:
    probably_defunct_scopus_ids_list = []

    for assorted_results in scopus_client.get_assorted_citations_by_scopus_ids(scopus_ids):
        probably_defunct_scopus_ids_list += list(assorted_results.success.probably_defunct_scopus_ids)
        queue.put(assorted_results)

    # Download only the probably defunct Scopus IDs, to verify that they really return 404s:
    probably_defunct_scopus_ids_set, _ = ScopusIds.factory(
        probably_defunct_scopus_ids_list
    )
    for assorted_results in scopus_client.get_assorted_citations_by_scopus_ids(probably_defunct_scopus_ids_set):
        queue.put(assorted_results)

def consumer(queue: Queue, db_session) -> None:
    select_cursor = db_session.cursor()
    meta = get_collection_meta_by_local_name(
        cursor=select_cursor,
        local_name='citation',
    )
    insert_cursor = db_session.cursor()

    while True:
        assorted_results = queue.get()

        documents_to_insert = [
            {
                'scopus_id': record.scopus_id,
                'scopus_created': record.sort_year,
                'scopus_modified': record.sort_year,
                'inserted': datetime.now(),
                'updated': datetime.now(),
                'json_document': record.json_dumps(),
            }
            for record in assorted_results.success.single_records
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
            scopus_ids=assorted_results.defunct.requested_scopus_ids,
            meta=meta,
        )

        # log errors for scopus ids in error list
        for result in assorted_results.error:
            logger.error('request failed', error=result.serialize())

        db_session.commit()

        queue.task_done()

@logger.catch
def run() -> None:
    with (
        db.cx_oracle_connection() as db_session,
        scopus.Client() as scopus_client,
        logger.contextualize(vendor='scopus', content_type='citation'),
    ):
        select_cursor = db_session.cursor()
        abstract_meta = get_collection_meta_by_local_name(
            cursor=select_cursor,
            local_name='abstract',
        )
        citation_meta = get_collection_meta_by_local_name(
            cursor=select_cursor,
            local_name='citation',
        )

        insert_cursor = db_session.cursor()
        scopus_json.update_citation_to_download(
            cursor=insert_cursor,
            abstract_meta=abstract_meta,
            citation_meta=citation_meta,
        )

        scopus_ids, invalid_scopus_ids = ScopusIds.factory(
            scopus_json.scopus_ids_to_download(
                select_cursor,
                meta=citation_meta,
            ),
        )
        # TODO: Handle any invalid_scopus_ids

        queue = Queue()
        consumer = Thread(target=consumer, args=(queue, db_session), daemon=True)
        consumer.start()
        producer = Thread(target=producer, args=(queue, scopus_client, scopus_ids))
        producer.start()

        producer.join()
        queue.join()

        meta = get_collection_meta_by_local_name(
            cursor=insert_cursor,
            local_name='citation',
        )
        scopus_json.load_documents_from_staging(
            insert_cursor,
            meta=citation_meta,
        )

        db_session.commit()
