from app import app
from peer import *
from piece import *
import asyncio
from dataclasses import dataclass
from storage_manager import StorageManager

max_block_size=16384

class Leecher:

    def __init__(self):
        self.piece_dispatcher: PieceDispatcher = PieceDispatcher()
        self.get_block = asyncio.Event()
        self.file_path = StorageManager.download_path / app.torrent_file.info["name"]
    async def upload(self):
        def read_block(index, offset, length):
            with self.file_path.open("rb") as f:
                f.seek(app.torrent_file["piece length"] * index + offset)
                block = f.read(length)
            return block
        
        while not self.piece_dispatcher.closed.is_set():
            payload = await app.request_queue.get()
            ip = ".".join(map(str, payload[:4]))
            port = int.from_bytes(payload[4:6], "big")
            index, offset, length = struct.unpack(">III", payload[6:])
            if index in app.bitfield.get_all(1):
                block = await asyncio.to_thread(read_block, index, offset, length)
            peer = next(
                (
                    peer for peer in app.peer_pool.get_all(PeerState.ACTIVE) 
                    if peer.ip == ip and peer.port == port
                ),
                None
            )
            if peer:
                data = struct.pack(">II", index + offset)
                data += block
                peer.send_message(7, data)

    async def download(self):
        def write_block(index, offset, block):
            if not self.file_path.exists():
                self.file_path.touch(exist_ok = True)
            with self.file_path.open("r+b") as f:
                f.seek(app.torrent_file.info["piece length"] * index + offset)
                f.write(block)
        def write_bitfield():
            with StorageManager.bitfield_path().open("wb") as f:
                f.write(app.bitfield)
        def validate(index: int, offset: int, block_size: int, piece: Peer) -> bool:
            whether_legal = (
                 index < len(app.torrent_file.info["pieces"]) // 20 # index 未超界限
                and offset + block_size <= piece.requested
                and block_size <= max_block_size
            )
            return whether_legal
        
        while not self.piece_dispatcher.closed.is_set():

            payload = await app.download_queue.get()
            # print("block got from download queue")
            # self.get_block.set()
            index, offset = struct.unpack(">II", payload[0:8])
            block = payload[8:]

            piece = self.piece_dispatcher.find(index)
            if not validate(index, offset, len(block), piece): # 非法payload 直接斷開
                peer = piece.reserved_by_peer
                # print("block failed: try disconnect")
                if peer:
                    await peer.disconnect()
                # print("finish disconnect")
                # await self.piece_dispatcher.release_piece(piece)
            
            await asyncio.to_thread(write_block, index, offset, block)

            piece.downloaded += len(block)
            if piece.downloaded >= piece.length:
                # 驗證有效性 
                
                with self.file_path.open("rb") as f:
                    f.seek(app.torrent_file.info["piece length"] * index)
                    piece_chunk = f.read(piece.length)
                peer = piece.reserved_by_peer
                if hashlib.sha1(piece_chunk).digest() == piece.hash:
                    # print(f"piece#{piece.index} downloaded from {peer.ip}:{peer.port}")
                    app.bitfield.set(index)
                    await asyncio.to_thread(write_bitfield)
                    for other_peer in app.peer_pool.get_all(PeerState.ACTIVE):
                        if other_peer != peer:
                            await other_peer.send_message(4, struct.pack(">I", index))

                else:
                    # print(f"piece#{piece.index} download failed: try disconnect {peer.ip}:{peer.port}")
                    piece.downloaded = 0
                    await peer.disconnect()

                await self.piece_dispatcher.release_piece(piece)
                # print(f"piece# {piece.index} released")

    async def request_loop(self):

        async def request(peer: Peer):

            if peer.choked:
                await peer.send_message(2)
            await peer.unchoked.wait()
            # print(f"unchoked by {peer.ip}:{peer.port}")
            piece: Piece = await self.piece_dispatcher.reserve_piece(peer)
            window_size = 6
            while piece.requested < piece.length and not self.piece_dispatcher.closed.is_set():
                if peer.choked:
                    await peer.send_message(2)
                    await peer.unchoked.wait()
                block_size = max_block_size if max_block_size + piece.requested <= piece.length else piece.length - piece.requested
                payload = struct.pack(">I", piece.index) + struct.pack(">I", piece.requested) + struct.pack(">I", block_size)
                await peer.send_message(6, payload)
                piece.requested += block_size           
                # await asyncio.sleep(0.5)
                window_size -= 1
                if window_size < 0:
                    # await self.get_block.is_set()
                    # await self.get_block.wait()
                    await asyncio.sleep(0.3)
                    window_size = 6
                    # self.get_block.clear()

            while piece.downloaded < piece.length and not self.piece_dispatcher.closed.is_set():
                if peer.closed.is_set():
                    await self.piece_dispatcher.release_piece(piece)
                    piece.downloaded = 0
                    return
                await asyncio.sleep(1)
                
        
        while not self.piece_dispatcher.closed.is_set():
            not_empty = (
                len(app.peer_pool.get_all(PeerState.ACTIVE))
            )
            # print("Active peers number:", not_empty)
            if not_empty:
                for peer in app.peer_pool.get_all(PeerState.ACTIVE):
                    # print("app peer", app.peer)
                    if peer.idle == True:
                        # print(f"create task to request {peer.ip}:{peer.port}")
                        # if not app.peer:
                        #     app.peer = peer
                        # if peer == app.peer:
                        #     print(f"create task to request {peer.ip}:{peer.port}")
                        # print(f"create task to request {peer.ip}:{peer.port}")
                        asyncio.create_task(request(peer))

            await app.peer_pool.updated.wait()
            app.peer_pool.updated.clear()

    async def handle_peer(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        try:
            ip, port = writer.get_extra_info("peername")
            peer = Peer(ip, port)
            peer.reader = reader
            peer.writer = writer
            app.peer_pool.put(peer)
            remote_peer_id = await peer.wait_handshake()
            peer.id = remote_peer_id

            send_task = asyncio.create_task(peer.send_loop())
            recv_task = asyncio.create_task(peer.recv_loop())

            await peer.send_message(5, app.bitfield[:]) # bitfield 的 長度必須正確
            # await self.send_message(1)
            peer.state = PeerState.ACTIVE
            app.peer_pool.updated.set()

            done, pending = await asyncio.wait(
                [send_task, recv_task],
                return_when = asyncio.FIRST_COMPLETED
            )
            if not self.closed.is_set():
                peer.closed.set()
            for task in pending:
                task.cancel()

            await asyncio.gather(*pending, return_exceptions = True)

            for task in done:
                task.result()

            peer.state = PeerState.FAILED

        except TimeoutError:            
            peer.state = PeerState.FAILED
        except (          
            asyncio.exceptions.IncompleteReadError,
            asyncio.exceptions.CancelledError,
            ConnectionRefusedError,
            ConnectionResetError,
            OSError
        ):
            peer.state = PeerState.FAILED
        except:
            peer.state = PeerState.FAILED
            traceback.print_exc()        
        try:
            if peer.writer:
                peer.writer.close()
                await peer.writer.wait_closed()
        except:
            pass


    async def leech(self):
            # print("start leeching")
            # print([piece.index for piece in self.piece_dispatcher.piece_list if piece.state == PieceState.MISSING])
            request_task = asyncio.create_task(self.request_loop())
            download_task = asyncio.create_task(self.download())
            server = await asyncio.start_server(
                self.handle_peer,
                "0.0.0.0",
                app.listen_port
            )
            await asyncio.gather(request_task, download_task)
            server.close()
            await server.wait_closed()
            print("download finished")
        