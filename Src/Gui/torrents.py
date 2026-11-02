# 20.10.26

# Class import
from Src.Lib.Nas import nas
from Src.Lib.Torrent import checks, config as torrent_config, jackett, plugins, probe, qbittorrent, release
from Src.Util import storage
from Src.Util.cancel import DownloadCancelled
from Src.Util.console import console
from Src.Util.errors import AppError, describe
from Src.Util.log import log_error

# General import
import collections, hashlib, math, os, posixpath, queue, re, secrets, sys, tempfile, threading, time

# Variable
ITEMS_FILE = "torrents.json"
MAX_RESULTS = 3000              # Results of the searches kept, the page asks for them by id
MAX_ITEMS = 200
POLL_ACTIVE = 2                 # Seconds between two questions to qbittorrent while something moves
POLL_IDLE = 15
METADATA_TIMEOUT = 180          # A magnet nobody shares never gets its list of files
PIECES_TIMEOUT = 600
INSPECT_MAX_AGE = 30 * 60       # A scheda tecnica never turned into a download is thrown away
HEAD_BYTES = 12 * 1024 * 1024   # Start of the video read by ffprobe: header and tracks
MAX_HEAD_BYTES = 96 * 1024 * 1024
MISSING_GRACE = 60              # Seconds a torrent just added can take to appear in qbittorrent
NAS_RETRY_INTERVAL = 120
MAX_AUTO_UPLOADS = 5
NO_ETA = 8640000                # Eta of qbittorrent when it cant tell
LIVE_PHASES = ('inspect', 'download', 'upload', 'done', 'discard')


class TorrentError(AppError):
    pass


class InspectStopped(Exception):
    """The scheda tecnica is not wanted anymore: discarded or turned into a download"""


