import dotenv_switch.auto

from itertools import islice

from experts.api.scopus import \
    Client, \
    AbstractRequestResultAssorter as a_assorter, \
    CitationRequestResultAssorter as c_assorter, \
    AbstractResponseBodyParser as parser

with Client() as session:
    authored_scopus_ids = [
        '75149190029',
        '85150001360',
        '49949145584',
        '84924664029',
        '85159902125',
    ]
    
    # This works, but we don't need it in this little test program. Will come in handy for
    # processing results in chunks, though.
    #authored_assorted_results = assorter.assort(
    #    islice(session.get_many_abstracts_by_scopus_id(scopus_ids), len(scopus_ids))
    #)
    authored_assorted_results = a_assorter.assort(
        session.get_many_abstracts_by_scopus_id(authored_scopus_ids)
    )
    for response in authored_assorted_results.success.values():
        print(f'{response.headers=}')

    print(f'{authored_assorted_results.success.keys()=}, {authored_assorted_results.defunct.keys()=}, {authored_assorted_results.error.keys()=}')
    print(f'{authored_assorted_results.scopus_ids()=}')

    cited_scopus_ids = [
        scopus_id
        for value in authored_assorted_results.success.values()
            for scopus_id in parser.reference_scopus_ids(value.body)
    ]
    print(f'{cited_scopus_ids=}')
    cited_assorted_results = c_assorter.assort(
        session.get_many_citations_by_scopus_ids(cited_scopus_ids)
    )
    print(f'{cited_assorted_results.success.keys()=}, {cited_assorted_results.defunct.keys()=}, {cited_assorted_results.error.keys()=}')
    print(f'{cited_assorted_results.scopus_ids()=}')
    print(f'{cited_assorted_results.success.scopus_ids()=}')
    print(f'{cited_assorted_results.success_subrecords.keys()=}')
    print(f'{cited_assorted_results.defunct.scopus_ids()=}')
    print(f'{cited_assorted_results.defunct_scopus_ids=}')

    # Why is this here?
    #print(f'{authored_assorted_results.success[next(iter(authored_scopus_ids))]}')
