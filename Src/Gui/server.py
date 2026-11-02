# 15.09.26

# Class import
import Src.Api.page as Page
from Src.Api import anime, film, tv
from Src.Gui.anime_source import AnimeSource
from Src.Gui import instance, remote
from Src.Gui.recommend import Recommender
from Src.Gui.anime_recommend import AnimeRecommender
from Src.Gui.torrents import TorrentManager
from Src.Gui.player import Streams
from Src.Lib.Nas import nas
from Src.Lib.Torrent import config as torrent_config, jackett, plugins, qbittorrent
from Src.Util import history, storage, videos
from Src.Util import progress as watch_progress
from Src.Util.cancel import DownloadCancelled
from Src.Util.errors import AppError, DownloadError, describe, is_disk_full, is_online, step
from Src.Util.log import log_error
from Src.Util.console import console
from Src.Api.vixcloud import get_stream
from Src.Util.os import remove_folder

# General import
import argparse, collections, itertools, json, os, queue, re, shutil, subprocess, sys, threading, time, webbrowser
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import requests

# Variable
WEB_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "web")
DATA_FILE = "data.json"
DEFAULT_PORT = 8765
JOBS_FILE = "downloads.json"
MAX_SAVED_JOBS = 300
ACTIVE = ('queued', 'running', 'waiting')
RETRY_DELAYS = (30, 120, 600)       # Seconds before the automatic attempts after an error
NAS_RETRY_INTERVAL = 120            # How often the files the nas refused are tried again
MAX_AUTO_UPLOADS = 5
ADDRESS_ENV = "SC_ADDRESS"          # Address shown in the qr code, used by the docker image
REMOTE_HOST = '0.0.0.0'             # Every network card of the pc, the key and the private addresses protect it
SEGMENTS_MAX_AGE = 7 * 24 * 3600    # Segments of a download not resumed for a week are removed
SPEED_WINDOW = 5                    # Seconds of the speed shown, short enough to follow the changes
CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
}


