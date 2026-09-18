# 18.09.26

# General import
import json, os, threading

# Files written by different threads at the same time would mix
lock = threading.RLock()


def write_json(path, data, **options):
    """
    Save a json file so that it is never left half written.
    The new content goes to a temporary file that takes the place of the old one only when complete,
    the previous version stays in .bak in case the disk loses the new one (power cut).
    """

    temp_path = f"{path}.tmp"
    text = json.dumps(data, ensure_ascii=False, **options)

    with lock:
        with open(temp_path, 'w', encoding='utf-8') as file:
            file.write(text)
            file.flush()
            os.fsync(file.fileno())

        if os.path.exists(path):
            try:
                os.replace(path, f"{path}.bak")
            except OSError:
                pass

        os.replace(temp_path, path)

def read_json(path, default=None):
    """Read a json file, if it is damaged the last good copy is used"""

    with lock:
        for candidate in (path, f"{path}.bak"):
            try:
                with open(candidate, 'r', encoding='utf-8-sig') as file:
                    return json.load(file)
            except FileNotFoundError:
                continue
            except (ValueError, OSError, UnicodeDecodeError):
                continue

    return default
