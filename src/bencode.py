
def decode(filename):
    with open(filename,'rb') as f:
        return unmarshal(f)
    
def encode(data_struct):
    return marshal(data_struct)
    
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
    if (isinstance(f, bytes)):
        value, pos = _decode(f, 0)

        if pos != len(f):
            raise ValueError("Bencode 後面還有多餘資料")

        return value

    else:
        ch=f.read(1)

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

def _decode(data: bytes, pos: int):
    if pos >= len(data):
        raise ValueError("資料意外結束")

    ch = data[pos:pos + 1]

    # 整數：i123e
    if ch == b"i":
        end = data.find(b"e", pos + 1)

        if end == -1:
            raise ValueError("整數缺少結尾 e")

        number = int(data[pos + 1:end])
        return number, end + 1

    # 列表：l...e
    if ch == b"l":
        result = []
        pos += 1

        while True:
            if pos >= len(data):
                raise ValueError("列表缺少結尾 e")

            if data[pos:pos + 1] == b"e":
                return result, pos + 1

            value, pos = _decode(data, pos)
            result.append(value)

    # 字典：d...e
    if ch == b"d":
        result = {}
        pos += 1

        while True:
            if pos >= len(data):
                raise ValueError("字典缺少結尾 e")

            if data[pos:pos + 1] == b"e":
                return result, pos + 1

            key, pos = _decode(data, pos)
            value, pos = _decode(data, pos)

            result[key] = value

    # bytes：4:spam
    if ch.isdigit():
        colon = data.find(b":", pos)

        if colon == -1:
            raise ValueError("字串缺少冒號")

        length = int(data[pos:colon])
        start = colon + 1
        end = start + length

        if end > len(data):
            raise ValueError("字串長度不足")
        
        string = data[start:end]
        try:
            string = string.decode("utf-8")
        except:
            pass
        return string, end

    raise ValueError(f"無效的 Bencode 資料：{ch!r}")