class ApiError(AppError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


# [ site ]
class Site:
    """Domain and inertia version of the site, shared by every request"""

    def __init__(self):
        self.lock = threading.Lock()
        # The old versions saved only the extension: it becomes the whole address
        self.domain = Page.get_host(self.read_data().get('domain', ''))
        self.version = None

    def read_data(self):
        data = storage.read_json(DATA_FILE, {})
        return data if isinstance(data, dict) else {}

    def connect(self, domain=None):
        """Get version of the site and save the domain if it works"""

        domain = Page.get_host(self.domain if domain is None else domain)

        if not domain:
            raise ApiError("Inserisci l'indirizzo del sito")

        try:
            version = Page.get_version(domain)
        except Exception as e:
            # The reason is shown in the settings: missing domain, blocked by the provider, site moved...
            console.log(f"[red]Site {domain} not reachable: {e!r}")
            raise ApiError(describe(e), 502)

        with self.lock:
            self.domain, self.version = domain, version

        data = self.read_data()
        data['domain'] = domain

        # The site works also if the domain cant be saved, it is asked again at the next start
        try:
            storage.write_json(DATA_FILE, data)
        except OSError as e:
            console.log(f"[yellow]Domain not saved: {e}")

    def status(self):
        error = None

        if self.domain and self.version is None:
            try:
                self.connect()
            except ApiError as e:
                error = str(e)

        return {
            'domain': self.domain,
            'site_name': Page.SITE_NAME,
            'site': self.domain or None,
            'connected': self.version is not None,
            'ffmpeg': shutil.which('ffmpeg') is not None,
            'nas': nas.is_enabled(),
            'error': error,
        }

    def request(self, fetch):
        """Call fetch(domain, version), getting the new version if the site has been updated"""

        if self.version is None:
            self.connect()

        try:
            return fetch(self.domain, self.version)
        except requests.HTTPError as e:

            # Inertia answer 409 when the version of the site is changed
            if e.response is None or e.response.status_code != 409:
                raise

            self.connect()
            return fetch(self.domain, self.version)


# [ format ]
def get_image(cdn_url, images, *types):
    for image_type in types:
        for image in images or []:
            if image.get('type') == image_type and image.get('filename'):
                return f"{cdn_url}/images/{image['filename']}"

    return None

def format_title(title, cdn_url):
    images = title.get('images')
    date = title.get('release_date') or title.get('last_air_date') or ''

    return {
        'id': title['id'],
        'slug': title['slug'],
        'name': title['name'],
        'source': 'sc',
        'type': title['type'],
        'score': title.get('score'),
        'year': date[:4] or None,
        'age': title.get('age'),
        'seasons_count': title.get('seasons_count'),
        'sub_ita': bool(title.get('sub_ita')),
        'poster': get_image(cdn_url, images, 'poster', 'cover_mobile'),
        'backdrop': get_image(cdn_url, images, 'background', 'cover'),
        'logo': get_image(cdn_url, images, 'logo'),
    }

def format_detail(props):
    title = props['title']
    detail = format_title(title, props['cdn_url'])

    detail.update({
        'plot': title.get('plot'),
        'original_name': title.get('original_name'),
        'runtime': title.get('runtime'),
        'quality': title.get('quality'),
        'genres': [genre['name'] for genre in title.get('genres') or []],
        'actors': [actor['name'] for actor in title.get('main_actors') or []][:6],
        'directors': [director['name'] for director in title.get('main_directors') or []][:3],
        'seasons': [season['number'] for season in title.get('seasons') or []],
    })
    return detail

def format_episode(episode, cdn_url):
    return {
        'id': episode['id'],
        'number': episode['number'],
        'name': episode.get('name') or f"Episodio {episode['number']}",
        'plot': episode.get('plot'),
        'duration': episode.get('duration'),
        'cover': get_image(cdn_url, episode.get('images'), 'cover'),
    }

def parse_int(value, name):
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ApiError(f"Parametro non valido: {name}")

def read_nas(body):
    """Nas settings sent by the gui, the password is kept apart"""

    return {
        'enabled': bool(body.get('enabled')),
        'host': str(body.get('host') or '').strip(),
        'port': parse_int(body.get('port') or 22, 'port'),
        'user': str(body.get('user') or '').strip(),
        'film_path': str(body.get('film_path') or '').strip().rstrip('/'),
        'tv_path': str(body.get('tv_path') or '').strip().rstrip('/'),
        'anime_path': str(body.get('anime_path') or '').strip().rstrip('/'),
    }

def read_torrent_config(body, saved):
    """Torrent settings sent by the gui, the key of jackett and the password are never sent back"""

    values = {key: str(body.get(key) or '').strip() for key in ('jackett_url', 'qbit_url', 'qbit_user', 'save_path', 'after_upload', 'path_from', 'path_to', 'plugins', 'plugins_path')}
    values['jackett_key'] = str(body.get('jackett_key') or '').strip() or saved['jackett_key']

    # An address written without http
    for key in ('jackett_url', 'qbit_url'):
        url = values[key].rstrip('/')
        values[key] = f"http://{url}" if url and not re.match(r'^https?://', url, re.IGNORECASE) else url

    return {**saved, **values}

def parse_seconds(value, name):
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        raise ApiError(f"Parametro non valido: {name}")

    if not 0 <= seconds < 100 * 3600:
        raise ApiError(f"Parametro non valido: {name}")

    return seconds

def read_watch_item(item):
    """A film or an episode watched in the app, with what the row of the home needs to show it"""

    if not isinstance(item, dict):
        raise ApiError("Video non valido")

    optional_int = lambda key: parse_int(item[key], key) if item.get(key) is not None else None
    text = lambda key: item[key] if isinstance(item.get(key), str) and item[key] else None

    return {
        'source': 'anime' if item.get('source') == 'anime' else 'sc',
        'id': parse_int(item.get('id'), 'id'),
        'slug': str(item.get('slug') or ''),
        'name': str(item.get('name') or item.get('slug') or ''),
        'type': 'tv' if item.get('type') == 'tv' else 'movie',
        'year': str(item['year'])[:4] if item.get('year') else None,
        'poster': text('poster'),
        'backdrop': text('backdrop'),
        'dub': bool(item.get('dub')),
        'season': optional_int('season'),
        'episode_id': optional_int('episode_id'),
        'episode_number': str(item['episode_number']) if item.get('episode_number') is not None else None,
        'episode_name': text('episode_name'),
    }

def parse_slug(value):

    # Slug is used in urls and file names
    if not isinstance(value, str) or not re.fullmatch(r"[\w+-]+", value):
        raise ApiError("Parametro non valido: slug")

    return value

def open_in_explorer(path):
    path = os.path.abspath(path)

    if sys.platform == 'win32':
        if os.path.isfile(path):
            subprocess.Popen(f'explorer /select,"{path}"')
        else:
            os.startfile(path)
    elif sys.platform == 'darwin':
        subprocess.Popen(['open', '-R', path] if os.path.isfile(path) else ['open', path])
    else:
        subprocess.Popen(['xdg-open', os.path.dirname(path) if os.path.isfile(path) else path])


# [ downloads ]
class DownloadManager:
    """
    Queue of downloads, executed one at a time.
    The queue is saved on disk: after a crash or a power cut the downloads go on from where they were.
    """

    def __init__(self, site):
        self.site = site
        self.jobs = []
        self.lock = threading.Lock()
        self.queue = queue.Queue()
        self.next_id = itertools.count(1)
        self.speeds = {}            # Bytes of the running job along the time, the base of the speed shown
        self.load()

        threading.Thread(target=self.worker, daemon=True).start()
        threading.Thread(target=self.scheduler, daemon=True).start()

    # [ saved queue ]
    def load(self):
        """Downloads of the last time: the ones not finished start again by themselves"""

        saved = storage.read_json(JOBS_FILE, {})
        jobs = saved.get('jobs') if isinstance(saved, dict) else None
        resumed = 0

        for job in jobs if isinstance(jobs, list) else []:
            if not isinstance(job, dict) or not isinstance(job.get('id'), int):
                continue

            job = {**self.empty_job(), **job, 'cancel': False, 'stage': None, 'done': 0, 'total': 0, 'waiting': None}

            if job['status'] in ('queued', 'running', 'waiting'):
                # An upload whose file is gone cant go on
                if job['upload_only'] and not (job['output'] and os.path.isfile(job['output'])):
                    job.update(status='error', error="Il file da caricare non c'è più", upload_only=False)
                else:
                    job.update(status='queued', retry_at=None)
                    resumed += 1

            elif job['status'] not in ('done', 'error', 'cancelled'):
                continue

            self.jobs.append(job)

        self.jobs = self.jobs[-MAX_SAVED_JOBS:]
        self.next_id = itertools.count(max((job['id'] for job in self.jobs), default=0) + 1)

        for job in self.jobs:
            if job['status'] == 'queued':
                self.queue.put(job)

        if resumed:
            console.print(f"[green]Resumed {resumed} downloads of the last time")

    def save(self):
        """Write the queue on disk, a full disk is not a reason to stop the downloads"""

        with self.lock:
            jobs = [{key: value for key, value in job.items() if key not in ('cancel', 'stage', 'done', 'total', 'waiting')}
                    for job in self.jobs if job['status'] != 'removed']

        try:
            storage.write_json(JOBS_FILE, {'jobs': jobs[-MAX_SAVED_JOBS:]}, indent=2)
        except Exception as e:
            log_error("Downloads queue not saved", e)

    # [ jobs ]
    def empty_job(self):
        return {
            'id': None,
            'source': 'sc',
            'title_id': None,
            'slug': None,
            'name': None,
            'type': 'movie',
            'year': None,
            'poster': None,
            'season': None,
            'episode_id': None,
            'episode_number': None,
            'episode_name': None,
            'status': 'queued',
            'stage': None,
            'done': 0,
            'total': 0,
            'error': None,
            'warning': None,
            'output': None,
            'remote': None,
            'upload_only': False,
            'cancel': False,
            'attempt': 0,               # Automatic attempts after an error
            'retry_at': None,
            'waiting': None,            # 'offline' while the connection is missing
            'auto_uploads': 0,
            'upload_cancelled': False,
        }

    def make_job(self, item):
        if not isinstance(item, dict):
            raise ApiError("Elemento da scaricare non valido")

        job = {
            **self.empty_job(),
            'source': 'anime' if item.get('source') == 'anime' else 'sc',
            'title_id': parse_int(item.get('id'), 'id'),
            'slug': parse_slug(item.get('slug')),
            'name': str(item.get('name') or item.get('slug')),
            'type': 'tv' if item.get('type') == 'tv' else 'movie',
            'year': str(item.get('year'))[:4] if item.get('year') else None,
            'poster': item.get('poster') if isinstance(item.get('poster'), str) else None,
        }

        if job['source'] == 'anime':
            # Films of anime have a single episode, it is found when the download starts
            if job['type'] == 'tv':
                job['episode_id'] = parse_int(item.get('episode_id'), 'episode_id')
                job['episode_number'] = str(item.get('episode_number') or '')

        elif job['type'] == 'tv':
            job['season'] = parse_int(item.get('season'), 'season')
            job['episode_id'] = parse_int(item.get('episode_id'), 'episode_id')
            job['episode_number'] = parse_int(item.get('episode_number'), 'episode_number')
            job['episode_name'] = str(item.get('episode_name') or '')

        return job

    def add(self, items):
        jobs = [self.make_job(item) for item in items]
        added = []

        with self.lock:
            for job in jobs:
                # Ids of the two sites can be the same number
                key = (job['source'], job['title_id'], job['episode_id'])
                duplicate = next((other for other in self.jobs if other['status'] in ACTIVE
                                  and (other['source'], other['title_id'], other['episode_id']) == key), None)

                if duplicate is None:
                    job['id'] = next(self.next_id)
                    self.jobs.append(job)
                    self.queue.put(job)
                    added.append(job)

        self.save()
        return [dict(job) for job in added]

    # [ worker ]
    def worker(self):
        """Nothing can stop the queue: an unexpected error ends only its download"""

        while True:
            job = self.queue.get()

            try:
                self.run(job)

            except BaseException as e:
                log_error(f"Unexpected error in the downloads queue ({job.get('name')})", e)
                with self.lock:
                    if job['status'] == 'running':
                        job.update(status='error', error=describe(e), waiting=None)
                self.save()

    def run(self, job):
        with self.lock:
            if job['status'] != 'queued':
                return
            job.update(status='running', waiting=None, retry_at=None, stage=None, done=0, total=0)

        self.save()
        console.print(f"\n[green]GUI download [white]=> [cyan]{job['name']}")
        progress = lambda stage, done, total, received=None: self.update(job, stage, done, total, received)
        output, remote, warning, status, error, retry = None, None, None, 'done', None, False
        upload_only = job['upload_only']

        try:
            if upload_only:
                result = nas.finalize(job['output'], self.get_media(job), progress)
            else:
                result = self.download(job, progress)

            # A nas that does not answer leaves the file here, with a warning
            output, remote, warning = result['path'], result['remote'], result['warning']

        except DownloadCancelled as e:
            if e.keep_files:
                # The program is closing: the download goes on at the next start
                status = 'queued'
                console.print(f"[yellow]GUI download paused [white]=> [cyan]{job['name']}")
            else:
                status = 'cancelled'
                console.print(f"[yellow]GUI download cancelled [white]=> [cyan]{job['name']}")

        except SystemExit:
            status, error, retry = 'error', "Download non riuscito, dettagli nella console", True
            log_error(f"Download stopped by the site code ({job['name']})")

        except Exception as e:
            status, error, retry = 'error', describe(e), self.can_retry(e)
            console.print(f"[red]GUI download failed [white]=> [cyan]{job['name']}: [red]{error}")
            log_error(f"Download failed ({job['name']})", e)

        # Past downloads are the base of the recommendations, a history not saved is not a failed download
        if status == 'done' and not upload_only:
            try:
                history.add(job['title_id'], job['slug'], job['name'], job['type'], job['year'], source=job['source'])
            except Exception as e:
                log_error("History not saved", e)

        with self.lock:
            user_cancel = job['cancel'] is True
            self.speeds.pop(job['id'], None)

            if status == 'error' and retry and job['attempt'] < len(RETRY_DELAYS) and not job['cancel']:
                # Tried again later by itself, the segments already saved are kept
                delay = RETRY_DELAYS[job['attempt']]
                job['attempt'] += 1
                job.update(status='waiting', error=error, retry_at=time.time() + delay, waiting=None)
                console.print(f"[yellow]New attempt in {delay} seconds [white]=> [cyan]{job['name']}")

            else:
                job.update(status=status, error=error, waiting=None, cancel=False)

                if status != 'queued':
                    # A failed upload keeps its file on the pc, a failed download has no file
                    kept = job['output'] if upload_only else None
                    job.update(output=output if status == 'done' else kept, remote=remote, warning=warning, upload_only=False)

                if status == 'done':
                    job['attempt'] = 0
                    job['upload_cancelled'] = bool(warning and user_cancel)

        self.save()

    def can_retry(self, error):
        """Errors that can go away by themselves: connection, site busy, expired links"""

        if isinstance(error, DownloadError):
            return error.retry
        if isinstance(error, PermissionError) or is_disk_full(error):
            return False

        return True

    def scheduler(self):
        """Start again the downloads waiting for a new attempt, and upload the files the nas refused"""

        last_nas_check = time.time()

        while True:
            time.sleep(2)

            try:
                self.resume_waiting()

                if time.time() - last_nas_check > NAS_RETRY_INTERVAL:
                    last_nas_check = time.time()
                    self.retry_pending_uploads()

            except Exception as e:
                log_error("Scheduler of the downloads", e)

    def resume_waiting(self):
        now = time.time()

        with self.lock:
            ready = [job for job in self.jobs if job['status'] == 'waiting' and job['retry_at'] and job['retry_at'] <= now]

        # Without internet the attempt would fail again at once
        if not ready or not is_online():
            return

        with self.lock:
            for job in ready:
                if job['status'] == 'waiting':
                    job.update(status='queued', retry_at=None)
                    self.queue.put(job)

        self.save()

    def retry_pending_uploads(self):
        """Files left on the pc because the nas was off go there when it comes back"""

        config = nas.load_config()
        if not nas.is_enabled(config):
            return

        with self.lock:
            pending = [job for job in self.jobs if job['status'] == 'done' and job['warning'] and not job['upload_cancelled']
                       and job['auto_uploads'] < MAX_AUTO_UPLOADS and job['output'] and os.path.isfile(job['output'])]

        if not pending or not nas.is_reachable(config):
            return

        for job in pending:
            with self.lock:
                job['auto_uploads'] += 1
            console.print(f"[green]NAS is back, upload of [cyan]{job['name']}")
            self.retry_upload(job['id'])

    def get_media(self, job):
        """Data used to name the file and to build the path on the nas"""

        if job['source'] == 'anime':
            return {'name': job['name'], 'year': job['year'], 'type': 'anime', 'single': job['type'] == 'movie', 'episode_number': job['episode_number']}

        media = {'name': job['name'], 'year': job['year'], 'type': job['type']}

        if job['type'] == 'tv':
            media.update(season=job['season'], episode_number=job['episode_number'], episode_name=job['episode_name'])

        return media

    def download(self, job, progress):
        media = self.get_media(job)
        self.check_cancel(job)

        if job['source'] == 'anime':
            return self.download_anime(job, progress, media)

        # The site is asked again at every attempt, it could have changed domain version meanwhile
        if self.site.version is None:
            with step("Collegamento al sito"):
                self.site.connect()

        domain = self.site.domain

        if job['type'] == 'movie':
            return film.main_dw_film(job['title_id'], job['slug'], domain, progress_callback=progress, media=media)

        with step("Ricerca dell'episodio sul sito"):
            props = self.site.request(lambda domain, version: tv.get_season(job['title_id'], job['slug'], domain, version, job['season']))
            episodes = [{'id': ep['id'], 'n': ep['number'], 'name': ep['name']} for ep in props['loadedSeason']['episodes']]
            index = next((i for i, ep in enumerate(episodes) if ep['id'] == job['episode_id']), None)

            if index is None:
                raise DownloadError(f"La stagione {job['season']} non contiene più questo episodio", retry=False)

            token = tv.get_token(job['title_id'], domain)
        self.check_cancel(job)
        return tv.dw_single_ep(job['title_id'], episodes, index, domain, token, job['slug'], job['season'], progress_callback=progress, media=media)

    def download_anime(self, job, progress, media):
        episode_id, number = job['episode_id'], job['episode_number']

        # A film of anime is its first and only episode
        if episode_id is None:
            with step("Ricerca del film su AnimeUnity"):
                episodes = anime.client.get_episodes(job['title_id'], 1, 1)

            if not episodes:
                raise DownloadError("AnimeUnity non ha nessun episodio per questo titolo", retry=False)

            episode_id, number = int(episodes[0]['id']), str(episodes[0]['number'])

        self.check_cancel(job)
        return anime.dw_episode(job['title_id'], job['slug'], episode_id, number, progress_callback=progress, media=media)

    def update(self, job, stage, done, total, received=None):
        """Progress of a job, it stops the download when the user cancels it"""

        self.check_cancel(job)

        with self.lock:
            # Waiting for the connection is shown without losing the progress
            if stage in ('offline', 'online'):
                job['waiting'] = 'offline' if stage == 'offline' else None
            else:
                job.update(stage=stage, done=done, total=total)
                # The upload counts the bytes sent to the nas
                self.sample_speed(job['id'], stage, done if stage == 'upload' else received)

    def sample_speed(self, job_id, stage, amount):
        """Bytes moved until now, called with the lock taken"""

        # Joining and merging move nothing on the network
        if amount is None:
            self.speeds.pop(job_id, None)
            return

        now = time.time()
        speed = self.speeds.get(job_id)

        # Every stage counts its bytes from zero
        if speed is None or speed['stage'] != stage or amount < speed['samples'][-1][1]:
            self.speeds[job_id] = {'stage': stage, 'samples': collections.deque([(now, amount)])}
            return

        samples = speed['samples']

        # The progress arrives many times a second, one sample every half second is enough
        if len(samples) > 1 and now - samples[-2][0] < 0.5:
            samples[-1] = (now, amount)
        else:
            samples.append((now, amount))

        # The oldest sample kept is the start of the window
        while len(samples) > 2 and samples[1][0] <= now - SPEED_WINDOW:
            samples.popleft()

    def get_speed(self, job_id, now):
        """Bytes per second of the last seconds, None while there is nothing to measure"""

        speed = self.speeds.get(job_id)
        if speed is None:
            return None

        (start, first), (end, last) = speed['samples'][0], speed['samples'][-1]

        # Too soon after the start of the stage to tell
        if now - start < 1:
            return None

        # A download that does not move goes down to zero by itself
        if now - end > SPEED_WINDOW:
            return 0
        return round((last - first) / (now - start))

    def check_cancel(self, job):
        if job['cancel']:
            raise DownloadCancelled(keep_files=job['cancel'] == 'shutdown')

    def stop(self, timeout=15):
        """
        The program is closing: the running download stops but keeps its segments,
        the queue stays saved and goes on at the next start
        """

        with self.lock:
            for job in self.jobs:
                if job['status'] == 'running':
                    job['cancel'] = 'shutdown'

        end = time.time() + timeout
        while time.time() < end and any(job['status'] == 'running' for job in self.list()):
            time.sleep(0.2)

        self.save()

    def cancel(self, job_id):
        """Stop a running download, or take a waiting one out of the queue"""

        with self.lock:
            job = next((job for job in self.jobs if job['id'] == job_id), None)

            if job is None or job['status'] not in ACTIVE:
                return False

            if job['status'] in ('queued', 'waiting'):
                # Worker skip removed jobs still in queue
                job['status'] = 'removed'
                self.jobs.remove(job)
            else:
                job['cancel'] = True

        self.save()
        return True

    def list(self):
        now = time.time()

        with self.lock:
            jobs = [dict(job) for job in self.jobs]
            speeds = {job['id']: self.get_speed(job['id'], now) for job in jobs if job['status'] == 'running' and not job['waiting']}

        # A failed upload can be retried, the file is still here
        enabled = nas.is_enabled()

        for job in jobs:
            job['speed'] = speeds.get(job['id'])
            job['can_upload'] = bool(enabled and (job['warning'] or job['status'] == 'error')
                                     and job['output'] and os.path.isfile(job['output']))
            job['retry_in'] = max(0, round(job['retry_at'] - now)) if job['status'] == 'waiting' and job['retry_at'] else None
            job['cancel'] = bool(job['cancel'])

        return jobs

    def retry_upload(self, job_id):
        with self.lock:
            job = next((job for job in self.jobs if job['id'] == job_id and job['output'] and job['status'] in ('done', 'error')
                        and (job['warning'] or job['status'] == 'error')), None)

            if job is None:
                return False

            job.update(status='queued', stage=None, done=0, total=0, error=None, warning=None, upload_only=True, cancel=False, upload_cancelled=False)
            self.queue.put(job)

        self.save()
        return True

    def remove(self, job_id):
        with self.lock:
            job = next((job for job in self.jobs if job['id'] == job_id and job['status'] != 'running'), None)

            if job is None:
                return False

            # Worker skip removed jobs still in queue
            job['status'] = 'removed'
            self.jobs.remove(job)

        self.save()
        return True

    def clear(self):
        with self.lock:
            self.jobs = [job for job in self.jobs if job['status'] in ACTIVE]

        self.save()

    def get_output(self, job_id):
        with self.lock:
            return next((job['output'] for job in self.jobs if job['id'] == job_id), None)


# [ api ]
class App:
    def __init__(self):
        self.site = Site()
        self.anime = AnimeSource()
        self.downloads = DownloadManager(self.site)
        self.recommender = Recommender(self.site, format_title)
        self.anime_recommender = AnimeRecommender()
        self.torrents = TorrentManager()
        self.streams = Streams()
        self.remote_server = None
        self.remote_lock = threading.Lock()
        self.server = None
        self.last_request = time.time()

    def close(self, query, body):
        """The window has been closed, stop the program when no download is running"""

        threading.Thread(target=self.close_when_idle, args=(self.last_request,), daemon=True).start()
        return {'ok': True}

    def close_when_idle(self, closed_at):
        while True:
            time.sleep(4)

            # The page is open again, keep working
            if self.last_request > closed_at:
                return

            if any(job['status'] in ACTIVE for job in self.downloads.list()) or self.torrents.is_busy():
                continue

            console.print("[red]GUI closed")
            threading.Thread(target=self.server.shutdown, daemon=True).start()
            return

    def status(self, query, body):
        return self.site.status()

    # [ access from the phone ]
    def start_remote(self):
        """Open the app to the devices of the home network, on its own port and with the key"""

        with self.remote_lock:
            if self.remote_server is not None:
                return

            config = remote.load_config()
            error = None

            # The saved port could be taken by another program, the next free one is used
            for port in [config['port']] + list(range(remote.DEFAULT_PORT, remote.DEFAULT_PORT + 20)):
                try:
                    server = Server((REMOTE_HOST, port), Handler)
                    break
                except OSError as e:
                    error = e
            else:
                raise ApiError(f"Nessuna porta libera per l'accesso dal telefono ({error})", 500)

            server.app = self
            server.remote = True
            self.remote_server = server
            threading.Thread(target=server.serve_forever, daemon=True).start()

            if port != config['port']:
                config['port'] = port
                remote.save_config(config)

            console.print(f"[green]Access from the home network [white]=> [cyan]port {port}")

    def stop_remote(self):
        with self.remote_lock:
            server, self.remote_server = self.remote_server, None

        if server is not None:
            server.shutdown()
            server.server_close()

    def remote_info(self):
        port = self.remote_server.server_port if self.remote_server else remote.load_config()['port']

        # In docker the pc is not the container: the address to show is given from outside
        addresses = [os.environ[ADDRESS_ENV]] if os.environ.get(ADDRESS_ENV) else [f"http://{ip}:{port}" for ip in remote.get_lan_ips()]

        return {
            'running': self.remote_server is not None,
            'port': port,
            'addresses': addresses,
            'qr': remote.get_qr_svg(addresses[0]) if addresses else None,
        }

    def get_remote(self, query, body):
        return self.remote_info()

    def set_domain(self, query, body):
        self.site.connect(str(body.get('domain') or ''))
        return self.site.status()

    def home(self, query, body):
        props = self.site.request(Page.get_home)

        return {'sliders': [{
            'name': slider['name'],
            'label': slider['label'],
            'titles': [format_title(title, props['cdn_url']) for title in slider['titles']],
        } for slider in props.get('sliders') or []]}

    def recommendations(self, query, body):
        return self.recommender.get()

    def search(self, query, body):
        text = query.get('q', '').strip()

        if not text:
            raise ApiError("Scrivi il titolo da cercare")

        props = self.site.request(lambda domain, version: Page.get_search(text, domain, version))
        return {'results': [format_title(title, props['cdn_url']) for title in props['titles']]}

    def title(self, query, body):
        title_id, slug = parse_int(query.get('id'), 'id'), parse_slug(query.get('slug'))
        return format_detail(self.site.request(lambda domain, version: Page.get_title(title_id, slug, domain, version)))

    def season(self, query, body):
        title_id, slug, number = parse_int(query.get('id'), 'id'), parse_slug(query.get('slug')), parse_int(query.get('number'), 'number')
        props = self.site.request(lambda domain, version: tv.get_season(title_id, slug, domain, version, number))

        return {
            'number': number,
            'episodes': [format_episode(episode, props['cdn_url']) for episode in props['loadedSeason']['episodes']],
        }

    def anime_home(self, query, body):
        return self.anime.home()

    def anime_recommendations(self, query, body):
        return self.anime_recommender.get()

    def anime_search(self, query, body):
        text = query.get('q', '').strip()

        if not text:
            raise ApiError("Scrivi il titolo da cercare")

        return self.anime.search(text)

    def anime_title(self, query, body):
        return self.anime.title(parse_int(query.get('id'), 'id'))

    def anime_episodes(self, query, body):
        anime_id, start, end = parse_int(query.get('id'), 'id'), parse_int(query.get('start'), 'start'), parse_int(query.get('end'), 'end')

        if start < 1 or end < start or end - start > 500:
            raise ApiError("Intervallo di episodi non valido")

        return self.anime.episodes(anime_id, start, end)

    def stream(self, query, body):
        """The whole film or episode to watch in the app, in the same quality of the download"""

        source = 'anime' if query.get('source') == 'anime' else 'sc'
        title_id = parse_int(query.get('id'), 'id')
        episode_id = parse_int(query['episode_id'], 'episode_id') if query.get('episode_id') else None

        if source == 'sc' and not self.site.domain:
            raise ApiError("Imposta prima il dominio del sito", 409)
        if source == 'sc' and query.get('type') == 'tv' and episode_id is None:
            raise ApiError("Parametro non valido: episode_id")

        stream = self.streams.open(get_stream(self.get_player(source, title_id, episode_id)))
        width, height = stream.resolution or (0, 0)

        return {
            'url': f"/api/stream/{stream.id}/master.m3u8",
            'quality': f"{height}p" if height else None,
            'language': stream.language,
            'duration': round(stream.duration),
            'subtitles': [{
                'url': f"/api/stream/{stream.id}/subtitles/{index}.vtt",
                'label': track['title'],
                'language': track['language'],
                'default': track['default'],
            } for index, track in enumerate(stream.subtitles)],
        }

    def get_player(self, source, title_id, episode_id):
        """Script of the vixcloud player of a film or an episode"""

        if source == 'anime':

            # A film of anime is its first episode
            if episode_id is None:
                episodes = anime.client.get_episodes(title_id, 1, 1)
                if not episodes:
                    raise ApiError("Episodio non trovato", 404)
                episode_id = int(episodes[0]['id'])

            return anime.get_player_script(anime.client.get_embed_url(episode_id))

        domain = self.site.domain
        if episode_id is None:
            return film.get_iframe(title_id, domain)

        return tv.get_iframe(title_id, episode_id, domain, tv.get_token(title_id, domain))

    # [ where the videos have been stopped ]
    def watch(self, query, body):
        return watch_progress.view()

    def save_watch(self, query, body):
        """Position of the video watched now, sent by the player every few seconds and when it closes"""

        item = read_watch_item(body.get('item'))
        entry = {**item, 'position': parse_seconds(body.get('position'), 'position'), 'duration': parse_seconds(body.get('duration'), 'duration')}

        # The episode after it, proposed in the home when this one is seen to the end
        following = body.get('next')
        next_entry = None
        if isinstance(following, dict) and following.get('episode_id') is not None:
            next_entry = read_watch_item({**body['item'], 'episode_name': None, **following})

        return watch_progress.view(watch_progress.save(entry, next_entry))

    def dismiss_watch(self, query, body):
        source = 'anime' if body.get('source') == 'anime' else 'sc'
        return watch_progress.view(watch_progress.dismiss(source, parse_int(body.get('id'), 'id')))

    def list_downloads(self, query, body):
        return {'jobs': self.downloads.list()}

    def add_downloads(self, query, body):
        items = body.get('items')

        if not isinstance(items, list) or not items:
            raise ApiError("Nessun elemento da scaricare")

        return {'added': self.downloads.add(items), 'jobs': self.downloads.list()}

    def remove_download(self, query, body):
        if not self.downloads.remove(parse_int(body.get('id'), 'id')):
            raise ApiError("Questo download non può essere rimosso")

        return {'jobs': self.downloads.list()}

    def clear_downloads(self, query, body):
        self.downloads.clear()
        return {'jobs': self.downloads.list()}

    def cancel_download(self, query, body):
        if not self.downloads.cancel(parse_int(body.get('id'), 'id')):
            raise ApiError("Questo download non è più in corso")

        return {'jobs': self.downloads.list()}

    def upload_download(self, query, body):
        if not self.downloads.retry_upload(parse_int(body.get('id'), 'id')):
            raise ApiError("Questo file non può essere caricato di nuovo")

        return {'jobs': self.downloads.list()}

    def nas_config(self, query, body):
        return self.nas_status(nas.load_config())

    def save_nas(self, query, body):
        before = nas.load_config()
        config = nas.save_config(read_nas(body))
        status = self.nas_status(config)

        # A nas just turned on, or with other folders, has past downloads never imported (the first start could be without nas)
        where = lambda config: [config[key] for key in ('host', 'port', 'film_path', 'tv_path', 'anime_path')]
        if nas.is_enabled(config) and not (nas.is_enabled(before) and where(before) == where(config)):
            history.reset_imported()

        if body.get('password') and not nas.save_password(config, str(body['password'])):
            status['password_error'] = f"Password non salvata: non riesco a scriverla, impostala con la variabile {nas.PASSWORD_ENV}"

        return status

    def test_nas(self, query, body):
        config = read_nas(body)

        try:
            return {'ok': True, **nas.test_connection(config, str(body.get('password') or '') or None)}
        except nas.NasError as e:
            return {'ok': False, 'error': str(e)}

    def nas_status(self, config):
        return {**config, 'password_saved': bool(nas.get_password(config))}

    # [ torrents ]
    def torrent_status(self, query, body):
        return self.torrents.status()

    def torrent_search(self, query, body):
        text = query.get('q', '').strip()

        if not text:
            raise ApiError("Scrivi cosa cercare")

        category = query.get('cat') if query.get('cat') in jackett.CATEGORIES else 'all'
        return self.torrents.search(text, category)

    def torrent_list(self, query, body):
        return {'items': self.torrents.list(), 'status': self.torrents.status()}

    def torrent_item(self, query, body):
        """A scheda tecnica being made, asked often by the page while it waits"""

        item = self.torrents.touch(parse_int(query.get('id'), 'id'))
        if item is None:
            raise ApiError("Questo torrent non c'è più", 404)

        return self.torrents.view(item)

    def torrent_inspect(self, query, body):
        return self.torrents.inspect(str(body.get('result') or ''), body.get('media'))

    def torrent_download(self, query, body):
        return {**self.torrents.download(body), 'items': self.torrents.list()}

    def torrent_discard(self, query, body):
        self.torrents.discard(parse_int(body.get('id'), 'id'))
        return {'items': self.torrents.list()}

    def torrent_pause(self, query, body):
        self.torrents.set_paused(parse_int(body.get('id'), 'id'), bool(body.get('paused')))
        return {'items': self.torrents.list()}

    def torrent_upload(self, query, body):
        self.torrents.retry_upload(parse_int(body.get('id'), 'id'))
        return {'items': self.torrents.list()}

    def torrent_open(self, query, body):
        path = self.torrents.get_folder(parse_int(body.get('id'), 'id'))

        if not path or not os.path.exists(path):
            raise ApiError("I file di questo torrent non si trovano su questo PC", 404)

        open_in_explorer(path)
        return {'ok': True}

    def torrent_config(self, query, body):
        config = torrent_config.load_config()
        return {**self.torrent_settings(config), **self.plugin_settings(config)}

    def plugin_settings(self, config):
        """Search plugins of qbittorrent found on this pc"""

        try:
            folder, engines = plugins.get_engines(config)
            return {'plugins_folder': folder, 'plugins_found': [engine['name'] for engine in engines.values()], 'plugins_error': None}
        except AppError as e:
            return {'plugins_folder': None, 'plugins_found': [], 'plugins_error': str(e)}

    def save_torrent_config(self, query, body):
        config = torrent_config.save_config(read_torrent_config(body, torrent_config.load_config()))
        saved = not body.get('qbit_password') or torrent_config.save_password(config, str(body['qbit_password']))
        settings = self.torrent_settings(config)

        if not saved:
            settings['password_error'] = "Password non salvata: non riesco a scriverla"

        self.torrents.reset_client()
        plugins.forget()
        return {**settings, **self.plugin_settings(config)}

    def test_torrent_config(self, query, body):
        config = read_torrent_config(body, torrent_config.load_config())
        result = {'plugins': 0}

        if config['plugins'] != 'off':
            try:
                result['plugins'] = len(plugins.get_engines(config)[1])
            except AppError:
                pass

        try:
            result['jackett'] = {'ok': True, 'indexers': jackett.count_indexers(config)}
        except AppError as e:
            result['jackett'] = {'ok': False, 'error': str(e)}

        if not config['qbit_url']:
            result['qbit'] = {'ok': True, 'mode': 'app'}
            return result

        try:
            client = qbittorrent.Client(config, str(body.get('qbit_password') or '') or None)
            result['qbit'] = {'ok': True, 'version': client.version(), 'save_path': client.preferences().get('save_path')}
        except AppError as e:
            result['qbit'] = {'ok': False, 'error': str(e)}

        return result

    def torrent_settings(self, config):
        return {
            **{key: value for key, value in config.items() if key != 'jackett_key'},
            'jackett_key_saved': bool(config['jackett_key']),
            'jackett_key_auto': bool(torrent_config.find_plugin_key()),
            'password_saved': bool(torrent_config.get_password(config)),
            'docker': os.path.exists('/.dockerenv'),
        }

    def open_folder(self, query, body):
        output = self.downloads.get_output(parse_int(body['id'], 'id')) if body.get('id') is not None else None
        folder = videos.get_folder()
        os.makedirs(folder, exist_ok=True)
        open_in_explorer(output if output and os.path.isfile(output) else folder)
        return {'ok': True}

    # [ folder of the videos ]
    def videos_status(self):
        return {
            'path': videos.load_path(),
            'folder': os.path.abspath(videos.get_folder()),
            'default': os.path.abspath(videos.DEFAULT_FOLDER),
            'docker': videos.IN_DOCKER,
        }

    def videos_config(self, query, body):
        return self.videos_status()

    def save_videos(self, query, body):
        try:
            videos.save_path(body.get('path'))
        except OSError as e:
            raise ApiError(f"Non riesco a scrivere in questa cartella: {e.strerror or e}")

        return self.videos_status()


ROUTES = {
    ('GET', '/api/status'): App.status,
    ('GET', '/api/remote'): App.get_remote,
    ('POST', '/api/domain'): App.set_domain,
    ('GET', '/api/home'): App.home,
    ('GET', '/api/recommendations'): App.recommendations,
    ('GET', '/api/search'): App.search,
    ('GET', '/api/title'): App.title,
    ('GET', '/api/season'): App.season,
    ('GET', '/api/anime/home'): App.anime_home,
    ('GET', '/api/anime/search'): App.anime_search,
    ('GET', '/api/anime/title'): App.anime_title,
    ('GET', '/api/anime/episodes'): App.anime_episodes,
    ('GET', '/api/anime/recommendations'): App.anime_recommendations,
    ('GET', '/api/stream'): App.stream,
    ('GET', '/api/progress'): App.watch,
    ('POST', '/api/progress'): App.save_watch,
    ('POST', '/api/progress/dismiss'): App.dismiss_watch,
    ('GET', '/api/downloads'): App.list_downloads,
    ('POST', '/api/downloads'): App.add_downloads,
    ('POST', '/api/downloads/remove'): App.remove_download,
    ('POST', '/api/downloads/clear'): App.clear_downloads,
    ('POST', '/api/downloads/upload'): App.upload_download,
    ('POST', '/api/downloads/cancel'): App.cancel_download,
    ('GET', '/api/nas'): App.nas_config,
    ('POST', '/api/nas'): App.save_nas,
    ('POST', '/api/nas/test'): App.test_nas,
    ('GET', '/api/torrents/status'): App.torrent_status,
    ('GET', '/api/torrents/search'): App.torrent_search,
    ('GET', '/api/torrents'): App.torrent_list,
    ('GET', '/api/torrents/item'): App.torrent_item,
    ('POST', '/api/torrents/inspect'): App.torrent_inspect,
    ('POST', '/api/torrents/download'): App.torrent_download,
    ('POST', '/api/torrents/discard'): App.torrent_discard,
    ('POST', '/api/torrents/pause'): App.torrent_pause,
    ('POST', '/api/torrents/upload'): App.torrent_upload,
    ('POST', '/api/torrents/open'): App.torrent_open,
    ('GET', '/api/torrents/config'): App.torrent_config,
    ('POST', '/api/torrents/config'): App.save_torrent_config,
    ('POST', '/api/torrents/config/test'): App.test_torrent_config,
    ('POST', '/api/open'): App.open_folder,
    ('GET', '/api/videos'): App.videos_config,
    ('POST', '/api/videos'): App.save_videos,
    ('POST', '/api/close'): App.close,
}


# [ server ]
class Handler(BaseHTTPRequestHandler):

    def log_message(self, format, *args):
        pass    # Console is used by download logs

    def do_GET(self):
        self.handle_request('GET')

    def do_POST(self):
        self.handle_request('POST')

    def handle_request(self, method):
        url = urlparse(self.path)
        is_remote = getattr(self.server, 'remote', False)

        if is_remote:
            if not self.check_remote(method, url):
                return

        # Accept only requests addressed to this server (dns rebinding)
        elif self.headers.get('Host') not in (f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"):
            return self.send_json({'error': "Host non valido"}, 403)

        if method == 'GET' and not url.path.startswith('/api/'):
            return self.send_static(url.path)

        # The video watched in the app, the player asks its playlists and then the segments one by one
        if method == 'GET' and url.path.startswith('/api/stream/'):
            return self.send_stream(url.path)

        route = ROUTES.get((method, url.path))
        if route is None:
            return self.send_json({'error': "Risorsa non trovata"}, 404)

        # Used to know if the window is still open
        if url.path != '/api/close':
            self.server.app.last_request = time.time()

        try:
            body = self.read_json() if method == 'POST' else {}
            query = {key: values[0] for key, values in parse_qs(url.query).items()}
            result = route(self.server.app, query, body)

            # The page on the phone hides what works only on the pc
            if url.path == '/api/status':
                result = {**result, 'remote_client': is_remote}

            self.send_json(result)

        except ApiError as e:
            self.send_json({'error': str(e)}, e.status)

        except AppError as e:
            self.send_json({'error': describe(e)}, 502)

        # Download functions of the cli call sys.exit when something goes wrong
        except (Exception, SystemExit) as e:
            console.log(f"[red]GUI error on {url.path}: {e!r}")
            log_error(f"GUI error on {url.path}", e if isinstance(e, Exception) else None)

            # Which site did not answer and why, never a generic message
            message = describe(e) if isinstance(e, Exception) else "Il sito non ha risposto come previsto, riprova tra poco"
            self.send_json({'error': message}, 502)

    def check_remote(self, method, url):
        """Requests from the other devices: any device of the home network, never from internet"""

        if not remote.is_home_network(self.client_address[0]):
            self.send_json({'error': "Accesso consentito solo dalla rete di casa"}, 403)
            return False

        if (method, url.path) in remote.LOCAL_ONLY:
            self.send_json({'ok': True})
            return False

        return True

    def read_json(self):

        # Json content type needs a cors preflight, so other web pages cant post here
        if self.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
            raise ApiError("Content-Type non valido", 415)

        try:
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)) or b'{}')
        except ValueError:
            raise ApiError("JSON non valido")

        if not isinstance(body, dict):
            raise ApiError("JSON non valido")

        return body

    def send_static(self, path):
        file_path = os.path.normpath(os.path.join(WEB_FOLDER, path.lstrip('/') or 'index.html'))
        extension = os.path.splitext(file_path)[1]

        if not file_path.startswith(WEB_FOLDER + os.sep) or extension not in CONTENT_TYPES or not os.path.isfile(file_path):
            return self.send_json({'error': "Risorsa non trovata"}, 404)

        with open(file_path, 'rb') as file:
            self.send_body(file.read(), CONTENT_TYPES[extension])

    def send_stream(self, path):
        match = re.fullmatch(r'/api/stream/([0-9a-f]{16})/(?:(master|video|audio)\.m3u8|(video|audio)/(\d+)\.ts|subtitles/(\d+)\.vtt)', path)
        stream = self.server.app.streams.get(match.group(1)) if match else None

        if stream is None:
            return self.send_json({'error': "Video non trovato, riaprilo"}, 404)

        if match.group(5):
            try:
                text = stream.subtitle(int(match.group(5)))
            except (AppError, requests.RequestException) as e:
                return self.send_json({'error': describe(e)}, 502)

            if text is None:
                return self.send_json({'error': "Sottotitoli non trovati"}, 404)
            return self.send_body(text.encode('utf-8'), 'text/vtt; charset=utf-8')

        if match.group(2):
            text = stream.master() if match.group(2) == 'master' else stream.playlist(match.group(2))
            if text is None:
                return self.send_json({'error': "Traccia non trovata"}, 404)
            return self.send_body(text.encode('utf-8'), 'application/vnd.apple.mpegurl')

        # The player asks again by itself the segments that fail
        try:
            data = stream.segment(match.group(3), int(match.group(4)))
        except ConnectionError as e:
            return self.send_json({'error': str(e)}, 502)

        if data is None:
            return self.send_json({'error': "Segmento non trovato"}, 404)

        self.send_body(data, 'video/mp2t')

    def send_json(self, data, status=200):
        self.send_body(json.dumps(data).encode('utf-8'), 'application/json; charset=utf-8', status)

    def send_body(self, body, content_type, status=200):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)

