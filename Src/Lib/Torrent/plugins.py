# 20.10.26

# Class import
from Src.Util.errors import AppError

# General import
import datetime, os, subprocess, sys, threading
import xml.etree.ElementTree as ET
from urllib.parse import urlparse

# Variable
SEARCH_TIMEOUT = 90
FETCH_TIMEOUT = 60
SKIPPED = {'jackett'}           # Jackett is asked directly, through its plugin it would give the same results twice

# Categories of the app and of the plugins
CATEGORIES = {'all': 'all', 'movies': 'movies', 'tv': 'tv', 'anime': 'anime'}
NEWZNAB = {'movies': [2000], 'tv': [5000], 'anime': [5070]}

cache = {'folder': None, 'engines': None}
cache_lock = threading.Lock()


class PluginError(AppError):
    pass


# [ folder ]
def candidate_folders(config):
    """The search engine of qbittorrent: its own folder on this pc, or a copy next to the data (docker)"""

    if config.get('plugins_path'):
        return [config['plugins_path']]

    home = os.path.expanduser("~")
    folders = [
        os.path.join(home, ".local", "share", "qBittorrent", "nova3"),
        os.path.join(home, "Library", "Application Support", "qBittorrent", "nova3"),
        os.path.abspath("nova3"),
    ]

    if os.environ.get("LOCALAPPDATA"):
        folders.insert(0, os.path.join(os.environ["LOCALAPPDATA"], "qBittorrent", "nova3"))

    return folders

def find_folder(config):
    for folder in candidate_folders(config):
        if os.path.isfile(os.path.join(folder, "nova2.py")):
            return folder
    return None

def run(folder, arguments, timeout):
    """A script of the search engine of qbittorrent, with the python of this program"""

    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if sys.platform == 'win32' else {}

    try:
        return subprocess.run([sys.executable, *arguments], cwd=folder, capture_output=True, timeout=timeout, **options)
    except subprocess.TimeoutExpired:
        raise PluginError("I plugin di ricerca di qBittorrent non hanno risposto in tempo")
    except OSError as e:
        raise PluginError(f"Plugin di ricerca di qBittorrent non avviati ({e})")


# [ engines ]
def get_engines(config):
    """Plugins installed in qbittorrent: name of the module, name of the site, address and categories"""

    folder = find_folder(config)
    if folder is None:
        return folder, {}

    with cache_lock:
        if cache['folder'] == folder and cache['engines'] is not None:
            return folder, cache['engines']

    result = run(folder, ['nova2.py', '--capabilities'], 30)
    engines = {}

    try:
        for node in ET.fromstring(result.stdout.decode('utf-8', 'replace')):
            engines[node.tag] = {
                'name': node.findtext('name') or node.tag,
                'url': (node.findtext('url') or '').rstrip('/'),
                'categories': (node.findtext('categories') or '').split(),
            }
    except ET.ParseError:
        raise PluginError("I plugin di ricerca di qBittorrent non si avviano: aggiornali da qBittorrent (Ricerca → Estensioni)")

    engines = {module: engine for module, engine in engines.items() if module not in SKIPPED}

    with cache_lock:
        cache.update(folder=folder, engines=engines)

    return folder, engines

def forget():
    """The settings changed: the plugins are looked for again"""

    with cache_lock:
        cache.update(folder=None, engines=None)

def host(url):
    return (urlparse(url or '').hostname or '').removeprefix('www.')


# [ search ]
def search(config, query, category='all'):
    """Results of every plugin of qbittorrent that knows the category, in the format of the jackett results"""

    folder, engines = get_engines(config)
    if not engines:
        return {'results': [], 'engines': 0, 'failed': False}

    wanted = [module for module, engine in engines.items() if category == 'all' or CATEGORIES[category] in engine['categories']]
    if not wanted:
        return {'results': [], 'engines': 0, 'failed': False}

    result = run(folder, ['nova2.py', ','.join(wanted), CATEGORIES.get(category, 'all'), *query.split()], SEARCH_TIMEOUT)
    by_host = {host(engine['url']): (module, engine) for module, engine in engines.items()}
    results = []

    for line in result.stdout.decode('utf-8', 'replace').splitlines():
        parts = line.split('|')
        if len(parts) < 6:
            continue

        link, name, size, seeds, leech, engine_url = parts[:6]
        details = parts[6] if len(parts) > 6 else ''
        module, engine = by_host.get(host(engine_url), (None, None))

        if module is None or not link:
            continue

        try:
            published = int(float(parts[7])) if len(parts) > 7 else -1
            date = datetime.datetime.fromtimestamp(published).strftime('%Y-%m-%d') if published > 0 else ''
        except (ValueError, OverflowError, OSError):
            date = ''

        results.append({
            'source': 'plugin',
            'engine': module,
            'title': name.strip(),
            'tracker': engine['name'],
            'size': to_int(size),
            'seeders': max(0, to_int(seeds)),
            'peers': max(0, to_int(leech)),
            'date': date,
            'category': '',
            'categories': NEWZNAB.get(category, []),
            'details': details if details.startswith('http') else '',
            'link': '' if link.startswith('magnet:') else link,
            'magnet': link if link.startswith('magnet:') else '',
        })

    # A plugin that fails (site blocked, changed) does not stop the others
    return {'results': results, 'engines': len(wanted), 'failed': result.returncode != 0}

def to_int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return 0


# [ torrent of a result ]
def fetch(config, engine, link):
    """
    The torrent behind a result that is not a magnet: the plugin knows how to get it from the page of its site.
    Return ('magnet', uri) or ('file', bytes)
    """

    folder, engines = get_engines(config)
    if engine not in engines:
        raise PluginError("Il plugin di questo risultato non c'è più in qBittorrent")
    if not link.startswith(('http://', 'https://')):
        raise PluginError("Link del torrent non valido")

    result = run(folder, ['nova2dl.py', engine, link], FETCH_TIMEOUT)
    output = result.stdout.decode('utf-8', 'replace').strip().split(' ')[0] if result.stdout else ''

    if output.startswith('magnet:'):
        return 'magnet', output

    # The plugin saved the .torrent in a temporary file
    if output and os.path.isfile(output):
        try:
            with open(output, 'rb') as file:
                data = file.read()
        finally:
            try:
                os.remove(output)
            except OSError:
                pass

        if data.startswith(b'd'):
            return 'file', data

    raise PluginError(f"{engines[engine]['name']} non ha dato il torrent: il sito è bloccato o è cambiato")
