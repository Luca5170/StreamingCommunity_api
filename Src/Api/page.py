# 10.12.23

# Class import
from Src.Util.headers import get_headers
from Src.Util.console import console
from Src.Util.errors import SiteError, describe, redirected_to

# General import
import requests, sys, json, re
from bs4 import BeautifulSoup

SITE_NAME = "streamingcommunityz"      # Used when only the extension is given

def get_host(domain):
    """
    Full address of the site, from what the user writes: a whole domain (streamingcommunityz.shiksha, a new name),
    a pasted link, or only the extension (shiksha) as the old versions saved it
    """

    host = re.sub(r'^[a-z][a-z0-9+.-]*://', '', (domain or '').strip().lower())
    host = re.split(r'[/?#]', host)[0].strip('.')
    host = host[4:] if host.startswith('www.') else host

    return host if '.' in host or not host else f"{SITE_NAME}.{host}"

def get_site_url(domain):
    return f"https://{get_host(domain)}"

def get_base_url(domain):
    return f"{get_site_url(domain)}/it"

def get_version(domain):
    """Inertia version of the site, the errors say why the domain does not work"""

    site = get_host(domain)
    site_request = requests.get(get_site_url(domain), headers={'user-agent': get_headers()}, timeout=15)
    site_request.raise_for_status()

    app = BeautifulSoup(site_request.text, "lxml").find("div", {"id": "app"})

    if app is None or not app.get("data-page"):
        # A domain that is no more of the site often sends to another one
        moved = redirected_to(site_request)
        if moved:
            raise SiteError(f"{site} rimanda a {moved}, che non è il sito: l'indirizzo è cambiato o il provider blocca il sito")
        raise SiteError(f"{site} risponde, ma non con la pagina del sito: l'indirizzo potrebbe essere cambiato o il provider blocca il sito")

    try:
        return json.loads(app.get("data-page"))['version']
    except (ValueError, KeyError, TypeError):
        raise SiteError(f"La pagina di {site} è cambiata: il programma non trova la versione del sito")

def get_page_props(url, version, params=None, headers=None):
    """Make inertia req to a page of the site and return its props, raise if it fails"""

    req = requests.get(url, params=params, timeout=15, headers={
        'user-agent': get_headers(),
        'x-inertia': 'true',
        'x-inertia-version': version,
        **(headers or {})
    })
    req.raise_for_status()
    return req.json()['props']

def get_home(domain, version):
    return get_page_props(get_base_url(domain), version)

def get_search(title_search, domain, version):
    return get_page_props(f"{get_base_url(domain)}/search", version, params={'q': title_search})

def get_title(title_id, slug, domain, version):
    return get_page_props(f"{get_base_url(domain)}/titles/{title_id}-{slug}", version)

def domain_version():
    console.print("[green]Get rules ...")
    req_repo = None
    try:
        with open('data.json', 'r') as file:
            req_repo = json.load(file)
    except FileNotFoundError:
        req_repo = {"domain": ""}
    domain = req_repo['domain']

    while True:
        if not domain:
            domain = get_host(input(f"Insert domain (es. {SITE_NAME}.shiksha): "))
            req_repo['domain'] = domain
            with open('data.json', 'w') as file:
                json.dump(req_repo, file)
        console.print(f"[blue]Test domain [white]=> [red]{domain}")
        try:
            version = get_version(domain)
            console.print(f"[blue]Rules [white]=> [red].{domain}")
            return domain, version
        
        except Exception as e:
            console.log(f"[red]{describe(e)}")
            domain = None
            continue

def search(title_search, domain, version):

    try:
        titles = get_search(title_search, domain, version)['titles']
    except requests.HTTPError as e:
        console.log(f"[red]Error: {e.response.status_code}")
        sys.exit(0)
    except (ValueError, KeyError):
        console.log("[red]Invalid search response")
        sys.exit(0)

    return [{
        'name': title['name'],
        'type': title['type'],
        'id': title['id'],
        'slug': title['slug'],
        'year': (title.get('release_date') or title.get('last_air_date') or '')[:4] or None,
    } for title in titles][0:21]

def display_search_results(db_title):
    for i, title in enumerate(db_title):
        console.print(f"[yellow]{i} [white]-> [green]{title['name']} [white]- [cyan]{title['type']}")
