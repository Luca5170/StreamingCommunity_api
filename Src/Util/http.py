# 18.09.26

# Class import
from Src.Util.errors import is_network_error, wait_online

# General import
import time
import requests

# Variable
TIMEOUT = 20
RETRY_CODES = (429, 500, 502, 503, 504)


def request(method, url, session=None, retries=3, check=None, wait=False, **kwargs):
    """
    Request with a time limit, tried again when the connection breaks or the server is busy.
    With wait, a missing internet is waited for (downloads), without it the error comes at once (pages of the gui).
    """

    kwargs.setdefault('timeout', TIMEOUT)
    sender = session or requests

    for attempt in range(retries + 1):
        try:
            response = sender.request(method, url, **kwargs)

            if response.status_code not in RETRY_CODES or attempt == retries:
                return response

        except requests.RequestException as e:
            if attempt == retries:
                raise

            # No internet: a download waits for it, the gui tries once more and then answers
            if is_network_error(e):
                if wait and not wait_online(check):
                    raise
                if not wait and attempt >= 1:
                    raise

        time.sleep(min(2 ** attempt, 10))

def get(url, **kwargs):
    return request('GET', url, **kwargs)
