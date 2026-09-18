# 15.09.26

# Class import
from Src.Util.headers import get_headers
from Src.Util.console import console
from Src.Util.errors import DownloadError
from Src.Util import http

# General import
import requests, re, sys
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, urljoin
from m3u8 import M3U8


# [func]
def parse_content(embed_content):

    # Parse parameter of window.masterPlaylist from req embed content
    master_playlist = str(embed_content).split("window.masterPlaylist", 1)[-1]
    token = re.search(r"""['"]?token['"]?\s*:\s*['"]([^'"]+)['"]""", master_playlist)
    expires = re.search(r"""['"]?expires['"]?\s*:\s*['"]([^'"]+)['"]""", master_playlist)
    url = re.search(r"""['"]?url['"]?\s*:\s*['"]([^'"]+)['"]""", master_playlist)

    if not (token and expires and url):
        raise DownloadError("Video non disponibile (il player non ha i dati del video)")

    return {
        'token': token.group(1),
        'expires': expires.group(1),
        'url': url.group(1),
        'canPlayFHD': re.search(r"window\.canPlayFHD\s*=\s*true", str(embed_content)) is not None
    }

def get_playlist(json_win_param):

    # Add token and expires to master playlist url
    playlist_url = urlparse(json_win_param['url'])
    params = parse_qs(playlist_url.query)
    params.update({'token': json_win_param['token'], 'expires': json_win_param['expires']})

    if json_win_param['canPlayFHD']:
        params['h'] = '1'

    return urlunparse(playlist_url._replace(query=urlencode(params, doseq=True)))

def get_master_playlist(m3u8_playlist):
    req = http.get(m3u8_playlist, headers={'user-agent': get_headers()})

    if not req.ok:
        raise DownloadError(f"Il player ha risposto con errore {req.status_code}")

    return M3U8(req.text)

def get_m3u8_url(master_playlist):

    if not master_playlist.playlists:
        raise DownloadError("Il player non ha nessun video")

    # Select video playlist with best quality
    best_playlist = max(master_playlist.playlists, key=lambda playlist: playlist.stream_info.bandwidth or 0)
    resolution = best_playlist.stream_info.resolution
    render_quality = f"{resolution[1]}p" if resolution else "unknown"
    console.print(f"[blue]Quality select => [red]{render_quality}")

    return best_playlist.uri

def get_m3u8_audio(master_playlist):

    # Select italian audio if present, otherwise first audio track
    audio_tracks = [media for media in master_playlist.media if media.type == "AUDIO" and media.uri]

    for audio in audio_tracks:
        if audio.language == "ita":
            return audio.uri

    return audio_tracks[0].uri if audio_tracks else None

def get_m3u8_key(m3u8_url):
    req = http.get(urljoin(m3u8_url, '/storage/enc.key'), headers={'user-agent': get_headers()})

    if not req.ok or len(req.content) != 16:
        raise DownloadError(f"Chiave del video non disponibile (errore {req.status_code})")

    return req.content.hex()

def get_stream(embed_content):
    """Video with the best quality, audio and key of a player, used by the preview"""

    master_playlist = get_master_playlist(get_playlist(parse_content(embed_content)))

    if not master_playlist.playlists:
        raise ValueError("Video non disponibile")

    best = max(master_playlist.playlists, key=lambda playlist: playlist.stream_info.bandwidth or 0)
    audio_url = get_m3u8_audio(master_playlist)
    audio = next((media for media in master_playlist.media if media.type == "AUDIO" and media.uri == audio_url), None)

    return {
        'video': best.uri,
        'audio': audio_url,
        'key': get_m3u8_key(best.uri),
        'resolution': best.stream_info.resolution,
        'language': audio.language if audio else None,
    }
