# 20.10.26

# Class import
from Src.Lib.Torrent import config as torrent_config
from Src.Util.errors import AppError

# General import
from urllib.parse import urljoin
import requests

# Variable
SEARCH_TIMEOUT = 100            # Jackett waits every indexer, the slow ones take long
FETCH_TIMEOUT = 60
MAX_REDIRECTS = 5

# Newznab categories, the sub categories are included by jackett
CATEGORIES = {
    'all': [],
    'movies': [2000],
    'tv': [5000],
    'anime': [5070],
}


class JackettError(AppError):
    pass


def get_base(config):
    url = config['jackett_url']
    if not url:
        raise JackettError("Indirizzo di Jackett mancante: impostalo nelle impostazioni, scheda Torrent")
    return url.rstrip('/')

def get_key(config):
    key = torrent_config.get_jackett_key(config)
    if not key:
        raise JackettError("Chiave API di Jackett non trovata: copiala dalla dashboard di Jackett nelle impostazioni, scheda Torrent")
    return key

def request(config, url, **options):
    """A request to jackett with a message for the user when it does not answer"""

    try:
        return requests.get(url, **options)

    except requests.ConnectionError:
        raise JackettError(f"Jackett non risponde su {get_base(config)}: è avviato?")
    except requests.Timeout:
        raise JackettError("Jackett non ha risposto in tempo: qualche indicizzatore è lento, riprova")
    except requests.RequestException as e:
        raise JackettError(f"Jackett non ha risposto come previsto ({e})")


# [ search ]
def search(config, query, category='all'):
    """Results of every indexer of jackett, with the errors of the ones that did not answer"""

    params = [('apikey', get_key(config)), ('Query', query)]
    params += [('Category[]', str(number)) for number in CATEGORIES.get(category, [])]

    response = request(config, f"{get_base(config)}/api/v2.0/indexers/all/results", params=params, timeout=SEARCH_TIMEOUT)

    if response.status_code in (401, 403):
        raise JackettError("Jackett ha rifiutato la chiave API: copiala di nuovo dalla sua dashboard")
    if not response.ok:
        raise JackettError(f"Jackett ha risposto con errore {response.status_code}")

    try:
        data = response.json()
    except ValueError:
        raise JackettError("Jackett ha risposto con una pagina al posto dei risultati: l'indirizzo è giusto?")

    results = []
    for item in data.get('Results') or []:
        link, magnet = item.get('Link') or '', item.get('MagnetUri') or ''
        if not (link or magnet):
            continue

        results.append({
            'source': 'jackett',
            'title': item.get('Title') or '',
            'tracker': item.get('Tracker') or '',
            'size': item.get('Size') or 0,
            'seeders': item.get('Seeders') or 0,
            'peers': item.get('Peers') or 0,
            'date': (item.get('PublishDate') or '')[:10],
            'category': item.get('CategoryDesc') or '',
            'categories': item.get('Category') or [],
            'details': item.get('Details') or '',
            'link': link,
            'magnet': magnet,
        })

    indexers = data.get('Indexers') or []
    return {
        'results': results,
        'indexers': len(indexers),
        'failed': [indexer.get('Name') for indexer in indexers if indexer.get('Error')],
    }


def count_indexers(config):
    """Indexers configured in jackett, used to test the settings"""

    response = request(config, f"{get_base(config)}/api/v2.0/indexers/all/results/torznab/api",
                       params={'t': 'indexers', 'configured': 'true', 'apikey': get_key(config)}, timeout=20)

    if response.status_code in (401, 403) or 'Invalid API Key' in response.text:
        raise JackettError("Jackett ha rifiutato la chiave API: copiala di nuovo dalla sua dashboard")
    if not response.ok:
        raise JackettError(f"Jackett ha risposto con errore {response.status_code}")
    if '<indexers' not in response.text:
        raise JackettError("A questo indirizzo non risponde Jackett")

    return response.text.count('<indexer ')


# [ torrent of a result ]
def fetch(config, link):
    """
    The torrent behind a download link of jackett.
    Return ('magnet', uri) when the indexer gives a magnet, ('file', bytes) for a .torrent
    """

    if not link.startswith(get_base(config) + '/'):
        raise JackettError("Link del torrent non proveniente da Jackett")

    url = link
    for _ in range(MAX_REDIRECTS):
        response = request(config, url, timeout=FETCH_TIMEOUT, allow_redirects=False)

        if response.is_redirect or response.status_code in (301, 302, 303, 307, 308):
            location = response.headers.get('Location', '')
            if location.startswith('magnet:'):
                return 'magnet', location

            url = urljoin(url, location)
            continue

        if not response.ok:
            raise JackettError(f"Download del torrent non riuscito: l'indicizzatore ha risposto con errore {response.status_code}")

        # A bencoded dictionary, not an error page
        if not response.content.startswith(b'd'):
            raise JackettError("L'indicizzatore non ha dato un file .torrent valido")

        return 'file', response.content

    raise JackettError("Download del torrent non riuscito: troppi reindirizzamenti")
