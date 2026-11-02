# 20.10.26

# General import
import os, re

# Variable
VIDEO_EXTENSIONS = {'.mkv', '.mp4', '.avi', '.m4v', '.mov', '.wmv', '.ts', '.m2ts', '.webm', '.mpg', '.mpeg'}
SUBTITLE_EXTENSIONS = {'.srt', '.ass', '.ssa', '.sub', '.idx', '.vtt'}
DANGEROUS_EXTENSIONS = {'.exe', '.scr', '.bat', '.cmd', '.msi', '.lnk', '.com', '.vbs', '.js', '.ps1', '.jar', '.apk'}
ARCHIVE_EXTENSIONS = {'.rar', '.zip', '.7z'}
FLAGS = re.IGNORECASE

# Tags of a release name: label shown in the app, pattern, kind
TAGS = [
    ('4K', r'2160p|\b4k\b|\buhd\b', 'quality'),
    ('1080p', r'1080[pi]', 'quality'),
    ('720p', r'720p', 'quality'),
    ('SD', r'480p|576p|\bdvdrip\b|\bxvid\b', 'quality'),
    ('Dolby Vision', r'dolby[ ._-]?vision|\bdovi\b|\bdv\b', 'hdr'),
    ('HDR10+', r'hdr10(?:\+|plus)', 'hdr'),
    ('HDR', r'\bhdr(?:10)?\b', 'hdr'),
    ('HEVC', r'\bx\.?265\b|\bh\.?265\b|\bhevc\b', 'codec'),
    ('AV1', r'\bav1\b', 'codec'),
    ('H.264', r'\bx\.?264\b|\bh\.?264\b|\bavc\b', 'codec'),
    ('Remux', r'\bremux\b', 'source'),
    ('BluRay', r'blu[ ._-]?ray|\bbd(?:rip)?\b|\bbrrip\b', 'source'),
    ('WEB-DL', r'\bweb[ ._-]?dl\b|\bwebdl\b', 'source'),
    ('WEBRip', r'\bweb[ ._-]?rip\b', 'source'),
    ('HDTV', r'\bhdtv\b', 'source'),
    ('CAM', r'\b(?:hd)?cam(?:rip)?\b|\bhdts\b|\btelesync\b|\btsrip\b', 'source'),
    ('Sub ITA', r'\bsub(?:bed|s)?[ ._-]?ita(?:liano)?\b', 'subtitles'),
    ('ITA', r'\bita\b|\bitalian[oa]?\b', 'language'),
    ('ENG', r'\beng\b|\benglish\b', 'language'),
    ('JAP', r'\bjap\b|\bjpn\b|\bjapanese\b', 'language'),
    ('MULTI', r'\bmulti\b', 'language'),
]
TAG_PATTERNS = [(label, re.compile(pattern, FLAGS), kind) for label, pattern, kind in TAGS]
SUB_ITA = re.compile(r'\bsub(?:bed|s)?[ ._-]?ita(?:liano)?\b', FLAGS)

EPISODE = re.compile(r'\bS(\d{1,2})[ ._-]?E(\d{1,4})\b', FLAGS)
CROSS_EPISODE = re.compile(r'\b(\d{1,2})x(\d{2,3})\b', FLAGS)
SEASON = re.compile(r'\bS(\d{1,2})\b|\b(?:stagione|season|stagioni)[ ._-]?(\d{1,2})\b', FLAGS)
ANIME_EPISODE = re.compile(r'\s-\s(\d{1,4})(?:v\d)?(?=\s|\[|\(|$)')
YEAR = re.compile(r'(?<![\d])(19[2-9]\d|20[0-4]\d)(?![\d])')
GROUP = re.compile(r'^\s*[\[(【][^\])】]*[\])】]\s*')
COMPLETE = re.compile(r'\b(?:complete|completa|integrale)\b', FLAGS)


# [ files ]
def extension(name):
    return os.path.splitext(name or '')[1].lower()

