from pathlib import Path
from app import app

class StorageManager:

    work_path = Path("../")
    torrent_path = work_path / "torrent"
    download_path = work_path / "download"
    cache_path = work_path / "cache"
    log_path = work_path / "log"
    bitfield = None

    @classmethod
    def bitfield_path(cls): 
        return cls.cache_path / f"{app.torrent_file.info['name']}.bitfield"
    @classmethod
    def init_work_directories(cls):   
        directories = ["torrent", "download", "cache", "log"]   
        for directory in directories:
            directory_path = cls.work_path / directory
            directory_path.mkdir(parents = True, exist_ok = True)

        # cls.bitfield_path.touch(exist_ok = True)


