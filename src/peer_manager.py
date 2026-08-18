from peer import PeerPool, PeerState, Peer
import asyncio
import time
from tracker import *
from app import app
from functools import wraps
import random

class PeerManager:

    def __init__(self, size: int, peer_pool: PeerPool):

        self.max_active_peers = size
        self.semaphore = asyncio.Semaphore(self.max_active_peers)
        self.peer_pool: PeerPool = peer_pool
        self.request_tracker = asyncio.Condition()

    # def timer(func):
    #     @wraps(func)
    #     async def wrapper(self, *args, **kwargs):
    #         start_time = time.perf_counter()
    #         try:
    #             return await func(self, *args, **kwargs)
    #         finally:
    #             self.last_elapsed = time.perf_counter() - start_time
    #     return wrapper

    async def announce_loop(self):
            while True:
                # 從 tracker 導入 peer
                peer_list = await peer_discovery(get_trackers(app.torrent_file))
                async with self.request_tracker:
                    for peer in peer_list:
                        self.peer_pool.put(peer)
                        await app.peer_queue.put(peer)  # 追加コンテンツ
                    self.request_tracker.notify_all()

                jitter = random.uniform(-0.05, 0.05)
                await asyncio.sleep(max((app.interval * (jitter + 1)), 60))

    async def connect_loop(self):
        async def connect(peer: Peer):
            async with self.semaphore:
                await peer.connect()

        while True:
            try:
                peer = await app.peer_queue.get()
                peer.state = PeerState.CONNECTING
                task = asyncio.create_task(connect(peer))

            except asyncio.exceptions.CancelledError:
                raise
            except Exception:
                traceback.print_exc()


    async def populate_peer_pool(self):

        count = 0

        async def activate_peer(peer: Peer):
            async with self.semaphore:
                await peer.connect()

        running_tasks = set()

        async with self.request_tracker:
            await self.request_tracker.wait_for(
                lambda: bool(self.peer_pool.get_all(PeerState.QUEUED))
            )

        while True:
            # 激活連接 peer
            # not_empty = (
            #     len(self.peer_pool.get_all(PeerState.QUEUED)) != 0
            #     or len(self.peer_pool.get_all(PeerState.FAILED)) != 0
            # )
            # has_capacity = (
            #     len(self.peer_pool.get_all(PeerState.ACTIVE)) < self.max_active_peers
            # )
            # if not_empty and has_capacity:
            
            try:
                # self.peer_pool.del_all(PeerState.FAILED)
                # print("導入後 Peer Pool 中 Peer 數量: ", len(self.peer_pool))
                async with self.request_tracker:
                    while not bool(self.peer_pool.get_all(PeerState.QUEUED)):
                    
                        await asyncio.sleep(0.2)

                    queued_peers = self.peer_pool.get_all(PeerState.QUEUED)
                # active_count = sum(
                #     1 for peer in self.peer_pool.get_all(PeerState.ACTIVE)
                # )

                # available_slots = self.max_active_peers - active_count
                # queued_peers = [
                #     peer for peer in self.peer_pool.get_all(PeerState.QUEUED)
                # ]

                # for peer in queued_peers[:available_slots]:
                #     asyncio.create_task(activate_peer(peer))

                # await asyncio.sleep(0.2)
                # print("queued peer count: ", len(queued_peers))
                # print("failed peer count ", len(self.peer_pool.get_all(PeerState.FAILED)))
                ############################################################################
                for peer in queued_peers:
                    peer.state = PeerState.CONNECTING
                    task = asyncio.create_task(activate_peer(peer))
                    running_tasks.add(task)
                    task.add_done_callback(running_tasks.discard)
                # await asyncio.gather(*list(running_tasks))
                await asyncio.sleep(0.2)
                count += 1
                print(f"{count}回目のループが完了しました")
                
            except asyncio.exceptions.CancelledError:
                # for task in running_tasks:
                #     task.cancel()

                # await asyncio.gather(
                #     *running_tasks,
                #     return_exceptions=True,
                # )
                raise
            except Exception:
                traceback.print_exc()



                # self.peer_pool.del_all(PeerState.FAILED)
                # await self.request_tracker.wait()


    async def start(self):
        tracker_task = asyncio.create_task(self.announce_loop())
        peer_keeper_task = asyncio.create_task(self.connect_loop())
        done, pending = await asyncio.wait(
            [tracker_task, peer_keeper_task],
            return_when = asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending)
        for task in done:
            task.result()
            task.exception()
            # interval_reached = (
            #     self.last_elapsed == 0
            #     or self.last_elapsed >= self.interval
            # )
