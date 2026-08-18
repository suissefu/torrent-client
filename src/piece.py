from app import app
from peer import *
from enum import auto, Enum
from dataclasses import dataclass
from storage_manager import StorageManager

class PieceState(Enum):
    MISSING = auto()
    RESERVED = auto()
    COMPLETED = auto()

class Piece:
    def __init__(self, index):
        
        self.index = index
        self.hash = app.torrent_file.info["pieces"][index * 20: (index + 1) * 20]
        self.length = min(
            app.torrent_file.info["piece length"],
            app.torrent_file.info["length"] - index * app.torrent_file.info["piece length"]
        )
        self.state = PieceState.MISSING
        self.reserved_by_peer: Peer = None
        self.downloaded_by_peer: Peer = None
        self.requested = 0
        self.downloaded = 0
        
        # super().__init__(self.length)
        # self.data=bytearray(length)
    
    # @property
    # def rarity(self):
    #     count = 0
    #     # start = time.perf_counter()
    #     active_peers = app.peer_pool.get_all(PeerState.ACTIVE)
    #     # print(f"get active {time.perf_counter() - start}")
    #     # start = time.perf_counter()
    #     for peer in active_peers:
    #         if self.index in peer.bitfield.get_all(1):
    #             count += 1
    #     # print(f"get bitfield {time.perf_counter() - start}")
    #     return count

        

class PieceDispatcher:
    def __init__(self):

        self.condition = asyncio.Condition()
        self.piece_list: list[Piece] = [Piece(index) for index in range(len(app.torrent_file.info["pieces"]) // 20)]
        # 檢查 bitfield
        completed_pieces = app.bitfield.get_all(1)
        self.closed = asyncio.Event()
        for index in completed_pieces:
            self.piece_list[index].state = PieceState.COMPLETED

    def rarity_algorithm(self, candidates: list[Piece]):
        # count = 0
        rarity_map = {} # 不包含 count 為 0 的 piece
        candidate_indexes = set(candidate.index for candidate in candidates)

        active_peers = app.peer_pool.get_all(PeerState.ACTIVE)
        for peer in active_peers:
                intersection = candidate_indexes & set(peer.bitfield.get_all(1))
                # count += 1
                for i in intersection:
                    rarity_map[i] = rarity_map.get(i, 0) + 1

        # sorted_rarity_map = sorted(rarity_map.items(), key = lambda x: x[1])
        rarest_tuple = min(rarity_map.items(), key = lambda x: x[1])
        piece = self.find(rarest_tuple[0])
        return piece
    
    async def reserve_piece(self, peer: Peer) -> Piece:
  
        async with self.condition:

            while True:

                candidates = [
                        self.piece_list[index] for index in peer.bitfield.get_all(1) 
                        if self.piece_list[index].state == PieceState.MISSING
                    ]

                if candidates: 
                    # piece = min(candidates, key = lambda item: item.rarity) # 每個peer單獨計算 浪費時間掃描 peer bifield 
                    piece = self.rarity_algorithm(candidates)
                    piece.state = PieceState.RESERVED
                    piece.reserved_by_peer = peer
                    peer.idle = False
                    return piece
                # 若無合適 piece, 等待直至出現
                await self.condition.wait()
  

    async def release_piece(self, piece: Piece):
        async with self.condition:
            if piece.downloaded < piece.length:
                self.piece_list[piece.index].state = PieceState.MISSING
                self.piece_list[piece.index].reserved_by_peer.idle = True
                self.piece_list[piece.index].reserved_by_peer = None
                self.piece_list[piece.index].requested = 0
                # self.piece_list[piece.index].downloaded = 0
            else:
                self.piece_list[piece.index].state = PieceState.COMPLETED
                self.piece_list[piece.index].downloaded_by_peer = self.piece_list[piece.index].reserved_by_peer
                self.piece_list[piece.index].reserved_by_peer.idle = True
                self.piece_list[piece.index].reserved_by_peer = None
                if all (piece.state == PieceState.COMPLETED for piece in self.piece_list):
                    self.closed.set()

            app.peer_pool.updated.set()
            self.condition.notify_all()


    def find(self, index: int) -> Piece:
        try:
            return self.piece_list[index]
        except:
            raise
            
    # async def start(self):
    #     while True:
    #         not_empty = (
    #            not len(app.peer_pool.get_all(PeerState.ACTIVE)) 
    #         )
    #         if not_empty:
    #             pass
    #         await asyncio.sleep(5)
    