class TorrentManager:
    """
    Torrents sent to qbittorrent from the app: the scheda tecnica before the download,
    the progress while qbittorrent downloads, and the upload to the nas at the end.
    """

    def __init__(self):
        self.lock = threading.RLock()
        self.results = collections.OrderedDict()
        self.items = []
        self.next_id = 1
        self.live = {}              # Last state of each torrent in qbittorrent, by item id
        self.upload_state = {}      # Upload running, by item id
        self.uploads = queue.Queue()
        self.client = None
        self.client_error = None
        self.stopping = False
        self.wake = threading.Event()
        self.load()

        threading.Thread(target=self.poller, daemon=True).start()
        threading.Thread(target=self.uploader, daemon=True).start()

    # [ saved list ]
    def load(self):
        saved = storage.read_json(ITEMS_FILE, {})
        items = saved.get('items') if isinstance(saved, dict) else None

        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict) or not isinstance(item.get('id'), int) or item.get('phase') not in LIVE_PHASES + ('error',):
                continue

            # The scheda tecnica of the last time has nobody waiting for it
            if item['phase'] == 'inspect':
                item['phase'] = 'discard'
            if item['phase'] == 'upload':
                self.uploads.put(item['id'])

            self.items.append(item)

        self.next_id = max((item['id'] for item in self.items), default=0) + 1

    def save(self):
        with self.lock:
            items = [dict(item) for item in self.items][-MAX_ITEMS:]

        try:
            storage.write_json(ITEMS_FILE, {'items': items}, indent=2)
        except Exception as e:
            log_error("Torrents list not saved", e)

    def get(self, item_id):
        with self.lock:
            return next((item for item in self.items if item['id'] == item_id), None)

    # [ qbittorrent ]
    def get_client(self):
        with self.lock:
            if self.client is None:
                self.client = qbittorrent.Client(torrent_config.load_config())
            return self.client

    def reset_client(self):
        with self.lock:
            self.client = None
            self.client_error = None
        self.wake.set()

    def find_torrent(self, client, item):
        if item.get('hash'):
            found = client.torrents(hashes=item['hash'])
        else:
            found = client.torrents(tag=item['tag'])

        torrent = found[0] if found else None
        if torrent and not item.get('hash'):
            with self.lock:
                item['hash'] = torrent['hash']
            self.save()

        return torrent

    def send(self, client, raw, tag, paused=False, sequential=False):
        """Give a result of the search to qbittorrent"""

        config = torrent_config.load_config()
        options = {'tag': tag, 'save_path': config['save_path'], 'paused': paused, 'sequential': sequential}

        if raw['magnet']:
            return client.add(magnet=raw['magnet'], **options)

        kind, payload = self.fetch(raw)
        if kind == 'magnet':
            return client.add(magnet=payload, **options)
        return client.add(torrent=payload, **options)

    def open_with_system(self, raw):
        """Without the web ui the torrent is opened by qbittorrent like a double click"""

        if sys.platform != 'win32':
            raise TorrentError("Senza la Web UI di qBittorrent il torrent si apre solo sul PC Windows: attivala nelle impostazioni, scheda Torrent")

        if raw['magnet']:
            os.startfile(raw['magnet'])
            return

        kind, payload = self.fetch(raw)
        if kind == 'magnet':
            os.startfile(payload)
            return

        path = os.path.join(tempfile.mkdtemp(prefix="sc_torrent_"), "download.torrent")
        with open(path, 'wb') as file:
            file.write(payload)
        os.startfile(path)

    def fetch(self, raw):
        """The torrent of a result that is not a magnet, from the source that found it"""

        config = torrent_config.load_config()

        if raw.get('source') == 'plugin':
            return plugins.fetch(config, raw['engine'], raw['link'])
        return jackett.fetch(config, raw['link'])

    def file_path(self, torrent, file):
        """Where a file of the torrent is on this pc, while downloading it can have the .!qB extension"""

        config = torrent_config.load_config()

        for base in (torrent.get('download_path'), torrent.get('save_path')):
            if not base:
                continue

            path = torrent_config.to_local_path(config, base.rstrip('/\\') + '/' + file['name'])
            for candidate in (path, path + '.!qB'):
                if os.path.isfile(candidate):
                    return candidate

        return None

    # [ search ]
    def search(self, query, category):
        """Jackett and the search plugins of qbittorrent together: a source that fails does not stop the other"""

        config = torrent_config.load_config()
        sources = []

        if config['jackett_url'] and torrent_config.get_jackett_key(config):
            sources.append(('jackett', jackett.search))
        if config['plugins'] != 'off':
            sources.append(('plugins', plugins.search))

        if not sources:
            raise TorrentError("Nessuna fonte per cercare: imposta Jackett o attiva i plugin di qBittorrent nelle impostazioni, scheda Torrent")

        found, errors = {}, {}

        def ask(name, function):
            try:
                found[name] = function(config, query, category)
            except AppError as e:
                errors[name] = str(e)
            except Exception as e:
                log_error(f"Torrent search on {name}", e)
                errors[name] = describe(e)

        threads = [threading.Thread(target=ask, args=source, daemon=True) for source in sources]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        if not found:
            raise TorrentError(next(iter(errors.values())))

        from_jackett, from_plugins = found.get('jackett'), found.get('plugins')
        failed = list(from_jackett['failed']) if from_jackett else []
        if 'jackett' in errors:
            failed.append(f"Jackett ({errors['jackett']})")
        if 'plugins' in errors:
            failed.append(f"plugin di qBittorrent ({errors['plugins']})")
        elif from_plugins and from_plugins['failed']:
            failed.append("alcuni plugin di qBittorrent (sito bloccato o cambiato)")

        # The same torrent found by two sources: the one with more seeds, a magnet if possible
        unique = []
        for raw in (from_jackett or {}).get('results', []) + (from_plugins or {}).get('results', []):
            index = next((index for index, other in enumerate(unique) if is_same(raw, other)), None)

            if index is None:
                unique.append(raw)
            elif (raw['seeders'], bool(raw['magnet'])) > (unique[index]['seeders'], bool(unique[index]['magnet'])):
                unique[index] = raw

        results = []
        with self.lock:
            for raw in unique:
                result_id = hashlib.sha1((raw['magnet'] or raw['link']).encode('utf-8')).hexdigest()[:16]
                self.results[result_id] = raw
                self.results.move_to_end(result_id)
                guess = release.parse(raw['title'], raw['categories'])

                # Links of jackett have its key inside, the page gets only the id
                results.append({
                    'id': result_id,
                    'title': raw['title'],
                    'tracker': raw['tracker'],
                    'source': raw.get('source'),
                    'size': raw['size'],
                    'seeders': raw['seeders'],
                    'peers': raw['peers'],
                    'date': raw['date'],
                    'category': raw['category'],
                    'details': raw['details'] if raw['details'].startswith('http') and 'apikey' not in raw['details'].lower() else None,
                    'guess': guess,
                    'check': checks.check_result(raw['title'], raw['size'], guess),
                })

            while len(self.results) > MAX_RESULTS:
                self.results.popitem(last=False)

        return {
            'results': results,
            'indexers': from_jackett['indexers'] if from_jackett else 0,
            'plugins': from_plugins['engines'] if from_plugins else 0,
            'failed': failed,
        }

    def get_result(self, result_id):
        with self.lock:
            raw = self.results.get(result_id)

        if raw is None:
            raise TorrentError("Risultato scaduto: cerca di nuovo")
        return raw

    # [ items ]
    def new_item(self, raw, media, phase, result_id):
        with self.lock:
            item = {
                'id': self.next_id,
                'result': result_id,
                'tag': f"scd-{secrets.token_hex(5)}",
                'hash': None,
                'title': raw['title'],
                'tracker': raw['tracker'],
                'size': raw['size'],
                'media': media,
                'phase': phase,
                'created': time.time(),
                'touched': time.time(),
                'files': None,              # Indexes of the files chosen, None for all
                'selection': False,         # Priorities still to give once the list of files is known
                'inspect': None,
                'uploads': [],
                'warning': None,
                'error': None,
                'auto_uploads': 0,
                'note': None,
            }
            self.next_id += 1
            self.items.append(item)

            # The oldest finished torrents leave the list
            finished = [other for other in self.items if other['phase'] in ('done', 'error')]
            for other in finished[:max(0, len(self.items) - MAX_ITEMS)]:
                self.items.remove(other)

        self.save()
        return item

    def inspect(self, result_id, media):
        """Scheda tecnica: qbittorrent downloads only the start of the video, ffprobe reads its tracks"""

        if not probe.is_available():
            raise TorrentError("ffprobe non trovato: installa FFmpeg completo per la scheda tecnica")
        if not torrent_config.load_config()['qbit_url']:
            raise TorrentError("La scheda tecnica ha bisogno della Web UI di qBittorrent: attivala nelle impostazioni, scheda Torrent")

        media = read_media(media)
        raw = self.get_result(result_id)
        client = self.get_client()
        item = self.new_item(raw, media, 'inspect', result_id)
        item['inspect'] = {'status': 'adding', 'have': 0, 'need': 0, 'info': None, 'message': None}

        try:
            self.send(client, raw, item['tag'], sequential=True)
        except Exception:
            with self.lock:
                self.items.remove(item)
            self.save()
            raise

        threading.Thread(target=self.run_inspect, args=(item['id'],), daemon=True).start()
        self.wake.set()
        return self.view(item)

    def download(self, body):
        """A result goes to qbittorrent, or a scheda tecnica becomes a download"""

        media = read_media(body.get('media'))
        files = body.get('files')
        files = [int(index) for index in files if isinstance(index, int)] if isinstance(files, list) else None
        result_id = str(body.get('result') or '')

        # The same torrent already in qbittorrent: qbittorrent would refuse it a second time
        with self.lock:
            same = next((item for item in self.items if result_id and item.get('result') == result_id
                         and item['phase'] in ('inspect', 'download', 'upload')), None)

        if same is not None and same['phase'] != 'inspect':
            raise TorrentError("Questo torrent è già nella lista dei tuoi torrent")
        if same is not None:
            body = {**body, 'item': same['id']}

        if body.get('item') is not None:
            item = self.get(int(body['item']))
            if item is None or item['phase'] != 'inspect':
                raise TorrentError("Questa scheda tecnica non c'è più: cerca di nuovo il torrent")

            # The scheda tecnica has done its job, the saved list does not need it
            with self.lock:
                item.update(phase='download', media=media, files=files, selection=True, touched=time.time(), inspect=None)

            self.save()
            self.wake.set()
            return {'item': self.view(item), 'message': "Inviato a qBittorrent"}

        raw = self.get_result(result_id)

        if not torrent_config.load_config()['qbit_url']:
            self.open_with_system(raw)
            return {'item': None, 'message': "Aperto con qBittorrent"}

        client = self.get_client()
        item = self.new_item(raw, media, 'download', result_id)
        item['selection'] = True

        try:
            self.send(client, raw, item['tag'])
        except Exception:
            with self.lock:
                self.items.remove(item)
            self.save()
            raise

        self.wake.set()
        return {'item': self.view(item), 'message': "Inviato a qBittorrent"}

    def discard(self, item_id):
        """Torrent and files removed from qbittorrent, done by the poller"""

        item = self.get(item_id)
        if item is None or item['phase'] in ('upload', 'discard'):
            return False

        with self.lock:
            if item['phase'] in ('done', 'error'):
                # Already finished: only the line of the list goes away, the files stay where they are
                self.items.remove(item)
            else:
                item['phase'] = 'discard'

        self.save()
        self.wake.set()
        return True

    def touch(self, item_id):
        item = self.get(item_id)
        if item is not None:
            item['touched'] = time.time()
        return item

    def set_paused(self, item_id, paused):
        item = self.get(item_id)
        if item is None or item['phase'] != 'download' or not item.get('hash'):
            raise TorrentError("Questo torrent non si può mettere in pausa ora")

        client = self.get_client()
        if paused:
            client.pause(item['hash'])
        else:
            client.resume(item['hash'])
        self.wake.set()

    def retry_upload(self, item_id):
        item = self.get(item_id)
        if item is None or item['phase'] != 'done' or not item.get('warning'):
            raise TorrentError("Questo torrent non ha nulla da caricare")

        with self.lock:
            item.update(phase='upload', warning=None)
        self.uploads.put(item_id)
        self.save()

    def get_folder(self, item_id):
        torrent = self.live.get(item_id)
        if not torrent:
            return None

        return torrent_config.to_local_path(torrent_config.load_config(), torrent.get('content_path') or torrent.get('save_path'))

    def is_busy(self):
        with self.lock:
            return any(item['phase'] == 'upload' for item in self.items)

    def stop(self, timeout=15):
        """The program is closing: an upload stops and goes on at the next start"""

        self.stopping = True
        end = time.time() + timeout

        while time.time() < end and self.upload_state:
            time.sleep(0.2)

        self.save()

    # [ scheda tecnica ]
    def set_inspect(self, item, **values):
        with self.lock:
            if item['inspect'] is not None:
                item['inspect'].update(values)

    def check_inspect(self, item):
        if item['phase'] != 'inspect' or self.stopping:
            raise InspectStopped()

    def run_inspect(self, item_id):
        item = self.get(item_id)

        try:
            info = self.inspect_steps(item)
            self.set_inspect(item, status='ready', info=info, message=None)

        except InspectStopped:
            return

        except Exception as e:
            if not isinstance(e, AppError):
                log_error(f"Scheda tecnica of {item['title']}", e)
            self.set_inspect(item, status='error', message=describe(e))

        # The rest is downloaded only if the user wants it
        try:
            if item['phase'] == 'inspect' and item.get('hash'):
                self.get_client().pause(item['hash'])
        except Exception:
            pass

    def inspect_steps(self, item):
        client = self.get_client()
        start = time.time()

        # [ list of the files ]
        self.set_inspect(item, status='metadata')
        while True:
            self.check_inspect(item)
            torrent = self.find_torrent(client, item)

            if torrent and qbittorrent.has_metadata(torrent):
                break
            if time.time() - start > METADATA_TIMEOUT:
                raise TorrentError("Nessuno condivide questo torrent: in 3 minuti non è arrivato nemmeno l'elenco dei file. Prova un risultato con più seed")
            time.sleep(1)

        files = [{**file, 'index': file.get('index', position)} for position, file in enumerate(client.files(torrent['hash']))]
        guess = release.parse(item['title'])
        file_check = checks.check_files(files, guess)
        info = {'files': describe_files(files), 'check': file_check, 'probe': None, 'main': None}

        # Junk: nothing to read, and nothing more is downloaded
        main = max(checks.get_videos(files), key=lambda file: file['size'], default=None)
        if main is None:
            return info

        info['main'] = main['index']

        # Only the start and the end of the main video
        client.set_file_priority(torrent['hash'], [file['index'] for file in files if file is not main], 0)
        client.set_sequential(torrent, True)

        piece_size = client.properties(torrent['hash']).get('piece_size') or 0
        first, last = main.get('piece_range') or (0, 0)
        if not piece_size:
            raise TorrentError("qBittorrent non dice la dimensione dei pezzi del torrent")

        head = HEAD_BYTES
        start = time.time()

        while True:
            needed = set(range(first, min(last, first + math.ceil(head / piece_size)) + 1)) | {last}
            self.set_inspect(item, status='pieces', have=0, need=len(needed))

            while True:
                self.check_inspect(item)
                states = client.piece_states(torrent['hash'])
                have = sum(1 for piece in needed if piece < len(states) and states[piece] == 2)
                self.set_inspect(item, have=have)

                if have == len(needed):
                    break
                if time.time() - start > PIECES_TIMEOUT:
                    raise TorrentError("Il torrent scarica troppo lentamente: in 10 minuti non sono arrivati i primi MB del video")
                time.sleep(1)

            self.set_inspect(item, status='probe')
            torrent = self.find_torrent(client, item) or torrent
            path = self.file_path(torrent, main)

            if path is None:
                raise TorrentError("Il video scaricato non si trova sul PC: se usi Docker imposta le cartelle nelle impostazioni, scheda Torrent")

            try:
                info['probe'] = probe.describe(probe.run(path))
                info['check'] = checks.merge(file_check, checks.check_probe(info['probe'], guess, main['size']))
                return info

            except probe.ProbeError as e:
                # Some files keep their tracks further on: a few more MB, up to a limit
                if head >= MAX_HEAD_BYTES or last - first <= math.ceil(head / piece_size):
                    raise TorrentError(f"Il formato del video non si legge dai primi MB ({e})")
                head *= 2

    # [ poller ]
    def poller(self):
        last_nas_check = time.time()

        while True:
            busy = False

            try:
                busy = self.poll()

                if time.time() - last_nas_check > NAS_RETRY_INTERVAL:
                    last_nas_check = time.time()
                    self.retry_pending_uploads()

            except Exception as e:
                log_error("Poller of the torrents", e)

            self.wake.wait(POLL_ACTIVE if busy else POLL_IDLE)
            self.wake.clear()

    def poll(self):
        """Progress of the torrents, the ones complete go to the nas"""

        with self.lock:
            tracked = [item for item in self.items if item['phase'] in ('inspect', 'download', 'discard', 'done', 'upload')]

        if not tracked or not torrent_config.load_config()['qbit_url']:
            return False

        try:
            client = self.get_client()
            torrents = client.torrents()
        except AppError as e:
            if self.client_error != str(e):
                console.log(f"[yellow]qBittorrent: {e}")
            self.client_error = str(e)
            return True

        self.client_error = None
        by_hash = {torrent['hash']: torrent for torrent in torrents}
        by_tag = {tag.strip(): torrent for torrent in torrents for tag in (torrent.get('tags') or '').split(',') if tag.strip()}
        changed = False
        now = time.time()

        for item in tracked:
            torrent = by_hash.get(item.get('hash')) or by_tag.get(item['tag'])

            if torrent and item.get('hash') != torrent['hash']:
                item['hash'] = torrent['hash']
                changed = True

            self.live[item['id']] = torrent

            try:
                changed |= self.update_item(client, item, torrent, now)
            except AppError as e:
                console.log(f"[yellow]Torrent {item['title']}: {e}")

        if changed:
            self.save()

        return any(item['phase'] in ('inspect', 'download', 'upload', 'discard') for item in tracked)

    def update_item(self, client, item, torrent, now):
        """Return True when the item has changed"""

        phase = item['phase']

        if phase == 'discard':
            if torrent:
                client.delete(torrent['hash'], delete_files=True)

            # Just added, qbittorrent could still be making it
            elif now - item['created'] < MISSING_GRACE:
                return False

            with self.lock:
                if item in self.items:
                    self.items.remove(item)
            self.live.pop(item['id'], None)
            return True

        if phase == 'inspect':
            if now - item['touched'] > INSPECT_MAX_AGE:
                item['phase'] = 'discard'
                return True
            return False

        if phase != 'download':
            return False

        if torrent is None:
            if now - item['created'] > MISSING_GRACE:
                item.update(phase='error', error="Il torrent non c'è più in qBittorrent: è stato rimosso da lì")
                return True
            return False

        if item['selection'] and qbittorrent.has_metadata(torrent):
            self.apply_selection(client, item, torrent)
            return True

        if qbittorrent.is_complete(torrent) and not item['selection']:
            if nas.is_enabled():
                item['phase'] = 'upload'
                self.uploads.put(item['id'])
            else:
                item['phase'] = 'done'

            console.print(f"[green]Torrent completato [white]=> [cyan]{item['title']}")
            return True

        return False

    def apply_selection(self, client, item, torrent):
        """
        Files chosen in the scheda tecnica (or the videos when nobody chose), then a normal download from where it was.
        A torrent with nothing to watch is thrown away, a program inside is never downloaded.
        """

        files = [{**file, 'index': file.get('index', position)} for position, file in enumerate(client.files(torrent['hash']))]
        junk = checks.get_junk(files)

        if junk:
            client.delete(torrent['hash'], delete_files=True)
            item.update(phase='error', selection=False, error=f"Torrent falso, l'ho cancellato: {junk}")
            console.print(f"[red]Torrent falso cancellato [white]=> [cyan]{item['title']}")
            return

        chosen = set(item['files']) if item['files'] is not None else set(checks.default_files(files))
        programs = [file for file in files if checks.is_program(file)]
        chosen -= {file['index'] for file in programs}

        if programs:
            item['note'] = f"Ho escluso un programma nascosto nel torrent ({programs[0]['name'].split('/')[-1]})"

        client.set_file_priority(torrent['hash'], [file['index'] for file in files if file['index'] in chosen], 1)
        client.set_file_priority(torrent['hash'], [file['index'] for file in files if file['index'] not in chosen], 0)
        client.set_sequential(torrent, False)
        client.resume(torrent['hash'])

        item['selection'] = False

    # [ nas ]
    def uploader(self):
        """One upload at a time, nothing can stop the queue"""

        while True:
            item_id = self.uploads.get()

            try:
                self.upload(item_id)

            except DownloadCancelled:
                pass

            except BaseException as e:
                log_error(f"Upload of a torrent to the nas ({item_id})", e)
                item = self.get(item_id)
                if item is not None:
                    with self.lock:
                        item.update(phase='done', warning=describe(e))
                    self.save()

            finally:
                self.upload_state.pop(item_id, None)

    def upload(self, item_id):
        item = self.get(item_id)
        if item is None or item['phase'] != 'upload':
            return

        config = nas.load_config()
        if not nas.is_enabled(config):
            with self.lock:
                item['phase'] = 'done'
            self.save()
            return

        client = self.get_client()
        torrent = self.find_torrent(client, item)

        if torrent is None:
            with self.lock:
                item.update(phase='done', warning="Il torrent non c'è più in qBittorrent: niente da caricare")
            self.save()
            return

        files = [file for file in client.files(torrent['hash']) if file.get('priority', 1) > 0
                 and release.is_video(file['name']) and not release.is_sample(file['name'], file['size'])]

        # A film is its biggest video, the others are extras
        if item['media']['type'] == 'movie' and files:
            files = [max(files, key=lambda file: file['size'])]

        if not files:
            with self.lock:
                item.update(phase='done', warning="Nel torrent non c'è nessun video da caricare")
            self.save()
            return

        plan = []
        for file in files:
            path = self.file_path(torrent, file)
            if path is None:
                with self.lock:
                    item.update(phase='done', warning=f"File non trovato sul PC: {file['name']} (se usi Docker imposta le cartelle nelle impostazioni)")
                self.save()
                return
            plan.append((file, path, get_remote_path(config, item['media'], file)))

        total = sum(file['size'] for file, _, _ in plan)
        sent_before = 0

        for position, (file, path, remote_path) in enumerate(plan):
            if remote_path in item['uploads']:
                sent_before += file['size']
                continue

            console.print(f"[green]Upload to nas [white]=> [cyan]{remote_path}")
            progress = self.make_progress(item_id, sent_before, total, os.path.basename(remote_path), position + 1, len(plan))

            try:
                nas.upload(config, path, remote_path, progress=nas.make_progress(progress))
            except nas.NasError as e:
                with self.lock:
                    item.update(phase='done', warning=str(e))
                self.save()
                return

            with self.lock:
                item['uploads'].append(remote_path)
            self.save()
            sent_before += file['size']

        # Everything is on the nas: qbittorrent can forget the torrent, or keep sharing it
        if torrent_config.load_config()['after_upload'] == 'remove':
            try:
                client.delete(torrent['hash'], delete_files=True)
            except AppError as e:
                console.log(f"[yellow]Torrent caricato, ma non rimosso da qBittorrent: {e}")

        with self.lock:
            item.update(phase='done', warning=None)
        self.save()

    def make_progress(self, item_id, sent_before, total, name, index, count):
        started = time.time()

        def report(stage, sent, size):
            if self.stopping:
                raise DownloadCancelled(keep_files=True)

            elapsed = time.time() - started
            self.upload_state[item_id] = {
                'done': sent_before + sent,
                'total': total,
                'file': name,
                'index': index,
                'count': count,
                'speed': round(sent / elapsed) if elapsed > 1 else None,
            }

        return report

    def retry_pending_uploads(self):
        """Files the nas refused go there when it comes back"""

        config = nas.load_config()
        if not nas.is_enabled(config):
            return

        with self.lock:
            pending = [item for item in self.items if item['phase'] == 'done' and item.get('warning')
                       and item['auto_uploads'] < MAX_AUTO_UPLOADS and item.get('hash')]

        if not pending or not nas.is_reachable(config):
            return

        for item in pending:
            with self.lock:
                item['auto_uploads'] += 1
                item.update(phase='upload', warning=None)
            self.uploads.put(item['id'])

        self.save()

    # [ page ]
    def view(self, item):
        torrent = self.live.get(item['id'])
        upload = self.upload_state.get(item['id'])
        state = torrent.get('state') if torrent else None

        return {
            'id': item['id'],
            'title': item['title'],
            'tracker': item['tracker'],
            'size': (torrent.get('size') if torrent else None) or item['size'],
            'media': item['media'],
            'phase': item['phase'],
            'created': item['created'],
            'inspect': item['inspect'] if item['phase'] == 'inspect' else None,
            'warning': item['warning'],
            'error': item['error'],
            'note': item.get('note'),
            'uploaded': len(item['uploads']),
            'remote': item['uploads'][0] if item['uploads'] else None,
            'progress': torrent.get('progress') if torrent else None,
            'speed': torrent.get('dlspeed') if torrent else None,
            'eta': torrent.get('eta') if torrent and 0 <= torrent.get('eta', NO_ETA) < NO_ETA else None,
            'seeds': torrent.get('num_seeds') if torrent else None,
            'peers': torrent.get('num_leechs') if torrent else None,
            'state': state,
            'paused': state in qbittorrent.PAUSED_STATES,
            'stalled': state == 'stalledDL',
            'problem': "Errore in qBittorrent: file mancanti o disco non raggiungibile" if state in qbittorrent.ERROR_STATES else None,
            'in_client': torrent is not None,
            'upload': upload,
        }

    def list(self):
        with self.lock:
            items = [item for item in self.items if item['phase'] not in ('inspect', 'discard')]
            return [self.view(item) for item in reversed(items)]

    def status(self):
        config = torrent_config.load_config()

        return {
            'mode': 'webui' if config['qbit_url'] else 'app',
            'jackett_url': config['jackett_url'],
            'jackett_key': bool(torrent_config.get_jackett_key(config)),
            'plugins': count_plugins(config),
            'client_error': self.client_error,
            'nas': nas.is_enabled(),
            'probe': probe.is_available(),
            'system_open': sys.platform == 'win32',
        }


