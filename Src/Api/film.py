# 3.12.23 -> 10.12.23

# Class import
from Src.Util.headers import get_headers
from Src.Util.console import console
from Src.Util.errors import DownloadError, describe_response, get_host, step
from Src.Util import http, videos
from Src.Lib.FFmpeg.my_m3u8 import download_m3u8
from Src.Lib.Nas.nas import finalize
from Src.Api.page import get_base_url
from Src.Api.vixcloud import parse_content, get_playlist, get_master_playlist, get_m3u8_url, get_m3u8_audio, get_m3u8_key, get_subtitles

# General import
import requests, os, sys
from bs4 import BeautifulSoup

# [func]
def get_iframe(id_title, domain):
    req = http.get(f"{get_base_url(domain)}/iframe/{id_title}", headers={"User-agent": get_headers()})

    if not req.ok:
        # A title that is not on the site is not there also at the next attempt
        raise DownloadError(describe_response(req, "Il sito"), retry=req.status_code not in (404, 410))

    iframe = BeautifulSoup(req.text, "lxml").find("iframe")
    if iframe is None or not iframe.get("src"):
        raise DownloadError("La pagina del film non contiene il player: il video non è disponibile sul sito", retry=False)

    return get_player_script(iframe.get("src"))

def get_player_script(url_embed):
    """Script of the vixcloud player with the parameters of the video"""

    req_embed = http.get(url_embed, headers={"User-agent": get_headers()})

    if not req_embed.ok:
        raise DownloadError(describe_response(req_embed, "Il player"))

    body = BeautifulSoup(req_embed.text, "lxml").find("body")
    script = body.find("script") if body else None

    if script is None:
        raise DownloadError(f"Il player {get_host(url_embed)} ha risposto con una pagina senza video, forse è cambiato")

    return script.text
    

# [func \ main]
def main_dw_film(id_film, title_name, domain, progress_callback=None, media=None):

    with step("Ricerca del film sul sito"):
        embed_content = get_iframe(id_film, domain)

    with step("Lettura del player"):
        json_win_param = parse_content(embed_content)

        m3u8_playlist = get_playlist(json_win_param)
        master_playlist = get_master_playlist(m3u8_playlist)

        m3u8_url = get_m3u8_url(master_playlist)
        m3u8_key = get_m3u8_key(m3u8_url)

    mp4_name = title_name.replace("+", " ").replace(",", "")
    mp4_format = mp4_name + ".mp4"
    mp4_path = os.path.join(videos.get_folder(), mp4_format)

    m3u8_url_audio = get_m3u8_audio(master_playlist)

    if m3u8_url_audio != None:
        console.print("[blue]Use m3u8 audio => [red]True")

    download_m3u8(m3u8_index=m3u8_url, m3u8_audio=m3u8_url_audio, subtitles=get_subtitles(master_playlist), key=m3u8_key, output_filename=mp4_path, progress_callback=progress_callback)

    # Rename the file and move it to the nas if it is enabled
    with step("Salvataggio del file"):
        return finalize(mp4_path, media, progress_callback)
