# 18.09.26

# General import
import logging, os, traceback
from logging.handlers import RotatingFileHandler

# Variable
LOG_FOLDER = "logs"
LOG_FILE = os.path.join(LOG_FOLDER, "errori.log")

logger = logging.getLogger("sc_downloader")
logger.setLevel(logging.INFO)
logger.propagate = False


def get_logger():
    """Errors are written in logs/errori.log, the file never grows beyond a few MB"""

    if not logger.handlers:
        try:
            os.makedirs(LOG_FOLDER, exist_ok=True)
            handler = RotatingFileHandler(LOG_FILE, maxBytes=1024 * 1024, backupCount=3, encoding='utf-8', delay=True)
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            logger.addHandler(handler)
        except OSError:
            logger.addHandler(logging.NullHandler())

    return logger

def log_error(message, error=None):
    """Never raises: a log that cant be written must not stop the program"""

    try:
        details = "".join(traceback.format_exception(type(error), error, error.__traceback__)) if error is not None else ""
        get_logger().error(f"{message}\n{details}".rstrip())
    except Exception:
        pass

def log_info(message):
    try:
        get_logger().info(message)
    except Exception:
        pass
