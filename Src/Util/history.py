# 18.09.26

# General import
import json, threading, time

# Variable
HISTORY_FILE = "history.json"
lock = threading.Lock()


def load():
    """Titles downloaded in the past, a series is kept once"""

    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as file:
            data = json.load(file)
    except (FileNotFoundError, ValueError):
        data = {}

    # Films and series, anime are imported by themselves
    return {'imported': bool(data.get('imported')), 'imported_anime': bool(data.get('imported_anime')), 'titles': data.get('titles') or []}

def save(data):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

def get_key(title):
    """Titles of different sites can have the same id"""

    return (title.get('source') or 'sc', title['id'])

def add(title_id, slug, name, kind, year=None, date=None, source='sc'):
    """Remember a downloaded title, the most recent download wins"""

    add_many([{'id': title_id, 'slug': slug, 'name': name, 'type': kind, 'year': year, 'date': date or time.time(), 'source': source}])

def add_many(titles, imported=None, flag='imported'):
    with lock:
        data = load()
        new_keys = {get_key(title) for title in titles}
        data['titles'] = [title for title in data['titles'] if get_key(title) not in new_keys] + titles

        if imported != None:
            data[flag] = imported

        save(data)
