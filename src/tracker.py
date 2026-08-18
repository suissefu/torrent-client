from torrentfile import TorrentFile
import requests
import socket
import string
import random
from urllib.parse import urlencode
import asyncio
from aiohttp import ClientSession, ClientTimeout
import hashlib
from storage_manager import StorageManager
import bencode
from peer import Peer
import socket 
import struct
import time
import traceback
from app import app
import aiohttp

import secrets
from urllib.parse import urlparse


peer_list = []
interval = 0
last_success_request_time = None

def parse_compact_peers(peer_data: bytes) -> list[Peer]:
    """解析 IPv4 compact peer list：4 bytes IP + 2 bytes port。"""
    peers = []

    for offset in range(0, len(peer_data), 6):
        chunk = peer_data[offset:offset + 6]

        if len(chunk) != 6:
            break

        ip = socket.inet_ntoa(chunk[:4])
        port = struct.unpack("!H", chunk[4:6])[0]

        peers.append(Peer(ip, port))

    return peers


def get_bencode_value(data: dict, key: str, default=None):
    """兼容 bencode library 返回 str key 或 bytes key。"""
    if key in data:
        return data[key]

    return data.get(key.encode(), default)


def calculate_downloaded_bytes() -> int:
    """計算已完成 piece 的實際 bytes，正確處理最後一個 piece。"""
    file = app.torrent_file

    total_length = file.info["length"]
    piece_length = file.info["piece length"]

    downloaded = 0

    for index in app.bitfield.get_all(1):
        piece_start = index * piece_length
        current_length = min(
            piece_length,
            total_length - piece_start,
        )

        if current_length > 0:
            downloaded += current_length

    return downloaded

async def peer_discovery(trackers: list) -> list[Peer]:
    global peer_list

    tasks = [
        request_tracker(tracker)
        for tracker in trackers
    ]

    peers_clusters = await asyncio.gather(
        *tasks,
        return_exceptions=True,
    )

    for result in peers_clusters:
        if isinstance(result, Exception):
            print(f"Tracker task failed: {result}")
            continue

        for peer in result:
            if peer not in peer_list:
                peer_list.append(peer)

    return peer_list

# async def peer_discovery(trackers: list) -> list:
#     # loop = asyncio.new_event_loop()
#     # asyncio.set_event_loop(loop)
#     tasks=[]
#     try:
#         for tracker in trackers:
#             tasks.append(request_tracker(tracker))
#         # peers_clusters = loop.run_until_complete(asyncio.gather(*tasks))
#         peers_clusters = await asyncio.gather(*tasks)
#         for peers in peers_clusters:
#             for peer in peers:
#                 if peer not in peer_list:
#                     peer_list.append(peer)
#         # 檢查 peer_list 中 peer 數量, 不到條件繼續 切換 tracker
#         # if len(peer_list) <= 5 and len(trackers) != 0:
#         #     tracker = trackers.pop(0)
#         #     trackers.append(tracker)
#     finally:
#         pass          
#         # loop.close()
#     return peer_list


# def generate_random_port():
#     try:
#         with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
#             s.bind(('localhost',0))
#             host,port=s.getsockname()
#             return port
#     except Exception as e:
#         print('Err:',e)
#         return False

def get_trackers(torrent_file: TorrentFile) -> list:
    announce_list = torrent_file.announce_list or []

    trackers = [
        tracker
        for item in announce_list
        for tracker in (item if isinstance(item, list) else [item])
    ]

    return trackers or (
        [torrent_file.announce] if torrent_file.announce else []
    )

async def request_tracker(tracker: str) -> list[Peer]:
    if isinstance(tracker, bytes):
        tracker = tracker.decode("utf-8")

    scheme = urlparse(tracker).scheme.lower()

    try:
        if scheme in ("http", "https"):
            return await request_http_tracker(tracker)

        if scheme == "udp":
            return await request_udp_tracker(tracker)

        print(f"Unsupported tracker protocol: {tracker}")
        return []

    except asyncio.CancelledError:
        raise
    except TimeoutError:
        print(f"Tracker timeout: {tracker}")
        return []

    except aiohttp.ClientConnectorError as error:
        print(f"Cannot connect to tracker {tracker}: {error}")
        return []

    except Exception as error:
        print(f"Tracker failed {tracker}: {error}")
        return []
    # except Exception as error:
    #     print(f"Tracker request failed: {tracker}")
    #     print(error)
    #     traceback.print_exc()
    #     return []

