# 16.09.26

# Class import
from Src.Util.console import console
from Src.Util.cancel import DownloadCancelled

# General import
import json, os, posixpath, re, socket, time
from contextlib import contextmanager
from stat import S_ISDIR
import keyring, paramiko

# Variable
CONFIG_FILE = "nas.json"
KNOWN_HOSTS_FILE = "nas_known_hosts"
KEYRING_SERVICE = "SC Downloader NAS"
DEFAULT_CONFIG = {
    'enabled': False,
    'host': '',
    'port': 22,
    'user': '',
    'film_path': '',
    'tv_path': '',
}

# Characters not allowed in a file name
INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


class NasError(Exception):
    def __init__(self, message, local_path=None):
        super().__init__(message)
        self.local_path = local_path


# [ config ]
def load_config():
    """Read nas settings, password is not saved here"""

    try:
        with open(CONFIG_FILE, 'r') as file:
            saved = json.load(file)
    except (FileNotFoundError, ValueError):
        saved = {}

    config = {**DEFAULT_CONFIG, **saved}
    config['port'] = int(config['port'] or 22)
    return config

def save_config(config):
    config = {key: config.get(key, value) for key, value in DEFAULT_CONFIG.items()}
    config['port'] = int(config['port'] or 22)

    with open(CONFIG_FILE, 'w') as file:
        json.dump(config, file, indent=4)

    return config

def is_enabled(config=None):
    config = config or load_config()
    return bool(config['enabled'] and config['host'] and config['user'] and config['film_path'])

def get_account(config):
    return f"{config['user']}@{config['host']}"

def get_password(config):
    """Read password from the credential manager of the system"""

    if not config['host'] or not config['user']:
        return None

    try:
        return keyring.get_password(KEYRING_SERVICE, get_account(config))
    except Exception:
        return None

def save_password(config, password):
    if password:
        keyring.set_password(KEYRING_SERVICE, get_account(config), password)

def delete_password(config):
    try:
        keyring.delete_password(KEYRING_SERVICE, get_account(config))
    except Exception:
        pass


# [ name of the files ]
def clean_name(text):
    """Remove from a name the characters not allowed in a file name"""

    name = INVALID_CHARS.sub('', str(text or '')).replace('\t', ' ')
    return ' '.join(name.split()).strip(' .')

def get_title_folder(media):
    title = clean_name(media.get('name'))
    year = str(media.get('year') or '')
    return f"{title} ({year})" if year else title

def get_file_name(media):
    """Readable name of the file, without extension"""

    title = clean_name(media.get('name')) or 'Senza nome'

    if media.get('type') == 'tv':
        code = f"S{int(media.get('season') or 0):02d}E{int(media.get('episode_number') or 0):02d}"
        episode = clean_name(media.get('episode_name'))
        return f"{title} - {code} - {episode}" if episode else f"{title} - {code}"

    year = str(media.get('year') or '')
    return f"{title} ({year})" if year else title

def get_remote_path(config, media):
    """Path of the file on the nas, with the folders used by media servers"""

    folder = get_title_folder(media) or 'Senza nome'
    file_name = f"{get_file_name(media)}.mp4"

    if media.get('type') == 'tv':
        season = f"Stagione {int(media.get('season') or 0):02d}"
        return posixpath.join(config['tv_path'] or config['film_path'], folder, season, file_name)

    return posixpath.join(config['film_path'], folder, file_name)

def rename_local(local_path, media):
    """Rename a downloaded file with its readable name"""

    if not local_path or not os.path.exists(local_path):
        return local_path

    new_path = os.path.join(os.path.dirname(local_path), get_file_name(media) + os.path.splitext(local_path)[1])

    if os.path.abspath(new_path) == os.path.abspath(local_path):
        return local_path

    try:
        os.replace(local_path, new_path)
    except OSError:
        return local_path

    return new_path


# [ connection ]
@contextmanager
def open_sftp(config, password=None):
    """Open a sftp connection to the nas"""

    if not config['host'] or not config['user']:
        raise NasError("Indirizzo o utente del NAS non impostati")

    password = password or get_password(config)

    if not password:
        raise NasError("Password del NAS non salvata, inseriscila nelle impostazioni")

    # Fast check, a nas that is off must not hold the download for long
    try:
        socket.create_connection((config['host'], config['port']), timeout=4).close()
    except OSError:
        raise NasError(f"NAS non raggiungibile su {config['host']}:{config['port']}")

    client = paramiko.SSHClient()

    if os.path.exists(KNOWN_HOSTS_FILE):
        client.load_host_keys(KNOWN_HOSTS_FILE)

    # The key of the nas is saved at the first connection and checked after
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(config['host'], port=config['port'], username=config['user'], password=password,
                       timeout=15, allow_agent=False, look_for_keys=False)

    except paramiko.BadHostKeyException:
        client.close()
        raise NasError("La chiave del NAS è cambiata, controlla di collegarti al NAS giusto")

    except paramiko.AuthenticationException:
        client.close()
        raise NasError("Utente o password del NAS non corretti")

    except (paramiko.SSHException, socket.error, OSError) as e:
        client.close()
        raise NasError(f"Impossibile collegarsi al NAS: {e}")

    try:
        client.save_host_keys(KNOWN_HOSTS_FILE)
    except OSError:
        pass

    try:
        yield client.open_sftp()
    finally:
        client.close()

