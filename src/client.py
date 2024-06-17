import threading
import queue
import hashlib
import os
import struct
import time
# below is custom module
import Peers
import bitfield
from piece import Piece
from config import config
from log import Logger

verbose=config['verbose']

#定义bittorent 协议消息类型 和 对应数字
#define bittorent protocol message and corresponding digits
msg_choke=0
msg_unchoke=1
msg_interested=2
msg_not_interested=3
msg_have=4
msg_bitfield=5
msg_request=6
msg_piece=7
msg_cancel=8


max_backlog=1
max_block_size=16384

work_queue=queue.Queue()
results=queue.Queue()

class CustomError(Exception):
    def __init__(self,*args) -> None:
        super().__init__(*args)
        self.information=''
        for arg in args:
            self.information+=str(arg) if not isinstance(arg,str) else arg
    def __str__(self) -> str:
        return self.information
class HandShakeError(CustomError):
    def __init__(self, *args) -> None:
        super().__init__(*args)

class MessageError(CustomError):
    def __init__(self,*args) -> None:
        super().__init__(self,*args)
        pass
class ParseError(CustomError):
    def __init__(self,*args):
        super().__init__(self,*args)
        pass
class DownloadPieceError(CustomError):
    def __init__(self,*args):
        super().__init__(self,*args)
        pass
class Message():
    def __init__(self,id:int=None,payload:bytes=None,length:int=0):
        
        self.id:int=id
        self.payload=payload
        if length!=0:
            self.length=length
        else:
            if id==None:
                id_length=0
            else :
                id_length=1
            if payload==None:
                payload_length=0
            else:
                payload_length=len(payload)
            self.length=id_length+payload_length
    def marshal(self):
        if self.payload!=None:
            return self.length.to_bytes(4,byteorder='big')+self.id.to_bytes(1,byteorder='big')+self.payload
        else: 
            if self.id!=None:
                return self.length.to_bytes(4,byteorder='big')+self.id.to_bytes(1,byteorder='big')
            else :
                return self.length.to_bytes(4,byteorder='big')

