# 18.09.26

# Class import
from Src.Api import anime
from Src.Gui.anime_source import format_anime
from Src.Gui.recommend import normalize, parse_name
from Src.Lib.Nas import nas
from Src.Util import history
from Src.Util.console import console

# General import
import os, re, threading, time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from stat import S_ISDIR

# Variable
MAX_TITLES = 20         # Titles in the row
MAX_SEEDS = 10          # Recent downloads used to find new titles
MAX_RELATED = 4         # Sequels and prequels of every download looked in detail
MIN_SCORE = 1.6         # Below this an anime is not similar enough to be proposed
CACHE_TIME = 6 * 3600

# Genres that almost every anime has, they say little about a taste
COMMON_GENRES = {'Action', 'Comedy', 'Drama', 'Adventure', 'Fantasy', 'Shounen'}


# [ similarity ]
def get_genres(record):
    return {genre if isinstance(genre, str) else genre.get('name') for genre in record.get('genres') or []} - {None}

def base_name(record):
    """Name without the (ITA) of the dubbed copies, the same anime has one copy for every audio"""

    return normalize(re.sub(r'\(\s*ita\s*\)', '', anime.get_title_name(record) or '', flags=re.I))

def similarity(seed, record, related):
    genres = get_genres(record)
    genre_sim = len(seed['genres'] & genres) / max(1, len(seed['genres'] | genres))
    rating = float(record.get('score') or 6) / 10

    # The other seasons and films of the same story are the best proposals
    return genre_sim * 3 + rating * 0.6 + (1.5 if related else 0)


# [ past downloads ]
def get_past():
    return [title for title in history.load()['titles'] if title.get('source') == 'anime']

def list_downloads():
    """Anime already downloaded: folders with the slug in videos/anime, folders 'Name (Year)' on the nas"""

    found = []

    if os.path.isdir(os.path.join("videos", "anime")):
        for entry in os.scandir(os.path.join("videos", "anime")):
            if entry.is_dir() and not entry.name.startswith('.'):
                found.append({**parse_name(entry.name), 'date': entry.stat().st_mtime})

    config = nas.load_config()
    if nas.is_enabled(config) and config.get('anime_path'):
        with nas.open_sftp(config) as sftp:
            try:
                entries = sftp.listdir_attr(config['anime_path'])
            except IOError:
                entries = []

            for entry in entries:
                if S_ISDIR(entry.st_mode) and not entry.filename.startswith('.'):
                    found.append({**parse_name(entry.filename), 'date': entry.st_mtime})

    return found

def find_anime(item):
    """The anime of the site with this name, the year decides between anime with the same name"""

    same_name = []

    for record in anime.client.search(item['name']):
        if item.get('slug') and record.get('slug') == item['slug']:
            return record

        names = {normalize(record.get(key)) for key in ('title_it', 'title_eng', 'title')}
        if normalize(item['name']) in names:
            if item.get('year') and str(record.get('date') or '')[:4] == item['year']:
                return record
            same_name.append(record)

    # The copy with the original audio before the dubbed one
    same_name.sort(key=lambda record: bool(record.get('dub')))
    return same_name[0] if same_name else None

def has_sources():
    config = nas.load_config()
    return os.path.isdir(os.path.join("videos", "anime")) or bool(nas.is_enabled(config) and config.get('anime_path'))

def import_downloads():
    """At the first start the past anime are taken from the names of the folders"""

    # Without folders of anime yet, the import waits for them
    if not has_sources():
        return

    try:
        found = list_downloads()
    except nas.NasError as e:
        console.log(f"[yellow]Anime recommendations: nas not reachable, past downloads imported later ({e})")
        return

    def match(item):
        try:
            return find_anime(item)
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        records = list(pool.map(match, found))

    known = {title['id'] for title in get_past()}
    imported = {}

    for item, record in zip(found, records):
        if record and record['id'] not in known:
            previous = imported.get(record['id'])
            if previous is None or item['date'] > previous['date']:
                title = format_anime(record)
                imported[record['id']] = {
                    'id': title['id'], 'slug': title['slug'], 'name': title['name'], 'type': title['type'],
                    'year': title['year'], 'date': item['date'], 'source': 'anime',
                }

    history.add_many(list(imported.values()), imported=True, flag='imported_anime')
    console.log(f"[green]Anime recommendations: {len(imported)} past downloads imported")


