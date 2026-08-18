try:
    import time
    import sys
    import os
    import csv
    import collections
    # below is custom module
    from torrentfile import TorrentFile
    # from clientmanager import ClientManager
    # from client import work_queue, results
    from bitfield import Bitfield
    from piece import Piece
    from log import Log
    from storage_manager import StorageManager
    import bencode
    from tracker import *
    from peer import *
    from app import App, app
    from peer_manager import PeerManager
    from datetime import datetime
    from downloader import Leecher 
    import asyncio
    from dashboard import dashboard_loop



except KeyboardInterrupt as e:
    print('\noperation stopped by user')
    os.execl(sys.executable,sys.executable,'main.py','-e')
# 以下全局变量从命令行获得，torrent_file_name 指定种子文件名称
# the global variables are got from cmd, torrent_file_name specify the torrent file name
torrent_file_name=None
reset=False
clean=False
help=False
exit=False
change_verbose_to=None
view_bitfield = False


#这是入口函数，指定种子文件名下载
#this is entrance function, specify torrent file name to start downloading 
async def download(torrent_filename:str):
    loop = asyncio.get_running_loop()
    loop.slow_callback_durtion = 0.01
    print("Start parsing ...")
    file=TorrentFile()
    file.parse(torrent_filename)
    app.torrent_file = file

    pieces_number = len(file.info["pieces"]) // 20 # hash_len 20 bytes
    bitfield = Bitfield(pieces_number)
    app.bitfield = bitfield
    if StorageManager.bitfield_path().exists():
        with StorageManager.bitfield_path().open("rb") as f:
            chunck = f.read()
        app.bitfield[:] = chunck
    else:
        with StorageManager.bitfield_path().open("wb") as f:
            f.write(app.bitfield)


    # for i in range(pieces_number):
    #     work_queue.put(Piece(i))

    # validation = work_queue.get()
    # print(validation.__dict__) 

    peer_pool = PeerPool()
    app.peer_pool = peer_pool
    # peer_list = peer_discovery(get_trackers(file))
    # for peer in peer_list:
    #     peer_pool.put(peer)
    # print([f"{peer.ip}:{peer.port}" for peer in peer_pool.get_all(PeerState.QUEUED)])
    peer_manager = PeerManager(10, peer_pool=peer_pool)
    peer_manager_task = asyncio.create_task(peer_manager.start())
    leecher = Leecher()
    leech_task = asyncio.create_task(leecher.leech())
    display_task = asyncio.create_task(dashboard_loop())
    done, pending = await asyncio.wait(
       [peer_manager_task, leech_task],
        return_when = asyncio.FIRST_COMPLETED
    )
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions = True)
    for task in done:
        task.result()

    while True: 
        await asyncio.sleep(1)


def handling_cmd_argument():

    global help
    global clean
    global change_verbose_to
    global torrent_file_name
    global exit
    global view_bitfield

    # 没给参数情况下
    if len(sys.argv)==1:
        return
    # 给参数情况下
    for i ,param_name in enumerate(sys.argv):

        if param_name=='-h' or param_name=='--help':
            help = True
  
        elif param_name=='-c' or param_name=='--clean':
            clean = True
        elif param_name=='-e' or param_name=='--exit':
            exit=True

        elif param_name=='-v' or param_name=='--verbose':
            if i !=len(sys.argv)-1:
                param_value=sys.argv[i+1]
                if param_value=='0':
                    change_verbose_to=0
                elif param_value=='1':
                    change_verbose_to=1
                else:
                    print('illegal verbose value')
                    sys.exit(0)
        elif param_name=='-f' or param_name=='--file':
            if i !=len(sys.argv)-1:
                torrent_file_name=sys.argv[i+1]

        elif param_name == "-b" or param_name == "--bitfield":
            view_bitfield = True
            if i !=len(sys.argv)-1:
                torrent_file_name = sys.argv[i+1]            


        else:
            continue

        

if __name__=='__main__':

    try:
        StorageManager.init_work_directories()
        handling_cmd_argument()

        if help:
            print('usage: python main.py [option] ... [-c | -v verbose | -] [arg] ...')
            print('Options and arguments (and corresponding environment variables):')
            print('-h   :print this help message (also --help)')
            print('-c   :clean all files in cache,temp,log directory (also --clean)')
            print('-v   :specify the level of details shown in procedures (also --verbose)')
            print('      by default use -v 0, which means there will be no log files generated')
            print('      in the /log directory')
            print('      the optional range from 0 to 1')
            print('-f   :give the torrent file name that you want to download (also --file)')
            print('      for example, python main.py -f debian-12.5.0-amd64-netinst.iso.torrent')
            print('      by default, the torrent file should be put in /torrent directory')
        elif exit:
            sys.exit(0)
        elif clean:
            directories_need_to_be_cleaned=['log','temp']
            for d in directories_need_to_be_cleaned:
                if os.path.exists(f'../{d}'):
                    for root,directories,files in os.walk(f'../{d}/',topdown=False):
                        for i in files:
                            os.remove(os.path.join(root,i))
                        for i in directories:
                            os.rmdir(os.path.join(root,i))
                    print(f'{d} has been cleaned')
                else:
                    print(f'{d} doesn\'t exists')        
        elif not isinstance(change_verbose_to,type(None)):
            with open('config.txt','w',encoding='utf-8') as f:
                config={
                    'verbose':change_verbose_to
                }
                for key,value in config.items():
                    f.write(f'[{key}] {str(value)}\n')
            if torrent_file_name:
                os.execl(sys.executable,sys.executable,'main.py','-f',torrent_file_name)
        elif view_bitfield:
            file=TorrentFile()
            file.parse(f'../torrent/{torrent_file_name}')
            app.torrent_file = file

            pieces_number = len(app.torrent_file.info["pieces"]) // 20 # hash_len 20 bytes
            bitfield = Bitfield(pieces_number)
            try:
                with StorageManager.bitfield_path().open("rb") as f:
                    bitfield[:] = f.read()
                print(f"bitfield bit number: {len(bitfield)}")
                print(f"bitfield index possesed: \n{bitfield.get_all(0)}")
            except:
                pass
        else :

            if torrent_file_name==None:
                print('you want to use bittorent to download,but you didn\'t specify any torrent file')
                print('try to using -f or --file to specify the torrent file')
                print('or using -h or --help to check the help manual')
                sys.exit(0)
            if torrent_file_name  not in os.listdir('../torrent'):
                print('the file you want to download doesn\'t exist in /torrent')
                print('please put your file in the /torrent directory and run the program again')
                sys.exit(0)
            try:
                
                asyncio.run(download(f'../torrent/{torrent_file_name}'), debug = True)
            except KeyboardInterrupt as e:
                # print('\noperation stopped by user')
                # os.execl(sys.executable,sys.executable,'main.py','-e')
                raise
            # except Exception as e:
            #     print('when starting download :',e,',traceback line ',e.__traceback__.tb_lineno,',module ',e.__class__.__module__)
            #     os.execl(sys.executable,sys.executable,'main.py','-e')
    except KeyboardInterrupt as e:
        print('\noperation stopped by user')
        # os.execl(sys.executable,sys.executable,'main.py','-e')

