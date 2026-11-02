# 20.10.26

# Class import
from Src.Lib.Torrent import config as torrent_config
from Src.Util.errors import AppError

# General import
import threading
import requests

# Variable
TIMEOUT = 20
CATEGORY = "SC Downloader"      # Every torrent of the program is in this category of qbittorrent

# States of qbittorrent, the names changed in version 5 (paused became stopped)
DONE_STATES = {'uploading', 'stalledUP', 'pausedUP', 'stoppedUP', 'queuedUP', 'forcedUP'}
BUSY_STATES = {'checkingDL', 'checkingUP', 'checkingResumeData', 'moving', 'metaDL', 'forcedMetaDL', 'allocating'}
ERROR_STATES = {'error', 'missingFiles'}
PAUSED_STATES = {'pausedDL', 'stoppedDL', 'pausedUP', 'stoppedUP'}


class QbitError(AppError):
    pass


class Client:
    """Web api of qbittorrent, the login is done again when the session expires"""

    def __init__(self, config, password=None):
        if not config['qbit_url']:
            raise QbitError("Web UI di qBittorrent non impostata: attivala e inserisci l'indirizzo nelle impostazioni, scheda Torrent")

        self.base = config['qbit_url'].rstrip('/')
        self.user = config['qbit_user']
        self.password = password if password is not None else torrent_config.get_password(config)
        self.session = requests.Session()

        # The web ui refuses requests whose origin is another site
        self.session.headers.update({'Referer': self.base, 'Origin': self.base})
        self.lock = threading.Lock()
        self.logged = False

    # [ requests ]
    def login(self):
        if not self.user:
            raise QbitError("qBittorrent chiede l'accesso: inserisci utente e password della Web UI, oppure attiva \"Salta l'autenticazione per i client su localhost\"")

        response = self.send('post', '/api/v2/auth/login', data={'username': self.user, 'password': self.password or ''}, login=False)

        if response.status_code == 403:
            raise QbitError("qBittorrent ha bloccato l'accesso per troppi tentativi sbagliati: aspetta qualche minuto")
        if response.text.strip() != 'Ok.':
            raise QbitError("Accesso a qBittorrent rifiutato: controlla utente e password della Web UI")

        self.logged = True

    def send(self, method, path, login=True, **options):
        try:
            response = getattr(self.session, method)(self.base + path, timeout=TIMEOUT, **options)
        except requests.ConnectionError:
            raise QbitError(f"qBittorrent non risponde su {self.base}: è aperto, con la Web UI attiva?")
        except requests.Timeout:
            raise QbitError("qBittorrent non ha risposto in tempo")
        except requests.RequestException as e:
            raise QbitError(f"qBittorrent non ha risposto come previsto ({e})")

        # Without the session cookie the web ui answers forbidden, unless localhost can skip the login
        if login and response.status_code in (401, 403):
            with self.lock:
                self.login()
            return self.send(method, path, login=False, **options)

        return response

    def call(self, method, path, **options):
        response = self.send(method, path, **options)

        if response.status_code == 404:
            raise QbitError("Torrent non trovato in qBittorrent")
        if response.status_code == 415:
            raise QbitError("qBittorrent non ha accettato il torrent: il file non è valido")
        if not response.ok:
            raise QbitError(f"qBittorrent ha risposto con errore {response.status_code}")

        return response

    def get(self, path, **params):
        return self.call('get', path, params=params).json()

    def post(self, path, **data):
        return self.call('post', path, data=data)

    def post_any(self, paths, **data):
        """Calls renamed in qbittorrent 5 (pause became stop): the new name first"""

        for path in paths[:-1]:
            response = self.send('post', path, data=data)
            if response.status_code != 404:
                if not response.ok:
                    raise QbitError(f"qBittorrent ha risposto con errore {response.status_code}")
                return response

        return self.post(paths[-1], **data)

    # [ app ]
    def version(self):
        return self.call('get', '/api/v2/app/version').text.strip()

    def preferences(self):
        return self.get('/api/v2/app/preferences')

    def ensure_category(self):
        response = self.send('post', '/api/v2/torrents/createCategory', data={'category': CATEGORY, 'savePath': ''})

        # 409: the category is already there
        if not response.ok and response.status_code != 409:
            raise QbitError(f"Categoria \"{CATEGORY}\" non creata in qBittorrent (errore {response.status_code})")

    # [ torrents ]
    def add(self, magnet=None, torrent=None, tag=None, save_path='', paused=False, sequential=False):
        self.ensure_category()

        data = {
            'category': CATEGORY,
            'tags': tag or '',
            'paused': 'true' if paused else 'false',
            'stopped': 'true' if paused else 'false',
            'sequentialDownload': 'true' if sequential else 'false',
            'firstLastPiecePrio': 'true' if sequential else 'false',
        }
        if save_path:
            data['savepath'] = save_path

        if magnet:
            data['urls'] = magnet
            response = self.call('post', '/api/v2/torrents/add', data=data)
        else:
            response = self.call('post', '/api/v2/torrents/add', data=data, files={'torrents': ('download.torrent', torrent, 'application/x-bittorrent')})

        if response.text.strip().startswith('Fails'):
            raise QbitError("qBittorrent non ha accettato il torrent (forse c'è già, fuori da questa app)")

    def torrents(self, **filters):
        return self.get('/api/v2/torrents/info', category=CATEGORY, **filters)

    def files(self, torrent_hash):
        return self.get('/api/v2/torrents/files', hash=torrent_hash)

    def properties(self, torrent_hash):
        return self.get('/api/v2/torrents/properties', hash=torrent_hash)

    def piece_states(self, torrent_hash):
        return self.get('/api/v2/torrents/pieceStates', hash=torrent_hash)

    def set_file_priority(self, torrent_hash, indexes, priority):
        if indexes:
            self.post('/api/v2/torrents/filePrio', hash=torrent_hash, id='|'.join(str(index) for index in indexes), priority=priority)

    def set_sequential(self, torrent, enabled):
        """The web api only toggles: the state of the torrent says if it is needed"""

        if bool(torrent.get('seq_dl')) != enabled:
            self.post('/api/v2/torrents/toggleSequentialDownload', hashes=torrent['hash'])
        if bool(torrent.get('f_l_piece_prio')) != enabled:
            self.post('/api/v2/torrents/toggleFirstLastPiecePrio', hashes=torrent['hash'])

    def pause(self, torrent_hash):
        self.post_any(['/api/v2/torrents/stop', '/api/v2/torrents/pause'], hashes=torrent_hash)

    def resume(self, torrent_hash):
        self.post_any(['/api/v2/torrents/start', '/api/v2/torrents/resume'], hashes=torrent_hash)

    def delete(self, torrent_hash, delete_files=True):
        self.post('/api/v2/torrents/delete', hashes=torrent_hash, deleteFiles='true' if delete_files else 'false')


# [ state of a torrent ]
def is_complete(torrent):
    return torrent.get('progress', 0) >= 1 and torrent.get('state') in DONE_STATES

def has_metadata(torrent):
    # A magnet without metadata has no size yet
    return torrent.get('state') not in ('metaDL', 'forcedMetaDL') and (torrent.get('total_size') or torrent.get('size') or 0) > 0
