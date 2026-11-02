# 18.09.26

# Class import
from Src.Util.log import LOG_FILE

# General import
import errno, json, socket, threading, time
from contextlib import contextmanager
from urllib.parse import urlparse
import requests

# Variable
PROBE_HOSTS = (("1.1.1.1", 443), ("8.8.8.8", 443), ("9.9.9.9", 443))
OFFLINE_LIMIT = 30 * 60         # After this the download gives up, the manager tries again later
OFFLINE_TEXT = "Connessione a internet assente o instabile"
DISK_FULL_TEXT = "Spazio su disco esaurito, libera spazio e riprova"
DNS_MARKERS = ("getaddrinfo failed", "name or service not known", "failed to resolve", "nodename nor servname",
               "name resolution", "no address associated")
HTTP_REASONS = {
    400: "richiesta rifiutata",
    401: "accesso negato",
    403: "accesso negato, il sito blocca la richiesta o il link è scaduto",
    404: "pagina non trovata, il contenuto è stato rimosso o l'indirizzo è cambiato",
    410: "contenuto rimosso",
    419: "sessione scaduta",
    429: "troppe richieste, il sito chiede di rallentare",
    500: "errore interno del sito",
    502: "il sito non risponde",
    503: "sito sovraccarico o in manutenzione",
    504: "il sito non ha risposto in tempo",
}
probe_lock = threading.Lock()
last_probe = {'time': 0.0, 'online': True}


class AppError(Exception):
    """An error with a message already written for the user"""

class DownloadError(AppError):
    """A download that did not work, with a message for the user"""

    def __init__(self, message, retry=True):
        super().__init__(message)
        self.retry = retry          # False when trying again gives the same result

class DiskFullError(DownloadError):
    def __init__(self, path=None):
        super().__init__(DISK_FULL_TEXT, retry=False)
        self.path = path

class SiteError(AppError):
    """The site answered, but not with what the program expects"""


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

def find_cause(error, types):
    """First error of the given types in the chain of causes, requests hides the real reason inside"""

    stack, seen = [error], set()

    while stack:
        current = stack.pop()
        if current is None or id(current) in seen:
            continue
        seen.add(id(current))

        if isinstance(current, types):
            return current

        stack += [current.__cause__, current.__context__, getattr(current, 'reason', None)]
        stack += [arg for arg in getattr(current, 'args', ()) if isinstance(arg, BaseException)]

    return None

def get_host(url):
    return urlparse(url or '').hostname or url or "il sito"

def describe_network(error):
    """What broke in a connection: internet, the name of the site, its answer or its certificate"""

    if not is_online():
        return OFFLINE_TEXT

    request = getattr(error, 'request', None)
    host = get_host(getattr(request, 'url', None))
    text = repr(error).lower()

    if isinstance(error, requests.exceptions.SSLError) or "certificate" in text:
        return f"Connessione sicura con {host} non riuscita (certificato non valido): spesso è il provider che blocca il sito, prova un DNS come 1.1.1.1"
    if find_cause(error, socket.gaierror) or any(marker in text for marker in DNS_MARKERS):
        return f"Il dominio {host} non esiste o non viene trovato: l'indirizzo è sbagliato o è cambiato, oppure il provider lo blocca (prova un DNS come 1.1.1.1)"
    if isinstance(error, requests.Timeout) or find_cause(error, TimeoutError) or "timed out" in text:
        return f"{host} non ha risposto in tempo: il sito è lento o irraggiungibile, riprova tra poco"
    if find_cause(error, ConnectionRefusedError) or "refused" in text:
        return f"{host} ha rifiutato la connessione: il sito è fermo o bloccato"

    return f"Connessione con {host} interrotta: rete instabile o sito irraggiungibile"


# [ http ]
def redirected_to(response):
    """Host the request has been sent to, when it is not the one asked (a domain that has changed)"""

    if not response.history:
        return None

    asked, final = get_host(response.history[0].url), get_host(response.url)
    return final if asked != final else None

def describe_response(response, who=None):
    """Answer that is not ok: who answered, the code and what it means"""

    host = get_host(response.url)
    code = response.status_code
    reason = HTTP_REASONS.get(code)

    if reason is None and 520 <= code <= 530:
        reason = "il sito dietro Cloudflare non risponde"
    elif reason is None and code >= 500:
        reason = "problema del server, di solito passa da solo"

    text = f"{who} {host}" if who else host
    text += f" ha risposto con errore {code}" + (f": {reason}" if reason else "")

    moved = redirected_to(response)
    if moved:
        text += f" (la richiesta è stata spostata su {moved})"

    return text


# [ disk ]
def is_disk_full(error):
    return isinstance(error, OSError) and error.errno in (errno.ENOSPC, getattr(errno, 'EDQUOT', -1)) or getattr(error, 'winerror', None) in (39, 112)


# [ text for the user ]
@contextmanager
def step(label):
    """Phase of a download: an error raised inside says where it happened"""

    try:
        yield
    except Exception as e:
        # The innermost phase is the most precise
        if getattr(e, 'step', None) is None:
            e.step = label
        raise

def lower_first(text):
    """'Il sito...' becomes 'il sito...', names like FFmpeg or AnimeUnity stay as they are"""

    return text[0].lower() + text[1:] if text.split(" ", 1)[0][1:].islower() else text

def explain(error):
    name = type(error).__name__

    if isinstance(error, AppError):
        return str(error)
    if is_disk_full(error):
        return DISK_FULL_TEXT
    if is_network_error(error):
        return describe_network(error)
    if isinstance(error, requests.HTTPError) and error.response is not None:
        return describe_response(error.response)
    if isinstance(error, PermissionError):
        return f"Permesso negato su {error.filename or 'un file'}: la cartella è protetta o il file è aperto in un altro programma"
    if isinstance(error, FileNotFoundError):
        if error.filename:
            return f"File o cartella non trovati: {error.filename}"
        return f"Percorso di un file vuoto (errore del programma), dettagli in {LOG_FILE}"
    if isinstance(error, OSError):
        return f"Errore sul file {error.filename}: {error.strerror or error}" if error.filename else f"Errore di sistema: {error.strerror or error}"
    if isinstance(error, (json.JSONDecodeError, requests.exceptions.JSONDecodeError)):
        return "Il sito ha risposto con una pagina al posto dei dati: potrebbe essere cambiato o bloccare le richieste automatiche"
    if isinstance(error, (KeyError, IndexError, TypeError, AttributeError)):
        return f"Risposta del sito diversa dal previsto ({name}: {error}), forse il sito è cambiato: dettagli in {LOG_FILE}"

    return f"Errore inatteso ({name}: {error}), dettagli in {LOG_FILE}" if str(error) else f"Errore inatteso ({name}), dettagli in {LOG_FILE}"

def describe(error):
    """Italian text of an error, for the gui: what went wrong, where, and what to do"""

    text = explain(error)
    where = getattr(error, 'step', None)

    # Where it happened does not matter for a full disk or a missing internet
    if not where or text in (DISK_FULL_TEXT, OFFLINE_TEXT):
        return text

    return f"{where}: {lower_first(text)}"
