# 18.09.26

# Class import
import Src.Api.page as Page
from Src.Lib.Nas import nas
from Src.Util import history, videos
from Src.Util.console import console

# General import
import math, os, re, threading, time, unicodedata
from concurrent.futures import ThreadPoolExecutor
from stat import S_ISDIR

# Variable
MAX_TITLES = 20         # Titles in the row
MAX_SEEDS = 10          # Recent downloads used to find new titles
SHORTLIST = 8           # Candidates of every download that are looked in detail
MIN_SCORE = 2.0         # Below this a title is not similar enough to be proposed
CACHE_TIME = 6 * 3600

# Tags about the production of a film, they say nothing about its story
STOP_KEYWORDS = {'aftercreditsstinger', 'duringcreditsstinger', 'woman director', 'live action and animation', 'short film'}


# [ similarity ]
def normalize(text):
    text = unicodedata.normalize('NFKD', str(text or '')).encode('ascii', 'ignore').decode().lower()
    return ' '.join(re.sub(r'[^a-z0-9]+', ' ', text).split())

def get_tags(title):
    genres = {genre['name'] for genre in title.get('genres') or []}
    keywords = {keyword['name'] for keyword in title.get('keywords') or []} - STOP_KEYWORDS
    return genres, keywords

def similarity(seed, title):
    """How much a title looks like a past download, mostly by the keywords of the story"""

    genres, keywords = get_tags(title)
    keyword_sim = len(seed['keywords'] & keywords) / math.sqrt(max(1, len(seed['keywords'])) * max(1, len(keywords)))
    genre_sim = len(seed['genres'] & genres) / max(1, len(seed['genres'] | genres))
    rating = float(title.get('score') or 6) / 10

    return keyword_sim * 3 + genre_sim * 2 + rating * 0.3 + (0.3 if title['type'] == seed['type'] else 0)


# [ past downloads ]
def get_past():
    """Films and series of streamingcommunity, anime have their own history"""

    return [title for title in history.load()['titles'] if (title.get('source') or 'sc') == 'sc']

def parse_name(name):
    """Title and year from 'Mary Poppins (1964)', or the slug of old names like 'x-men-linizio.mp4'"""

    name = name[:-4] if name.endswith('.mp4') else name
    match = re.match(r'^(.*) \((\d{4})\)$', name)

    if match:
        return {'name': match.group(1), 'year': match.group(2)}
    if re.fullmatch(r'[a-z0-9+-]+', name):
        return {'name': name.replace('-', ' '), 'slug': name}

    return {'name': name}

def list_downloads():
    """Names of the titles already downloaded, in the videos folder and on the nas"""

    found = []

    def add(name, kind, is_folder, date):
        if name.startswith('.') or name in ('subtitle', 'anime') or name.endswith(('.parte', '.audio.mp4')):
            return
        if not is_folder and not name.endswith('.mp4'):
            return
        if kind == 'tv' and not is_folder:
            return

        found.append({**parse_name(name), 'type': kind, 'date': date})

    # Films are files, series are folders with their episodes
    if os.path.isdir(videos.get_folder()):
        for entry in os.scandir(videos.get_folder()):
            add(entry.name, 'tv' if entry.is_dir() else 'movie', entry.is_dir(), entry.stat().st_mtime)

    config = nas.load_config()
    if nas.is_enabled(config):
        with nas.open_sftp(config) as sftp:
            for path, kind in ((config['film_path'], 'movie'), (config['tv_path'], 'tv')):
                try:
                    entries = sftp.listdir_attr(path) if path else []
                except IOError:
                    continue

                for entry in entries:
                    add(entry.filename, kind, S_ISDIR(entry.st_mode), entry.st_mtime)

    return found

def find_title(site, item):
    """The title of the site with this name, the year decides between titles with the same name"""

    titles = site.request(lambda domain, version: Page.get_search(item['name'], domain, version))['titles']
    same_name = []

    for title in titles:
        if item.get('slug') and title['slug'] == item['slug']:
            return title

        if normalize(title['name']) == normalize(item['name']) and title['type'] == item['type']:
            if item.get('year') and (title.get('last_air_date') or '')[:4] == item['year']:
                return title
            same_name.append(title)

    return same_name[0] if same_name else None

