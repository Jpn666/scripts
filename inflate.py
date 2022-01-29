# -*- coding: utf-8 -*-
import sys


##############################################################################
## Aux stuff
##############################################################################

class BitReader(bytearray):
    """
    """

    def __init__(self, array):
        super(BitReader, self).__init__(array)
        self.bc     = 0
        self.buffer = 0
        self.offset = 0

    def getbits(self, length):
        if length == 0:
            return 0
        
        buffer = self.buffer
        while length > self.bc:
            self.buffer += self.pop(0) << self.bc
            self.bc     += 8
            self.offset += 1
        return self.buffer & ((1 << length) - 1)

    def dropbits(self, n):
        self.buffer = self.buffer >> n
        self.bc    -= n
        if self.bc < 0:
            raise Exception("Fuck")

    def getbyte(self):
        self.bc      = 0
        self.buffer  = 0
        self.offset += 1
        return self.pop(0)

    def getremaining(self):
        return self.buffer


class ByteBuffer(bytearray):
    """
    """

    def __init__(self):
        super().__init__(self)

    def copyblock(self, distance, length):
        index = len(self) - distance
        if index >= 0:
            for i in range(length):
                self.append(self[index + i])
            return
        raise Exception("Block distance overpass the beginning output stream")


def reversecode(code, length):
    rtable = [
        0x000, 0x008, 0x004, 0x00c,
        0x002, 0x00a, 0x006, 0x00e,
        0x001, 0x009, 0x005, 0x00d,
        0x003, 0x00b, 0x007, 0x00f
    ]
    if length < 8:
        r = rtable[code >> 4] + (rtable[code & 0x0f] << 4)
        return r >> (0x08 - length)
    a = (code >> 0) & 0xff
    b = (code >> 8) & 0xff
    
    a = rtable[a >> 4] | (rtable[a & 0x0f] << 4)
    b = rtable[b >> 4] | (rtable[b & 0x0f] << 4)
    r = b | (a << 8)

    return r >> (0x10 - length)


def reverseinc(code, length):
    def ffzero16(n):
        ffztable = [
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
            0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01,
            0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01,
            0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01,
            0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01,
            0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01,
            0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01,
            0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01,
            0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01, 0x01,
            0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02,
            0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02,
            0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02,
            0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02, 0x02,
            0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03,
            0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03, 0x03,
            0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04,
            0x05, 0x05, 0x05, 0x05, 0x06, 0x06, 0x07, 0x08
        ]

        r = ffztable[0xff & (n >> 8)]
        if (r == 0x08):
            r += ffztable[0xff & (n >> 0)]
        return r

    offset = 0x10 - length
    code   = code << offset

    s = 0x8000 >> ffzero16(code)
    if not s:
        return 0
    return ((code & (s - 1)) + s) >> offset


##############################################################################
## Main stuff
##############################################################################


class TableEntry(object):
    """
    """

    def __init__(self):
        self.symbol   = 0
        self.length   = 0
        self.subtable = None


