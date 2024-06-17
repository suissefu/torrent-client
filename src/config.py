import os 
config={
    'verbose':0
}
if os.path.exists('config.txt'):
    try:
        with open('config.txt','r',encoding='utf-8') as f:
            for line in f:
                if line.split('#')[0].strip():
                    key,value=line.split()
                    config[key.strip('[]')]=value.strip()

    except :
        pass
                    


