class BitField(bytes):
    def __init__(self,bitfield:bytes=b'') -> None:
        super().__init__()
        self.bitfield=bitfield

    def has_piece(self,index):
        #print('has piece current bitfield',len(self.bitfield),self.bitfield)
        byte_index=index//8
        offset=index%8
        return self.bitfield[byte_index]>>(7-offset)&1!=0
    
    def set_piece(self,index): 
        #print('set piece current bitfield',len(self.bitfield),self.bitfield)   
        byte_index=index//8
        offset=index%8
        if index<0 or index >len(self.bitfield)-1:
            return False
        self.bitfield[byte_index] |= 1 << (7-offset) 


    def reset_piece(self,index):
        byte_index=index//8
        offset=index%8
        if index<0 or index >len(self.bitfield)-1:
            return False
        self.bitfield[byte_index] &= not(1 <<(7-offset))

    def get_value(self)->bytes:
        return self.bitfield
    def set_value(self,value:bytes=b''):
        self.bitfield =value