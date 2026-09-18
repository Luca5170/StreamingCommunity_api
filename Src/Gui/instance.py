# 18.09.26

# Class import
from Src.Util import storage

# General import
import os, sys
import requests

# Variable
LOCK_FILE = "sc_downloader.lock"
INSTANCE_FILE = "sc_downloader.instance.json"
lock_handle = None


def acquire():
    """
    True if this is the only program open in this folder.
    The lock belongs to the process: if the program dies (crash, power cut) the system frees it by itself.
    """

    global lock_handle

    try:
        handle = open(LOCK_FILE, 'a+')
    except OSError:
        return True     # Without the lock the program works the same

    try:
        if sys.platform == 'win32':
            import msvcrt
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    except OSError:
        handle.close()
        return False

    lock_handle = handle
    return True

def save_url(url):
    try:
        storage.write_json(INSTANCE_FILE, {'url': url, 'pid': os.getpid()})
    except OSError:
        pass

def get_running_url():
    """Address of the program already open, if it answers"""

    saved = storage.read_json(INSTANCE_FILE, {})
    url = saved.get('url') if isinstance(saved, dict) else None

    if not url:
        return None

    try:
        response = requests.get(f"{url}/api/status", timeout=3)
        return url if response.ok and 'site_name' in response.json() else None
    except (requests.RequestException, ValueError):
        return None
