
def decode(filename):
    with open(filename,'rb') as f:
        return decode_from_reader(f)
    
def encode(data_struct):
    return encode_from_writer(data_struct)
    
def decode_from_reader(f):
    #error process
    result=unmarshal(f)
    return result
def encode_from_writer(data_struct):
    result=marshal(data_struct)
    return result

def marshal(data_struct):
    if isinstance(data_struct,int):
        return b'i'+str(data_struct).encode('utf-8')+b'e'
    elif isinstance(data_struct,list):
        return b'l'+b''.join(marshal(i) for i in data_struct )+b'e'
    elif isinstance(data_struct,dict):
        return b'd'+b''.join(marshal(i)+marshal(value) for i,value in data_struct.items() )+b'e'
    else :
        try:
           data_struct=data_struct.encode('utf-8') 
        except Exception as e:
            pass
        return str(len(data_struct)).encode('utf-8')+b':'+data_struct
def unmarshal(f):
    try:
        ch=f.read(1)
    except Exception as e:
        print('Err:',e)
    if ch==b'i':
        data=optimistic_read_bytes(f,b'e')
        return int(data)
    elif ch ==b'l':
        list=[]
        while True:
            c=f.read(1)
            if c==b'e':
                return list
            else:
                f.seek(-1,1)
            value=unmarshal(f)
            list.append(value)
    elif ch==b'd':
        dictionary={}
        while True:
            c=f.read(1)
            if c==b'e':
                return dictionary
            else:
                f.seek(-1,1)
            value =unmarshal(f)
            key=value
            value= unmarshal(f)
            dictionary[key]=value
    else:
        length_prefix=ch
        length_suffix=optimistic_read_bytes(f,b':')
        length=int(length_prefix+length_suffix)
        string=f.read(length)
        try:
            string=string.decode('utf-8')
        except Exception as e:
            pass
        return string

def optimistic_read_bytes(f,delim):
    data_lump=b''
    while True:
        data=f.read(1)
        if data==delim:
            return data_lump
        data_lump+=data

