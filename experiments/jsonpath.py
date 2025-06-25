import dotenv_switch.auto

from itertools import chain
import json
import sys

import jsonpath_ng.ext as jp

filename = sys.argv[1]
with open(filename) as file:
    abstract = json.load(file)

    #scopus_id_expr = jp.parse("$.abstracts-retrieval-response.item.bibrecord.item-info.itemidlist.itemid[?('@idtype'=='SGR')]['$']")
    #scopus_id_expr = jp.parse("$.abstracts-retrieval-response.item.bibrecord.item-info.itemidlist.itemid[?('@idtype'=='SGR')]")

    itemids_expr = jp.parse("$..itemidlist.itemid[*]")
    #itemids_expr = jp.parse("$..itemidlist.itemid")
    itemids = [match.value for match in itemids_expr.find(abstract)]
    print(f'{itemids=}')

    scopus_itemid_expr = jp.parse("$..itemidlist.itemid[?('@idtype'=='SGR')]")
    scopus_itemid = scopus_itemid_expr.find(abstract)[0].value
    print(f'{scopus_itemid=}')

    scopus_id_expr = jp.parse("$..itemidlist.itemid[?('@idtype'=='SGR')]['$']")
    scopus_id = scopus_id_expr.find(abstract)[0].value
    print(f'{scopus_id=}')

    # works:
    ref_itemids_expr = jp.parse("$..reference[*].ref-info.refd-itemidlist.itemid")

    #ref_scopus_ids_expr = jp.parse("$..reference[*]['ref-info']['refd-itemidlist'].itemid[?(@.'@idtype'=='SGR')]['$']")
    #ref_scopus_ids_expr = jp.parse("$..reference[*].ref-info.refd-itemidlist.itemid[?@.'@idtype'=='SGR']")
    #ref_scopus_ids_expr = jp.parse("$..reference[*].ref-info.refd-itemidlist.itemid[?('@idtype'=='SGR')]")
    #ref_scopus_ids_expr = jp.parse("$..reference[*].ref-info.refd-itemidlist.itemid['@idtype','$']")
    #ref_scopus_ids_expr = jp.parse("$..reference[*].ref-info.refd-itemidlist.itemid[?('@idtype'=='SGR')]")

    #ref_scopus_ids_expr = jp.parse("$..reference[*]['ref-info']['refd-itemidlist'].itemid[?('@idtype'=='SGR')]['$']")
    #ref_scopus_ids_expr = jp.parse("$..reference[*]['ref-info']['refd-itemidlist'].itemid[?('@idtype'=='SGR')]")
    #ref_scopus_ids_expr = jp.parse("$..reference[*][?(ref-info.refd-itemidlist.itemid['@idtype']=='SGR')]")

    # works
    #ref_scopus_ids_expr = jp.parse("$..reference[*]['ref-info']['refd-itemidlist'].itemid['$']")

    # works
    #ref_scopus_ids_expr = jp.parse("$..reference[*]['ref-info']['refd-itemidlist'].itemid['@idtype']")

    refcount_expr = jp.parse("$..['@refcount']")
    matches = refcount_expr.find(abstract)
    refcount = int(matches[0].value) if matches else 0
    print(f'{refcount=}')

#    for _match in ref_itemids_expr.find(abstract):
#        print(_match.value)
#    ref_itemids_match_lists = list(map(
#        lambda x: [x.value] if isinstance(x.value, dict) else x.value,
#        ref_itemids_expr.find(abstract)
#    ))
#    print(f'{ref_itemids_match_lists=}')

#    ref_itemids_match_list_of_dicts = list(chain.from_iterable(map(
#        lambda x: [x.value] if isinstance(x.value, dict) else x.value,
#        ref_itemids_expr.find(abstract)
#    )))
#    print(f'{ref_itemids_match_list_of_dicts=}')

    def flatten_mixed_match_values(matches: list):
        for _match in matches:
            if isinstance(_match.value, list):
                for subvalue in _match.value:
                    yield subvalue
            else:
                yield _match.value

#    ref_scopus_ids = [
#        _match.value['$']
#        for _match in flatten_nested_match_lists(ref_itemids_expr.find(abstract))
#        if _match.value['@idtype'] == 'SGR'
#    ]

    ref_scopus_ids = [
        itemid['$'] for itemid in filter(
            lambda itemid: itemid['@idtype'] == 'SGR',
            flatten_mixed_match_values(
                #ref_itemids_expr.find(abstract)
                jp.parse("$..reference[*].ref-info.refd-itemidlist.itemid").find(abstract)
            )
        )
    ]
    print(f'{len(ref_scopus_ids)=}')
    print(f'{ref_scopus_ids=}')
    
#    issn_expr = jp.parse('$.abstracts-retrieval-response.item.bibrecord.head.source.issn')
#    issn_match = issn_expr.find(abstract)
#    print('issn:', issn_match[0].value)
#    
#    prism_issn_expr = jp.parse("$.abstracts-retrieval-response.coredata['prism:issn']")
#    prism_issn_match = prism_issn_expr.find(abstract)
#    print('prism_issn:', prism_issn_match[0].value)
#
#    bogus_expr = jp.parse('$.abstracts-retrieval-response.item.bibrecord.head.source.bogus')
#    bogus_match = bogus_expr.find(abstract)
#    print(f'{bogus_match=}')
    
