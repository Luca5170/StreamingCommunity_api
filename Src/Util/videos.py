# 01.11.26

# Class import
from Src.Util import storage
from Src.Util.errors import AppError

# General import
import os, re, tempfile

# Variable
CONFIG_FILE = "videos.json"
DEFAULT_FOLDER = "videos"
IN_DOCKER = os.path.exists('/.dockerenv')


# [ config ]
def load_path():
    """Folder written in the settings, empty when it is the default one"""

    saved = storage.read_json(CONFIG_FILE, {})
    path = saved.get('path') if isinstance(saved, dict) else None
    return path if isinstance(path, str) else ''

def get_folder():
    return load_path() or DEFAULT_FOLDER

def save_path(path):
    """Save the folder after checking that it can be written, an empty one goes back to the default"""

    # The copy of a path from the explorer has the quotes
    path = os.path.expandvars(os.path.expanduser(str(path or '').strip().strip('"')))

    if path:
        if IN_DOCKER:
            check_docker(path)

        path = os.path.abspath(path)
        os.makedirs(path, exist_ok=True)
        tempfile.TemporaryFile(dir=path).close()

    storage.write_json(CONFIG_FILE, {'path': path}, indent=4)
    return path

def check_docker(path):
    """The container sees only the folders linked in docker-compose.yml, the files of the others are lost with it"""

    if re.match(r'^([A-Za-z]:|\\\\)', path):
        raise AppError("Questo è un percorso di Windows, il container non lo vede: collega la cartella in docker-compose.yml (per esempio - E:/Film:/data/film) e qui scrivi /data/film")

    current = os.path.abspath(path)

    while current != os.path.dirname(current):
        if os.path.ismount(current):
            return
        current = os.path.dirname(current)

    raise AppError("Questa cartella è dentro il container e sparirebbe con lui: usa /data oppure collega una cartella del PC in docker-compose.yml")


# [ paths ]
def stable_path(path):
    """Path of a video as it would be in the default folder, it stays the same after changing the folder"""

    try:
        return os.path.join(DEFAULT_FOLDER, os.path.relpath(path, get_folder()))
    except ValueError:
        # On windows there is no relative path between two disks
        return path
