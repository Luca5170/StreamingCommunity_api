# 18.09.26

# Class import
from Src.Api import anime
from Src.Util.console import console

# General import
import threading, time
from concurrent.futures import ThreadPoolExecutor

# Variable
HOME_CACHE = 10 * 60
EPISODES_GROUP = 100        # Episodes in every tab of the gui

TYPE_LABELS = {'TV': 'Anime', 'Movie': 'Film', 'OVA': 'OVA', 'ONA': 'ONA', 'Special': 'Speciale', 'TV Short': 'Corto'}

# Genres of the site are in english
GENRES = {
    'Action': 'Azione', 'Adventure': 'Avventura', 'Comedy': 'Commedia', 'Drama': 'Drammatico', 'Horror': 'Horror',
    'Mystery': 'Mistero', 'Romance': 'Romantico', 'Sci-Fi': 'Fantascienza', 'Sports': 'Sport', 'Supernatural': 'Soprannaturale',
    'Psychological': 'Psicologico', 'Music': 'Musica', 'School': 'Scolastico', 'Historical': 'Storico', 'Military': 'Militare',
    'Magic': 'Magia', 'Martial Arts': 'Arti marziali', 'Demons': 'Demoni', 'Game': 'Giochi', 'Space': 'Spazio', 'Police': 'Polizieschi',
    'Parody': 'Parodia', 'Vampire': 'Vampiri', 'Super Power': 'Superpoteri', 'Kids': 'Bambini', 'Shounen': 'Shōnen', 'Shoujo': 'Shōjo',
}

# Rows of the home after the top 10 and the new episodes
ROWS = (
    ('airing', 'In corso', {'status': 'In Corso', 'order': 'Popolarità'}),
    ('top_rated', 'I più votati', {'order': 'Valutazione'}),
    ('dubbed', 'Doppiati in italiano', {'dubbed': 1, 'order': 'Popolarità'}),
    ('movies', 'Film', {'type': 'Movie', 'order': 'Popolarità'}),
)


# [ format ]
def format_anime(record, reason=None):
    """Anime in the same shape of the titles of streamingcommunity, so the gui shows both"""

    kind = record.get('type') or 'TV'
    count = int(record.get('episodes_count') or 0)
    single = kind == 'Movie' or count == 1

    title = {
        'id': int(record['id']),

        # Related anime come without slug, the page of the anime has it
        'slug': record.get('slug') or '',
        # Dubbed copies keep the (ITA) of the name, so on the nas they are not mixed with the original
        'name': anime.get_title_name(record),
        'source': 'anime',
        'type': 'movie' if single else 'tv',
        'label': TYPE_LABELS.get(kind, kind),
        'score': record.get('score'),
        'year': str(record['date'])[:4] if record.get('date') else None,
        'episodes_count': count or None,
        'runtime': record.get('episodes_length') if single else None,
        'dub': bool(record.get('dub')),
        'poster': record.get('imageurl'),
        'backdrop': record.get('imageurl_cover') or record.get('cover'),
        'logo': None,
    }

    if reason:
        title['reason'] = reason

    return title

def format_many(records, reason=None):
    return [format_anime(record, reason) for record in records if record.get('id')]

def format_detail(info):
    detail = format_anime(info)
    count = detail['episodes_count'] or 0
    genres = [genre if isinstance(genre, str) else genre.get('name') for genre in info.get('genres') or []]
    credits = (('Studio', info.get('studio')), ('Stato', info.get('status')), ('Episodi', str(count) if count else None))

    detail.update({
        'plot': info.get('plot'),
        'original_name': info.get('title'),
        'genres': [GENRES.get(genre, genre) for genre in genres if genre],
        'credits': [{'label': label, 'value': value.strip()} for label, value in credits if value and value.strip()],

        # Long anime have hundreds of episodes, the gui shows them in groups
        'groups': [] if detail['type'] == 'movie' else [
            {'start': start, 'end': min(start + EPISODES_GROUP - 1, count)} for start in range(1, count + 1, EPISODES_GROUP)
        ],
        'related': format_many([record for record in info.get('related') or [] if record.get('id') != info.get('id')]),
    })
    return detail

def format_episode(episode):
    return {
        'id': int(episode['id']),
        'number': str(episode['number']),
        'name': f"Episodio {episode['number']}",
        'plot': None,
        'duration': None,
        'cover': None,
    }


# [ source ]
class AnimeSource:
    """Home, search and titles of animeunity for the gui"""

    def __init__(self):
        self.lock = threading.Lock()
        self.home_cache = None
        self.home_time = 0

    def home(self):
        with self.lock:
            if self.home_cache is None or time.time() - self.home_time > HOME_CACHE:
                self.home_cache = self.build_home()
                self.home_time = time.time()

            return self.home_cache

    def build_home(self):
        with ThreadPoolExecutor(max_workers=6) as pool:
            page = pool.submit(anime.client.get_home)
            popular = pool.submit(anime.client.get_archive, order='Popolarità')
            rows = [(name, label, pool.submit(anime.client.get_archive, **filters)) for name, label, filters in ROWS]

        def result(future):
            # A list that does not load leaves the others
            try:
                return future.result()
            except Exception as e:
                console.log(f"[yellow]Anime home: a list is not available ({e})")
                return None

        home_page = result(page) or {'featured': [], 'latest': []}

        # Dubbed copies of the same anime would repeat the banner
        featured = [record for record in home_page['featured'] if record.get('imageurl_cover') and not record.get('dub')]

        latest, seen = [], set()
        for episode in home_page['latest']:
            record = episode.get('anime') or {}
            if record.get('id') and record['id'] not in seen:
                seen.add(record['id'])
                latest += format_many([record], reason=f"Nuovo: episodio {episode.get('number')}")

        sliders = [
            {'name': 'top10', 'label': 'Top 10 anime più popolari', 'titles': format_many((result(popular) or [])[:10])},
            {'name': 'latest', 'label': 'Nuovi episodi', 'titles': latest},
        ]
        sliders += [{'name': name, 'label': label, 'titles': format_many(result(future) or [])} for name, label, future in rows]

        # The banners show the plot at once, without asking the page of the anime
        hero = [{**format_anime(record), 'plot': record.get('plot')} for record in featured[:8]]
        return {'hero': hero, 'sliders': [slider for slider in sliders if slider['titles']]}

    def search(self, text):
        return {'results': format_many(anime.client.search(text))}

    def title(self, anime_id):
        info = anime.client.get_info(anime_id)

        # The page of the anime has the related ones with images, without it they are shown with the initials
        try:
            info['related'] = anime.client.get_related(anime_id, info['slug']) or info.get('related')
        except Exception as e:
            console.log(f"[yellow]Anime: images of the related anime not available ({e})")

        return format_detail(info)

    def episodes(self, anime_id, start, end):
        return {'episodes': [format_episode(episode) for episode in anime.client.get_episodes(anime_id, start, end)]}
