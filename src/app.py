from torrentfile import TorrentFile
# from peer import PeerPool
import string
import random
import asyncio
from bitfield import Bitfield
from pathlib import Path
import socket

def generate_random_port():
    try:
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
            s.bind(('localhost', 0))
            host, port = s.getsockname()
            return port
    except Exception as e:
        print('Err:',e)
        return False

def generate_random_string(num:int):
    char_set=string.ascii_letters+string.digits+'!@#$%^&*()'
    random_string= ''.join(random.choice(char_set) for _ in range(num))
    return random_string

work_path = Path("../")
torrent_path = work_path / "torrent"

class App:

    def __init__(self):
        self.torrent_file: TorrentFile = None
        self.bitfield: Bitfield = None
        self.peer_id = ('-TR4050-'+generate_random_string(12)).encode('utf-8')
        self.interval = 0
        self.peer_pool = None
        self.peer_manager = None
        self.request_queue = asyncio.Queue()
        self.download_queue = asyncio.Queue()
        # self.peer = None
        self.listen_port = generate_random_port()
        # self.torrent_file.parse(torrent_path / torrent_filename)
        self.peer_queue = asyncio.Queue()

app = App()

