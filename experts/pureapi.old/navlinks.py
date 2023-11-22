pages = [
    { "title": "page_with_next_link",
      "navigationLinks": [
          { "ref": "next",
            "href": "https://experts.umn.edu/ws/api/524/organisational-units?size=500&offset=500"
          },
      ],
    },
    { "title": "page_with_prev_and_next_links",
      "navigationLinks": [
          { "ref": "prev",
            "href": "https://experts.umn.edu/ws/api/524/organisational-units?size=500&offset=0"
          },
          { "ref": "next",
            "href": "https://experts.umn.edu/ws/api/524/organisational-units?size=500&offset=1000"
          },
      ],
    },
    { "title": "page_with_prev_link",
      "navigationLinks": [
          { "ref": "prev",
            "href": "https://experts.umn.edu/ws/api/524/organisational-units?size=500&offset=500"
          },
      ],
    },
    { "title": "page_with_no_links",
    },
]

for page in pages:
    print(page['title'])
    #if 'navigationLinks' in page and next((link for link in page['navigationLinks'] if link['ref'] == 'next'), None):
    if 'navigationLinks' in page and list(filter(lambda link: link['ref'] == 'next', page['navigationLinks'])):
        print('  found next link')
    else:
        print('  no next link found')

