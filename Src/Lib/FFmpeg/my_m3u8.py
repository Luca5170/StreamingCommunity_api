# 5.01.24 -> 7.01.24 -> 17.02.24

# Class import
from Src.Util.console import console
from Src.Util.headers import get_headers
from Src.Util.cancel import DownloadCancelled
from Src.Util.errors import DownloadError, DiskFullError, is_disk_full, is_network_error, is_online, wait_online
from Src.Util import http, storage
from Src.Lib.FFmpeg.util import print_duration_table

# Import
from m3u8 import M3U8 as M3U8_Lib
from tqdm.rich import tqdm
import requests, os, ffmpeg, sys, warnings, shutil, time, threading, random, hashlib, subprocess
from collections import Counter
from urllib.parse import urlparse, parse_qsl, urlencode
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

# Disable warning
from tqdm import TqdmExperimentalWarning
warnings.filterwarnings("ignore", category=TqdmExperimentalWarning)
warnings.filterwarnings("ignore", category=UserWarning, module="cryptography")

# Variable
MAX_WORKER = 12         # Cdn of the site answer 503 when it gets too many segments together
MIN_WORKER = 2
RETRY_WORKER = 2        # Used for the segments that failed the first time
BUSY_CODES = (429, 500, 502, 503, 504)
MIN_FREE_SPACE = 2 * 1024 ** 3          # Needed to start a download
MIN_FREE_SPACE_JOIN = 200 * 1024 ** 2   # Below this a failed join is a full disk
DONWLOAD_SUB = True
DOWNLOAD_DEFAULT_LANGUAGE = False


# [ main class ]
class Decryption():
    def __init__(self, key):
        self.iv = None
        self.key = key

    def parse_key(self, raw_iv):
        self.iv = bytes.fromhex(raw_iv.replace("0x", ""))

    def decrypt_ts(self, encrypted_data):
        cipher = Cipher(algorithms.AES(self.key), modes.CBC(self.iv), backend=default_backend())
        decryptor = cipher.decryptor()
        decrypted_data = decryptor.update(encrypted_data) + decryptor.finalize()

        return decrypted_data

class M3U8_Parser:
    def __init__(self):
        self.segments = []
        self.video_playlist = []
        self.keys = []
        self.subtitle_playlist = []     # No vvt ma url a vvt
        self.subtitle = []              # Url a vvt
        self.audio_ts = []

    def parse_data(self, m3u8_content):
        """Extract all info present in m3u8 content"""

        try:
            m3u8_obj = M3U8_Lib(m3u8_content)

            for playlist in m3u8_obj.playlists:
                self.video_playlist.append({"uri": playlist.uri})
                self.stream_infos = ({
                    "bandwidth": playlist.stream_info.bandwidth,
                    "codecs": playlist.stream_info.codecs,
                    "resolution": playlist.stream_info.resolution
                })

            for key in m3u8_obj.keys:
                if key != None:
                    self.keys = ({
                        "method": key.method,
                        "uri": key.uri,
                        "iv": key.iv
                    })

            for media in m3u8_obj.media:
                if media.type == "SUBTITLES":
                    self.subtitle_playlist.append({
                        "type": media.type,
                        "name": media.name,
                        "default": media.default,
                        "language": media.language,
                        "uri": media.uri
                    })
                else:
                    self.audio_ts.append({
                        "type": media.type,
                        "name": media.name,
                        "default": media.default,
                        "language": media.language,
                        "uri": media.uri
                    })


            for segment in m3u8_obj.segments:
                if "vtt" not in segment.uri:
                    self.segments.append(segment.uri)
                else:
                    self.subtitle.append(segment.uri)

        except Exception as e:
            print(f"Error parsing M3U8 content: {e}")

    def get_best_quality(self):
        """Need to fix, return m3u8 valid with best quality"""

        # To fix
        if self.video_playlist:
            return self.video_playlist[0].get('uri')
        else:
            print("No video playlist find")
            return None
        
    def download_subtitle(self):
        """Download all subtitle if present"""

        path = os.path.join("videos", "subtitle")

        if self.subtitle_playlist:
            for sub_info in self.subtitle_playlist:
                name_language = sub_info.get("language")

                if name_language in ["auto", "ita"]:
                    continue

                os.makedirs(path, exist_ok=True)
                console.log(f"[green]Download subtitle: [red]{name_language}")
                req_sub_content = http.get(sub_info.get("uri"))

                sub_parse = M3U8_Parser()
                sub_parse.parse_data(req_sub_content.text)
                url_subititle = sub_parse.subtitle[0]

                open(os.path.join(path, name_language + ".vtt"), "wb").write(http.get(url_subititle).content)

        else:
            console.log("[red]No subtitle find")

    def get_track_audio(self, language_name):   # Ex. English
        """Return url of audio eng audio playlist if present"""

        if self.audio_ts:
            console.log(f"[cyan]Find {len(self.audio_ts)}, playlist with audio")

            if language_name != None:
                for obj_audio in self.audio_ts:
                    if obj_audio.get("name") == language_name:
                        return obj_audio.get("uri")

            return None
        
        else:
            console.log("[red]Cant find playlist with audio")
                