# [ recommendations ]
class AnimeRecommender:
    """Anime similar to the past downloads: other seasons of the same story and anime with the same genres"""

    def __init__(self):
        self.lock = threading.Lock()
        self.infos = {}         # Pages of the anime, they change rarely
        self.lists = {}         # Lists of the archive by genres
        self.result = None
        self.result_key = None
        self.result_time = 0

    def get(self):
        with self.lock:
            if not history.load()['imported_anime']:
                import_downloads()

            past = get_past()
            key = tuple(sorted((title['id'], title['date']) for title in past))

            if self.result is None or key != self.result_key or time.time() - self.result_time > CACHE_TIME:
                self.result = self.compute(past)
                self.result_key, self.result_time = key, time.time()

            return self.result

    def get_info(self, anime_id):
        if anime_id not in self.infos:
            try:
                self.infos[anime_id] = anime.client.get_info(anime_id)
            except Exception:
                return None

        return self.infos[anime_id]

    def get_list(self, filters):
        key = repr(sorted(filters.items()))
        if key not in self.lists:
            try:
                self.lists[key] = anime.client.get_archive(**filters)
            except Exception:
                return []

        return self.lists[key]

    def run(self, function, items):
        with ThreadPoolExecutor(max_workers=6) as pool:
            return list(pool.map(function, items))

    def compute(self, past):
        recent = sorted(past, key=lambda title: title['date'], reverse=True)[:MAX_SEEDS]
        infos = self.run(self.get_info, [title['id'] for title in recent])

        owned_ids = {title['id'] for title in past}
        owned_names = {base_name(info) for info in infos if info}

        # Ids and rarity of the genres come from the most popular anime
        popular = self.get_list({'order': 'Popolarità'}) + self.get_list({'order': 'Valutazione'})
        genre_ids = {genre['name']: genre['id'] for record in popular for genre in record.get('genres') or [] if isinstance(genre, dict)}
        frequency = Counter(name for record in popular for name in get_genres(record))

        seeds, searches = [], []
        for title, info in zip(recent, infos):
            if info is None:
                continue

            genres = get_genres(info)
            seed = {**title, 'genres': genres, 'related': [record for record in info.get('related') or [] if record.get('id') != info['id']]}
            seeds.append(seed)

            # The two rarest genres of the anime find the ones like it
            specific = sorted((genre for genre in genres if genre in genre_ids), key=lambda genre: (genre in COMMON_GENRES, frequency[genre]))[:2]
            if specific:
                filters = {'genres': [{'id': genre_ids[genre], 'name': genre} for genre in specific]}
                searches += [{**filters, 'order': 'Popolarità'}, {**filters, 'order': 'Valutazione'}]

        # Other seasons and films of the same story, the related list has no image so their page is needed
        related_ids = []
        for seed in seeds:
            others = [record for record in seed['related'] if record['id'] not in owned_ids and record.get('type') in ('TV', 'Movie', 'ONA')]
            related_ids += [record['id'] for record in others[:MAX_RELATED] if record['id'] not in related_ids]

        lists = self.run(self.get_list, searches)
        related_infos = dict(zip(related_ids, self.run(self.get_info, related_ids)))

        candidates = {}
        for record in [record for records in lists for record in records] + [info for info in related_infos.values() if info]:
            if record['id'] not in owned_ids and base_name(record) not in owned_names:
                candidates.setdefault(record['id'], record)

        # One copy for every anime, the original audio unless only the dubbed one is there
        copies = {}
        for record in sorted(candidates.values(), key=lambda record: bool(record.get('dub'))):
            copies.setdefault(base_name(record), record)
        candidates = {record['id']: record for record in copies.values()}

        ranked = {}
        for seed in seeds:
            related = {record['id'] for record in seed['related']}
            ranked[seed['id']] = sorted(
                ((similarity(seed, record, record['id'] in related), record_id) for record_id, record in candidates.items()),
                key=lambda pair: pair[0], reverse=True,
            )

        # Turns between downloads, so different tastes all have their place
        picked = {}
        while len(picked) < MAX_TITLES and any(ranked.values()):
            for seed in seeds:
                queue = ranked[seed['id']]

                while queue and len(picked) < MAX_TITLES:
                    score, record_id = queue.pop(0)

                    if score < MIN_SCORE:
                        queue.clear()
                    elif record_id not in picked:
                        picked[record_id] = seed['name']
                        break

        titles = [format_anime(candidates[record_id], reason=f"Perché hai scaricato {because}") for record_id, because in picked.items()]
        return {'titles': titles, 'based_on': len(past)}