class Client(threading.Thread):
    def __init__(self,peer:Peers.Peer=None,torrent_file=None,peer_id:bytes=b'') -> None:
        super().__init__()
        self.conn=None
        self.choked:bool=True
        self.peer:Peers.Peer=peer
        self.info_hash:bytes=torrent_file.info_hash if torrent_file!=None else None
        self.torrent_file=torrent_file
        self.peer_id:bytes=peer_id
        self.peer_bitfield=None
        self.flag:str=None

        self.backlog=0

        self.piece=None
        self.piece_done=0

        self.last_download_time=time.time()

        self.logger=Logger(self.torrent_file,self)
        self.last_message_time=None
    # 先是进行握手报的发送接收，收到 peer 的 bitfield 并且 被 unchoke 后继续
    # client 线程的主要工作就是收取工作队列 work_queue中的待下载的piece,然后请求对应peer下载
    # 下载piece后，比对种子文件中的piece hashes ，若 哈希值不相同抛弃该piece,相同则放入结果队列
    # at first send and receive handshake packages, after receiving the bitfeld & getting unchoked ,proceed to the next step 
    # the main work of the client thread is to get piece need to downloaded from work queue & request its peer to download that piece 
    # after piece downloaded,check the piece's hash, if not corret abandon it else put it into the result queue
    def run(self):
        try:

            start_handshake_time=time.time()
            self.send_handshake(self.info_hash,self.peer_id)
            #self.send_bitfield()
            self.recv_handshake()
            self.read_message()
            self.send_interested()
            while self.choked==True or self.peer_bitfield==None:
                self.read_message()

                if time.time()-start_handshake_time>10:
                    raise TimeoutError('initiate client time out')
                
        except Exception as e:
            self.logger.error(f'when testing the peer\'s availability ,an error "{e}" occurred,traceback line {e.__traceback__.tb_lineno}')
            return False

        while self.torrent_file.this_time_done_pieces< len(self.torrent_file.piece_hashes)-self.torrent_file.previous_done_pieces:
            piece = work_queue.get()
            if self.peer_bitfield.has_piece(piece.index)!=1:
                work_queue.put(piece)
                continue
            try:    
                #self.send_keep_alive()
                self.attempt_download_piece(piece=piece)
            # 严重异常 直接抛弃该线程 
            # very critical error, let's just abandon this thread
            except Exception as e:
                piece.downloaded=0
                piece.requested=0
                self.logger.error(f'client exit ,when trying to download Piece #{piece.index}  :',e)
                work_queue.put(piece)
                return False
            #确认 piece 的哈希值是否与 种子文件中的相同，不同则可能已被篡改，丢弃
            # check whether the hash value of the piece is same as the that of the piece hashes in the torrent file
            # if there is difference ,this piece might has already been tempered , abandon it
            if self.piece.hash!=hashlib.sha1(self.piece.data).digest():
                piece.downloaded=0
                piece.requested=0
                self.logger.warn(f'Piece #{self.piece.index} unverified by hash')
                work_queue.put(piece)
                continue
            #self.send_have(piece.index)
            self.logger.info(f'Piece #{self.piece.index} download success')
            self.torrent_file.bitfield.set_piece(self.piece.index)
            self.last_download_time=time.time()
            self.piece_done+=1
            self.piece.downloaded_by_client=f'{self.peer.ip}:{self.peer.port}'

            results.put(self.piece)

    def attempt_download_piece(self,piece:Piece):
        if verbose==1:
            self.logger.debug(f'from {self.peer.ip}:{self.peer.port},start attempt to download Piece #{piece.index}')
        self.piece=piece
        if time.time()-self.last_message_time >30:
            try:
                self.send_keep_alive()
            except Exception as e:
                raise e
            
        while piece.downloaded < piece.length:
            if self.choked!=True:
                while piece.requested < piece.length and self.backlog<=max_backlog:
                    block_size=max_block_size
                    if piece.length-piece.requested < block_size:
                        block_size=piece.length-piece.requested  
                    if verbose==1: 
                        self.logger.debug(f"to {self.peer.ip}:{self.peer.port} ,send request for Piece#{piece.index} begin:{piece.requested} block_size:{block_size}")
                    try:
                        self.send_request(piece.index,piece.requested,block_size)  
                    except Exception as e:
                        raise e
                    piece.requested+=block_size 
                    self.backlog+=1 
            #不停地从 peer 收消息，直到完整地下载一个 block
            # continously get message utill a block is fully downloaded         
            downloaded=self.piece.downloaded
            start_recv_time=time.time()
            while self.piece.downloaded<=downloaded:
                try:
                    self.logger.debug(f'attempt to read piece blocks from {self.peer.ip}:{self.peer.port}')
                    self.read_message()
                except Exception as e:
                    raise e
                if time.time()-start_recv_time>30:
                    raise DownloadPieceError(f'download Piece #{self.piece.index} time out')
            self.logger.debug(f'to {self.peer.ip}:{self.peer.port} ,piece status {(self.piece.downloaded/self.piece.length*100):.2f}%')

  
    
    def read_message(self)->int:
        try:
            msg=self.recv_message()
        except Exception as e :
            raise e

        if msg.id==None:
            #keep alive
            pass
        elif msg.id==msg_choke:
            self.choked=True
            
        elif msg.id==msg_unchoke:
            self.choked=False

        elif msg.id==msg_interested:
            self.send_unchoke()
        
        elif msg.id==msg_not_interested:
            self.send_choke()

        elif msg.id==msg_have:
            try:
                index=int.from_bytes(msg.payload,byteorder='big')
                self.logger.debug(f'peer_bitfield: {self.peer_bitfield.get_value()}')
                self.peer_bitfield.set_piece(index)
                self.choked=False
            except Exception as e:
                self.logger.error('when reading have message: ',e,',traceback line ',e.__traceback__.tb_lineno)

        elif msg.id==msg_bitfield:
            self.peer_bitfield=bitfield.BitField(msg.payload)

        elif msg.id==msg_request:
            index,begin,block_size=struct.unpack('>III',msg.payload)
            try:
                if self.torrent_file.bitfield.have_piece(index):
                    if os.path.exists(f'../download/{self.torrent_file.name}'):
                        with open(f'../download/{self.torrent_file.name}','rb') as f:
                            f.seek(self.torrent_file.piece_length*index+begin)
                            block=f.read(block_size)
                        self.conn.sendall(Message(id=7,payload=struct.pack('>I',index)+struct.pack('>I',begin)+block).marshal())
            except :
                # requested data not exists
                pass
            pass
        elif msg.id==msg_piece:

            parsed_index=int.from_bytes(msg.payload[:4],byteorder='big')
            begin=int.from_bytes(msg.payload[4:8],byteorder='big')
            data=msg.payload[8:]
            self.piece.data[begin:]=data
            success_downloaded=len(data)
            self.logger.info(f'piece #{parsed_index} begin {begin},end {begin+len(data)-1}')
            #如果 从 peer 收到的 block 数据 不符合请求的，抛弃 该 block
            # if from the peer got a block which doesn't meet our request, abandon this block 
            if parsed_index!=self.piece.index or begin> self.piece.length or begin+len(data) >self.piece.length:
                success_downloaded=0
                if verbose==1:
                    self.logger.warn(f'something wrong with the Piece #{parsed_index} ,begin offset {begin}')
            # piece 中的一个block 成功被下载
            # one block of the piece has been downloaded successfully
            self.piece.downloaded+=success_downloaded
            self.backlog-=1


    def recv_message(self,timeout:int=10)->Message:
        start_recv_time=time.time()
        try:
            length_raw=self.conn.recv(4)
            # 接收 消息 长度，4 字节
            # receive message length,4 bytes
            while len(length_raw)!=4 and timeout>time.time()-start_recv_time:
                length_raw=self.conn.recv(4)
            length=struct.unpack('>I',length_raw)[0]

            # 接受 消息 体，字节长度由刚才接收到的 消息长度 给出
            # receive message body,its length depends on the message length ,which's been received just now
            start_recv_time=time.time()
            content_raw=self.conn.recv(length)
            while len(content_raw) < length and timeout>time.time()-start_recv_time:
                content_raw+=self.conn.recv(length-len(content_raw))

            id=content_raw[0] if len(content_raw) >0 else None
            payload=content_raw[1:] if len(content_raw)>0 else None
            if verbose==1:
                if id !=7:
                    self.logger.debug(f'from {self.peer.ip}:{self.peer.port} ,recv_message got ',id,' ,payload is ',payload)
                else:
                    self.logger.debug(f'from {self.peer.ip}:{self.peer.port} ,recv_message got ',id,' ,payload length is ',len(payload))
            self.last_message_time=time.time()
            return Message(id=id,payload=payload)
        except Exception as e:
            if verbose==1:
                self.logger.error(f'from {self.peer.ip}:{self.peer.port} ,when recv message: ',e ,',trackback line ',e.__traceback__.tb_lineno)
            raise e

           
        
    def send_handshake(self,info_hash:bytes=b'',peer_id:bytes=b''):   
        hs_send=HandShake(info_hash,peer_id)
        self.conn.sendall(hs_send.marshal())

    def send_keep_alive(self):
        try:
            self.conn.sendall(Message().marshal())
        except Exception as e:
            raise e
        self.logger.info(f'send keep alive message {Message().marshal().hex()} ')

    def send_choke(self):
        self.conn.sendall(Message(msg_choke).marshal())
