from enum import Enum
import time

# PeerConnection
import asyncio
import struct
from peer import *
from app import app
import hashlib
import bencode
import traceback
from bitfield import Bitfield


# input Peer
# output Connection (for downloading)

class PeerState(Enum):
    QUEUED = "queued"
    ACTIVE = "active"
    FAILED = "failed"
    BANNED = "banned"
    CONNECTING = "connecting"

class Peer():
    def __init__(self, ip: str, port: int) -> None:
        self.ip: str = ip 
        self.port: int = port
        self.id = None
        self.last_seen = None
        self.next_try = time.time()
        self._state = PeerState.QUEUED
        self._fail_count = 0
        self.reader = None
        self.writer = None
        self.send_queue = asyncio.Queue(16)
        self.recv_queue = asyncio.Queue()
        self.activated = False
        self.closed = asyncio.Event()
        self.bitfield = Bitfield(len(app.torrent_file.info["pieces"]) // 20)
        self.choked = True
        self.unchoked = asyncio.Event()
        self.idle = True
    # @property
    # def unchoked(self):
    #     return not self.choked
   
    def __eq__(self, other) -> bool:
        if not other:
            return False
        return self.ip == other.ip and self.port == other.port
    
    @property
    def state(self):
        match self._state:
            case PeerState.ACTIVE:
                pass
            case PeerState.FAILED:
                if self.next_try <= time.time():
                    self._state = PeerState.QUEUED
                    app.peer_queue.put_nowait(self)

        return self._state
    
    @state.setter
    def state(self, state: PeerState):
        match state:
            case PeerState.ACTIVE:
                pass
            case PeerState.QUEUED:
                app.peer_queue.put_nowait(self)
            case PeerState.FAILED:
                self._fail_count += 1
                self.next_try = time.time() + min(5 * 2 ** (self._fail_count - 1), 300)
                if self._fail_count > 3:
                    self._state = PeerState.BANNED
                    return

        self._state = state

        


    async def connect(self):
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.ip, self.port),
                timeout = 5
            )
            remote_peer_id = await self.handshake()
            self.id = remote_peer_id

            send_task = asyncio.create_task(self.send_loop())
            recv_task = asyncio.create_task(self.recv_loop())

            await self.send_message(5, app.bitfield[:]) # bitfield 的 長度必須正確
            # await self.send_message(1)
            self.state = PeerState.ACTIVE
            app.peer_pool.updated.set()

            done, pending = await asyncio.wait(
                [send_task, recv_task],
                return_when = asyncio.FIRST_COMPLETED
            )
            if not self.closed.is_set():

                # print(f"passively disconnect {self.ip}:{self.port}")
                self.closed.set()

            for task in pending:
                task.cancel()

            await asyncio.gather(*pending, return_exceptions = True)

            for task in done:
                task.result()

            # self.state = PeerState.QUEUED
            self.state = PeerState.FAILED
            ## done, pending = asyncio.wait()

        # except asyncio.CancelledError:
        #     self.state = PeerState.QUEUED
        #     raise
        except TimeoutError:            
            # print(f"Timeout error from {self.ip}:{self.port}")
            self.state = PeerState.FAILED
        except (
            
            asyncio.exceptions.IncompleteReadError,
            asyncio.exceptions.CancelledError,
            ConnectionRefusedError,
            ConnectionResetError,
            OSError
        ):
            self.state = PeerState.FAILED

        except:
            self.state = PeerState.FAILED
            traceback.print_exc()
        
        try:
            if self.writer:
                self.writer.close()
                await self.writer.wait_closed()
                
        except (ConnectionResetError, BrokenPipeError):
            self.state = PeerState.FAILED

    async def disconnect(self):
        print(f"proactively disconnect {self.ip}:{self.port}")
        self.closed.set()
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
        self.state = PeerState.FAILED
        app.peer_pool.updated.set()

            
    async def send_loop(self):
        while not self.closed.is_set():
            data = await self.send_queue.get()
            self.writer.write(data)
            await self.writer.drain()
            # await asyncio.sleep(5)

    async def recv_loop(self):
        while not self.closed.is_set():
            # async with asyncio.timeout(5):
                raw_length = await asyncio.wait_for(self.reader.readexactly(4), timeout = 15)
                length = struct.unpack(">I", raw_length)[0]
                if length == 0:
                    # keep alive
                    continue
                msg_id = await asyncio.wait_for(self.reader.readexactly(1), timeout = 15)
                payload = await asyncio.wait_for(self.reader.readexactly(length - 1), timeout = 15)
                await self.handle_message(msg_id[0], payload)
            # await asyncio.sleep(5)

    async def send_message(self, msg_id: int, payload: bytearray = b''):

        length = len(payload) + 1
        data = struct.pack(">I", length)
        data += struct.pack("B", msg_id)
        data += payload
        # if msg_id == 6:
        #     pass
        # else:
        #     print(f"msg_id {msg_id} to {self.ip}:{self.port}")
        await self.send_queue.put(data)

    async def handle_message(self, msg_id: int, payload: bytearray | None = None):
        match msg_id:
            case 0:
                # choke
                # print(f"msg_id 0 from {self.ip}:{self.port}")
                self.choked = True
                self.unchoked.clear()
            case 1:
                # unchoke
                # print(f"msg_id 1 from {self.ip}:{self.port}")
                self.choked = False
                self.unchoked.set()
            case 2:
                # interested
                print("msg_id 2")
                await self.send_message(1)
            case 3:
                # not interested
                print("msg_id 3")
                pass
            case 4:
                # have
                # print(f"msg_id 4 from {self.ip}:{self.port}")
                self.bitfield.set(struct.unpack(">I", payload[0:4])[0])
            case 5:
                # bitfield
                # print(f"msg_id 5 from {self.ip}:{self.port}")
                self.bitfield[:] = payload
            case 6:
                # request
                print("msg_id 6")
                ip = bytes(map(int, self.ip.split(".")))
                port = self.port.to_bytes(2, "big")
                await app.request_queue.put(ip + port + payload)
                # index, begin, length = struct.unpack(">III", payload)
                # if app.bitfield.get(index):
                #     pass
            case 7:
                # piece
                # print(f"msg_id 7 from {self.ip}:{self.port}")
                # print(f"block from {self.ip}:{self.port}")
                await app.download_queue.put(payload)
            case 8:
                print("msg_id 8")

            case 9:
                print("msg_id 9")
  

                
                
    
    async def handshake(self) -> str:
        pstr = b"BitTorrent protocol"

        handshake_packet = (
            bytes([len(pstr)])
            + pstr
            + b"\x00" * 8
            + hashlib.sha1(bencode.encode(app.torrent_file.info)).digest()
            + app.peer_id
        )

        try:
            self.writer.write(handshake_packet)
            await self.writer.drain()
            async with asyncio.timeout(10):
                length_data = await self.reader.readexactly(1)
                protocol_type = await self.reader.readexactly(length_data[0])
                response = await self.reader.readexactly(48)
            remote_info_hash = response[8:28]
            remote_peer_id = response[28:48]

            if protocol_type != pstr or remote_info_hash != hashlib.sha1(bencode.encode(app.torrent_file.info)).digest():
                raise Exception("handshake validation failed")
            return remote_peer_id
        except:
            raise

    async def wait_handshake(self) -> str:
        pstr = b"BitTorrent protocol"

        handshake_packet = (
            bytes([len(pstr)])
            + pstr
            + b"\x00" * 8
            + hashlib.sha1(bencode.encode(app.torrent_file.info)).digest()
            + app.peer_id
        )

        try:
            
            async with asyncio.timeout(10):
                length_data = await self.reader.readexactly(1)
                protocol_type = await self.reader.readexactly(length_data[0])
                response = await self.reader.readexactly(48)
            remote_info_hash = response[8:28]
            remote_peer_id = response[28:48]

            if protocol_type != pstr or remote_info_hash != hashlib.sha1(bencode.encode(app.torrent_file.info)).digest():
                raise Exception("handshake validation failed")

            self.writer.write(handshake_packet)
            await self.writer.drain()
            return remote_peer_id
        except:
            raise

