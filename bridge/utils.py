import gevent


def threaded(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        return gevent.spawn(fn, *args, **kwargs)
    return wrapper


def create_db_url(username, passwd, host, port):
    if username and passwd:
        cr = '{}:{}@'.format(username, passwd)
    else:
        cr = ''
    return 'http://{}{}:{}/'.format(
                cr, host, port
            )
