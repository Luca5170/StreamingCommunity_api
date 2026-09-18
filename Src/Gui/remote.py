# 18.09.26

# Class import
from Src.Util import storage

# General import
import hmac, ipaddress, secrets, socket

# Variable
CONFIG_FILE = "remote.json"
DEFAULT_PORT = 8770
COOKIE_NAME = "sc_key"
COOKIE_AGE = 365 * 24 * 3600

# The phone can use the app, the settings of the pc stay on the pc
LOCAL_ONLY = {
    ('POST', '/api/domain'),
    ('GET', '/api/nas'),
    ('POST', '/api/nas'),
    ('POST', '/api/nas/test'),
    ('POST', '/api/open'),
    ('POST', '/api/close'),
    ('GET', '/api/remote'),
    ('POST', '/api/remote'),
    ('POST', '/api/remote/key'),
}


# [ config ]
def load_config():
    saved = storage.read_json(CONFIG_FILE, {})
    saved = saved if isinstance(saved, dict) else {}

    config = {
        'enabled': bool(saved.get('enabled')),
        'key': saved.get('key') if isinstance(saved.get('key'), str) and len(saved.get('key')) >= 24 else None,
        'port': saved.get('port') if isinstance(saved.get('port'), int) and 1024 < saved.get('port') < 65536 else DEFAULT_PORT,
    }

    # The key is made once, the phones that have it stay connected
    if config['key'] is None:
        config['key'] = new_key()
        save_config(config)

    return config

def save_config(config):
    storage.write_json(CONFIG_FILE, {'enabled': config['enabled'], 'key': config['key'], 'port': config['port']}, indent=4)

def new_key():
    return secrets.token_urlsafe(24)


# [ access ]
def is_valid_key(config, key):
    return bool(key) and hmac.compare_digest(str(key).encode(), config['key'].encode())

def is_home_network(address):
    """Only devices of the home network: private addresses, never internet"""

    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False

    return ip.is_private or ip.is_loopback or ip.is_link_local

def get_cookie(header, name=COOKIE_NAME):
    for part in (header or '').split(';'):
        key, _, value = part.strip().partition('=')
        if key == name:
            return value

    return None

def make_cookie(key):
    return f"{COOKIE_NAME}={key}; Path=/; Max-Age={COOKIE_AGE}; HttpOnly; SameSite=Strict"


# [ address ]
def get_lan_ips():
    """Addresses of this pc in the home network, the one used to go on internet first"""

    found = []

    # The address used for the internet is the one of the home network
    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("192.0.2.1", 80))
        found.append(probe.getsockname()[0])
        probe.close()
    except OSError:
        pass

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.append(info[4][0])
    except OSError:
        pass

    ips = []
    for ip in found:
        address = ipaddress.ip_address(ip)
        if ip not in ips and address.is_private and not address.is_loopback and not address.is_link_local:
            ips.append(ip)

    return ips

def get_qr_svg(url):
    """Qr code of the link, as svg to put in the page"""

    import segno
    return segno.make(url, error='m').svg_inline(scale=5, border=2, dark='#08090d', light='#ffffff')
