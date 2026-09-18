# 18.09.26

# Class import
from Src.Util.headers import get_headers
from Src.Lib.FFmpeg.my_m3u8 import run_ffmpeg

# General import
import os, shutil, time, hashlib
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urljoin
import requests, ffmpeg
from m3u8 import M3U8
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# Variable
PREVIEW_FOLDER = os.path.join("tmp", "preview")
PREVIEW_SECONDS = 120       # Length of the preview
PREVIEW_POSITION = 0.5      # Where it starts, half of the video
WORKERS = 8
MAX_PREVIEWS = 3            # Older previews are removed


# [ segments ]
def load_playlist(session, url):
    response = session.get(url, timeout=20)
    response.raise_for_status()
    return M3U8(response.text, base_uri=url)

def get_times(playlist):
    """Start time of every segment inside the video"""

    times, position = [], 0.0
    for segment in playlist.segments:
        times.append(position)
        position += segment.duration or 0

    return times, position

def select(playlist, start, end):
    """Indexes of the segments that cover the time from start to end"""

    times, _ = get_times(playlist)
    return [index for index, segment in enumerate(playlist.segments) if times[index] + (segment.duration or 0) > start and times[index] < end]

def get_iv(playlist, index):
    """Iv of the segment, when the playlist has none it is the number of the segment"""

    key = playlist.segments[index].key
    if key is not None and key.iv:
        return bytes.fromhex(key.iv.replace("0x", "").replace("0X", "").zfill(32))

    return ((playlist.media_sequence or 0) + index).to_bytes(16, 'big')

def download_part(session, playlist, indexes, key, output):
    """Download some segments in parallel and write them in order in one ts file"""

    def fetch(index):
        segment = playlist.segments[index]
        url = urljoin(playlist.base_uri, segment.uri)

        for attempt in range(4):
            try:
                response = session.get(url, timeout=20)
                if response.status_code == 200:
                    data = response.content
                    break
            except requests.RequestException:
                pass
            time.sleep(1 + attempt)
        else:
            raise ConnectionError("Segmento dell'anteprima non disponibile")

        if key is not None and segment.key is not None and segment.key.method == 'AES-128':
            decryptor = Cipher(algorithms.AES(key), modes.CBC(get_iv(playlist, index))).decryptor()
            data = decryptor.update(data) + decryptor.finalize()

        return data

    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        parts = list(pool.map(fetch, indexes))

    with open(output, 'wb') as file:
        for part in parts:
            file.write(part)


# [ preview ]
def clean_old():
    """Keep only the last previews, a preview is useful only while it is watched"""

    if not os.path.isdir(PREVIEW_FOLDER):
        return

    files = sorted((entry for entry in os.scandir(PREVIEW_FOLDER) if entry.is_file()), key=lambda entry: entry.stat().st_mtime, reverse=True)
    for entry in files[MAX_PREVIEWS:]:
        try:
            os.remove(entry.path)
        except OSError:
            pass

def get_path(name):
    """Path of a preview from its name, only names made here are accepted"""

    if not (len(name) == 16 and all(char in '0123456789abcdef' for char in name)):
        return None

    path = os.path.join(PREVIEW_FOLDER, f"{name}.mp4")
    return path if os.path.isfile(path) else None

def make_preview(video_url, audio_url, key, cache_id):
    """
    A few minutes from the middle of the video, with the same quality of the download.
    Returns name, start and length of the preview.
    """

    name = hashlib.md5(str(cache_id).encode()).hexdigest()[:16]
    output = os.path.join(PREVIEW_FOLDER, f"{name}.mp4")
    work = os.path.join(PREVIEW_FOLDER, f"{name}_work")
    os.makedirs(work, exist_ok=True)

    session = requests.Session()
    session.headers['user-agent'] = get_headers()
    key = bytes.fromhex(key) if key else None

    try:
        video = load_playlist(session, video_url)
        _, total = get_times(video)
        start = max(0.0, total * PREVIEW_POSITION - PREVIEW_SECONDS / 2)
        indexes = select(video, start, start + PREVIEW_SECONDS)

        # The audio covers the same time of the video segments
        times, _ = get_times(video)
        video_start = times[indexes[0]]
        video_end = times[indexes[-1]] + (video.segments[indexes[-1]].duration or 0)

        video_file = os.path.join(work, "video.ts")
        audio_file = os.path.join(work, "audio.ts")

        def download_audio():
            audio = load_playlist(session, audio_url)
            download_part(session, audio, select(audio, video_start, video_end), key, audio_file)

        # Video and audio together, the preview is ready in half the time
        with ThreadPoolExecutor(max_workers=2) as pool:
            parts = [pool.submit(download_part, session, video, indexes, key, video_file)]
            if audio_url:
                parts.append(pool.submit(download_audio))

            for part in parts:
                part.result()

        if audio_url:
            stream = [ffmpeg.input(video_file, copyts=None).video, ffmpeg.input(audio_file, copyts=None).audio]
        else:
            stream = [ffmpeg.input(video_file, copyts=None)]

        # Video and audio keep the times of the film, so they stay together, then everything starts from zero
        temp = os.path.join(work, "preview.mp4")
        run_ffmpeg(ffmpeg.output(*stream, temp, c='copy', avoid_negative_ts='make_zero', movflags='+faststart', loglevel='error').overwrite_output())
        os.replace(temp, output)

    finally:
        shutil.rmtree(work, ignore_errors=True)
        session.close()

    clean_old()
    return {'name': name, 'start': round(video_start), 'length': round(video_end - video_start), 'total': round(total)}
