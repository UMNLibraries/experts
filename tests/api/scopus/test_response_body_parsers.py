import pytest

from experts.api.scopus import AbstractResponseBodyParser

def test_abstract_response_body_parser():
    response = {
        'abstracts-retrieval-response': {
            'item': {
                'bibrecord': {
                    'head': {
                        'source': {
                            'codencode': 'FORIE',
                            'sourcetitle-abbrev': 'Food Res. Int.',
                            '@country': 'gbr',
                            'issn': {
                                '$': '09639969',
                                '@type': 'print'
                            },
                            'volisspag': {
                                'voliss': {
                                    '@volume': '43',
                                    '@issue': '2'
                                },
                                'pagerange': {
                                    '@first': '432',
                                    '@last': '442'
                                }
                            },
                            '@type': 'j',
                            'publicationyear': {
                                '@first': '2010'
                            },
                            'sourcetitle': 'Food Research International',
                            '@srcid': '23180',
                            'publicationdate': {
                                'month': '03',
                                'year': '2010',
                                'date-text': {
                                    '@xfab-added': 'true',
                                    '$': 'March 2010'
                                }
                            }
                        }
                    },
                    'tail': {
                        'bibliography': {
                            '@refcount': 3,
                            'reference': [
                                {
                                    'ref-fulltext': 'Adsule R.N. In: Nwoloko E., and Smartt J. (Eds). Food and feed from legumes and oilseeds (1996), Chapman & Hall Pub. 84-110',
                                    '@id': '1',
                                    'ref-info': {
                                        'ref-publicationyear': {
                                            '@first': '1996'
                                        },
                                        'refd-itemidlist': {
                                            'itemid': {
                                                '$': '75149160193',
                                                '@idtype': 'SGR'
                                            }
                                        },
                                        'ref-volisspag': {
                                            'pagerange': {
                                                '@first': '84',
                                                '@last': '110'
                                            }
                                        },
                                        'ref-text': 'Nwoloko E., and Smartt J. (Eds), Chapman & Hall Pub.',
                                        'ref-authors': {
                                            'author': [
                                                {
                                                    '@seq': '1',
                                                    'ce:initials': 'R.N.',
                                                    '@_fa': 'true',
                                                    'ce:surname': 'Adsule',
                                                    'ce:indexed-name': 'Adsule R.N.'
                                                }
                                            ]
                                        },
                                        'ref-sourcetitle': 'Food and feed from legumes and oilseeds'
                                    }
                                },
                                {
                                    'ref-fulltext': 'Agriculture & Agri-Food Canada (2006). Chickpeas: Situation and outlook. Bi-weekly Bulletin, 19(13). <www.agr.gc.ca> Retrieved 20.08.08.',
                                    '@id': '2',
                                    'ref-info': {
                                        'refd-itemidlist': {
                                            'itemid': {
                                                '$': '75149115900',
                                                '@idtype': 'SGR'
                                            }
                                        },
                                        'ref-text': 'Agriculture & Agri-Food Canada (2006). Chickpeas: Situation and outlook. Bi-weekly Bulletin, 19(13). <www.agr.gc.ca> Retrieved 20.08.08.'
                                    }
                                },
                                {
                                    'ref-fulltext': 'Agriculture & Agri-Food Canada (2006). Lentils: Situation and outlook. Bi-weekly Bulletin, 19(7). <www.agr.gc.ca> Retrieved 21.08.08.',
                                    '@id': '3',
                                    'ref-info': {
                                        'refd-itemidlist': {
                                            'itemid': {
                                                '$': '75149191551',
                                                '@idtype': 'SGR'
                                            }
                                        },
                                        'ref-text': 'Agriculture & Agri-Food Canada (2006). Lentils: Situation and outlook. Bi-weekly Bulletin, 19(7). <www.agr.gc.ca> Retrieved 21.08.08.'
                                    }
                                }
                            ]
                        }
                    }
                }
            }
        }
    }

    parser = AbstractResponseBodyParser
    assert parser.issn(response) == response['abstracts-retrieval-response']['item']['bibrecord']['head']['source']['issn']['$']
    assert parser.issn_type(response) == response['abstracts-retrieval-response']['item']['bibrecord']['head']['source']['issn']['@type']
    assert parser.refcount(response) == response['abstracts-retrieval-response']['item']['bibrecord']['tail']['bibliography']['@refcount']
    assert parser.refcount(response) == len(parser.reference_scopus_ids(response))
    assert parser.reference_scopus_ids(response) == ['75149160193','75149115900','75149191551']
