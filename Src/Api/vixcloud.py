# 15.09.26

# Class import
from Src.Util.headers import get_headers
from Src.Util.console import console
from Src.Util.errors import DownloadError, describe_response
from Src.Util import http

# General import
import requests, re, sys
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse, urljoin
from m3u8 import M3U8

# Variable
LANGUAGE_NAMES = {'ita': 'Italiano', 'eng': 'Inglese', 'jpn': 'Giapponese', 'fra': 'Francese', 'fre': 'Francese',
                  'deu': 'Tedesco', 'ger': 'Tedesco', 'spa': 'Spagnolo'}
VTT_HEADER = re.compile(r'^WEBVTT[^\n]*\n(?:[^\n]+\n)*\n?')


# [func]
def parse_content(embed_content):

    # Parse parameter of window.masterPlaylist from req embed content
    master_playlist = str(embed_content).split("window.masterPlaylist", 1)[-1]
    token = re.search(r"""['"]?token['"]?\s*:\s*['"]([^'"]+)['"]""", master_playlist)
    expires = re.search(r"""['"]?expires['"]?\s*:\s*['"]([^'"]+)['"]""", master_playlist)
    url = re.search(r"""['"]?url['"]?\s*:\s*['"]([^'"]+)['"]""", master_playlist)

    if not (token and expires and url):
        raise DownloadError("Il player non contiene i dati del video: il video non è disponibile o il player è cambiato")

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
        raise DownloadError(describe_response(req, "Il player"))

    return M3U8(req.text)

def get_m3u8_url(master_playlist):

    if not master_playlist.playlists:
        raise DownloadError("La playlist del player non contiene nessuna qualità video")

    # Select video playlist with best quality
    best_playlist = max(master_playlist.playlists, key=lambda playlist: playlist.stream_info.bandwidth or 0)
    resolution = best_playlist.stream_info.resolution
    render_quality = f"{resolution[1]}p" if resolution else "unknown"
    console.print(f"[blue]Quality select => [red]{render_quality}")

    return best_playlist.uri

def get_audio_track(master_playlist):

    # Select italian audio if present, otherwise first audio track
    audio_tracks = [media for media in master_playlist.media if media.type == "AUDIO" and media.uri]

    for audio in audio_tracks:
        if audio.language == "ita":
            return audio

    return audio_tracks[0] if audio_tracks else None

def get_m3u8_audio(master_playlist):
    audio = get_audio_track(master_playlist)
    return audio.uri if audio else None

def get_subtitle_tracks(master_playlist):
    """Subtitle tracks of the player, the one to show by itself comes first and is the default"""

    tracks = []

    for media in master_playlist.media:
        if media.type != "SUBTITLES" or not media.uri or media.language == "auto":
            continue

        # The player writes the tracks with the foreign lines of a dubbed film like ita-forced
        language = (media.language or 'und').lower()
        code = re.split(r'[-_]', language)[0]
        forced = media.forced == 'YES' or 'forced' in f"{language} {media.name}".lower()
        name = LANGUAGE_NAMES.get(code) or media.name or code

        tracks.append({'url': media.uri, 'language': code, 'forced': forced, 'default': False, 'title': f"{name} (forzati)" if forced else name})

    audio = get_audio_track(master_playlist)
    italian = [track for track in tracks if track['language'] == 'ita']

    # Who listens in italian needs only the foreign lines, a foreign audio needs all the subtitles there are
    if audio is None or audio.language == "ita":
        wanted = [track for track in italian if track['forced']]
    else:
        wanted = [track for track in italian if not track['forced']] + italian + tracks

    if wanted:
        wanted[0]['default'] = True

    tracks.sort(key=lambda track: not track['default'])
    return tracks

def decode_text(content):

    # The server does not say the charset of the subtitles, the accents must stay right
    try:
        return content.decode('utf-8-sig')
    except UnicodeDecodeError:
        return content.decode('cp1252', errors='replace')

def get_subtitle_part(url):
    req = http.get(url, headers={'user-agent': get_headers()})

    if not req.ok:
        raise DownloadError(describe_response(req, "Il server dei sottotitoli"))

    return decode_text(req.content)

def read_subtitle(url):
    """Text of a subtitle track in webvtt: its playlist points to one file, or to many pieces of it"""

    parts = [get_subtitle_part(segment.absolute_uri) for segment in M3U8(get_subtitle_part(url), base_uri=urljoin(url, '.')).segments]
    parts = [part.replace('\r\n', '\n').lstrip() for part in parts]

    if not parts or not all(part.startswith('WEBVTT') for part in parts):
        raise DownloadError("La traccia dei sottotitoli non è in formato WebVTT")

    # Only the header of the whole file stays
    body = '\n\n'.join(VTT_HEADER.sub('', part, count=1).strip() for part in parts)

    if '-->' not in body:
        raise DownloadError("La traccia dei sottotitoli è vuota")

    return f"WEBVTT\n\n{body}\n"

def get_subtitles(master_playlist):
    """Subtitles to put inside the file, they are an extra: the video is downloaded also when they fail"""

    found = []

    for track in get_subtitle_tracks(master_playlist):
        try:
            found.append({**track, 'text': read_subtitle(track['url'])})
            console.log(f"[green]Download subtitle: [red]{track['title']}")
        except Exception as e:
            console.log(f"[yellow]Subtitle {track['title']} not downloaded: {e}")

    # With no default track the players would show the first one: every line of a dubbed film subtitled
    if not any(track['default'] for track in found):
        console.print("[blue]Subtitles => [green]no track to show by itself")
        return []

    return found

def get_m3u8_key(m3u8_url):
    req = http.get(urljoin(m3u8_url, '/storage/enc.key'), headers={'user-agent': get_headers()})

    if not req.ok:
        raise DownloadError(describe_response(req, "Il server della chiave del video"))
    if len(req.content) != 16:
        raise DownloadError(f"Chiave del video non valida ({len(req.content)} byte invece di 16), il player potrebbe essere cambiato")

    return req.content.hex()

def get_stream(embed_content):
    """Video with the best quality, audio and key of a player, used by the streaming of the app"""

    master_playlist = get_master_playlist(get_playlist(parse_content(embed_content)))

    if not master_playlist.playlists:
        raise ValueError("Video non disponibile")

    best = max(master_playlist.playlists, key=lambda playlist: playlist.stream_info.bandwidth or 0)
    audio = get_audio_track(master_playlist)

    return {
        'video': best.uri,
        'audio': audio.uri if audio else None,
        'key': get_m3u8_key(best.uri),
        'resolution': best.stream_info.resolution,
        'bandwidth': best.stream_info.bandwidth,
        'codecs': best.stream_info.codecs,
        'language': audio.language if audio else None,
        'subtitles': get_subtitle_tracks(master_playlist),
    }
