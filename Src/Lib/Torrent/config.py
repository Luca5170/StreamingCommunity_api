# 20.10.26

# Class import
from Src.Util.console import console
from Src.Util import storage

# General import
import json, os
import keyring

# Variable
IN_DOCKER = os.path.exists('/.dockerenv')
CONFIG_FILE = "torrent.json"
KEYRING_SERVICE = "SC Downloader qBittorrent"
PASSWORD_FILE = "torrent_password"      # Used where there is no credential manager (docker), only readable by the program
DEFAULT_CONFIG = {
    'jackett_url': 'http://host.docker.internal:9117' if IN_DOCKER else 'http://127.0.0.1:9117',   # In docker the pc is not 127.0.0.1
    'jackett_key': '',                  # Empty: read from the jackett plugin of qbittorrent
    'qbit_url': '',                     # Empty: torrents are opened with qbittorrent like a double click
    'qbit_user': '',
    'save_path': '',                    # Empty: the folder chosen in qbittorrent
    'after_upload': 'remove',           # 'remove' the torrent and its files once on the nas, or 'keep' sharing them
    'path_from': '',                    # Folder of the downloads as qbittorrent sees it...
    'path_to': '',                      # ...and as this program sees it (docker)
    'plugins': 'on',                    # Search also with the search plugins of qbittorrent
    'plugins_path': '',                 # Empty: the nova3 folder of qbittorrent on this pc
}
AFTER_UPLOAD = ('remove', 'keep')


# [ config ]
def load_config():
    saved = storage.read_json(CONFIG_FILE, {})
    config = {**DEFAULT_CONFIG, **(saved if isinstance(saved, dict) else {})}

    if config['after_upload'] not in AFTER_UPLOAD:
        config['after_upload'] = DEFAULT_CONFIG['after_upload']
    if config['plugins'] not in ('on', 'off'):
        config['plugins'] = DEFAULT_CONFIG['plugins']

    return config

def save_config(config):
    config = {key: str(config.get(key, value) or '').strip() for key, value in DEFAULT_CONFIG.items()}

    for key in ('jackett_url', 'qbit_url'):
        config[key] = config[key].rstrip('/')
    if config['after_upload'] not in AFTER_UPLOAD:
        config['after_upload'] = DEFAULT_CONFIG['after_upload']
    if config['plugins'] not in ('on', 'off'):
        config['plugins'] = DEFAULT_CONFIG['plugins']

    storage.write_json(CONFIG_FILE, config, indent=4)
    return config


# [ jackett key ]
def plugin_key_paths():
    """The jackett plugin of the qbittorrent search keeps the key in its folder, also in the copy given to docker"""

    home = os.path.expanduser("~")
    paths = [
        os.path.join(home, ".local", "share", "qBittorrent", "nova3", "engines", "jackett.json"),
        os.path.join(home, "Library", "Application Support", "qBittorrent", "nova3", "engines", "jackett.json"),
        os.path.abspath(os.path.join("nova3", "engines", "jackett.json")),
    ]

    if os.environ.get("LOCALAPPDATA"):
        paths.insert(0, os.path.join(os.environ["LOCALAPPDATA"], "qBittorrent", "nova3", "engines", "jackett.json"))

    return paths

def find_plugin_key():
    for path in plugin_key_paths():
        try:
            with open(path, encoding='utf-8') as file:
                key = json.load(file).get('api_key', '')
        except (OSError, ValueError, AttributeError):
            continue

        if key and key != 'YOUR_API_KEY_HERE':
            return key

    return ''

def get_jackett_key(config):
    return config['jackett_key'] or find_plugin_key()


# [ qbittorrent password ]
def get_account(config):
    return f"{config['qbit_user']}@{config['qbit_url']}"

def get_password(config):
    """Password of the web ui, from the credential manager of the system or the file used in docker"""

    if not config['qbit_url'] or not config['qbit_user']:
        return None

    try:
        password = keyring.get_password(KEYRING_SERVICE, get_account(config))
        if password:
            return password
    except Exception:
        pass

    saved = storage.read_json(PASSWORD_FILE, {})
    return saved.get(get_account(config)) if isinstance(saved, dict) else None

def save_password(config, password):
    if not password:
        return True

    try:
        keyring.set_password(KEYRING_SERVICE, get_account(config), password)
        return True
    except Exception:
        pass

    try:
        storage.write_json(PASSWORD_FILE, {get_account(config): password})
    except OSError as e:
        console.log(f"[yellow]qBittorrent: password non salvata ({e})")
        return False

    # The copy kept by storage has the previous password
    for path in (PASSWORD_FILE, f"{PASSWORD_FILE}.bak"):
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass

    return True


# [ paths ]
def to_local_path(config, path):
    """A path given by qbittorrent, as this program sees it (in docker the two can differ)"""

    if not path:
        return path

    source, target = config['path_from'], config['path_to']
    normalized = path.replace('\\', '/')

    if source and target:
        prefix = source.replace('\\', '/').rstrip('/')

        if normalized == prefix or normalized.startswith(prefix + '/'):
            rest = normalized[len(prefix):].lstrip('/')
            return os.path.join(target, *rest.split('/')) if rest else target

    return os.path.normpath(path)