class Throttle:
    """
    Limit how many segments are asked at the same time.
    The cdn answers 503 when they are too many, so the limit goes down alone and comes back up slowly.
    """

    def __init__(self, limit=MAX_WORKER):
        self.condition = threading.Condition()
        self.limit = limit
        self.active = 0
        self.good = 0

    def __enter__(self):
        with self.condition:
            while self.active >= self.limit:
                self.condition.wait(0.5)

            self.active += 1

    def __exit__(self, *error):
        with self.condition:
            self.active -= 1
            self.condition.notify()

    def slow_down(self):
        with self.condition:
            self.limit = max(MIN_WORKER, self.limit // 2)
            self.good = 0

    def speed_up(self):
        with self.condition:
            self.good += 1

            if self.good >= 25 and self.limit < MAX_WORKER:
                self.limit += 1
                self.good = 0
                self.condition.notify()

class M3U8_Segments:
    def __init__(self, url, key=None, progress_callback=None, cache_name=None, offline_callback=None):
        self.url = url
        self.key = key
        self.progress_callback = progress_callback
        self.offline_callback = offline_callback
        if key != None:
            self.decription = Decryption(key)

        # Every download has its own folder. The name does not change when the download is started again,
        # so after a power cut or a lost connection the segments already saved are used again
        self.name = cache_name or hashlib.md5(url.encode()).hexdigest()[:10]
        self.temp_folder = os.path.join("tmp", "segments", self.name)
        os.makedirs(self.temp_folder, exist_ok=True)

        self.progress_timeout = 60
        self.max_retry = 5
        self.failed_segments = []
        self.failure_reasons = []
        self.throttle = Throttle()

        # Set when the download is cancelled, every worker stops at its next step
        self.stopped = threading.Event()
        self.fatal = None
        self.offline_lock = threading.Lock()
        self.offline_waiters = 0

        # One user agent and one pool of connections for the whole download
        self.user_agent = get_headers()
        self.session = requests.Session()
        self.session.mount('https://', requests.adapters.HTTPAdapter(pool_connections=MAX_WORKER, pool_maxsize=MAX_WORKER))

    def parse_data(self, m3u8_content):

        # Parse index m3u8
        m3u8_parser = M3U8_Parser()
        m3u8_parser.parse_data(m3u8_content)

        # Add decryption iv if present
        if self.key != None and m3u8_parser.keys:
            self.decription.parse_key(m3u8_parser.keys.get("iv"))

        # Add all segments
        self.segments = m3u8_parser.segments

    def get_info(self, check=None):
        """Make req to index m3u8"""

        response = http.get(self.url, session=self.session, headers={'user-agent': self.user_agent}, wait=True, check=check)

        if not response.ok:
            raise DownloadError(f"Il server del video ha risposto con errore {response.status_code}")

        self.parse_data(response.text)

        if not self.segments:
            raise DownloadError("Il video non ha segmenti da scaricare")

        self.check_cache()

    def get_identity(self):
        """The playlist without its token, the same video gives the same identity also with a new token"""

        url = urlparse(self.url)
        query = [(name, value) for name, value in parse_qsl(url.query) if name not in ('token', 'expires', 'edge', 'h')]
        return f"{url.netloc}{url.path}?{urlencode(sorted(query))}|{len(self.segments)}"

    def check_cache(self):
        """Segments saved before are kept only if they are of this same video and quality"""

        meta_path = os.path.join(self.temp_folder, "meta.json")
        identity = self.get_identity()
        saved = storage.read_json(meta_path, {})

        if not isinstance(saved, dict) or saved.get('identity') != identity:
            shutil.rmtree(self.temp_folder, ignore_errors=True)
            os.makedirs(self.temp_folder, exist_ok=True)
            storage.write_json(meta_path, {'identity': identity})

        else:
            ready = sum(1 for index in range(len(self.segments)) if os.path.exists(os.path.join(self.temp_folder, f"{index}.ts")))
            if ready:
                console.log(f"[green]Resume: {ready} of {len(self.segments)} segments already saved")

    def check(self, progress_counter):
        """Send the progress, raise DownloadCancelled if the download has been stopped"""

        if self.stopped.is_set():
            raise self.fatal or DownloadCancelled()

        # The callback of the gui raises DownloadCancelled when the user cancels
        if self.progress_callback != None:
            self.progress_callback(progress_counter.n, len(self.segments))

    def wait(self, seconds, check):
        """Sleep before a new attempt, but stop at once if the download is cancelled"""

        end = time.time() + seconds

        while time.time() < end:
            check()
            time.sleep(max(0, min(0.5, end - time.time())))

    def wait_online(self, check):
        """Internet is missing: the download stops here until it comes back, nothing is lost"""

        if is_online():
            return

        # Many workers wait together, the gui and the console hear it once
        with self.offline_lock:
            self.offline_waiters += 1
            if self.offline_waiters == 1:
                console.log("[yellow]Connection lost, waiting for it to come back")
                if self.offline_callback != None:
                    self.offline_callback(True)

        try:
            if not wait_online(check):
                raise DownloadError("Connessione a internet assente da troppo tempo, il download riprenderà più tardi")
        finally:
            with self.offline_lock:
                self.offline_waiters -= 1
                if self.offline_waiters == 0:
                    console.log("[green]Connection is back, the download goes on")
                    if self.offline_callback != None:
                        self.offline_callback(False)

    def get_req_ts(self, ts_url, check):
        """Single req to a ts file to get content, retry when the server is busy"""

        reason = None
        attempt = 0

        while attempt <= self.max_retry:
            check()

            try:
                with self.throttle:
                    response = self.session.get(ts_url, headers={'user-agent': self.user_agent}, timeout=20)

                if response.status_code == 200:
                    content = response.content
                    expected = response.headers.get('content-length')

                    # A connection closed in the middle gives a shorter segment
                    if expected and expected.isdigit() and len(content) != int(expected):
                        raise requests.ConnectionError("segmento incompleto")

                    self.throttle.speed_up()
                    return content

                reason = f"HTTP {response.status_code}"

                # Too many segments asked together, everyone slows down
                if response.status_code in BUSY_CODES:
                    self.throttle.slow_down()

                # Expired link: trying again does not help, the download is started again with a new link
                elif response.status_code in (401, 403, 404, 410) and attempt >= 1:
                    break

            except requests.RequestException as e:
                reason = type(e).__name__

                # Without internet the attempts are not wasted, the download waits for the connection
                if is_network_error(e) and not is_online():
                    self.wait_online(check)
                    continue

            attempt += 1
            if attempt <= self.max_retry:
                self.wait(min(2 ** attempt, 20) + random.random(), check)

        self.failure_reasons.append(reason)
        return None

    def save_ts(self, index, progress_counter):
        """Save ts file and decrypt if there is iv present in decryption class"""

        check = lambda: self.check(progress_counter)
        check()

        ts_filename = os.path.join(self.temp_folder, f"{index}.ts")

        if not os.path.exists(ts_filename):
            try:
                ts_content = self.get_req_ts(self.segments[index], check)

                # A segment that is not saved is not progress, it is asked again later
                if ts_content is None:
                    self.failed_segments.append(index)
                    return

                if self.key and self.decription.iv:
                    ts_content = self.decription.decrypt_ts(ts_content)

                # The segment gets its name only when it is complete, a power cut never leaves half a segment
                temp_filename = f"{ts_filename}.part"
                with open(temp_filename, "wb") as ts_file:
                    ts_file.write(ts_content)
                os.replace(temp_filename, ts_filename)

            except (DownloadCancelled, DownloadError, KeyboardInterrupt):
                raise

            except OSError as e:
                if is_disk_full(e):
                    raise DiskFullError(self.temp_folder)

                self.failed_segments.append(index)
                self.failure_reasons.append(type(e).__name__)
                return

            except Exception as e:
                # Any other problem (a segment that cant be decrypted...) is a missing segment, never a hole in the video
                self.failed_segments.append(index)
                self.failure_reasons.append(type(e).__name__)
                return

        progress_counter.update(1)
        check()

    def download_ts(self):
        """Download every segment, the ones refused by the server are asked again slowly"""

        progress_counter = tqdm(total=len(self.segments), unit="bytes", desc="[yellow]Download")

        try:
            self.download_pass(range(len(self.segments)), MAX_WORKER, progress_counter)

            if self.failed_segments:
                missing = sorted(set(self.failed_segments))
                self.failed_segments = []
                console.log(f"[yellow]Retry of {len(missing)} segments with {RETRY_WORKER} connections")

                self.throttle = Throttle(RETRY_WORKER)
                self.download_pass(missing, RETRY_WORKER, progress_counter)

        except DownloadCancelled as e:
            # Nothing of a cancelled download is kept, unless the program is only closing
            if not e.keep_files:
                self.clean()
            raise

        except KeyboardInterrupt:
            self.clean()
            raise

        finally:
            progress_counter.close()

        # The segments saved stay in tmp: the next attempt downloads only the missing ones
        if self.failed_segments:
            missing = len(set(self.failed_segments))
            raise DownloadError(f"{missing} segmenti su {len(self.segments)} non scaricati ({self.get_failures()}), il download riprenderà da qui")

    def download_pass(self, indexes, workers, progress_counter):
        """Download a group of segments and wait for all of them"""

        quit_event = threading.Event()
        timer_thread = threading.Thread(target=self.timer, args=(progress_counter, quit_event), daemon=True)
        timer_thread.start()

        try:
            with ThreadPoolExecutor(max_workers=workers) as executor:
                pending = {executor.submit(self.save_ts, index, progress_counter) for index in indexes}

                try:
                    # Short waits, so a cancel or CTRL+C is seen at once
                    while pending:
                        done, pending = wait(pending, timeout=0.5, return_when=FIRST_COMPLETED)

                        for future in done:
                            error = future.exception()

                            if isinstance(error, (DownloadCancelled, DownloadError)):
                                raise error
                            if error != None:
                                console.log(f"[red]Segment error: {error!r}")

                except (DownloadCancelled, DownloadError, KeyboardInterrupt) as error:
                    # Segments not started are dropped, running ones stop at their next check
                    if isinstance(error, DownloadError):
                        self.fatal = error
                    self.stopped.set()
                    for future in pending:
                        future.cancel()
                    raise

        finally:
            quit_event.set()  # Signal the timer thread to quit
            timer_thread.join()  # Ensure the timer thread is terminated

    def clean(self):
        shutil.rmtree(self.temp_folder, ignore_errors=True)

    def get_failures(self):
        """Most common reasons of the segments that are still missing"""

        return ", ".join(f"{reason}: {count}" for reason, count in Counter(self.failure_reasons).most_common(3))

    def timer(self, progress_counter, quit_event):
        """Warn when no segment is saved for a while, the server could be busy"""

        last_count = progress_counter.n
        start_time = time.time()

        while not quit_event.wait(1):
            if progress_counter.n != last_count:
                last_count = progress_counter.n
                start_time = time.time()

            elif time.time() - start_time > self.progress_timeout:
                console.log(f"[yellow]No segment saved in the last {self.progress_timeout} seconds, the server is busy")
                start_time = time.time()

        progress_counter.refresh()  # Refresh the progress bar to reflect the last progress

    def join(self, output_filename, check=None):
        """Join all segments file to a mp4 file name"""

        # A video with a hole is worse than no video: every segment must be there
        missing = [index for index in range(len(self.segments)) if not os.path.exists(os.path.join(self.temp_folder, f"{index}.ts"))]
        if missing:
            raise DownloadError(f"{len(missing)} segmenti mancanti, il download riprenderà da qui")

        # Segments of this playlist in their order, the list stays in the same folder
        file_list_path = os.path.join(self.temp_folder, 'file_list.txt')

        with open(file_list_path, 'w') as f:
            for index in range(len(self.segments)):
                f.write(f"file '{index}.ts'\n")

        console.log("[cyan]Start join all file")
        try:
            run_ffmpeg(ffmpeg.input(file_list_path, format='concat', safe=0).output(output_filename, c='copy', loglevel='error').overwrite_output(), check)

        except DownloadCancelled as e:
            if not e.keep_files:
                self.clean()
            raise

        except KeyboardInterrupt:
            self.clean()
            raise

        except ffmpeg.Error:
            check_disk(os.path.dirname(output_filename) or ".")
            raise DownloadError("FFmpeg non è riuscito a unire i segmenti del video")

        console.log(f"[cyan]Clean ...")
        self.clean()

class M3U8_Downloader:
    def __init__(self, m3u8_url, m3u8_audio = None, key=None, output_filename="output.mp4", progress_callback=None):
        self.m3u8_url = m3u8_url
        self.m3u8_audio = m3u8_audio
        self.key = key
        self.video_path = output_filename
        self.progress_callback = progress_callback

        # The file is built in tmp and reaches its folder only when it is complete
        self.name = hashlib.md5(os.path.abspath(output_filename).encode()).hexdigest()[:10]
        self.work_folder = os.path.join("tmp", "output", self.name)
        self.temp_video = os.path.join(self.work_folder, "video.mp4")
        self.temp_audio = os.path.join(self.work_folder, "audio.mp4")
        self.temp_merged = os.path.join(self.work_folder, "merged.mp4")

    def update_progress(self, stage, done=0, total=0):
        """
        Notify progress of current stage (video, join_video, audio, join_audio, merge).
        The callback raises DownloadCancelled to stop the download.
        """

        if self.progress_callback != None:
            self.progress_callback(stage, done, total)

    def set_offline(self, offline):
        """The gui shows that the download waits for the connection"""

        # A cancel is seen by the next check of the workers, not here
        try:
            if self.progress_callback != None:
                self.progress_callback("offline" if offline else "online", 0, 0)
        except DownloadCancelled:
            pass

    def start(self):
        # Half files of a join stopped by a power cut
        shutil.rmtree(self.work_folder, ignore_errors=True)
        check_disk(".", MIN_FREE_SPACE)
        os.makedirs(self.work_folder, exist_ok=True)

        try:
            result = self.download()
            os.makedirs(os.path.dirname(os.path.abspath(self.video_path)), exist_ok=True)
            os.replace(result, self.video_path)

        except OSError as e:
            if is_disk_full(e):
                raise DiskFullError(self.work_folder)
            raise

        finally:
            # Segments stay in tmp/segments for the next attempt, the half built files never
            shutil.rmtree(self.work_folder, ignore_errors=True)

    def download(self):
        """Download video and audio, return the complete file inside the work folder"""

        video_m3u8 = M3U8_Segments(self.m3u8_url, self.key, lambda done, total: self.update_progress("video", done, total),
                                   cache_name=f"{self.name}_video", offline_callback=self.set_offline)
        console.log("[green]Download video ts")
        video_m3u8.get_info(lambda: self.update_progress("video"))
        video_m3u8.download_ts()
        self.update_progress("join_video")
        video_m3u8.join(self.temp_video, lambda: self.update_progress("join_video"))
        print_duration_table(self.temp_video)
        print("\n")

        if self.m3u8_audio == None:
            return self.temp_video

        audio_m3u8 = M3U8_Segments(self.m3u8_audio, self.key, lambda done, total: self.update_progress("audio", done, total),
                                   cache_name=f"{self.name}_audio", offline_callback=self.set_offline)
        console.log("[green]Download audio ts")
        audio_m3u8.get_info(lambda: self.update_progress("audio"))
        audio_m3u8.download_ts()
        self.update_progress("join_audio")
        audio_m3u8.join(self.temp_audio, lambda: self.update_progress("join_audio"))
        print_duration_table(self.temp_audio)
        print("\n")

        self.update_progress("merge")
        return self.join_audio()

    def join_audio(self):
        """Join audio with video and sync it, return the file to keep"""

        try:
            video_stream = ffmpeg.input(self.temp_video)
            audio_stream = ffmpeg.input(self.temp_audio)

            run_ffmpeg(
                ffmpeg.output(
                    video_stream.video,
                    audio_stream.audio,
                    self.temp_merged,
                    vcodec="copy",
                    acodec="copy",
                    shortest=None,
                    strict="experimental",
                    loglevel='error'
                ).overwrite_output(),
                lambda: self.update_progress("merge")
            )

        except ffmpeg.Error as e:
            check_disk(self.work_folder)

            # Audio is kept apart, next to the video
            audio_path = os.path.splitext(self.video_path)[0] + ".audio.mp4"
            os.makedirs(os.path.dirname(os.path.abspath(audio_path)), exist_ok=True)
            os.replace(self.temp_audio, audio_path)
            console.log(f"[red]Error merging audio, audio saved in {audio_path}: {e}")
            return self.temp_video

        console.print("[green]Merge completed successfully.")
        return self.temp_merged


# [ main function ]
def check_disk(path, needed=None):
    """Raise DiskFullError when the disk has less free space than needed"""

    try:
        free = shutil.disk_usage(os.path.abspath(path) if os.path.exists(path) else ".").free
    except OSError:
        return

    if free < (MIN_FREE_SPACE_JOIN if needed is None else needed):
        raise DiskFullError(path)

def run_ffmpeg(stream, check=None):
    """Run ffmpeg and wait for it, ffmpeg is stopped if the download is cancelled meanwhile"""

    try:
        process = subprocess.Popen(ffmpeg.compile(stream), stdin=subprocess.DEVNULL)
    except FileNotFoundError:
        raise DownloadError("FFmpeg non trovato: installalo e riavvia il programma", retry=False)

    try:
        while process.poll() is None:
            if check != None:
                check()
            time.sleep(0.3)

    except (DownloadCancelled, KeyboardInterrupt):
        process.kill()
        process.wait()
        raise

    if process.returncode != 0:
        raise ffmpeg.Error('ffmpeg', None, None)

def df_make_req(url):
    """Make req to get text"""

    response = http.get(url)

    if not response.ok:
        raise DownloadError(f"Il server del video ha risposto con errore {response.status_code}")

    return response.text

def download_subtitle(url, name_language):
    """Make req to vtt url and save to video subtitle folder"""

    path = os.path.join("videos", "subtitle")
    os.makedirs(path, exist_ok=True)

    console.log(f"[green]Download subtitle: [red]{name_language}")
    open(os.path.join(path, name_language + ".vtt"), "wb").write(http.get(url).content)

def download_m3u8(m3u8_playlist=None, m3u8_index = None, m3u8_audio=None, m3u8_subtitle=None, key=None,  output_filename=os.path.join("videos", "output.mp4"), log=False, progress_callback=None):

    # Get byte of key
    key = bytes.fromhex(key) if key is not None else key

    if m3u8_playlist != None:
        console.log(f"[green]Dowload m3u8 from playlist")

        # Parse m3u8 playlist
        parse_class_m3u8 = M3U8_Parser()

        # Parse directly m3u8 content pass if present
        if "#EXTM3U" not in m3u8_playlist: 
            parse_class_m3u8.parse_data(df_make_req(m3u8_playlist))
        else: 
            parse_class_m3u8.parse_data(m3u8_playlist)


        # Get italian language in present as defualt
        if DOWNLOAD_DEFAULT_LANGUAGE:
            m3u8_audio = parse_class_m3u8.get_track_audio("Italian")
            console.log(f"[green]Select language => [purple]{m3u8_audio}")


        # Get best quality
        if m3u8_index == None:
            m3u8_index = parse_class_m3u8.get_best_quality()
            if "https" in m3u8_index:
                if log: console.log(f"[green]Select m3u8 index => [purple]{m3u8_index}")
            else:
                raise DownloadError("Il player non ha un video valido")


        # Download subtitle if present ( normaly in m3u8 playlist )
        if DONWLOAD_SUB: 
            parse_class_m3u8.download_subtitle()

    if m3u8_subtitle != None:

        # Subtitles are an extra, the video is downloaded also when they fail
        try:
            parse_class_m3u8_sub = M3U8_Parser()

            # Parse directly m3u8 content pass if present
            if "#EXTM3U" not in m3u8_subtitle:
                parse_class_m3u8_sub.parse_data(df_make_req(m3u8_subtitle))
            else:
                parse_class_m3u8_sub.parse_data(m3u8_subtitle)

            # Download subtitle if present ( normaly in m3u8 playlist )
            if DONWLOAD_SUB:
                parse_class_m3u8_sub.download_subtitle()

        except Exception as e:
            console.log(f"[yellow]Subtitles not downloaded: {e}")


    # Download m3u8 index, with segments
    # os.makedirs("videos", exist_ok=True)
    path = output_filename.split("\\")
    os.makedirs("\\".join(path[:-1]), exist_ok=True)
    if log: console.log(f"[green]Dowload m3u8 from index [white]=> [purple]{m3u8_index}")
    M3U8_Downloader(m3u8_index, m3u8_audio, key=key, output_filename=output_filename, progress_callback=progress_callback).start()