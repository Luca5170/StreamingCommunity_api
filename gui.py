# 15.09.26

# Class
from Src.Gui.server import main
from Src.Util.console import console
from Src.Util.os import remove_folder

# Import
import sys

if __name__ == '__main__':

    if sys.version_info < (3, 11):
        console.log("Install python version > 3.11")
        sys.exit(0)

    remove_folder("tmp")

    try:
        main()
    finally:
        # Files of a download stopped together with the program
        remove_folder("tmp")
