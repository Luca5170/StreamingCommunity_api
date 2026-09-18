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

    return {'imported': bool(data.get('imported')), 'titles': data.get('titles') or []}

def save(data):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4, ensure_ascii=False)

def add(title_id, slug, name, kind, year=None, date=None):
    """Remember a downloaded title, the most recent download wins"""

    add_many([{'id': title_id, 'slug': slug, 'name': name, 'type': kind, 'year': year, 'date': date or time.time()}])

def add_many(titles, imported=None):
    with lock:
        data = load()
        new_ids = {title['id'] for title in titles}
        data['titles'] = [title for title in data['titles'] if title['id'] not in new_ids] + titles

        if imported != None:
            data['imported'] = imported

        save(data)
