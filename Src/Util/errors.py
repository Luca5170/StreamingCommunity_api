# 18.09.26

# General import
import errno, socket, threading, time
import requests

# Variable
PROBE_HOSTS = (("1.1.1.1", 443), ("8.8.8.8", 443), ("9.9.9.9", 443))
OFFLINE_LIMIT = 30 * 60         # After this the download gives up, the manager tries again later
probe_lock = threading.Lock()
last_probe = {'time': 0.0, 'online': True}


class DownloadError(Exception):
    """A download that did not work, with a message for the user"""

    def __init__(self, message, retry=True):
        super().__init__(message)
        self.retry = retry          # False when trying again gives the same result

class DiskFullError(DownloadError):
    def __init__(self, path=None):
        super().__init__("Spazio su disco esaurito: libera spazio e riprova", retry=False)
        self.path = path


# [ network ]
def is_online():
    """True when internet answers, the answer is kept a few seconds so many threads can ask"""

    with probe_lock:
        if time.time() - last_probe['time'] < 3:
            return last_probe['online']

        online = False
        for host in PROBE_HOSTS:
            try:
                socket.create_connection(host, timeout=3).close()
                online = True
                break
            except OSError:
                continue

        last_probe.update(time=time.time(), online=online)
        return online

def is_network_error(error):
    """Errors that come from a connection that is missing or broken, not from the site"""

    return isinstance(error, (requests.ConnectionError, requests.Timeout, socket.timeout, ConnectionError, TimeoutError))

def wait_online(check=None, limit=OFFLINE_LIMIT):
    """
    Wait until internet comes back. check() is called often, it raises to stop the wait (cancel).
    Return False if internet is still missing after the limit.
    """

    end = time.time() + limit

    while time.time() < end:
        if is_online():
            return True

        for _ in range(10):
            if check is not None:
                check()
            time.sleep(0.5)

    return False


# [ disk ]
def is_disk_full(error):
    return isinstance(error, OSError) and error.errno in (errno.ENOSPC, getattr(errno, 'EDQUOT', -1)) or getattr(error, 'winerror', None) in (39, 112)

def describe(error):
    """Short italian text of an error, for the gui"""

    if isinstance(error, DownloadError):
        return str(error)
    if is_disk_full(error):
        return "Spazio su disco esaurito: libera spazio e riprova"
    if is_network_error(error):
        return "Connessione a internet assente o instabile"
    if isinstance(error, requests.HTTPError) and error.response is not None:
        return f"Il sito ha risposto con errore {error.response.status_code}"
    if isinstance(error, PermissionError):
        return f"Permesso negato su un file: {error.filename or error}"

    return str(error) or type(error).__name__
