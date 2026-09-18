# 16.09.26

class DownloadCancelled(Exception):
    """
    Raised to stop a download.
    keep_files is True when the program is closing: the segments stay, so the download goes on at the next start.
    """

    def __init__(self, keep_files=False):
        super().__init__("Download annullato")
        self.keep_files = keep_files