def buildtable(lengths, mainbits):
    # count the number of codes of each length
    lencount = []
    for s in lengths:
        while s > len(lencount) - 1:
            lencount.append(0)
        lencount[s] += 1

    if lencount[0] == len(lengths):
        raise Exception("Invalid lengths")

    lencount[0] = 0
    maxlen = len(lencount) - 1
    
    j = 1
    for i in range(1, len(lencount)):
        j = (j << 1) - lencount[i]
        if j < 0:
            raise Exception("overlength code")
    
    if j > 0:
        raise Exception("incomplete code")
    
    # determine the first code of each length
    code     = 0
    nextcode = [0] * (maxlen + 1)
    for i in range(1, maxlen + 1):
        code = (code + lencount[i - 1]) << 1
        nextcode[i] = reversecode(code, i)

    table = [0] * (1 << mainbits)
    
    if maxlen > mainbits:
        # mark the entries as secondary tables
        remmask = (1 << (maxlen - mainbits)) - 1
        r = maxlen - mainbits

        for i in reversed(range(mainbits + 1, maxlen + 1)):
            count = lencount[i]
            if count:
                code    = nextcode[i] & ((1 << mainbits) - 1)
                entries = count >> r
                if count & remmask:
                    entries += 1
                
                index = code
                for j in range(entries):
                    if not table[index]:
                        entry = TableEntry()
                        entry.subtable = [0] * (1 << r)
                        entry.length   = r
                        table[index] = entry
                    index = reverseinc(index, mainbits)

            r -= 1
            remmask = remmask >> 1
    
    # build the table
    for j in range(len(lengths)):
        length = lengths[j]
        if length == 0:
            continue
        
        entry = TableEntry()
        entry.length = length
        entry.symbol = j
        
        code = nextcode[length]
        nextcode[length] = reverseinc(code, length)
        
        e = table[code & ((1 << mainbits) - 1)]
        if length > mainbits:
            if not isinstance(e, TableEntry):
                raise Exception("error")

            code = code >> mainbits
            r = e.length - (length - mainbits)
            
            length = length - mainbits
            m = e.subtable
        else:
            r = mainbits - length
            m = table


        for i in reversed(range(1 << r)):
            index = code | (i << length)
            m[index] = entry
    return table


LCODES_ROOTBITS = 0x0a
DCODES_ROOTBITS = 0x08


def decode(table, bb, mainbits):
    c = bb.getbits(mainbits)
    e = table[c]
    if e.subtable:
        bb.dropbits(mainbits)
        need = e.length
        
        c = bb.getbits(need)
        e = e.subtable[c]
        bb.dropbits(e.length - mainbits)
    else:
        bb.dropbits(e.length)
    #if debug:
    #    print("symbol", e.symbol, c & ((1<<e.length) - 1), e.length)
    return e.symbol


# In all cases, the decoding algorithm for the actual data is as
# follows:
# ...
#
# Note that a duplicated string reference may refer to a string
# in a previous block; i.e., the backward distance may cross one
# or more block boundaries.  However a distance cannot refer past
# the beginning of the output stream.  (An application using a
# preset dictionary might discard part of the output stream; a
# distance can refer to that part of the output stream anyway)
# Note also that the referenced string may overlap the current
# position; for example, if the last 2 bytes decoded have values
# X and Y, a string reference with <length = 5, distance = 2>
# adds X,Y,X,Y,X to the output stream.

# 3.2.5. Compressed blocks (length and distance codes)

# As noted above, encoded data blocks in the "deflate" format
# consist of sequences of symbols drawn from three conceptually
# distinct alphabets: either literal bytes, from the alphabet of
# byte values (0..255), or <length, backward distance> pairs,
# where the length is drawn from (3..258) and the distance is
# drawn from (1..32,768).  In fact, the literal and length
# alphabets are merged into a single alphabet (0..285), where
# values 0..255 represent literal bytes, the value 256 indicates
# end-of-block, and values 257..285 represent length codes
# (possibly in conjunction with extra bits following the symbol
# code) as follows:
#
#         Extra               Extra               Extra
#    Code Bits Length(s) Code Bits Lengths   Code Bits Length(s)
#    ---- ---- ------     ---- ---- -------   ---- ---- -------
#     257   0     3       267   1   15,16     277   4   67-82
#     258   0     4       268   1   17,18     278   4   83-98
#     259   0     5       269   2   19-22     279   4   99-114
#     260   0     6       270   2   23-26     280   4  115-130
#     261   0     7       271   2   27-30     281   5  131-162
#     262   0     8       272   2   31-34     282   5  163-194
#     263   0     9       273   3   35-42     283   5  195-226
#     264   0    10       274   3   43-50     284   5  227-257
#     265   1  11,12      275   3   51-58     285   0    258
#     266   1  13,14      276   3   59-66
#
# The extra bits should be interpreted as a machine integer
# stored with the most-significant bit first, e.g., bits 1110
# represent the value 14.
#
#          Extra           Extra               Extra
#     Code Bits Dist  Code Bits   Dist     Code Bits Distance
#     ---- ---- ----  ---- ----  ------    ---- ---- --------
#       0   0    1     10   4     33-48    20    9   1025-1536
#       1   0    2     11   4     49-64    21    9   1537-2048
#       2   0    3     12   5     65-96    22   10   2049-3072
#       3   0    4     13   5     97-128   23   10   3073-4096
#       4   1   5,6    14   6    129-192   24   11   4097-6144
#       5   1   7,8    15   6    193-256   25   11   6145-8192
#       6   2   9-12   16   7    257-384   26   12  8193-12288
#       7   2  13-16   17   7    385-512   27   12 12289-16384
#       8   3  17-24   18   8    513-768   28   13 16385-24576
#       9   3  25-32   19   8   769-1024   29   13 24577-32768

