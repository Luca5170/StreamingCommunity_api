# 20.10.26

# Class import
from Src.Lib.Torrent import release

# General import
import datetime, re, statistics

# Variable
MB = 1024 * 1024
FAKE, SUSPECT = 'fake', 'suspect'

# Least weight that makes sense, in MB: (fake under, suspect under)
FILM_SIZES = {'4K': (1500, 4000), '1080p': (400, 900), '720p': (200, 450), 'SD': (100, 250), None: (100, 0)}
EPISODE_SIZES = {'4K': (250, 700), '1080p': (60, 150), '720p': (40, 90), 'SD': (20, 45), None: (20, 0)}
REMUX_SIZES = (4000, 12000)
PACK_EPISODES = 4                   # A whole season has at least these episodes

# Least bitrate of a real encode, in Mbit/s
MIN_BITRATE = {'4K': 3.0, '1080p': 0.9, '720p': 0.5}
RANK = {'SD': 0, '720p': 1, '1080p': 2, '4K': 3}
LANGUAGES = {'ita': 'italiano', 'eng': 'inglese', 'jpn': 'giapponese', 'fre': 'francese', 'fra': 'francese', 'ger': 'tedesco',
             'deu': 'tedesco', 'spa': 'spagnolo', 'por': 'portoghese', 'rus': 'russo', 'kor': 'coreano', 'chi': 'cinese', 'zho': 'cinese'}

PROGRAM_IN_NAME = re.compile(r'\.(exe|scr|bat|cmd|msi|lnk|vbs|apk|jar|ps1)\b', re.IGNORECASE)
ARCHIVE_IN_NAME = re.compile(r'\.(rar|zip|7z|iso)\b', re.IGNORECASE)
BAIT_WORDS = re.compile(r'\b(password|passwd|keygen|crack(?:ed)?|setup|installer|codec[ ._-]?pack|activator|serial[ ._-]?key)\b', re.IGNORECASE)
WEB_ADDRESS = re.compile(r'\bwww\.|https?://|\.(?:com|net|org|xyz|top|club|site|online|ru)\b', re.IGNORECASE)
RESOLUTIONS = {'4K': r'2160p|\b4k\b', '1080p': r'1080[pi]', '720p': r'720p', 'SD': r'480p|576p'}
X264 = re.compile(r'\b[xh]\.?264\b|\bavc\b', re.IGNORECASE)
X265 = re.compile(r'\b[xh]\.?265\b|\bhevc\b', re.IGNORECASE)
FAKE_VIDEO = re.compile(r'\.(mkv|mp4|avi|m4v|mov|wmv)\.[a-z0-9]{2,4}$', re.IGNORECASE)
LINK_EXTENSIONS = {'.url', '.website', '.webloc'}


# [ helpers ]
def verdict(reasons):
    """The worst level found, with every reason and its level: the fakes first"""

    reasons = sorted(reasons, key=lambda reason: reason[0] != FAKE)
    level = FAKE if any(level == FAKE for level, _ in reasons) else SUSPECT if reasons else None
    return {'level': level, 'reasons': [{'level': level, 'text': text} for level, text in reasons]}

def merge(*verdicts):
    return verdict([(reason['level'], reason['text']) for found in verdicts if found for reason in found['reasons']])

def size_label(size):
    if size >= 1024 * MB:
        return f"{size / 1024 / MB:.1f} GB".replace('.', ',')
    return f"{round(size / MB)} MB"

def quality_of(tags):
    return next((tag['label'] for tag in tags if tag['kind'] == 'quality'), None)

def size_reasons(size, kind, quality, remux=False, pack=False):
    """A file too light for what its name promises: fake, or a quality not worth it"""

    if not size or size <= 0:
        return []

    if kind == 'movie':
        fake, suspect = REMUX_SIZES if remux else FILM_SIZES.get(quality, FILM_SIZES[None])
        what = f"un film{f' {quality}' if quality else ''}"
    else:
        fake, suspect = EPISODE_SIZES.get(quality, EPISODE_SIZES[None])
        what = f"un episodio{f' {quality}' if quality else ''}"

        if pack:
            fake, suspect = fake * PACK_EPISODES, suspect * PACK_EPISODES
            what = f"una stagione intera{f' {quality}' if quality else ''}"

    if size < fake * MB:
        return [(FAKE, f"Pesa {size_label(size)}: troppo poco per {what}")]
    if size < suspect * MB:
        return [(SUSPECT, f"Pesa {size_label(size)}: poco per {what}, qualità probabilmente bassa")]
    return []


# [ result of a search ]
def check_result(title, size, guess):
    """Signs of a fake or of junk, from the name and the weight only"""

    reasons = []
    tags = guess['tags']

    program = PROGRAM_IN_NAME.search(title)
    if program:
        reasons.append((FAKE, f"Nel nome c'è un programma (.{program.group(1).lower()}): non è un video"))

    archive = ARCHIVE_IN_NAME.search(title)
    if archive:
        reasons.append((FAKE, f"Nel nome c'è un archivio (.{archive.group(1).lower()}): spesso chiede una password o nasconde un programma"))

    bait = BAIT_WORDS.search(title)
    if bait:
        reasons.append((FAKE, f"Parola tipica dei falsi nel nome: «{bait.group(1)}»"))

    if guess['year'] and int(guess['year']) > datetime.date.today().year + 1:
        reasons.append((FAKE, f"Anno nel futuro ({guess['year']})"))

    found = [label for label, pattern in RESOLUTIONS.items() if re.search(pattern, title, re.IGNORECASE)]
    if len(found) > 1:
        reasons.append((SUSPECT, f"Il nome elenca più risoluzioni insieme ({', '.join(found)}): tipico dei falsi"))

    if X264.search(title) and X265.search(title):
        reasons.append((SUSPECT, "Il nome dice due codec diversi (x264 e x265)"))

    if not program and WEB_ADDRESS.search(title):
        reasons.append((SUSPECT, "Nel nome c'è un indirizzo web: spesso pubblicità o falsi"))

    if any(tag['label'] == 'CAM' for tag in tags):
        reasons.append((SUSPECT, "Registrato al cinema con una videocamera: qualità pessima"))

    reasons += size_reasons(size, guess['type'], quality_of(tags), any(tag['label'] == 'Remux' for tag in tags), guess['pack'])
    return verdict(reasons)