#1
    def send_unchoke(self):
        self.conn.sendall(Message(msg_unchoke).marshal())

    def send_interested(self):
        self.conn.sendall(Message(msg_interested).marshal())
#3
    def send_not_interested(self):
        self.conn.sendall(Message(msg_not_interested).marshal())
#4 
    def send_have(self,index):
        self.conn.sendall(Message(msg_have,struct.pack('>I',index)).marshal())
#5
    def send_bitfield(self):
        self.conn.sendall(Message(msg_bitfield,self.torrent_file.bitfield.get_value()).marshal())
#6
    def send_request(self,index,begin,length):
        payload=bytearray(12)
        payload[:4]=index.to_bytes(4,byteorder='big')
        payload[4:8]=begin.to_bytes(4,byteorder='big')
        payload[8:12]=length.to_bytes(4,byteorder='big')
        self.conn.sendall(Message(msg_request,payload).marshal())


    def recv_handshake(self)->Message:
        hs_recv=HandShake()
        data=None

        try:
            start_handshake_time=time.time()
            protocol_length_raw=self.conn.recv(1)
            protocol_length=int.from_bytes(protocol_length_raw,byteorder='big')
            content=self.conn.recv(protocol_length+48)
            while len(content)<protocol_length+48:
                content+=self.conn.recv(protocol_length+48-len(content))
                if time.time()-start_handshake_time>10:
                    #raise HandShakeError()
                    pass
                
            data=protocol_length_raw+content

        except Exception as e:
            if verbose==1:
                self.logger.warn('when recv handshake: ',e)
            raise e

        try:
            hs_recv.pstring_length=data[0]
            if hs_recv.pstring!=data[1:hs_recv.pstring_length+1]:
                if verbose==1:
                    self.logger.warn('unsupported protocol :',data[1:hs_recv.pstring_length+1])
                raise HandShakeError('unsupported protocol :',data[1:hs_recv.pstring_length+1])

            hs_recv.reserved_byte=data[hs_recv.pstring_length+1:hs_recv.pstring_length+1+8]
            hs_recv.info_hash=data[hs_recv.pstring_length+1+8:hs_recv.pstring_length+1+8+20]
            hs_recv.peer_id=data[hs_recv.pstring_length+1+8+20:hs_recv.pstring_length+1+8+40]
        except:
            if verbose==1:
                self.logger.warn('invalid format of the received handshake response: ',data)
            raise HandShakeError('invalid format of the received handshake response: ',data)

        

class HandShake():
    def __init__(self,info_hash:bytes=b'',peer_id:bytes=b'') -> None:

        self.pstring_length=b'\x13'
        self.pstring=b'BitTorrent protocol'
        self.reserved_byte=b'\x00\x00\x00\x00\x00\x00\x00\x00'
        self.info_hash=info_hash
        self.peer_id=peer_id
    def marshal(self):
        return self.pstring_length+self.pstring+self.reserved_byte+self.info_hash\
        +self.peer_id


