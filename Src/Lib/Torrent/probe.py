# 20.10.26

# General import
import json, shutil, subprocess, sys

# Variable
TIMEOUT = 30
HDR_TRANSFERS = {'smpte2084': 'HDR10', 'arib-std-b67': 'HLG'}
CODECS = {
    'hevc': 'HEVC', 'h264': 'H.264', 'av1': 'AV1', 'vp9': 'VP9', 'mpeg4': 'MPEG-4', 'mpeg2video': 'MPEG-2',
    'aac': 'AAC', 'ac3': 'Dolby Digital', 'eac3': 'Dolby Digital Plus', 'truehd': 'Dolby TrueHD', 'dts': 'DTS',
    'flac': 'FLAC', 'opus': 'Opus', 'mp3': 'MP3', 'vorbis': 'Vorbis', 'pcm_s16le': 'PCM', 'pcm_s24le': 'PCM',
    'subrip': 'SRT', 'ass': 'ASS', 'hdmv_pgs_subtitle': 'PGS', 'dvd_subtitle': 'VobSub', 'mov_text': 'Testo',
}


class ProbeError(Exception):
    pass


def is_available():
    return shutil.which('ffprobe') is not None

def run(path):
    """Streams of a video read by ffprobe, also from a file downloaded only in part"""

    if not is_available():
        raise ProbeError("ffprobe non trovato: installa FFmpeg completo")

    command = ['ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', path]
    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if sys.platform == 'win32' else {}

    try:
        result = subprocess.run(command, capture_output=True, timeout=TIMEOUT, **options)
    except subprocess.TimeoutExpired:
        raise ProbeError("ffprobe non ha finito in tempo")

    try:
        data = json.loads(result.stdout or b'{}')
    except ValueError:
        data = {}

    if not data.get('streams'):
        error = result.stderr.decode('utf-8', 'replace').strip().splitlines()
        raise ProbeError(error[-1] if error else "Nessuna traccia leggibile")

    return data

def codec_name(stream):
    name = stream.get('codec_name') or ''
    profile = stream.get('profile') or ''

    # DTS-HD MA and DTS:X are profiles of dts
    if name == 'dts' and profile and profile != 'DTS':
        return profile
    return CODECS.get(name, name.upper() or None)

def channels_label(stream):
    channels = stream.get('channels')
    layout = stream.get('channel_layout') or ''

    if not channels:
        return None
    if channels == 1:
        return 'Mono'
    if channels == 2:
        return 'Stereo'
    if '7.1' in layout or channels == 8:
        return '7.1'
    if '5.1' in layout or channels == 6:
        return '5.1'
    return f"{channels} canali"

def get_hdr(stream):
    side = [item.get('side_data_type', '') for item in stream.get('side_data_list') or []]

    if any('DOVI' in item or 'Dolby Vision' in item for item in side):
        return 'Dolby Vision'
    if any('HDR10+' in item or 'HDR Dynamic Metadata' in item for item in side):
        return 'HDR10+'
    return HDR_TRANSFERS.get(stream.get('color_transfer'))

def get_fps(stream):
    try:
        numerator, denominator = (int(part) for part in (stream.get('avg_frame_rate') or '0/0').split('/'))
        return round(numerator / denominator, 3) if denominator else None
    except ValueError:
        return None

def describe(data):
    """Scheda tecnica: video, audio and subtitles of a file"""

    streams = data.get('streams') or []
    tags = lambda stream: {key.lower(): value for key, value in (stream.get('tags') or {}).items()}
    default = lambda stream: bool((stream.get('disposition') or {}).get('default'))

    videos = [stream for stream in streams if stream.get('codec_type') == 'video' and not (stream.get('disposition') or {}).get('attached_pic')]
    video = max(videos, key=lambda stream: (stream.get('width') or 0) * (stream.get('height') or 0), default=None)

    try:
        duration = float((data.get('format') or {}).get('duration') or 0) or None
    except ValueError:
        duration = None

    return {
        'container': ((data.get('format') or {}).get('format_long_name') or '').split(' / ')[0] or None,
        'duration': duration,
        'video': {
            'codec': codec_name(video),
            'width': video.get('width'),
            'height': video.get('height'),
            'hdr': get_hdr(video),
            'bit_depth': int(video['bits_per_raw_sample']) if str(video.get('bits_per_raw_sample', '')).isdigit() else (10 if '10' in (video.get('pix_fmt') or '') else None),
            'fps': get_fps(video),
        } if video else None,
        'audio': [{
            'language': tags(stream).get('language'),
            'title': tags(stream).get('title'),
            'codec': codec_name(stream),
            'channels': channels_label(stream),
            'default': default(stream),
        } for stream in streams if stream.get('codec_type') == 'audio'],
        'subtitles': [{
            'language': tags(stream).get('language'),
            'title': tags(stream).get('title'),
            'codec': codec_name(stream),
            'forced': bool((stream.get('disposition') or {}).get('forced')),
        } for stream in streams if stream.get('codec_type') == 'subtitle'],
    }