def import_downloads(site):
    """At the first start the past downloads are taken from the names of the files"""

    try:
        found = list_downloads()
    except nas.NasError as e:
        console.log(f"[yellow]Recommendations: nas not reachable, past downloads imported later ({e})")
        return

    def match(item):
        try:
            return find_title(site, item)
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=6) as pool:
        titles = list(pool.map(match, found))

    known = {title['id'] for title in get_past()}
    imported = {}

    for item, title in zip(found, titles):
        if title and title['id'] not in known:
            previous = imported.get(title['id'])
            if previous is None or item['date'] > previous['date']:
                imported[title['id']] = {
                    'id': title['id'],
                    'slug': title['slug'],
                    'name': title['name'],
                    'type': title['type'],
                    'year': (title.get('last_air_date') or '')[:4] or None,
                    'date': item['date'],
                    'source': 'sc',
                }

    history.add_many(list(imported.values()), imported=True)
    console.log(f"[green]Recommendations: {len(imported)} past downloads imported")


# [ recommendations ]
class Recommender:
    """Titles similar to the past downloads, every download proposes its own ones"""

    def __init__(self, site, format_title):
        self.site = site
        self.format_title = format_title
        self.lock = threading.Lock()
        self.pages = {}         # Pages of the titles, they change rarely
        self.result = None
        self.result_key = None
        self.result_time = 0

    def get(self):
        with self.lock:
            if not history.load()['imported']:
                import_downloads(self.site)

            past = get_past()
            key = tuple(sorted((title['id'], title['date']) for title in past))

            if self.result is None or key != self.result_key or time.time() - self.result_time > CACHE_TIME:
                self.result = self.compute(past)
                self.result_key, self.result_time = key, time.time()

            return self.result

    def get_page(self, title):
        if title['id'] not in self.pages:
            try:
                self.pages[title['id']] = self.site.request(lambda domain, version: Page.get_title(title['id'], title['slug'], domain, version))
            except Exception:
                return None

        return self.pages[title['id']]

    def get_pages(self, titles):
        with ThreadPoolExecutor(max_workers=6) as pool:
            return list(pool.map(self.get_page, titles))

    def compute(self, past):
        owned = {title['id'] for title in past}
        seeds = []
        candidates, proposals = {}, {}

        # Every recent download proposes the titles the site lists with it
        recent = sorted(past, key=lambda title: title['date'], reverse=True)[:MAX_SEEDS]
        for title, props in zip(recent, self.get_pages(recent)):
            if props is None:
                continue

            genres, keywords = get_tags(props['title'])
            seed = {**title, 'genres': genres, 'keywords': keywords}
            seeds.append(seed)
            proposals[seed['id']] = {}

            for slider in props.get('sliders') or []:
                weight = 2 if slider.get('name') == 'related' else 0.6

                for position, item in enumerate(slider.get('titles') or []):
                    if item['id'] in owned:
                        continue

                    candidates[item['id']] = item
                    score = weight * (1 - position / 40) + float(item.get('score') or 6) / 20
                    proposals[seed['id']][item['id']] = max(score, proposals[seed['id']].get(item['id'], 0))

        # Only the best proposals of every download are looked in detail
        shortlist = []
        for seed in seeds:
            best = sorted(proposals[seed['id']].items(), key=lambda pair: pair[1], reverse=True)[:SHORTLIST]
            shortlist += [item_id for item_id, _ in best if item_id not in shortlist]

        details = dict(zip(shortlist, self.get_pages([candidates[item_id] for item_id in shortlist])))
        details = {item_id: props for item_id, props in details.items() if props}

        ranked = {
            seed['id']: sorted(((similarity(seed, props['title']), item_id) for item_id, props in details.items()), reverse=True)
            for seed in seeds
        }

        # Turns between downloads, so different tastes all have their place
        picked = {}
        while len(picked) < MAX_TITLES and any(ranked.values()):
            for seed in seeds:
                queue = ranked[seed['id']]

                while queue and len(picked) < MAX_TITLES:
                    score, item_id = queue.pop(0)

                    if score < MIN_SCORE:
                        queue.clear()
                    elif item_id not in picked:
                        picked[item_id] = seed['name']
                        break

        titles = [
            {**self.format_title(details[item_id]['title'], details[item_id]['cdn_url']), 'reason': f"Perché hai scaricato {because}"}
            for item_id, because in picked.items()
        ]

        return {'titles': titles, 'based_on': len(past)}
