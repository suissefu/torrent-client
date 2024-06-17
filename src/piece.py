class Piece():
    def __init__(self,index,hash,length,data=None):

        self.index=index
        self.hash=hash
        self.length=length
        self.data=bytearray(length)
        self.downloaded=0
        self.requested=0
        self.downloaded_by_client=None