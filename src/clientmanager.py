
import requests
import socket
import string
import random
from threading import Thread
import time
from aiohttp import ClientSession,ClientTimeout
import asyncio
from urllib.parse import urlencode
# below is custom module
import bencode
import Peers
from torrentfile import TorrentFile
from client import work_queue,Client
from log import Log
from config import config

verbose=config['verbose']


class ClientManager(Thread):
    def __init__(self,torrent_file:TorrentFile):
        super().__init__()
        self.torrent_file=torrent_file
        #-qB4640-CS6EHUGcZu!f
        self.peer_id=('-TR4050-'+generate_random_string(12)).encode('utf-8')
        self.port=generate_random_port()
        #print('port %d is ready to request the tracker for peers'%self.port)
        self.trackers=self.torrent_file.announce_list \
        if self.torrent_file.announce_list !=None else [self.torrent_file.announce]
        self.clients=[]
        self.peers=[]
        self.black_peers=[]
        self.last_success_request_time=time.time()
        self.interval=0
        self.start_time=time.time()
        self.logger=Log(self.torrent_file,'ClientManager')
        
    def run(self):
        loop=asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        while self.torrent_file.this_time_done_pieces< len(self.torrent_file.piece_hashes)-self.torrent_file.previous_done_pieces:
            if time.time()-self.last_success_request_time>=self.interval or len(self.clients) <=6:
            
                tasks=[]
                # tasks.append(self.manage_clients())
                for tracker_url in self.trackers:
                    tasks.append(self.request_peers(tracker_url))
                results=loop.run_until_complete(asyncio.gather(*tasks))

                peers=[]
                for result in results:
                    for peer in result:
                        if not any(str(peer.ip)+':'+str(peer.port)==str(i.ip)+':'+str(i.port) for i in peers):
                            peers.append(peer)

                self.logger.info('try to test peers\' availability')
                # filter peers  对 peer 进行 筛选

                for  peer in peers:
                    if not any(str(peer.ip)+':'+str(peer.port)==client['client_id'] for client in self.clients)\
                        and not any(str(peer.ip)+':'+str(peer.port)==str(i.ip)+':'+str(i.port) for i in self.black_peers): 
                        t=Thread(target=self.initiate_client,args=(peer,))
                        t.start()
  
            # filter clients ,消除无效节点
            self.logger.debug('start clients filtering')
            for i, client in enumerate(self.clients):
                if client['client'].is_alive()==False or client['client'].last_download_time < time.time()-120:
                    self.clients.pop(i)
            for client in self.clients:
                self.logger.info('client id :',client['client_id'],',client :',client['client'],',client status: ',client['client'].is_alive())
            time.sleep(15)
        loop.close()     
 
    def initiate_client(self,peer):
        try:      
            conn=socket.socket(socket.AF_INET,socket.SOCK_STREAM)
            conn.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
            conn.setblocking(0)
            conn.settimeout(15.0)
            conn.connect((peer.ip,peer.port))
            c=Client(peer=peer,torrent_file=self.torrent_file,peer_id=self.peer_id)
            c.conn=conn
            c.start()
            self.clients.append({'client_id':f'{peer.ip}:{peer.port}','client':c})
            self.peers.append(peer)
        except Exception as e:

            self.black_peers.append(peer)
            self.logger.error(f'when testing the peer\'s availability ,an error "{e}" occurred,traceback line {e.__traceback__.tb_lineno}')
            return 

    
    #使用包装器，再获得响应后，解析响应中的peer和interval,interval指定再次请求tracker服务器时间
    # use wrapper , after getting the response, get peers and interval time by parsing the response
    # the interval time is used to specify the interval to request the tracker server
    def get_peers(func):
        async def wrapper(self,*args,**kw):
            response=await func(self,*args,**kw)
            if response.status_code==200:
                with open(f'../temp/{self.torrent_file.name}.tmp','wb') as f:
                    f.write((response.content))
                with open(f'../temp/{self.torrent_file.name}.tmp','rb') as f:
                    try:
                        peers_info=bencode.unmarshal(f)  
                        peers=Peers.unmarshal(peers_info['peers'])
                    except:
                        tracker=self.trackers.pop(0)
                        self.trackers.append(tracker)
                        return []
                if verbose==1:  
                    self.logger.info(f'got peer amount: {len(peers)}')                     
                if len(peers)<=5 and self.trackers!=None:
                    tracker=self.trackers.pop(0)
                    self.trackers.append(tracker)
                    return []
                self.interval=peers_info['interval']
                self.last_success_request_time=time.time()
                return peers
            else:
                
                self.logger.debug(f'got status code {response.status_code} from the tracker server')
                if self.trackers!=None:
                    tracker=self.trackers.pop(0)
                    self.trackers.append(tracker)
                return []
        return wrapper
    
    # 通过异步方式请求tracker服务器，获取到bittorent bencoding 编码的响应
    # use async methods to request a tracker server, get bencoded response from the server
    @get_peers       
    async def request_peers(self,tracker_url)->requests.models.Response:
        params={
		"info_hash":  self.torrent_file.info_hash,
		"peer_id":    self.peer_id,
		"port":       self.port,
		"uploaded":   self.torrent_file.previous_done_pieces*self.torrent_file.piece_length,
		"downloaded": self.torrent_file.previous_done_pieces*self.torrent_file.piece_length,
		"compact":    1,
		"left":       self.torrent_file.length-self.torrent_file.previous_done_pieces*self.torrent_file.piece_length
        }
        try:
            tracker_url+='?'+urlencode(params)
            timeout=ClientTimeout(total=15.0)
            async with ClientSession(timeout=timeout) as session:
                async with session.get(tracker_url) as resp:
                    self.logger.info('request url: ',resp.url)
                    content=await resp.read()
                    status =resp.status
                    self.logger.info(status)
                    response=requests.models.Response()
                    response._content=content
                    response.status_code=status
        except Exception as e:
            response=requests.models.Response()
            self.logger.error(f'when requesting peers :{e},traceback line {e.__traceback__.tb_lineno}')
        finally:

            self.logger.debug(tracker_url)
            return response
        

def generate_random_string(num:int):
    char_set=string.ascii_letters+string.digits+'!@#$%^&*()'
    random_string= ''.join(random.choice(char_set) for _ in range(num))
    return random_string
def generate_random_port():
    try:
        with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as s:
            s.bind(('localhost',0))
            host,port=s.getsockname()
            return port
    except Exception as e:
        print('Err:',e)
        return False