def decodeblock(lcodes, dcodes, bb, ostrm):
    lengths = [
        0x0003, 0x0004, 0x0005, 0x0006, 0x0007, 0x0008, 0x0009, 0x000a,
        0x000b, 0x000d, 0x000f, 0x0011, 0x0013, 0x0017, 0x001b, 0x001f,
        0x0023, 0x002b, 0x0033, 0x003b, 0x0043, 0x0053, 0x0063, 0x0073,
        0x0083, 0x00a3, 0x00c3, 0x00e3, 0x0102
    ]
    lengthsextra = [
        0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
        0x0001, 0x0001, 0x0001, 0x0001, 0x0002, 0x0002, 0x0002, 0x0002,
        0x0003, 0x0003, 0x0003, 0x0003, 0x0004, 0x0004, 0x0004, 0x0004,
        0x0005, 0x0005, 0x0005, 0x0005, 0x0000
    ]
    distances = [
        0x0001, 0x0002, 0x0003, 0x0004, 0x0005, 0x0007, 0x0009, 0x000d,
        0x0011, 0x0019, 0x0021, 0x0031, 0x0041, 0x0061, 0x0081, 0x00c1,
        0x0101, 0x0181, 0x0201, 0x0301, 0x0401, 0x0601, 0x0801, 0x0c01,
        0x1001, 0x1801, 0x2001, 0x3001, 0x4001, 0x6001
    ]
    distanceextra = [
        0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0x02, 0x02,
        0x03, 0x03, 0x04, 0x04, 0x05, 0x05, 0x06, 0x06,
        0x07, 0x07, 0x08, 0x08, 0x09, 0x09, 0x0a, 0x0a,
        0x0b, 0x0b, 0x0c, 0x0c, 0x0d, 0x0d
    ]
    while 1:
        symbol = decode(lcodes, bb, LCODES_ROOTBITS)
        
        if symbol < 256:
            ostrm.append(symbol)
            #print(symbol)

            continue
        
        if symbol == 256:
            break
        
        # decode distance
        symbol = symbol - 257
        
        n = lengthsextra[symbol]
        length = lengths[symbol] + bb.getbits(n)
        bb.dropbits(n)
        
        # get distance
        symbol = decode(dcodes, bb, DCODES_ROOTBITS)
        if symbol < 0:
            raise Exception()
        
        try:
            n = distanceextra[symbol]
        except IndexError:
            print(symbol)
            print(len(ostrm))
            exit()
        distance = distances[symbol] + bb.getbits(n)
        bb.dropbits(n)
        
        #print(f"{length} -> {distance}")
        ostrm.copyblock(distance, length)


# 3.2.4. Non-compressed blocks (BTYPE=00)

# Any bits of input up to the next byte boundary are ignored.
# The rest of the block consists of the following information:
#
#      0   1   2   3   4...
#    +---+---+---+---+================================+
#    |  LEN  | NLEN  |... LEN bytes of literal data...|
#    +---+---+---+---+================================+
#
# LEN is the number of data bytes in the block.  NLEN is the
# one's complement of LEN.