async def request_http_tracker(tracker: str) -> list[Peer]:
    global last_success_request_time

    file = app.torrent_file

    downloaded = calculate_downloaded_bytes()
    total_length = file.info["length"]

    params = {
        "info_hash": hashlib.sha1(
            bencode.encode(file.info)
        ).digest(),

        "peer_id": app.peer_id,

        # 必須是你的 client 真正監聽的 port
        "port": app.listen_port,

        # uploaded 應該是實際上傳量，不是下載量
        "uploaded": getattr(app, "uploaded", 0),

        "downloaded": downloaded,
        "left": max(total_length - downloaded, 0),
        "compact": 1,
    }

    separator = "&" if "?" in tracker else "?"
    tracker_url = tracker + separator + urlencode(params)

    timeout = ClientTimeout(total=15)

    async with ClientSession(timeout=timeout) as session:
        async with session.get(tracker_url) as response:
            response_body = await response.read()

            if response.status != 200:
                raise RuntimeError(
                    f"HTTP tracker returned {response.status}"
                )

    peers_info = bencode.unmarshal(response_body)

    failure_reason = get_bencode_value(
        peers_info,
        "failure reason",
    )

    if failure_reason:
        if isinstance(failure_reason, bytes):
            failure_reason = failure_reason.decode(
                "utf-8",
                errors="replace",
            )

        raise RuntimeError(
            f"Tracker failure: {failure_reason}"
        )

    peer_data = get_bencode_value(peers_info, "peers", b"")
    tracker_interval = get_bencode_value(
        peers_info,
        "interval",
        1800,
    )

    if not isinstance(peer_data, (bytes, bytearray)):
        raise TypeError(
            "This version currently supports compact peer lists only"
        )

    app.interval = tracker_interval
    last_success_request_time = time.time()

    return parse_compact_peers(bytes(peer_data))

def validate_udp_response(
    response: bytes,
    expected_transaction_id: int,
    expected_action: int,
    minimum_length: int,
) -> None:
    if len(response) < 8:
        raise ValueError("UDP tracker response is too short")

    action, transaction_id = struct.unpack(
        "!II",
        response[:8],
    )

    if transaction_id != expected_transaction_id:
        raise ValueError(
            "UDP tracker transaction ID does not match"
        )

    # action 3 表示 tracker error
    if action == 3:
        message = response[8:].decode(
            "utf-8",
            errors="replace",
        )
        raise RuntimeError(
            f"UDP tracker error: {message}"
        )

    if action != expected_action:
        raise ValueError(
            f"Unexpected UDP tracker action: {action}"
        )

    if len(response) < minimum_length:
        raise ValueError("Incomplete UDP tracker response")

async def request_udp_tracker(tracker: str) -> list[Peer]:
    global last_success_request_time

    file = app.torrent_file
    parsed = urlparse(tracker)

    host = parsed.hostname
    tracker_port = parsed.port

    if host is None or tracker_port is None:
        raise ValueError(
            f"Invalid UDP tracker URL: {tracker}"
        )

    info_hash = hashlib.sha1(
        bencode.encode(file.info)
    ).digest()

    peer_id = app.peer_id

    if len(info_hash) != 20:
        raise ValueError("info_hash must be 20 bytes")

    if len(peer_id) != 20:
        raise ValueError("peer_id must be 20 bytes")

    downloaded = calculate_downloaded_bytes()
    total_length = file.info["length"]
    left = max(total_length - downloaded, 0)
    uploaded = getattr(app, "uploaded", 0)

    loop = asyncio.get_running_loop()

    # 此版本先使用 IPv4，回傳 peer 大小固定為 6 bytes
    address_info = await loop.getaddrinfo(
        host,
        tracker_port,
        family=socket.AF_INET,
        type=socket.SOCK_DGRAM,
    )

    tracker_address = address_info[0][4]

    sock = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM,
    )
    sock.setblocking(False)

    try:
        # -----------------------------------
        # 第一步：UDP connect request
        # -----------------------------------

        connect_transaction_id = secrets.randbits(32)

        connect_request = struct.pack(
            "!QII",
            0x41727101980,           # protocol_id
            0,                       # action = connect
            connect_transaction_id,
        )

        await loop.sock_sendto(
            sock,
            connect_request,
            tracker_address,
        )

        connect_response, _ = await asyncio.wait_for(
            loop.sock_recvfrom(sock, 2048),
            timeout=15,
        )

        validate_udp_response(
            connect_response,
            expected_transaction_id=connect_transaction_id,
            expected_action=0,
            minimum_length=16,
        )

        _, _, connection_id = struct.unpack(
            "!IIQ",
            connect_response[:16],
        )

        # -----------------------------------
        # 第二步：UDP announce request
        # -----------------------------------

        announce_transaction_id = secrets.randbits(32)
        key = secrets.randbits(32)

        announce_request = struct.pack(
            "!QII20s20sQQQIIIiH",
            connection_id,
            1,                          # action = announce
            announce_transaction_id,
            info_hash,
            peer_id,
            downloaded,
            left,
            uploaded,
            0,                          # event: none
            0,                          # IP: tracker 使用來源 IP
            key,
            -1,                         # num_want: default
            app.listen_port,
        )

        await loop.sock_sendto(
            sock,
            announce_request,
            tracker_address,
        )

        announce_response, _ = await asyncio.wait_for(
            loop.sock_recvfrom(sock, 65536),
            timeout=15,
        )

        validate_udp_response(
            announce_response,
            expected_transaction_id=announce_transaction_id,
            expected_action=1,
            minimum_length=20,
        )

        (
            _,
            _,
            tracker_interval,
            leechers,
            seeders,
        ) = struct.unpack(
            "!IIIII",
            announce_response[:20],
        )

        peer_data = announce_response[20:]

        app.interval = tracker_interval
        last_success_request_time = time.time()

        print(
            f"UDP tracker returned "
            f"{seeders} seeders, {leechers} leechers"
        )

        return parse_compact_peers(peer_data)

    finally:
        sock.close()

