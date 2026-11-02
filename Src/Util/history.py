# 18.09.26

# Class import
from Src.Util import storage

# General import
import threading, time

# Variable
HISTORY_FILE = "history.json"
lock = threading.Lock()


def load():
    """Titles downloaded in the past, a series is kept once"""

    # A damaged file falls back to its last good copy, the history is never lost for a power cut
    data = storage.read_json(HISTORY_FILE, {})
    if not isinstance(data, dict):
        data = {}

    # Films and series, anime are imported by themselves
    return {'imported': bool(data.get('imported')), 'imported_anime': bool(data.get('imported_anime')), 'titles': data.get('titles') or []}

def save(data):
    storage.write_json(HISTORY_FILE, data, indent=4)

def get_key(title):
    """Titles of different sites can have the same id"""

    return (title.get('source') or 'sc', title['id'])

def add(title_id, slug, name, kind, year=None, date=None, source='sc'):
    """Remember a downloaded title, the most recent download wins"""

    add_many([{'id': title_id, 'slug': slug, 'name': name, 'type': kind, 'year': year, 'date': date or time.time(), 'source': source}])

def reset_imported():
    """Past downloads are looked for again, known titles are skipped"""

    with lock:
        data = load()
        data['imported'] = data['imported_anime'] = False
        save(data)

def add_many(titles, imported=None, flag='imported'):
    with lock:
        data = load()
        new_keys = {get_key(title) for title in titles}
        data['titles'] = [title for title in data['titles'] if get_key(title) not in new_keys] + titles

        if imported != None:
            data[flag] = imported

        save(data)
