import dotenv_switch.auto
import client_attempts_session
import returns
from returns.pipeline import is_successful
from returns.result import Result, Success, Failure, safe

with client_attempts_session.Config().session() as session:
    result = session.get('persons')
    print(result)
    if is_successful(result):
        response = result.unwrap()
        print(response.json())
