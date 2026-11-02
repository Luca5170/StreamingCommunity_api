# 28.10.26

# Class import
from Src.Util import storage

# General import
import threading, time

# Variable
PROGRESS_FILE = "progress.json"
MIN_RESUME = 10         # Seconds: before this the video starts again from the beginning
MAX_ENTRIES = 300       # The oldest positions go away, a few hundred videos are more than enough
MAX_CONTINUE = 20
lock = threading.Lock()


# [ positions ]
def get_key(entry):
    """Ids of the two sites can be the same number, a film has no episode"""

    return (entry.get('source') or 'sc', entry.get('id'), entry.get('episode_id'))

def is_finished(position, duration):
    """The end credits count as seen: the last 5%, or the last 45 seconds"""

    return duration > 0 and position > duration / 2 and (position >= duration * 0.95 or duration - position <= 45)

def can_resume(entry):
    return not entry.get('finished') and (entry.get('position') or 0) >= MIN_RESUME

def load():
    """Where the films and the episodes watched in the app have been stopped"""

    entries = storage.read_json(PROGRESS_FILE, [])
    return [entry for entry in entries if isinstance(entry, dict) and isinstance(entry.get('id'), int)] if isinstance(entries, list) else []

def store(entries):
    entries = sorted(entries, key=lambda entry: entry.get('updated_at') or 0, reverse=True)[:MAX_ENTRIES]
    storage.write_json(PROGRESS_FILE, entries, indent=2)
    return entries

def save(entry, next_entry=None):
    """
    Remember where the video is, a video watched again comes back in the row of the home.
    Seen to the end, the episode after it is proposed in its place.
    """

    with lock:
        entry = {**entry, 'updated_at': time.time(), 'dismissed': False, 'up_next': False}
        entry['finished'] = is_finished(entry['position'], entry['duration'])

        entries = [other for other in load() if get_key(other) != get_key(entry)] + [entry]
        if entry['finished'] and next_entry:
            entries = add_next(entries, next_entry)

        return store(entries)

def add_next(entries, entry):
    """The next episode goes in the home, without losing a position already saved for it"""

    existing = next((other for other in entries if get_key(other) == get_key(entry)), None)
    others = [other for other in entries if get_key(other) != get_key(entry)]

    if existing and can_resume(existing):
        return others + [{**existing, 'updated_at': time.time() + 0.001, 'dismissed': False}]

    fresh = {**entry, 'position': 0, 'duration': (existing or {}).get('duration') or 0, 'finished': False,
             'up_next': True, 'dismissed': False, 'updated_at': time.time() + 0.001}
    return others + [fresh]

def dismiss(source, title_id):
    """Out of the row of the home, the episodes stay marked as seen"""

    with lock:
        return store([{**entry, 'dismissed': True} if (entry.get('source') or 'sc', entry['id']) == (source, title_id) else entry
                      for entry in load()])

def continue_list(entries, source):
    """For every title its last film or episode, the ones to go on with: stopped in the middle, or the next episode"""

    latest = {}
    for entry in entries:
        if (entry.get('source') or 'sc') != source:
            continue
        current = latest.get(entry['id'])
        if current is None or (entry.get('updated_at') or 0) > (current.get('updated_at') or 0):
            latest[entry['id']] = entry

    found = [entry for entry in latest.values() if not entry.get('dismissed') and (entry.get('up_next') or can_resume(entry))]
    return sorted(found, key=lambda entry: entry.get('updated_at') or 0, reverse=True)[:MAX_CONTINUE]

def view(entries=None):
    """All the positions for the pages of the titles, and the rows of the two homes"""

    entries = load() if entries is None else entries
    return {
        'entries': entries,
        'continue': {source: continue_list(entries, source) for source in ('sc', 'anime')},
    }