# [ helpers ]
def count_plugins(config):
    if config['plugins'] == 'off':
        return 0

    try:
        return len(plugins.get_engines(config)[1])
    except AppError:
        return 0

def plain_name(title):
    return re.sub(r'[^a-z0-9]+', ' ', title.lower()).strip()

def get_hash(raw):
    match = re.search(r'btih:([0-9a-zA-Z]+)', raw['magnet'] or '')
    return match.group(1).lower() if match else None

def is_same(raw, other):
    """
    The same torrent found twice. Sites without magnet (LimeTorrents) give no hash and round the weight:
    the same name with almost the same weight is the same release.
    """

    if get_hash(raw) and get_hash(raw) == get_hash(other):
        return True

    sizes = (raw['size'] or 0, other['size'] or 0)
    return plain_name(raw['title']) == plain_name(other['title']) and min(sizes) > 0 and min(sizes) / max(sizes) > 0.98

def read_media(value):
    """Name, year and kind the file takes on the nas"""

    value = value if isinstance(value, dict) else {}
    name = str(value.get('name') or '').strip()[:200]
    if not name:
        raise TorrentError("Scrivi il titolo con cui salvarlo")

    kind = value.get('type') if value.get('type') in ('movie', 'tv', 'anime') else 'movie'
    year = str(value.get('year') or '').strip()
    season = value.get('season')

    return {
        'name': name,
        'year': year if re.fullmatch(r'(19|20)\d\d', year) else None,
        'type': kind,
        'season': int(season) if str(season or '').isdigit() and int(season) > 0 else (1 if kind != 'movie' else None),
    }

