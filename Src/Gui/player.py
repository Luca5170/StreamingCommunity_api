# 28.10.26

# Class import
from Src.Util.headers import get_headers

# General import
import collections, math, secrets, threading, time
from urllib.parse import urljoin
import requests
from m3u8 import M3U8
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# Variable
MAX_STREAMS = 4         # Older streams are forgotten, a stream is useful only while it is watched
ATTEMPTS = 4


# [ stream ]
class Stream:
    """
    A film or an episode watched in the app. Playlists and segments pass from here:
    the browser gets them already decrypted, without the key and the headers of the site.
    """

    def __init__(self, stream):
        self.id = secrets.token_hex(8)
        self.session = requests.Session()
        self.session.headers['user-agent'] = get_headers()
        self.key = bytes.fromhex(stream['key']) if stream['key'] else None
        self.resolution = stream['resolution']
        self.bandwidth = stream['bandwidth']
        self.codecs = stream['codecs']
        self.language = stream['language']

        self.tracks = {'video': self.load(stream['video'])}
        if stream['audio']:
            self.tracks['audio'] = self.load(stream['audio'])

        self.duration = sum(segment.duration or 0 for segment in self.tracks['video'].segments)

    def load(self, url):
        response = self.session.get(url, timeout=20)
        response.raise_for_status()

        # The library takes the folder of the playlist, it adds a slash to the address
        playlist = M3U8(response.text, base_uri=urljoin(url, '.'))

        if not playlist.segments:
            raise ConnectionError("La playlist del video è vuota")

        return playlist

    def close(self):
        self.session.close()

    # [ playlists ]
    def master(self):
        """One quality, the same of the download, with its audio when it is separated from the video"""

        info = [f"BANDWIDTH={self.bandwidth or 1000000}"]
        if self.resolution:
            info.append(f"RESOLUTION={self.resolution[0]}x{self.resolution[1]}")
        if self.codecs:
            info.append(f'CODECS="{self.codecs}"')

        lines = ['#EXTM3U']
        if 'audio' in self.tracks:
            language = self.language or 'und'
            lines.append(f'#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",NAME="{language}",LANGUAGE="{language}",DEFAULT=YES,AUTOSELECT=YES,URI="audio.m3u8"')
            info.append('AUDIO="audio"')

        lines += ['#EXT-X-STREAM-INF:' + ','.join(info), 'video.m3u8']
        return '\n'.join(lines) + '\n'

    def playlist(self, kind):
        """Playlist of the video or of the audio, its segments point here and have no key"""

        playlist = self.tracks.get(kind)
        if playlist is None:
            return None

        target = math.ceil(max(segment.duration or 0 for segment in playlist.segments))
        lines = ['#EXTM3U', '#EXT-X-VERSION:3', f"#EXT-X-TARGETDURATION:{target}", '#EXT-X-MEDIA-SEQUENCE:0', '#EXT-X-PLAYLIST-TYPE:VOD']

        for index, segment in enumerate(playlist.segments):
            if segment.discontinuity and index:
                lines.append('#EXT-X-DISCONTINUITY')
            lines += [f"#EXTINF:{segment.duration or 0},", f"{kind}/{index}.ts"]

        lines.append('#EXT-X-ENDLIST')
        return '\n'.join(lines) + '\n'

    # [ segments ]
    def segment(self, kind, index):
        playlist = self.tracks.get(kind)
        if playlist is None or not 0 <= index < len(playlist.segments):
            return None

        segment = playlist.segments[index]
        data = self.fetch(segment.absolute_uri)

        if self.key is not None and segment.key is not None and segment.key.method == 'AES-128':
            decryptor = Cipher(algorithms.AES(self.key), modes.CBC(get_iv(playlist, index))).decryptor()
            data = unpad(decryptor.update(data) + decryptor.finalize())

        return data

    def fetch(self, url):
        for attempt in range(ATTEMPTS):
            try:
                response = self.session.get(url, timeout=20)
                if response.status_code == 200:
                    return response.content
            except requests.RequestException:
                pass
            time.sleep(1 + attempt)

        raise ConnectionError("Segmento del video non disponibile")


def get_iv(playlist, index):
    """Iv of the segment, when the playlist has none it is the number of the segment"""

    key = playlist.segments[index].key
    if key is not None and key.iv:
        return bytes.fromhex(key.iv.replace("0x", "").replace("0X", "").zfill(32))

    return ((playlist.media_sequence or 0) + index).to_bytes(16, 'big')

def unpad(data):
    """Padding added by the encryption, the browser would read it as broken video"""

    size = data[-1] if data else 0
    if 1 <= size <= 16 and data[-size:] == bytes([size]) * size:
        return data[:-size]

    return data


# [ streams ]
class Streams:
    """The streams opened by the app, by their id"""

    def __init__(self):
        self.lock = threading.Lock()
        self.items = collections.OrderedDict()

    def open(self, stream):
        stream = Stream(stream)

        with self.lock:
            self.items[stream.id] = stream
            while len(self.items) > MAX_STREAMS:
                self.items.popitem(last=False)[1].close()

        return stream

    def get(self, stream_id):
        with self.lock:
            stream = self.items.get(stream_id)

            # The stream watched now is the last one forgotten
            if stream is not None:
                self.items.move_to_end(stream_id)

            return stream
