# 18.09.26

# Class import
from Src.Util.headers import get_headers
from Src.Util.console import console
from Src.Lib.FFmpeg.my_m3u8 import download_m3u8
from Src.Lib.Nas.nas import finalize
from Src.Api.vixcloud import parse_content, get_playlist, get_master_playlist, get_m3u8_url, get_m3u8_audio, get_m3u8_key

# General import
import json, os, threading
from urllib.parse import unquote
import requests
from bs4 import BeautifulSoup

# Variable
BASE_URL = "https://www.animeunity.so"
EPISODES_PAGE = 120     # The site gives at most 120 episodes for every request


class AnimeUnity:
    """Session with the site, its api wants the xsrf token of the session"""

    def __init__(self):
        self.lock = threading.Lock()
        self.session = None

    def open(self):
        session = requests.Session()
        session.headers.update({'user-agent': get_headers(), 'referer': f"{BASE_URL}/"})

        response = session.get(BASE_URL, timeout=15)
        response.raise_for_status()

        session.headers['x-xsrf-token'] = unquote(session.cookies.get('XSRF-TOKEN', ''))
        self.session = session

    def request(self, method, path, **kwargs):
        with self.lock:
            if self.session is None:
                self.open()
            session = self.session

        response = session.request(method, f"{BASE_URL}{path}", timeout=20, **kwargs)

        # Laravel answers 419 when the token of the session is expired
        if response.status_code in (401, 419):
            with self.lock:
                self.open()
                session = self.session
            response = session.request(method, f"{BASE_URL}{path}", timeout=20, **kwargs)

        response.raise_for_status()
        return response

    def get_home(self):
        """Featured anime and last episodes, the site puts them inside the page"""

        soup = BeautifulSoup(self.request('GET', '/').text, "lxml")
        carousel = soup.find('the-carousel')
        latest = soup.find('layout-items')

        return {
            'featured': json.loads(carousel['animes']) if carousel else [],
            'latest': json.loads(latest['items-json'])['data'] if latest else [],
        }

    def get_archive(self, **filters):
        body = {'title': False, 'type': False, 'year': False, 'order': False, 'status': False,
                'genres': False, 'offset': 0, 'dubbed': False, 'season': False}
        body.update(filters)
        return self.request('POST', '/archivio/get-animes', json=body).json().get('records') or []

    def search(self, title):
        """Quick search and archive search together, like the search bar of the site"""

        found = {}

        for record in self.request('POST', '/livesearch', data={'title': title}).json().get('records') or []:
            found.setdefault(record['id'], record)

        for record in self.get_archive(title=title):
            found.setdefault(record['id'], record)

        return list(found.values())

    def get_info(self, anime_id):
        return self.request('GET', f'/info_api/{anime_id}/').json()

    def get_episodes(self, anime_id, start, end):
        """Episodes from number start to end, asked in pages of the size allowed by the site"""

        episodes = []

        for first in range(start, end + 1, EPISODES_PAGE):
            last = min(first + EPISODES_PAGE - 1, end)
            response = self.request('GET', f'/info_api/{anime_id}/1', params={'start_range': first, 'end_range': last})
            episodes += response.json().get('episodes') or []

        return episodes

    def get_embed_url(self, episode_id):
        return self.request('GET', f'/embed-url/{episode_id}').text.strip()

client = AnimeUnity()


# [func]
def get_title_name(anime):
    """Italian title if the site has it, then the english one used by the site"""

    return anime.get('title_it') or anime.get('title_eng') or anime.get('title') or anime.get('slug')

def get_player_script(embed_url):
    """Script of the vixcloud player with the parameters of the video"""

    response = requests.get(embed_url, headers={'user-agent': get_headers()}, timeout=20)
    response.raise_for_status()
    return BeautifulSoup(response.text, "lxml").find("body").find("script").text


# [func \ main]
def dw_episode(anime_id, slug, episode_id, episode_number, progress_callback=None, media=None):
    console.print(f"[green]Download anime: [blue]{slug} [green]=> [purple]episode {episode_number}")

    # Same vixcloud player of streamingcommunity
    embed_content = get_player_script(client.get_embed_url(episode_id))
    json_win_param = parse_content(embed_content)

    m3u8_playlist = get_playlist(json_win_param)
    master_playlist = get_master_playlist(m3u8_playlist)

    m3u8_url = get_m3u8_url(master_playlist)
    m3u8_key = get_m3u8_key(m3u8_url)

    mp4_path = os.path.join("videos", "anime", slug, f"{slug}_E{episode_number}.mp4")
    m3u8_url_audio = get_m3u8_audio(master_playlist)

    if m3u8_url_audio != None:
        console.print("[blue]Use m3u8 audio => [red]True")

    # Animeunity burns the italian subtitles into the video, there is no subtitle track to look for
    console.print("[blue]Subtitles => [green]already in the video")
    download_m3u8(m3u8_index=m3u8_url, m3u8_audio=m3u8_url_audio, key=m3u8_key, output_filename=mp4_path, progress_callback=progress_callback)

    # Rename the file and move it to the nas if it is enabled
    return finalize(mp4_path, media, progress_callback)