def is_video(name):
    return extension(name) in VIDEO_EXTENSIONS

def is_sample(name, size=0):
    base = os.path.basename(name or '').lower()
    return bool(re.search(r'\bsample\b', base)) or ('sample' in (name or '').lower().split('/')[:-1]) or (0 < size < 30 * 1024 * 1024 and is_video(name))


# [ release names ]
def get_tags(title):
    """Labels of quality, codec, hdr, source and languages, at most one per kind except the languages"""

    tags, kinds = [], set()

    # "Sub ITA" says nothing about the language of the audio
    audio = SUB_ITA.sub(' ', title)

    for label, pattern, kind in TAG_PATTERNS:
        if kind != 'language' and kind in kinds:
            continue
        if pattern.search(audio if kind == 'language' else title):
            tags.append({'label': label, 'kind': kind})
            kinds.add(kind)

    return tags

def clean_title(text):
    text = re.sub(r'[._]+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip(' -–[](){}')

def parse(title, categories=()):
    """
    What a release name says: title, year, season and episode.
    The kind comes from the numbers when there are, from the category of the indexer otherwise.
    """

    text = GROUP.sub('', title or '')
    plain = re.sub(r'[._]+', ' ', text)

    season = episode = None
    cut = len(plain)

    match = EPISODE.search(plain) or CROSS_EPISODE.search(plain)
    if match:
        season, episode = int(match.group(1)), int(match.group(2))
        cut = min(cut, match.start())
    else:
        match = SEASON.search(plain)
        if match:
            season = int(match.group(1) or match.group(2))
            cut = min(cut, match.start())

    anime = ANIME_EPISODE.search(plain) if GROUP.match(title or '') and episode is None else None
    if anime:
        episode = int(anime.group(1))
        cut = min(cut, anime.start())

    year = None
    for match in YEAR.finditer(plain):
        # A year at the start is part of the title (2001 Odissea nello spazio)
        if match.start() == 0:
            continue
        year = match.group(1)
        cut = min(cut, match.start())
        break

    for _, pattern, _ in TAG_PATTERNS:
        match = pattern.search(plain)
        if match and match.start() > 0:
            cut = min(cut, match.start())

    name = clean_title(plain[:cut]) or clean_title(plain)

    categories = [int(category) for category in categories or [] if str(category).isdigit()]
    if anime or any(5070 <= category < 5080 or 100000 <= category and category % 1000 == 70 for category in categories):
        kind = 'anime'
    elif season is not None or episode is not None or any(5000 <= category < 6000 for category in categories):
        kind = 'tv'
    else:
        kind = 'movie'

    return {
        'name': name,
        'year': year,
        'type': kind,
        'season': season if season is not None else (1 if kind in ('tv', 'anime') else None),
        'episode': episode,
        'pack': kind != 'movie' and episode is None,
        'complete': bool(COMPLETE.search(plain)),
        'tags': get_tags(plain),
    }

def parse_file(name):
    """Season and episode of a file inside a torrent, the folders can say the season"""

    base = os.path.splitext(os.path.basename(name))[0]
    info = parse(base)

    if info['episode'] is None:
        # "Title - 05 [1080p].mkv" of anime, "Title/Season 2/05 - Name.mkv"
        match = ANIME_EPISODE.search(re.sub(r'[._]+', ' ', base)) or re.match(r'^\s*(?:e(?:p(?:isodio|isode)?)?[ ._-]*)?(\d{1,3})(?=\D|$)', base, FLAGS)
        if match and not YEAR.fullmatch(match.group(1)):
            info['episode'] = int(match.group(1))

    for folder in reversed(name.replace('\\', '/').split('/')[:-1]):
        match = SEASON.search(re.sub(r'[._]+', ' ', folder))
        if match and not EPISODE.search(base):
            info['season'] = int(match.group(1) or match.group(2))
            break

    return info
