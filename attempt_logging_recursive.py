import time
import uuid

def fun(attempt_number):
    print('in fun()')
    if (attempt_number < 3):
        raise Exception('My code is failing!')
    return True

def attempt(function_call_id, timeout=60, wait_seconds=10, max_attempts=10, attempt_number=1):
    meta = {}

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
    if result is not None:
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

    if retry is True and attempt_number < max_attempts:
        time.sleep(wait_seconds)
        return attempt(function_call_id, timeout, wait_seconds, max_attempts, attempt_number=attempt_number+1)
    else:
        maybe = {}
        if error is not None:
            maybe['failure'] = error
        if result is not None:
            maybe['success'] = result
        return maybe

maybe = attempt(function_call_id=str(uuid.uuid4()))
print(maybe)
