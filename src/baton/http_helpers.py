"""Bounded cleanup before closing a rejected loopback HTTP request."""
import time


def discard_rejected_body(handler, limit):
    """Discard bytes without parsing; never wait more than 0.2 seconds."""
    if type(limit) is not int or limit < 0:
        return 0
    if handler.headers.get_all('Transfer-Encoding') is not None:
        return 0
    lengths = handler.headers.get_all('Content-Length', [])
    if len(lengths) != 1:
        return 0
    value = lengths[0].strip(' \t')
    if not value or any(c < '0' or c > '9' for c in value):
        return 0
    length = 0
    for character in value:
        length = length * 10 + ord(character) - ord('0')
        if length > limit:
            return 0
    if not length:
        return 0
    try:
        previous = handler.connection.gettimeout()
    except OSError:
        return 0
    discarded = 0
    deadline = time.monotonic() + .2
    try:
        while discarded < length:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            timeout = min(.2, remaining)
            handler.connection.settimeout(min(timeout, previous) if previous is not None else timeout)
            count = len(handler.rfile.read1(min(8192, length-discarded)))
            if not count:
                break
            discarded += count
    except OSError:
        pass
    finally:
        try:
            handler.connection.settimeout(previous)
        except OSError:
            pass
    return discarded
