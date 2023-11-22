import time
import uuid

def fun(attempt_number):
    print('in fun()')
    if (attempt_number < 3):
        raise Exception('My code is failing!')
    return True

def attempt(timeout=60, wait_seconds=10, max_attempts=10):
    meta = {
        'function_call_id': str(uuid.uuid4()),
    }

    error = None
    result = None
    for attempt_number in (range(1, max_attempts+1)):
        error = None
        result = None
        retry = False
        start_time = time.perf_counter()
        pre_attempt_meta = {
            **meta,
            'attempt_stage': 'start',
            'attempt': attempt_number,
            'start_time': start_time,
        }
        if __debug__:
            print(pre_attempt_meta)

        post_attempt_meta = {
            **meta,
            'attempt': attempt_number,
            'attempt_stage': 'end',
        }

        try:
            result = fun(attempt_number)
        except Exception as e:
            error = e
            if isinstance(e, Exception):
                retry = True
            end_time = time.perf_counter()
            post_attempt_meta.update({
                'outcome': repr(e),
            })
        if result:
            if result is False:
                retry = True
            post_attempt_meta.update({
                'outcome': result,
            })

        end_time = time.perf_counter()
        post_attempt_meta.update({
            'end_time': end_time,
            'elapsed_time': end_time - start_time,
        })
        if __debug__:
            print(post_attempt_meta)
        if retry:
            time.sleep(wait_seconds)
        else:
            break

    if error:
        raise error
    else:
       return result

try:
    result = attempt()
    print('outcome:', result)
except Exception as e:
    print('outcome:', repr(e))