# async def request_tracker(tracker: str) -> list:

#     global trackers
#     global last_success_request_time

#     file = app.torrent_file
#     peers = []


#     params={
#     "info_hash":  hashlib.sha1(bencode.encode(file.info)).digest(),
#     "peer_id":    app.peer_id,
#     "port":       generate_random_port(),
#     # "uploaded":   sum(byte.bit_count() for byte in StorageManager.bitfield_path.read_bytes()) * file.info["piece length"],
#     # "downloaded": sum(byte.bit_count() for byte in StorageManager.bitfield_path.read_bytes()) * file.info["piece length"],
#     "uploaded":   len(app.bitfield.get_all(1)) * file.info["piece length"],
#     "downloaded": len(app.bitfield.get_all(1)) * file.info["piece length"],
#     "compact":    1,
#     "left":       file.info["length"] - sum(byte.bit_count() for byte in StorageManager.bitfield_path().read_bytes()) * file.info["piece length"]
#     }

    
#     try:
#         tracker+='?'+urlencode(params)
#         timeout=ClientTimeout(total=15.0)
#         async with ClientSession(timeout=timeout) as session:
#             async with session.get(tracker) as response:
#                 response_body = await response.read()
#                 status = response.status
#                 # response=requests.models.Response()
#                 # response._content=content
#                 # response.status_code=status
#         match status:
#             case 200:
#                     try:
#                         peers_info=bencode.unmarshal(response_body) 
#                         # print(peers_info)
#                         peer_size=6
#                         if len(peers_info['peers']) % peer_size == 0:      
#                             for i in range(len(peers_info['peers']) // peer_size):
#                                 peers.append(Peer(
#                                     socket.inet_ntoa(peers_info['peers'][0+i*peer_size:4+i*peer_size]),
#                                     struct.unpack('!H',peers_info['peers'][4+i*peer_size:6+i*peer_size])[0]
#                                     ))
#                         # peers=Peer.unmarshal(peers_info['peers'])

#                         # if verbose==1:  
#                         #     self.logger.info(f'got peer amount: {len(peers)}')                     

#                         app.interval = peers_info['interval']
#                         last_success_request_time=time.time()
#                     except:
#                         raise
            
#             case _:
#                 pass
#                 # self.logger.debug(f'got status code {response.status_code} from the tracker server')
#                 # if self.trackers!=None:
#                 #     tracker=self.trackers.pop(0)
#                 #     self.trackers.append(tracker)
#                 # return []
 

#     except Exception as e:
#         print(e)
#         traceback.print_exc()
#         # response=requests.models.Response()
#     #     self.logger.error(f'when requesting peers :{e},traceback line {e.__traceback__.tb_lineno}')
    

#     # self.logger.debug(tracker_url)
      
#     return peers  
    