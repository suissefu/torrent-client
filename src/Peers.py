import socket 
import struct


class Peer():
    def __init__(self) -> None:
        self.ip=None
        self.port=None

def unmarshal(peers_bin)->list:
    peer_size=6
    peer_num=len(peers_bin)//peer_size
    if len(peers_bin)%peer_size!=0:
        return []
    peers =[]
    for i in range(peer_num):
        peers.append(Peer())
        peers[i].ip=socket.inet_ntoa(peers_bin[0+i*peer_size:4+i*peer_size])
        peers[i].port=struct.unpack('!H',peers_bin[4+i*peer_size:6+i*peer_size])[0]

    return peers