class Server(ThreadingHTTPServer):
    daemon_threads = True

    # On windows reuse address let two servers bind the same port
    allow_reuse_address = sys.platform != 'win32'

    def handle_error(self, request, client_address):

        # Browser closing a connection is not an error
        if not isinstance(sys.exc_info()[1], ConnectionError):
            super().handle_error(request, client_address)

def open_window(url):
    """Open the gui in a browser window without address bar if possible"""

    browsers = [
        os.path.join(os.environ.get('ProgramFiles(x86)', ''), 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
        os.path.join(os.environ.get('ProgramFiles', ''), 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
        os.path.join(os.environ.get('ProgramFiles', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
        os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Google', 'Chrome', 'Application', 'chrome.exe'),
    ]

    for browser in browsers:
        if os.path.isfile(browser):
            subprocess.Popen([browser, f"--app={url}", "--window-size=1360,880"])
            return

    webbrowser.open(url)

def clean_temp():
    """
    Half built files are removed at the start. Segments stay, they are the downloads to resume,
    only the ones not touched for days (downloads removed from the list) are deleted.
    """

    # The preview folder is left by the old versions
    for folder in (os.path.join("tmp", "output"), os.path.join("tmp", "preview")):
        remove_folder(folder)

    segments = os.path.join("tmp", "segments")
    if not os.path.isdir(segments):
        return

    limit = time.time() - SEGMENTS_MAX_AGE
    for entry in os.scandir(segments):
        try:
            if entry.is_dir() and entry.stat().st_mtime < limit:
                shutil.rmtree(entry.path, ignore_errors=True)
        except OSError:
            pass

def main():
    parser = argparse.ArgumentParser(description="Graphic interface of StreamingCommunity downloader")
    parser.add_argument('--port', type=int, default=DEFAULT_PORT, help="port of the local server")
    parser.add_argument('--no-window', action='store_true', help="dont open the app window")
    args = parser.parse_args()

    # Two programs open would download the same things together: the second one only shows the first
    if not instance.acquire():
        url = instance.get_running_url()
        console.print(f"[yellow]SC Downloader is already open{f' => {url}' if url else ''}")

        if url and not args.no_window:
            open_window(url)
        return

    clean_temp()

    try:
        server = Server(('127.0.0.1', args.port), Handler)
    except OSError:
        server = Server(('127.0.0.1', 0), Handler)

    server.app = App()
    server.app.server = server
    url = f"http://127.0.0.1:{server.server_port}"
    instance.save_url(url)

    # Every device of the home network can open the app
    try:
        server.app.start_remote()
    except Exception as e:
        log_error("Access from the home network not started", e)
    console.print(f"[green]GUI ready [white]=> [cyan]{url} [white](close the window to quit)")

    if not args.no_window:
        open_window(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        console.print("[red]GUI closed")
    finally:
        server.server_close()
        server.app.stop_remote()
        server.app.downloads.stop()
        server.app.torrents.stop()
