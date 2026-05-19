import dotenv_switch.auto

import json
import sys

from pyrsistent import m
from returns.result import Success, Failure

from experts.api import scopus

id_type = sys.argv[1]
id_value = sys.argv[2]

with scopus.Client(base_path='analytics') as client:

    match client.get(f'plumx/{id_type}/{id_value}'):
        case Success(response):
            print(json.dumps(response.json(), indent=2))
        case Failure(exception_should_not_happen):
            raise exception_should_not_happen

