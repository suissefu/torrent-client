import os
import hashlib
import time
import json
import csv
#below is custom module
import bencode

class TorrentFile():
    def __init__(self):
        self.announce=None
        self.announce_list=None
        self.info=None
        self.info_hash=None
        self.piece_hashes=None
        self.piece_length=None
        self.length=None
        self.name=None

        self.previous_done_pieces=0
        self.this_time_done_pieces=0
        self.bitfield=None

    def calculate_bounds_for_piece(self,index:int):
        begin=index*self.piece_length
        end=begin+self.piece_length
        if end > self.length:
            end =self.length
        return begin,end
    def calculate_piece_size(self,index:int):
        begin,end=self.calculate_bounds_for_piece(index=index)
        return end- begin

    def split_piece_hashes(self)->list:
        hash_len=20
        buf=bytearray(self.info['pieces'])
        if len(buf)%hash_len!=0:
            print('received malformed pieces of length')
            return False
        num_hashes=len(buf)//hash_len
        hashes=[]
        for i in range(num_hashes):
            hashes.append(buf[i*hash_len:(i+1)*hash_len])
        return hashes
 
    def open_torrent_file(self,torrent_filename:str):
 
        torrent_file=bencode.decode(torrent_filename)
        #print(torrent_file)
        bencoded_info=bencode.encode(torrent_file['info'])
        self.announce=torrent_file['announce']
        self.info=torrent_file['info']
        self.name=self.info['name']
        self.length=self.info['length']
        self.piece_length=self.info['piece length']
        self.info_hash=hashlib.sha1(bencoded_info).digest()
        self.piece_hashes=self.split_piece_hashes()
        try:
            self.announce_list=[i[0] for i in torrent_file['announce-list']]

        except Exception as e:
            self.announce_list=None


    
    def log_torrent_file(self):
        data={'name':self.name,'total piece number':len(self.piece_hashes),'downloaded piece number':0}
        if not os.path.exists(f'../cache/{self.name}.json'):
            with open(f'../cache/{self.name}.json','w',encoding='utf-8') as f:
                f.write(json.dumps(data))
    
    def change_torrent_file_for_adding_piece_number(self):
        with open(f'../cache/{self.name}.json','r',encoding='utf-8') as f:
            data=json.load(f)
        data['downloaded piece number']+=1
        with open(f'../cache/{self.name}.json','w',encoding='utf-8') as f:
            f.write(json.dumps(data))
    def log_downloaded_piece(self,piece):
        insert_data=[piece.index,time.strftime('%Y/%m/%d-%H:%M:%S',time.localtime())]
        if not os.path.exists(f'../cache/{self.name}.csv'):
            with open(f'../cache/{self.name}.csv','w') as f:
                writer=csv.writer(f)
                writer.writerow(['downloaded piece number','downloaded time'])
        with open(f'../cache/{self.name}.csv','a',newline='') as f:
            writer=csv.writer(f)
            writer.writerow(insert_data)


    