class PeerPool():
    def __init__(self):
        self._queue = []
        self.updated = asyncio.Event()
    def __len__(self):
        return len(self._queue)
    def put(self, peer: Peer):
        # 檢查有沒有重複
        if peer not in self._queue:
            peer.last_seen = time.time()
            self._queue.append(peer)
        else:
            for p in self._queue:
                if p == peer:
                    p.last_seen = time.time()
    # def get(self):
    #     # 檢查 active peer 限制

    #     if sum(peer.state == PeerState.ACTIVE for peer in self._queue) >= 5:
    #         return None
    #     # 返還可用 peer, 例如 queued 和 failed (如果是 failed 必須檢查 next_try 時間)
    #     for peer in self._queue:
    #         if peer.state == PeerState.QUEUED:
    #             return peer
    #         elif peer.state == PeerState.FAILED:
    #             if peer.next_try >= time.time():
    #                 peer.state = PeerState.QUEUED
    #                 return peer
    # def del_all(self, state: PeerState) -> None:
    #     for peer in self._queue:
    #         if peer.state == state:
    #             self._queue.remove(peer)
    def del_all(self, state: PeerState) -> None:
        self._queue = [
            peer for peer in self._queue
            if peer.state != state
        ]
                
    def get_all(self, state: PeerState | None = None) -> list:
        # for peer in self._queue:
        #     if peer.state == PeerState.FAILED:
        #         if peer.next_try >= time.time():
        #             peer.state = PeerState.QUEUED
        if state == None:
            return []
        return [ peer for peer in self._queue if peer.state == state ]
    
    # def get_and_set_all(self, get_state: PeerState, set_state: PeerState):

    #     peer_list = []        
    #     for peer in self._queue:
    #         if peer.state == get_state:
    #             peer.state = set_state
    #             if peer.state == set_state: # 可能會設置失敗 所以需要檢查
    #                 peer_list.append(peer)
    #     return peer_list