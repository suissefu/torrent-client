from functools import wraps
from typing import Literal

# class BitField(bytes):
    # def __init__(self,bitfield:bytes=b'') -> None:
    #     super().__init__()
    #     self.bitfield=bitfield

    # def has_piece(self,index):
    #     #print('has piece current bitfield',len(self.bitfield),self.bitfield)
    #     byte_index=index//8
    #     offset=index%8
    #     return self.bitfield[byte_index]>>(7-offset)&1!=0
    
    # def set_piece(self,index): 
    #     #print('set piece current bitfield',len(self.bitfield),self.bitfield)   
    #     byte_index=index//8
    #     offset=index%8
    #     if index<0 or index >len(self.bitfield)-1:
    #         return False
    #     self.bitfield[byte_index] |= 1 << (7-offset) 


    # def reset_piece(self,index):
    #     byte_index=index//8
    #     offset=index%8
    #     if index<0 or index >len(self.bitfield)-1:
    #         return False
    #     self.bitfield[byte_index] &= not(1 <<(7-offset))

    # def get_value(self)->bytes:
    #     return self.bitfield
    # def set_value(self,value:bytes=b''):
    #     self.bitfield =value

def bit_to_byte (function):
    @wraps(function)
    def wrapper (self, bit_index:int, *args, **kwargs):
        byte_index = bit_index // 8
        offset = bit_index % 8
        return function(self, byte_index, offset, *args, **kwargs)
    return wrapper

class Bitfield(bytearray):

    def __init__(self, bits_number: int):
        bytes_number = (bits_number + 7) // 8
        super().__init__(bytes_number)
        self._bits_number = bits_number

    def __len__(self):
        return  self._bits_number

    @bit_to_byte
    def set(self, byte_index: int, offset: int) -> None:
        # MSB first, e.g. Piece #1 01000000
        self[byte_index] |= 1 << (7-offset)

    @bit_to_byte
    def clear(self, byte_index: int, offset: int) -> None:
        self[byte_index] &= not(1 << (7-offset))

    @bit_to_byte
    def get(self, byte_index: int, offset: int) -> bool:
        return self[byte_index]>>(7-offset)&1!=0

    def get_all(self, bit: Literal[0, 1]) -> list[int]:
        result = []

        for index in range(len(self)):
            byte_index = index // 8
            bit_index = 7 - (index % 8)

            value = (self[byte_index] >> bit_index) & 1

            if value == bit:
                result.append(index)

        return result

    # def get_all(self, bit: Literal[0, 1]) -> list[int]:
        
    #     if not bit:
    #         mask = (1 << len(self)) - 1
    #         zero_bits = (~int.from_bytes(self, "little")) & mask
    #     else:
    #         zero_bits = int.from_bytes(self, "little")

    #     result = []

    #     while zero_bits:
    #         lowest = zero_bits & -zero_bits
    #         index = lowest.bit_length() - 1
    #         if index < len(self):
    #             result.append(index)

    #         # 清除最低的 1
    #         zero_bits &= zero_bits - 1

    #     return result