def stored(bb, ostrm):
    bln = bb.getbyte() | (bb.getbyte() << 8)
    nln = bb.getbyte() | (bb.getbyte() << 8)
    
    if (~bln & nln) != nln:
        raise Exception("Bad length value for stored block")
    while bln:
        ostrm.append(bb.getbyte())
        bln -= 1


# 3.2.6. Compression with fixed Huffman codes (BTYPE=01)

# The Huffman codes for the two alphabets are fixed, and are not
# represented explicitly in the data.  The Huffman code lengths
# for the literal/length alphabet are:
#
#           Lit Value    Bits        Codes
#           ---------    ----        -----
#             0 - 143     8          00110000 through
#                                    10111111
#           144 - 255     9          110010000 through
#                                    111111111
#           256 - 279     7          0000000 through
#                                    0010111
#           280 - 287     8          11000000 through
#                                    11000111
#
# The code lengths are sufficient to generate the actual codes,
# as described above; we show the codes in the table for added
# clarity.  Literal/length values 286-287 will never actually
# occur in the compressed data, but participate in the code
# construction.
#
# Distance codes 0-31 are represented by (fixed-length) 5-bit
# codes, with possible additional bits as shown in the table
# shown in Paragraph 3.2.5, above.  Note that distance codes 30-
# 31 will never actually occur in the compressed data.

def fixed(bb, ostrm):
    lengths = []
    lengths += [8] * 144
    lengths += [9] * (256 - 144)
    lengths += [7] * (280 - 256)
    lengths += [8] * (288 - 280)
    
    # literal - length table
    lcodes = buildtable(lengths, LCODES_ROOTBITS)
    
    # distance table
    lengths = []
    lengths += [5] * 32
    dcodes = buildtable(lengths, DCODES_ROOTBITS)
    
    decodeblock(lcodes, dcodes, bb, ostrm)


# 3.2.7. Compression with dynamic Huffman codes (BTYPE=10)

# The Huffman codes for the two alphabets appear in the block
# immediately after the header bits and before the actual
# compressed data, first the literal/length code and then the
# distance code.  Each code is defined by a sequence of code
# lengths, as discussed in Paragraph 3.2.2, above.  For even
# greater compactness, the code length sequences themselves are
# compressed using a Huffman code.  The alphabet for code lengths
# is as follows:
# 
#       0 - 15: Represent code lengths of 0 - 15
#           16: Copy the previous code length 3 - 6 times.
#               The next 2 bits indicate repeat length
#                     (0 = 3, ... , 3 = 6)
#                  Example:  Codes 8, 16 (+2 bits 11),
#                            16 (+2 bits 10) will expand to
#                            12 code lengths of 8 (1 + 6 + 5)
#           17: Repeat a code length of 0 for 3 - 10 times.
#               (3 bits of length)
#           18: Repeat a code length of 0 for 11 - 138 times
#               (7 bits of length)
# 
# A code length of 0 indicates that the corresponding symbol in
# the literal/length or distance alphabet will not occur in the
# block, and should not participate in the Huffman code
# construction algorithm given earlier.  If only one distance
# code is used, it is encoded using one bit, not zero bits; in
# this case there is a single code length of one, with one unused
# code.  One distance code of zero bits means that there are no
# distance codes used at all (the data is all literals).
# 
# We can now define the format of the block:
# 
#       5 Bits: HLIT, # of Literal/Length codes - 257 (257 - 286)
#       5 Bits: HDIST, # of Distance codes - 1        (1 - 32)
#       4 Bits: HCLEN, # of Code Length codes - 4     (4 - 19)
# 
#       (HCLEN + 4) x 3 bits: code lengths for the code length
#          alphabet given just above, in the order: 16, 17, 18,
#          0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15
# 
#          These code lengths are interpreted as 3-bit integers
#          (0-7); as above, a code length of 0 means the
#          corresponding symbol (literal/length or distance code
#          length) is not used.
# 
#       HLIT + 257 code lengths for the literal/length alphabet,
#          encoded using the code length Huffman code
# 
#       HDIST + 1 code lengths for the distance alphabet,
#          encoded using the code length Huffman code
# 
#       The actual compressed data of the block,
#          encoded using the literal/length and distance Huffman
#          codes
# 
#       The literal/length symbol 256 (end of data),
#          encoded using the literal/length Huffman code
# 
# The code length repeat codes can cross from HLIT + 257 to the
# HDIST + 1 code lengths.  In other words, all code lengths form
# a single sequence of HLIT + HDIST + 258 values.


