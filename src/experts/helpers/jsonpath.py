def flatten_mixed_match_values(matches: list):
    '''
    Handles cases where jsonpath-ng matches may be either non-list values or lists of non-list values.

    This function is a generator that flattens the list of match values so that all items are non-list values.

    Example, from Scopus API abstracts:

    "reference": [
      {
        "ref-info": {
          "refd-itemidlist": {
            "itemid": {
              "$": "64349115740",
              "@idtype": "SGR"
            }
          }
        }
      },
      {
        "ref-info": {
          "refd-itemidlist": {
            "itemid": [
              {
                "$": "e25006",
                "@idtype": "ARTNUM"
              },
              {
                "$": "81155153943",
                "@idtype": "SGR"
              }
            ]
          }
        }
      }
    ]

    Loading the above into a dict called abstract and parsing with jsonpath-ng...

    import jsonpath_ng.ext as jp
    matches = jp.parse("$..reference[*].ref-info.refd-itemidlist.itemid").find(abstract)

    ...and then flattening with this function...

    for match in flatten_mixed_match_values(matches):
        print(match)

    ...produces:
    {"$": "64349115740", "@idtype": "SGR"}
    {"$": "e25006", "@idtype": "ARTNUM"}
    {"$": "81155153943", "@idtype": "SGR"}
    '''
    for _match in matches:
        if isinstance(_match.value, list):
            for subvalue in _match.value:
                yield subvalue
        else:
            yield _match.value