def describe_files(files):
    return [{
        'index': file['index'],
        'name': file['name'],
        'size': file['size'],
        'video': release.is_video(file['name']),
        'sample': release.is_sample(file['name'], file['size']),
        'dangerous': checks.is_program(file),
    } for file in sorted(files, key=lambda file: file['name'].lower())]

def get_remote_path(config, media, file):
    """Path on the nas of a file of the torrent, a pack of episodes keeps each episode apart"""

    info = release.parse_file(file['name'])
    extension = release.extension(file['name'])

    if media['type'] == 'movie':
        return nas.get_remote_path(config, {'name': media['name'], 'year': media['year'], 'type': 'movie'}, extension)

    if media['type'] == 'anime':
        target = {'name': media['name'], 'year': media['year'], 'type': 'anime', 'single': False, 'episode_number': info['episode']}
    else:
        target = {'name': media['name'], 'year': media['year'], 'type': 'tv', 'season': info['season'] or media['season'] or 1,
                  'episode_number': info['episode'], 'episode_name': None}

    if info['episode'] is not None:
        return nas.get_remote_path(config, target, extension)

    # No episode in the name: the file keeps its name in the folder of the season
    folder = posixpath.dirname(nas.get_remote_path(config, {**target, 'episode_number': 0}, extension))
    return posixpath.join(folder, (nas.clean_name(os.path.splitext(os.path.basename(file['name']))[0]) or 'Senza nome') + extension)
