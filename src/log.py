import os
import time
from  threading import Thread
from traceback import print_exc


class Log():
    def __init__(self,torrent_file,name:str) -> None:
        '''
        torrent file is used to specify the log path ,name is used to decide
        the name of the log file
        '''
        self.torrent_file=torrent_file
        self.name=name
        if not os.path.exists(f'../log/{self.torrent_file.name}'):
            os.makedirs(f'../log/{self.torrent_file.name}')
    def debug(*args):
        self=args[0]
        log_information=''
        for i ,value in enumerate(args):
            if i !=0:
                log_information+=str(value) if not isinstance(value,str) else value
        try:

            if not os.path.exists(f'../log/{self.torrent_file.name}/{self.name}.log'):
                with open(f'../log/{self.torrent_file.name}/{self.name}.log','w'):
                    pass
            with open(f'../log/{self.torrent_file.name}/{self.name}.log','a',encoding='utf-8') as f:
                current_time = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime())
                f.write(f'[DEBUG] {log_information} {current_time}\n')
        except Exception as e:
            print_exc()
            raise e

    def info(*args):
        self=args[0]
        log_information=''
        for i ,value in enumerate(args):
            if i !=0:
                log_information+=str(value) if not isinstance(value,str) else value
        try:

            if not os.path.exists(f'../log/{self.torrent_file.name}/{self.name}.log'):
                with open(f'../log/{self.torrent_file.name}/{self.name}.log','w'):
                    pass
            with open(f'../log/{self.torrent_file.name}/{self.name}.log','a',encoding='utf-8') as f:
                current_time = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime())
                f.write(f'[INFO] {log_information} {current_time}\n')
        except Exception as e:
            print_exc()
            raise e

    def warn(*args):
        self=args[0]
        log_information=''
        for i ,value in enumerate(args):
            if i !=0:
                log_information+=str(value) if not isinstance(value,str) else value
        try:

            if not os.path.exists(f'../log/{self.torrent_file.name}/{self.name}.log'):
                with open(f'../log/{self.torrent_file.name}/{self.name}.log','w'):
                    pass
            with open(f'../log/{self.torrent_file.name}/{self.name}.log','a',encoding='utf-8') as f:
                current_time = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime())
                f.write(f'[WARN] {log_information} {current_time}\n')
        except Exception as e:
            print_exc()
            raise e
        
    def error(*args):
        self=args[0]
        log_information=''
        for i ,value in enumerate(args):
            if i !=0:
                log_information+=str(value) if not isinstance(value,str) else value
        try:

            if not os.path.exists(f'../log/{self.torrent_file.name}/{self.name}.log'):
                with open(f'../log/{self.torrent_file.name}/{self.name}.log','w'):
                    pass
            with open(f'../log/{self.torrent_file.name}/{self.name}.log','a',encoding='utf-8') as f:
                current_time = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime())
                f.write(f'[ERROR] {log_information} {current_time}\n')
        except Exception as e:
            print_exc()
            raise e

    def fatal(*args):
        self=args[0]
        log_information=''
        for i ,value in enumerate(args):
            if i !=0:
                log_information+=str(value) if not isinstance(value,str) else value
        try:

            if not os.path.exists(f'../log/{self.torrent_file.name}/{self.name}.log'):
                with open(f'../log/{self.torrent_file.name}/{self.name}.log','w'):
                    pass
            with open(f'../log/{self.torrent_file.name}/{self.name}.log','a',encoding='utf-8') as f:
                current_time = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime())
                f.write(f'[FATAL] {log_information} {current_time}\n')
        except Exception as e:
            print_exc()
            raise e



class Logger():
    def __init__(self,torrent_file,client:Thread) -> None:

        self.torrent_file=torrent_file
        self.client=client
        if not os.path.exists(f'../log/{self.torrent_file.name}'):
            os.makedirs(f'../log/{self.torrent_file.name}')

    def debug(*args):
        self=args[0]
        log_information=''
        for i ,value in enumerate(args):
            if i !=0:
                log_information+=str(value) if not isinstance(value,str) else value
        try:

            if not os.path.exists(f'../log/{self.torrent_file.name}/{self.client.peer.ip}:{self.client.peer.port}.log'):
                with open(f'../log/{self.torrent_file.name}/{self.client.peer.ip}:{self.client.peer.port}.log','w'):
                    pass
            with open(f'../log/{self.torrent_file.name}/{self.client.peer.ip}:{self.client.peer.port}.log','a',encoding='utf-8') as f:
                current_time = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime())
                f.write(f'[DEBUG] {log_information} {current_time}\n')
        except Exception as e:
            print_exc()
            raise e

    def info(*args):
        self=args[0]
        log_information=''
        for i ,value in enumerate(args):
            if i !=0:
                log_information+=str(value) if not isinstance(value,str) else value
                
        if not os.path.exists(f'../log/{self.torrent_file.name}/{self.client.peer.ip}:{self.client.peer.port}.log'):
            with open(f'../log/{self.torrent_file.name}/{self.client.peer.ip}:{self.client.peer.port}.log','w'):
                pass
        with open(f'../log/{self.torrent_file.name}/{self.client.peer.ip}:{self.client.peer.port}.log','a',encoding='utf-8') as f:
            current_time = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime())
            f.write(f'[INFO] {log_information} {current_time}\n')

    def warn(*args):
        self=args[0]
        log_information=''
        for i ,value in enumerate(args):
            if i !=0:
                log_information+=str(value) if not isinstance(value,str) else value
                
        if not os.path.exists(f'../log/{self.torrent_file.name}/{self.client.peer.ip}:{self.client.peer.port}.log'):
            with open(f'../log/{self.torrent_file.name}/{self.client.peer.ip}:{self.client.peer.port}.log','w'):
                pass
        with open(f'../log/{self.torrent_file.name}/{self.client.peer.ip}:{self.client.peer.port}.log','a',encoding='utf-8') as f:
            current_time = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime())
            f.write(f'[WARN] {log_information} {current_time}\n')

    def error(*args):
        self=args[0]
        log_information=''
        for i ,value in enumerate(args):
            if i !=0:
                log_information+=str(value) if not isinstance(value,str) else value
                
        if not os.path.exists(f'../log/{self.torrent_file.name}/{self.client.peer.ip}:{self.client.peer.port}.log'):
            with open(f'../log/{self.torrent_file.name}/{self.client.peer.ip}:{self.client.peer.port}.log','w'):
                pass
        with open(f'../log/{self.torrent_file.name}/{self.client.peer.ip}:{self.client.peer.port}.log','a',encoding='utf-8') as f:
            current_time = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime())
            f.write(f'[ERROR] {log_information} {current_time}\n')

    def fatal(*args):
        self=args[0]
        log_information=''
        for i ,value in enumerate(args):
            if i !=0:
                log_information+=str(value) if not isinstance(value,str) else value
                
        if not os.path.exists(f'../log/{self.torrent_file.name}/{self.client.peer.ip}:{self.client.peer.port}.log'):
            with open(f'../log/{self.torrent_file.name}/{self.client.peer.ip}:{self.client.peer.port}.log','w'):
                pass
        with open(f'../log/{self.torrent_file.name}/{self.client.peer.ip}:{self.client.peer.port}.log','a',encoding='utf-8') as f:
            current_time = time.strftime('%Y-%m-%d %H:%M:%S',time.localtime())
            f.write(f'[fatal] {log_information} {current_time}\n')

