# 10.12.23 -> 31.01.24

# Class
import Src.Api.page as Page
from Src.Api.film import main_dw_film as download_film
from Src.Api.tv import main_dw_tv as download_tv
from Src.Util.message import msg_start
from Src.Util.console import console, msg
from Src.Util.os import remove_folder
from Src.Util import history
from Src.Upload.update import main_update
from Src.Lib.FFmpeg.installer import check_ffmpeg

from Src.Util.errors import DownloadError, describe

# Import
import os, sys

# [ main ]
def initialize():

    if sys.version_info < (3, 11):
        console.log("Install python version > 3.11")
        sys.exit(0)

    # Segments of the downloads to resume are kept, only half built files are removed
    remove_folder(os.path.join("tmp", "output"))
    msg_start()

    try:
        main_update()
    except Exception as e:
        console.print(f"[blue]Req github [white]=> [red]Failed: {e}")

    check_ffmpeg()
    print("\n")

def download_title(selected_title, site_version, domain):
    """Download a movie or a tv show, name and year are used for the file and the nas"""

    media = {'name': selected_title['name'], 'year': selected_title.get('year'), 'type': selected_title['type']}

    # A title that fails does not stop the others, what is saved is used by the next attempt
    try:
        if selected_title['type'] == "movie":
            console.print(f"[green]\nMovie select: {selected_title['name']}")
            download_film(selected_title['id'], selected_title['slug'], domain, media=media)
        else:
            console.print(f"[green]\nTv select: {selected_title['name']}")
            download_tv(selected_title['id'], selected_title['slug'], site_version, domain, media=media)

    except (DownloadError, OSError) as e:
        console.print(f"[red]Download non riuscito: {describe(e)}")
        return

    # Used by the recommendations of the gui
    history.add(selected_title['id'], selected_title['slug'], selected_title['name'], selected_title['type'], selected_title.get('year'))

def main():

    initialize()
    domain, site_version = Page.domain_version()

    film_search = msg.ask("\n[blue]Insert word to search in all site: ").strip()
    db_title = Page.search(film_search, domain, site_version)
    Page.display_search_results(db_title)

    if len(db_title) != 0:
        console.print(f"\n[blue]Total result: {len(db_title)}")
        console.print(
            "\n[green]Insert index [red]number [yellow]or [red][1-2] [green]for a range of movies/tv [yellow]or [red][1,3,5] [green]to select discontinued movie/tv"
        )
        console.print("\n[red]In case of tv show you will have to choose season and episode to download")
        index_select = str(msg.ask("\n[blue]Index to download: "))
        if index_select.isnumeric():
            index_select = int(index_select)
            if 0 <= index_select <= len(db_title) - 1:
                download_title(db_title[index_select], site_version, domain)
            else:
                console.print("[red]Wrong index for selection")
        elif "[" in index_select:
            if "-" in index_select:
                start, end = map(int, index_select[1:-1].split('-'))
                result = list(range(start, end + 1))
                for n in result:
                    download_title(db_title[n], site_version, domain)
            elif "," in index_select:
                result = list(map(int, index_select[1:-1].split(',')))
                for n in result:
                    download_title(db_title[n], site_version, domain)
            else:
                console.print("[red]Wrong index for selection")
    else:
        console.print("[red]Cant find a single element")

    console.print("[red]Done")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        # The stopped download removes its segments by itself, the ones of the gui to resume stay
        remove_folder(os.path.join("tmp", "output"))
        console.print("\n[red]Download stopped, temporary files removed")
