# 3.12.23 -> 10.12.23

# Class import
from Src.Util.headers import get_headers
from Src.Util.console import console
from Src.Lib.FFmpeg.my_m3u8 import download_m3u8
from Src.Lib.Nas.nas import finalize
from Src.Api.page import get_base_url
from Src.Api.vixcloud import parse_content, get_playlist, get_master_playlist, get_m3u8_url, get_m3u8_audio, get_m3u8_key

# General import
import requests, os, sys
from bs4 import BeautifulSoup

# [func]
def get_iframe(id_title, domain):
    req = requests.get(url = f"{get_base_url(domain)}/iframe/{id_title}", headers = {
        "User-agent": get_headers()
    })

    if req.ok:
        url_embed = BeautifulSoup(req.text, "lxml").find("iframe").get("src")
        req_embed = requests.get(url_embed, headers = {"User-agent": get_headers()}).text

        try:
            return BeautifulSoup(req_embed, "lxml").find("body").find("script").text
        except:
            console.log("[red]Cant play this video, (video not available)")
            sys.exit(0)

    else:
        console.log(f"[red]Error: {req.status_code}")
        sys.exit(0)
    

# [func \ main]
def main_dw_film(id_film, title_name, domain, progress_callback=None, media=None):

    embed_content = get_iframe(id_film, domain)
    json_win_param = parse_content(embed_content)

    m3u8_playlist = get_playlist(json_win_param)
    master_playlist = get_master_playlist(m3u8_playlist)

    m3u8_url = get_m3u8_url(master_playlist)
    m3u8_key = get_m3u8_key(m3u8_url)

    mp4_name = title_name.replace("+", " ").replace(",", "")
    mp4_format = mp4_name + ".mp4"
    mp4_path = os.path.join("videos", mp4_format)

    m3u8_url_audio = get_m3u8_audio(master_playlist)

    if m3u8_url_audio != None:
        console.print("[blue]Use m3u8 audio => [red]True")
        
    download_m3u8(m3u8_index=m3u8_url, m3u8_audio=m3u8_url_audio, m3u8_subtitle=m3u8_url, key=m3u8_key, output_filename=mp4_path, progress_callback=progress_callback)

    # Rename the file and move it to the nas if it is enabled
    return finalize(mp4_path, media, progress_callback)
