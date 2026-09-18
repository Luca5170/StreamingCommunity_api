# 15.09.26

# Class
from Src.Gui.server import main
from Src.Util.console import console
from Src.Util.log import log_error

# Import
import sys, traceback

if __name__ == '__main__':

    if sys.version_info < (3, 11):
        console.log("Install python version > 3.11")
        sys.exit(0)

    # Temporary files are cleaned by main: segments of unfinished downloads are kept, they are resumed
    try:
        main()
    except Exception as e:
        log_error("The program stopped", e)
        traceback.print_exc()
        sys.exit(1)
