# 18.09.26

# Class import
from Src.Util import storage

# General import
import ipaddress, socket

# Variable
CONFIG_FILE = "remote.json"
DEFAULT_PORT = 8770

# Closing the page on the phone must not close the program on the pc
LOCAL_ONLY = {('POST', '/api/close')}


# [ config ]
def load_config():
    saved = storage.read_json(CONFIG_FILE, {})
    port = saved.get('port') if isinstance(saved, dict) else None
    return {'port': port if isinstance(port, int) and 1024 < port < 65536 else DEFAULT_PORT}

def save_config(config):
    storage.write_json(CONFIG_FILE, {'port': config['port']}, indent=4)


# [ access ]
def is_home_network(address):
    """Every device of the home network can use the app, internet never"""

    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False

    return ip.is_private or ip.is_loopback or ip.is_link_local


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
    """Qr code of the address, to open it from the phone without typing"""

    import segno
    return segno.make(url, error='m').svg_inline(scale=5, border=2, dark='#08090d', light='#ffffff')
