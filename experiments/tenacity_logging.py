import uuid
from tenacity import Retrying, RetryError, stop_after_attempt

def make_attempt(attempt_number):
    print('in make_attempt()')
    if (attempt_number < 3):
        raise Exception('My code is failing!')
    return True

try:
    result = None
    function_call_id = uuid.uuid4()
    for attempt in Retrying(stop=stop_after_attempt(3)):
        meta = {
            'function_call_id': str(function_call_id),
            'attempt': attempt.retry_state.attempt_number,
        }
        print(meta)
        with attempt:
            #raise Exception('My code is failing!')
            result = make_attempt(attempt.retry_state.attempt_number)
        print(f'result = {result}')
        if not attempt.retry_state.outcome.failed:
           attempt.retry_state.set_result(result)
        print(f'RetryState = {attempt.retry_state}')
        print(f'RetryState outcome = {attempt.retry_state.outcome}')
        print(f'RetryState outcome result = {attempt.retry_state.outcome.result}')
except RetryError:
    print('Caught a RetryError')