blockcount = 0


def dynamic(bb, ostrm):
    cdlnsorder = [
        16, 17, 18, 0, 8, 7, 9, 6, 10, 5, 11, 4, 12, 3, 13, 2, 14, 1, 15
    ]
    
    hlit  = bb.getbits(5) + 257; bb.dropbits(5)
    hdist = bb.getbits(5) +   1; bb.dropbits(5)
    hclen = bb.getbits(4) +   4; bb.dropbits(4)

    lengths = [0] * 19
    for i in range(hclen):
        length = bb.getbits(3)
        lengths[cdlnsorder[i]] = length
        
        bb.dropbits(3)

    table = buildtable(lengths, 7)
    index = 0
    
    lengths = [0] * (hlit + hdist)
    while index < hlit + hdist:
        symbol = decode(table, bb, 7)
        
        if symbol < 16:
            lengths[index] = symbol
            index += 1
            continue
        if symbol == 16:
            length = bb.getbits(2) + 3
            bb.dropbits(2)
            
            s = lengths[index-1]
            for i in range(length):
                lengths[index] = s
                index += 1
            continue
        if symbol == 17:
            length = bb.getbits(3) + 3
            bb.dropbits(3)
            
            s = 0
            for i in range(length):
                lengths[index] = s
                index += 1
            continue
        if symbol == 18:
            length = bb.getbits(7) + 11
            bb.dropbits(7)
            
            s = 0
            for i in range(length):
                lengths[index] = s
                index += 1
            continue
    
    if lengths[256] == 0:
        raise Exception("missing BLOCK_END symbol")
    
    lcodes = buildtable(lengths[:hlit], LCODES_ROOTBITS)
    dcodes = buildtable(lengths[hlit:], DCODES_ROOTBITS)
    
    decodeblock(lcodes, dcodes, bb, ostrm)



# 3.2.3. Details of block format

# Each block of compressed data begins with 3 header bits
# containing the following data:
#
#    first bit       BFINAL
#    next 2 bits     BTYPE
#
# Note that the header bits do not necessarily begin on a byte
# boundary, since a block does not necessarily occupy an integral
# number of bytes.
#
# BFINAL is set if and only if this is the last block of the data
# set.
#
# BTYPE specifies how the data are compressed, as follows:
#
#    00 - no compression
#    01 - compressed with fixed Huffman codes
#    10 - compressed with dynamic Huffman codes
#    11 - reserved (error)
#
# The only difference between the two compressed cases is how the
# Huffman codes for the literal/length and distance alphabets are
# defined.

def inflate(data):
    global blockcount
    bb     = BitReader(data)
    ostrm  = ByteBuffer() 
    bfinal = 0
    
    while not bfinal:
        bfinal = bb.getbits(1)
        bb.dropbits(1)
        btype  = bb.getbits(2)
        bb.dropbits(2)
        
        #print(f"last block {bfinal}")
        #print(f"block type {btype} offset {len(ostrm)}")
        
        blockcount += 1
        if btype == 0:  # stored block
            stored(bb, ostrm)
            continue
        if btype == 1:  # fixed block
            fixed(bb, ostrm)
            continue
        if btype == 2:  # dynamic block
            dynamic(bb, ostrm)
            continue

        raise Exception("Invalid block type")
    
    return ostrm



message = b"this is an example for huffman encoding"


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: thisscript.py <input file> <output file>")
        exit()
    open(sys.argv[2], "wb").write(inflate(open(sys.argv[1], "rb").read()))