# [ files of a torrent ]
def get_videos(files):
    return [file for file in files if release.is_video(file['name']) and not release.is_sample(file['name'], file['size'])]

def is_program(file):
    return release.extension(file['name']) in release.DANGEROUS_EXTENSIONS

def get_junk(files):
    """Why a torrent is only junk (no real video), None when it has something to watch"""

    if get_videos(files):
        return None

    programs = [file for file in files if is_program(file)]
    if programs:
        return f"dentro c'è solo un programma ({programs[0]['name'].split('/')[-1]}), nessun video"
    if any(release.extension(file['name']) in release.ARCHIVE_EXTENSIONS for file in files):
        return "il video è chiuso in un archivio, che di solito chiede una password o nasconde un programma"
    return "dentro non c'è nessun video"

def default_files(files):
    """Files downloaded when nobody chose: the videos and their subtitles, never programs or samples"""

    videos = get_videos(files)
    if not videos:
        return [file['index'] for file in files if not is_program(file)]

    subtitles = [file for file in files if release.extension(file['name']) in release.SUBTITLE_EXTENSIONS]
    return [file['index'] for file in videos + subtitles]

def check_files(files, guess):
    """Signs of a fake from the list of files: programs, archives, links, a video too light"""

    reasons = []

    for file in files:
        if not is_program(file):
            continue

        name = file['name'].split('/')[-1]
        if FAKE_VIDEO.search(name):
            reasons.append((FAKE, f"«{name}» finge di essere un video ma è un programma: non aprirlo"))
        else:
            reasons.append((FAKE, f"Contiene un programma ({name}): non aprirlo, non lo scarico"))

    if any('password' in file['name'].lower() for file in files):
        reasons.append((FAKE, "C'è un file che parla di password: il video è protetto, quasi sempre un falso"))

    if any(release.extension(file['name']) in LINK_EXTENSIONS for file in files):
        reasons.append((SUSPECT, "Contiene collegamenti a siti web (pubblicità)"))

    junk = get_junk(files)
    if junk:
        reasons.append((FAKE, junk[0].upper() + junk[1:]))
        return verdict(reasons)

    videos = get_videos(files)
    quality = quality_of(guess['tags'])
    remux = any(tag['label'] == 'Remux' for tag in guess['tags'])

    if guess['type'] == 'movie':
        reasons += size_reasons(max(file['size'] for file in videos), 'movie', quality, remux)
    else:
        # Each episode on its own, the typical one of the pack
        reasons += size_reasons(statistics.median(file['size'] for file in videos), 'tv', quality)

    return verdict(reasons)


# [ tracks read by ffprobe ]
def actual_quality(video):
    width, height = video.get('width') or 0, video.get('height') or 0

    if width >= 3200 or height >= 1700:
        return '4K'
    if width >= 1700 or height >= 900:
        return '1080p'
    if width >= 1200 or height >= 650:
        return '720p'
    return 'SD'

def check_probe(data, guess, size):
    """What the name promises against what the video really is"""

    reasons = []
    video = data.get('video')

    if not video or not video.get('width'):
        return verdict([(FAKE, "Il file non contiene un video vero")])

    claimed, actual = quality_of(guess['tags']), actual_quality(video)
    if claimed in RANK and RANK[actual] < RANK[claimed]:
        reasons.append((FAKE, f"Il nome dice {claimed} ma il video è {actual} ({video['width']}×{video['height']})"))

    if any(tag['label'] == 'ITA' for tag in guess['tags']):
        languages = {(track.get('language') or '').lower() for track in data.get('audio') or []} - {'', 'und'}
        titles = ' '.join((track.get('title') or '').lower() for track in data.get('audio') or [])

        if not data.get('audio'):
            reasons.append((FAKE, "Il nome dice ITA ma il video non ha audio"))
        elif languages and 'ita' not in languages and 'ital' not in titles and not re.search(r'\bita\b', titles):
            names = ', '.join(sorted(LANGUAGES.get(language, language) for language in languages))
            reasons.append((FAKE, f"Il nome dice ITA ma nessuna traccia audio è in italiano (ci sono: {names})"))
        elif not languages and 'ital' not in titles:
            reasons.append((SUSPECT, "Le tracce audio non dicono la lingua: non posso verificare che ci sia l'italiano"))

    duration = data.get('duration') or 0
    if duration:
        minutes = round(duration / 60)

        if guess['type'] == 'movie' and duration < 40 * 60:
            reasons.append((SUSPECT, f"Dura solo {minutes} min: forse è un trailer o un pezzo del film"))
        elif guess['type'] != 'movie' and duration < 5 * 60:
            reasons.append((SUSPECT, f"Dura solo {minutes} min: troppo poco per un episodio"))

        bitrate = size * 8 / duration / 1e6 if size else 0
        if bitrate and actual in MIN_BITRATE and bitrate < MIN_BITRATE[actual]:
            reasons.append((SUSPECT, f"Bitrate molto basso ({bitrate:.1f} Mbit/s per un {actual}): immagine probabilmente impastata".replace('.', ',', 1)))

    return verdict(reasons)