def is_folder(sftp, path):
    try:
        return S_ISDIR(sftp.stat(path).st_mode)
    except IOError:
        return False

def list_folders(sftp, path):
    """Name of the folders inside a path, to help choosing the right one"""

    try:
        return sorted(entry.filename for entry in sftp.listdir_attr(path) if S_ISDIR(entry.st_mode))[:40]
    except IOError:
        return []

def make_folders(sftp, path):
    """Create a folder on the nas with all its parents"""

    current = '/' if path.startswith('/') else ''

    for part in [part for part in path.split('/') if part]:
        current = posixpath.join(current, part)

        if is_folder(sftp, current):
            continue

        try:
            sftp.mkdir(current)
        except IOError:
            raise NasError(f"Non riesco a creare la cartella {current} sul NAS")

def test_connection(config, password=None):
    """Check the connection and the folders, return what the gui shows"""

    with open_sftp(config, password) as sftp:
        try:
            home = sftp.normalize('.')
        except IOError:
            home = None

        folders = {}
        for key in ('film_path', 'tv_path'):
            path = config.get(key)

            if not path:
                folders[key] = {'path': path, 'exists': False, 'near': []}
                continue

            folders[key] = {
                'path': path,
                'exists': is_folder(sftp, path),
                'near': list_folders(sftp, posixpath.dirname(path) or '/'),
            }

        return {'home': home, 'folders': folders}


# [ upload ]
def upload(config, local_path, remote_path, password=None, progress=None):
    """Upload a file, it takes its real name only when the transfer is complete"""

    size = os.path.getsize(local_path)
    temp_path = f"{remote_path}.parte"

    with open_sftp(config, password) as sftp:
        folder = posixpath.dirname(remote_path)
        make_folders(sftp, folder)

        # Half files left by a program closed during an upload
        for name in sftp.listdir(folder):
            if name.endswith('.parte'):
                sftp.remove(posixpath.join(folder, name))

        try:
            sftp.put(local_path, temp_path, callback=progress)

        except (DownloadCancelled, KeyboardInterrupt):
            remove_partial(sftp, temp_path)
            raise

        except (IOError, OSError, paramiko.SSHException) as e:
            remove_partial(sftp, temp_path)
            raise NasError(f"Trasferimento sul NAS non riuscito: {e}")

        uploaded = sftp.stat(temp_path).st_size

        if uploaded != size:
            sftp.remove(temp_path)
            raise NasError(f"Trasferimento incompleto, {uploaded} byte invece di {size}")

        try:
            sftp.remove(remote_path)
        except IOError:
            pass

        sftp.rename(temp_path, remote_path)

    return remote_path

def remove_partial(sftp, temp_path):
    """Dont leave half files on the nas, nor the folder created for them"""

    for remove, path in ((sftp.remove, temp_path), (sftp.rmdir, posixpath.dirname(temp_path))):
        try:
            remove(path)
        except (IOError, OSError, paramiko.SSHException):
            pass

def make_progress(progress_callback):
    """Report the upload without calling back for every block"""

    last = {'time': 0.0}

    def report(sent, total):
        now = time.time()

        if progress_callback != None and (sent >= total or now - last['time'] > 0.3):
            last['time'] = now
            progress_callback("upload", sent, total)

    return report

def finalize(local_path, media=None, progress_callback=None):
    """
    Rename a downloaded file and move it to the nas if it is enabled.
    A nas that does not answer is never a lost download: the file stays here.
    Return {'path': file on this pc, 'remote': file on the nas, 'warning': why the nas failed}
    """

    result = {'path': local_path, 'remote': None, 'warning': None}

    if not media:
        return result

    local_path = rename_local(local_path, media)
    result['path'] = local_path
    config = load_config()

    if not is_enabled(config):
        return result

    remote_path = get_remote_path(config, media)
    console.print(f"[green]Upload to nas [white]=> [cyan]{remote_path}")

    try:
        if progress_callback != None:
            progress_callback("upload", 0, os.path.getsize(local_path))

        upload(config, local_path, remote_path, progress=make_progress(progress_callback))

    except DownloadCancelled:
        # The download is complete, only the upload is stopped
        console.log(f"[yellow]NAS: caricamento annullato, il file resta in {local_path}")
        result['warning'] = "Caricamento sul NAS annullato, il file è rimasto sul PC"
        return result

    except NasError as e:
        console.log(f"[red]NAS: {e}, il file resta in {local_path}")
        result['warning'] = str(e)
        return result

    except Exception as e:
        console.log(f"[red]NAS: errore inatteso ({e}), il file resta in {local_path}")
        result['warning'] = f"Errore inatteso durante il caricamento: {e}"
        return result

    os.remove(local_path)
    result.update(path=None, remote=remote_path)
    return result
