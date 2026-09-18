# 10.12.23

# Class import
from Src.Util.headers import get_headers
from Src.Util.console import console

# General import
import requests, sys, json
from bs4 import BeautifulSoup

SITE_NAME = "streamingcommunityz"

def get_site_url(domain):
    return f"https://{SITE_NAME}.{domain}"

def get_base_url(domain):
    return f"{get_site_url(domain)}/it"

def get_version(domain):
    site_request = requests.get(get_site_url(domain), headers={'user-agent': get_headers()}, timeout=15)
    soup = BeautifulSoup(site_request.text, "lxml")
    return json.loads(soup.find("div", {"id": "app"}).get("data-page"))['version']

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
            domain = input(f"Insert domain ({SITE_NAME}.?): ")
            req_repo['domain'] = domain
            with open('data.json', 'w') as file:
                json.dump(req_repo, file)
        console.print(f"[blue]Test domain [white]=> [red]{domain}")
        try:
            version = get_version(domain)
            console.print(f"[blue]Rules [white]=> [red].{domain}")
            return domain, version
        
        except Exception as e:
            console.log("[red]Cant get version, problem with domain. Try again.")
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
