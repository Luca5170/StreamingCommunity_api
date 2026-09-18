# 3.12.23 -> 10.12.23

# Class import
from Src.Util.headers import get_headers
from Src.Util.console import console, msg
from Src.Lib.FFmpeg.my_m3u8 import download_m3u8
from Src.Lib.Nas.nas import finalize
from Src.Api.page import get_base_url, get_page_props, get_title
from Src.Api.vixcloud import parse_content, get_playlist, get_master_playlist, get_m3u8_url, get_m3u8_audio, get_m3u8_key

# General import
import requests, os, sys
from bs4 import BeautifulSoup


# [func]
def get_token(id_tv, domain):
    session = requests.Session()
    session.get(f"{get_base_url(domain)}/watch/{id_tv}", headers={'user-agent': get_headers()})
    return session.cookies['XSRF-TOKEN']

def get_info_tv(id_film, title_name, site_version, domain):

    try:
        return get_title(id_film, title_name, domain, site_version)['title']['seasons_count']
    except requests.HTTPError as e:
        console.log(f"[red]Error: {e.response.status_code}")
        sys.exit(0)

def get_season(tv_id, tv_name, domain, version, n_season, token=None):
    headers = {'referer': f'{get_base_url(domain)}/titles/{tv_id}-{tv_name}'}

    if token != None:
        headers['x-xsrf-token'] = token

    return get_page_props(f'{get_base_url(domain)}/titles/{tv_id}-{tv_name}/season-{n_season}', version, headers=headers)

def get_info_season(tv_id, tv_name, domain, version, token, n_stagione):

    try:
        episodes = get_season(tv_id, tv_name, domain, version, n_stagione, token)['loadedSeason']['episodes']
        return [{'id': ep['id'], 'n': ep['number'], 'name': ep['name']} for ep in episodes]
    except requests.HTTPError as e:
        console.log(f"[red]Error: {e.response.status_code}")
        sys.exit(0)

def get_iframe(tv_id, ep_id, domain, token):
    req = requests.get(f'{get_base_url(domain)}/iframe/{tv_id}', params={'episode_id': ep_id, 'next_episode': '1'}, cookies={'XSRF-TOKEN': token}, headers={
        'referer': f'{get_base_url(domain)}/watch/{tv_id}?e={ep_id}',
        'user-agent': get_headers()
    })

    # Change user agent m3u8
    custom_headers_req = {
        'referer': f'{get_base_url(domain)}/watch/{tv_id}?e={ep_id}',
        'user-agent': get_headers()
    }

    if req.ok:
        url_embed = BeautifulSoup(req.text, "lxml").find("iframe").get("src")
        req_embed = requests.get(url_embed, headers = {"User-agent": get_headers()}).text
        return BeautifulSoup(req_embed, "lxml").find("body").find("script").text
    else:
        console.log(f"[red]Error: {req.status_code}")
        sys.exit(0)


# [func \ main]
def dw_single_ep(tv_id, eps, index_ep_select, domain, token, tv_name, season_select, progress_callback=None, media=None):

    console.print(f"[green]Download ep: [blue]{eps[index_ep_select]['n']} [green]=> [purple]{eps[index_ep_select]['name']}")

    if media != None:
        media = {**media, 'season': season_select, 'episode_number': eps[index_ep_select]['n'], 'episode_name': eps[index_ep_select]['name']}
    embed_content = get_iframe(tv_id, eps[index_ep_select]['id'], domain, token)
    json_win_param = parse_content(embed_content)

    m3u8_playlist = get_playlist(json_win_param)
    master_playlist = get_master_playlist(m3u8_playlist)

    m3u8_url = get_m3u8_url(master_playlist)
    m3u8_key = get_m3u8_key(m3u8_url)

    mp4_name = f"{tv_name.replace('+', '_')}_S{str(season_select).zfill(2)}E{str(index_ep_select+1).zfill(2)}"
    mp4_format = f"{mp4_name}.mp4"
    mp4_path = os.path.join("videos",tv_name, mp4_format)

    m3u8_url_audio = get_m3u8_audio(master_playlist)

    if m3u8_url_audio != None:
        console.print("[blue]Use m3u8 audio => [red]True")

    download_m3u8(m3u8_index=m3u8_url, m3u8_audio=m3u8_url_audio, m3u8_subtitle=m3u8_playlist, key=m3u8_key, output_filename=mp4_path, progress_callback=progress_callback)

    # Rename the file and move it to the nas if it is enabled
    return finalize(mp4_path, media, progress_callback)
    
def main_dw_tv(tv_id, tv_name, version, domain, media=None):

    token = get_token(tv_id, domain)

    num_season_find = get_info_tv(tv_id, tv_name, version, domain)
    console.print("\n[green]Insert season [red]number [yellow]or [red](*) [green]to download all seasons [yellow]or [red][1-2] [green]for a range of season")
    console.print(f"\n[blue]Season find: [red]{num_season_find}")
    season_select = str(msg.ask("\n[green]Insert season number: "))
    if "[" in season_select:
        start, end = map(int, season_select[1:-1].split('-'))
        result = list(range(start, end + 1))
        for n_season in result:
            eps = get_info_season(tv_id, tv_name, domain, version, token, n_season)
            for ep in eps:
                dw_single_ep(tv_id, eps, int(ep['n'])-1, domain, token, tv_name, n_season, media=media)
                print("\n")
    elif season_select != "*":
        season_select = int(season_select)
        if 1 <= season_select <= num_season_find:
            eps = get_info_season(tv_id, tv_name, domain, version, token, season_select)

            for ep in eps:
                console.print(f"[green]Ep: [blue]{ep['n']} [green]=> [purple]{ep['name']}")
            index_ep_select = str(msg.ask("\n[green]Insert ep [red]number [yellow]or [red](*) [green]to download all ep [yellow]or [red][1-2] [green]for a range of ep: "))

            # Download range []
            if "[" in index_ep_select:
                start, end = map(int, index_ep_select[1:-1].split('-'))
                result = list(range(start, end + 1))

                for n_randge_ep in result:
                    index_ep_select = int(n_randge_ep)
                    dw_single_ep(tv_id, eps, n_randge_ep-1, domain, token, tv_name, season_select, media=media)

            # Download single ep
            elif index_ep_select != "*":
                if 1 <= int(index_ep_select) <= len(eps):
                    index_ep_select = int(index_ep_select) - 1
                    dw_single_ep(tv_id, eps, index_ep_select, domain, token, tv_name, season_select, media=media)
                else:
                    console.print("[red]Wrong index for ep")

            # Download all
            else:
                for ep in eps:
                    dw_single_ep(tv_id, eps, int(ep['n'])-1, domain, token, tv_name, season_select, media=media)
                    print("\n")

        else:
            console.print("[red]Wrong index for season")
    else:
        for n_season in range(1, num_season_find+1):
            eps = get_info_season(tv_id, tv_name, domain, version, token, n_season)
            for ep in eps:
                dw_single_ep(tv_id, eps, int(ep['n'])-1, domain, token, tv_name, n_season, media=media)
                print("\n")
            
