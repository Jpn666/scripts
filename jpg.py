# -*- coding: utf-8 -*-
import math
import sys


# Jpg markers
def definemarkers():
    SOI  = 0xffd8
    EOI  = 0xffd9

    APP0 = 0xffe0
    APP1 = 0xffe1
    APP2 = 0xffe2
    APP3 = 0xffe3
    APP4 = 0xffe4
    APP5 = 0xffe5
    APP6 = 0xffe6
    APP7 = 0xffe7
    APP8 = 0xffe8
    APP9 = 0xffe9
    APPA = 0xffea
    APPB = 0xffeb
    APPC = 0xffec
    APPD = 0xffed
    APPE = 0xffee
    APPF = 0xffef

    DQT  = 0xffdb
    DHT  = 0xffc4

    SOF0 = 0xffc0
    SOF1 = 0xffc1
    SOF2 = 0xffc2
    SOF3 = 0xffc3
    SOF4 = 0xffc4
    SOF5 = 0xffc5
    SOF6 = 0xffc5
    SOF7 = 0xffc7
    SOF9 = 0xffc9
    SOFA = 0xffca
    SOFB = 0xffcb
    SOFD = 0xffcd
    SOFE = 0xffce
    SOFF = 0xffcf

    DRI  = 0xffdd
    SOS  = 0xffda

    RST0 = 0xffd0
    RST1 = 0xffd1
    RST2 = 0xffd2
    RST3 = 0xffd3
    RST4 = 0xffd4
    RST5 = 0xffd5
    RST6 = 0xffd6
    RST7 = 0xffd7

    DNL  = 0xffdc

    globals().update(locals())

    # map value to string
    r = {}

    key   = 0
    value = 0
    for key, value in locals().items():
        if key != "r":
            r[value] = key
    return r


markers = definemarkers()


###############################################################################
# AUX stuff
###############################################################################


class BitStream(object):
    """docstring for BitStream"""

    def __init__(self, handler):
        super(BitStream, self).__init__()

        self.handler = handler
        self.bc = 0  # bit buffer remaining bits
        self.bb = 0  # bit buffer
        self.overread = False

    def getbits(self, n):
        while self.bc < n:
            m = ord(self.handler.read(1))
            if m == 0xff:
                b = ord(self.handler.read(1))
                if b == 0x00:
                    m = 0xff
                else:
                    self.handler.seek(-2, 1)
                    self.overread = True
                    m = 0
            self.bb  = (self.bb << 8) | m
            self.bc += 8
        return self.bb >> (self.bc - n)

    def dropbits(self, n):
        self.bb  = self.bb & ((1 << (self.bc - n)) - 1)
        self.bc -= n

    def fetch(self, n):
        r = self.getbits(n)
        self.dropbits(n)
        return r


class HuffmanTree(object):
    """docstring for HuffmanTree"""

    def __init__(self, lengths, symbols):
        # condensed huffman table
        self.mincode = [0] * 16  #
        self.maxcode = [0] * 16  #
        self.soffset = [0] * 16  # symbol offset

        self.symbols = symbols

        # input
        self.bitstream = None

        c = 0
        m = 0
        for i in range(0, 16):
            self.mincode[i] = c
            self.maxcode[i] = c + lengths[i]
            self.soffset[i] = m

            c = self.maxcode[i] << 1

            # pre shift to left
            self.maxcode[i] = self.maxcode[i] << (15 - i)
            m += lengths[i]

    def setinput(self, bitstream):
        self.bitstream = bitstream

    def decode(self):
        code = self.bitstream.getbits(16)

        j = 16
        for i in range(16):
            if code < self.maxcode[i]:
                j = i
                break

        if j < 16:
            index = self.soffset[j] + ((code >> (15 - j)) - self.mincode[j])
            try:
                symbol = self.symbols[index]
            except IndexError:
                raise Exception("invalid code")
            self.bitstream.dropbits(j + 1)
            return symbol

        raise Exception("invalid code")


def read16(handler, avance=True):
    r = handler.read(2)
    if len(r) != 2:
        raise Exception(f"not a marker (read <> 2) {r}")

    if not avance:
        handler.seek(handler.tell() - 2)
    return r[0] << 8 | r[1]


###############################################################################
# Decoder
###############################################################################


class JPGComponent(object):
    """
    """

    def __init__(self):
        # quantization table
        self.qtable    = None
        self.id        = -1  # component id

        # huffman code tables
        self.dchuffman = None
        self.achuffman = None

        # coefficient
        self.coff = 0

        self.xsampling = 0
        self.ysampling = 0
        self.ys = 0
        self.xs = 0

        # size (in blocks) without padding
        self.nrows = 0
        self.ncols = 0

        self.bmap = []  # block map
        self.smap = []  # sample map

        # raw code units (complete scan is image is non-interleaved)
        self.scan   = None

        # decoded units
        self.blocks = []


class JPG(object):
    """
    """

    def __init__(self, handler):
        self.majorversion  = 0
        self.minorversion  = 0

        self.bitspersample = 0
        self.numcomponents = 0

        # image size
        self.sizey = 0
        self.sizex = 0
        self.image = []

        self.decoded = False

        # input stream
        self.handler = handler

        # restart interval in MCU units
        self.rinterval = 0

        # components in scan
        self.sccount = 0

        # bit reader
        self.bitstream = None

        # quatization tables
        self.QT = [None] * 4

        # 0: DC 1: AC
        self.HT = []
        for i in range(2):
            self.HT.append([None] * 4)

        self.isprogressive = False
        self.isinterleaved = True

        self.ysampling = 0
        self.xsampling = 0
        self.nrows = 0
        self.ncols = 0

        # sucessive aproximation
        self.al = 0
        self.ah = 0

        # spectral selection start and end
        self.ss = 0
        self.se = 0

        # pass
        self.npass = 0

        # JFIF uses either 1 component (Y, greyscaled) or 3 components
        self.components = []
        for i in range(4):
            self.components.append(JPGComponent())

        # component order in the scan
        self.corder = [0, 1, 2]
        self.isrgb  = False

        # component in the scan
        self.scancomponent = 0
        self.eobrun = 0

        self.iccp = None
        self.iccpsize = 0


# segment parsers

def parseAPP0(handler, jpg):
    position = handler.tell()
    r = read16(handler)
    s = handler.read(5)

    signature = s[:4]
    if signature != b"JFIF" and signature != b"JFXX":
        if signature == b"Ocad":
            remaining = handler.tell() - position
            handler.read(r - remaining)
            return
        raise Exception(f"bad signature {s[:4]}")

    jpg.majorversion = ord(handler.read(1))
    jpg.minorversion = ord(handler.read(1))
    if jpg.majorversion != 1:
        print("version may not be supported")

    # density units
    handler.read(1)
    handler.read(2)  # x density
    handler.read(2)  # y density

    remaining = handler.tell() - position
    handler.read(r - remaining)


def parseDQT(handler, jpg):
    position = handler.tell()
    r = read16(handler)

    def readtable():
        s = ord(handler.read(1))
        tableid   = (s >> 0) & 0x0f
        precision = (s >> 4) & 0x0f
        if precision:
            precision = 2  # 16 bit
        else:
            precision = 1  # 8 bit

        if tableid > 3:
            raise Exception("quantization table id > 3")

        table = []
        for i in range(64):
            if precision == 1:
                table.append(ord(handler.read(1)))
                continue

            # 16 bits
            a = ord(handler.read(1))
            b = ord(handler.read(1))
            table.append((a << 8) | b)
        jpg.QT[tableid] = table

    remaining = 1
    while remaining:
        readtable()
        remaining = r - (handler.tell() - position)


def getblockmap(isampling, csampling):
    ys = isampling[0] // csampling[0]
    xs = isampling[1] // csampling[1]

    iy = 64 // ys
    ix = 8  // xs

    i = 0
    n = 0
    r = [0] * (isampling[0] * isampling[1])
    a = [0] * (isampling[0] * isampling[1])
    for y in range(isampling[0]):
        for x in range(isampling[1]):
            r[i] = ((y // ys) * csampling[1]) + (x // xs)
            a[i] = (n + ((x * ix) & 0x07)) & 0x3f
            i += 1
        n += iy

    def getmap():
        bx = [0, 0, 1, 0, 2]
        by = [0, 0, 3, 0, 6]
        y = isampling[0] // csampling[0]
        x = isampling[1] // csampling[1]
        return offsetmap[by[y] + bx[x]]

    # block index, map offset
    return [r, a, getmap()]


def findcomponent(jpg, n):
    j = 0
    for c in jpg.components:
        if c.id == n:
            return j
        j += 1
    return None


def parseSOF0(handler, jpg):
    position = handler.tell()
    r = read16(handler)

    s = ord(handler.read(1))
    if s != 8 and s != 12 and s != 16:
       raise Exception("bad sample values")
    jpg.bitspersample = s

    # limit the sample to 8 cuz we can UwU
    if s != 8:
        raise Exception(f"bit sample {s} not supported")

    # image size
    sizey = read16(handler)
    sizex = read16(handler)
    if sizex == 0 or sizey == 0:
       raise Exception("image size values are wrong")

    jpg.sizey = sizey
    jpg.sizex = sizex
    print(f"image size y:{sizey} x:{sizex}")

    # jfif only has support for 1 or 3 components
    s = ord(handler.read(1))
    if s != 1 and s != 3:
        raise Exception(f"number of components <> 1 and <> 3 {s}")
    jpg.numcomponents = s

    ysampling = 0
    xsampling = 0

    # note: yuv may starts at component id 0, RGB DCT images uses
    # components ids: chr(82) + chr(71) + chr(66) (RGB)
    for i in range(jpg.numcomponents):
        c = ord(handler.read(1))

        component = jpg.components[i]
        component.id = c

        print(f"component {i} = id({c})")

        # sampling factors (vertical, horizontal)
        j = ord(handler.read(1))
        ys = (j >> 0) & 0x0f
        xs = (j >> 4) & 0x0f
        print(f"sampling {c} {ys} {xs}")

        if ys != 1 and ys != 2 and ys != 4:
            raise Exception("invalid sampling (not supported)")
        if xs != 1 and xs != 2 and xs != 4:
            raise Exception("invalid sampling (not supported)")

        component.ysampling = ys
        component.xsampling = xs
        if ys > ysampling:
            ysampling = ys
        if xs > xsampling:
            xsampling = xs

        # quantization table (it must be defined)
        j = ord(handler.read(1))
        if j > 3:
            raise Exception(f"quantization table {j} out of range (0, 3)")
        if jpg.QT[j] == None:
            raise Exception(f"quantization table {j} not defined")
        component.qtable = jpg.QT[j]

    if jpg.numcomponents == 3:
        j = 0
        for c in ["R", "G", "B"]:
            if jpg.components[j].id != ord(c):
                break
            j += 1
        jpg.isrgb = j == 3

    # calculate the MCU dimensions and block count
    nrows = (jpg.sizey + ((ysampling * 8) - 1)) // (ysampling * 8)
    ncols = (jpg.sizex + ((xsampling * 8) - 1)) // (xsampling * 8)

    jpg.ysampling = ysampling
    jpg.xsampling = xsampling
    jpg.nrows = nrows
    jpg.ncols = ncols

    for i in range(jpg.numcomponents):
        c = jpg.components[i]

        c.ys = ysampling // c.ysampling
        c.xs = xsampling // c.xsampling
        sy = c.ys * 8
        sx = c.xs * 8
        c.nrows = (jpg.sizey + sy - 1) // sy
        c.ncols = (jpg.sizex + sx - 1) // sx

        a = getblockmap((ysampling, xsampling), (c.ysampling, c.xsampling))
        c.bindex = a[0]  # block index
        c.offset = a[1]  # entry offset
        c.bmap   = a[2]  # offset map

        for i in range(c.ysampling * c.xsampling):
            c.blocks.append([0] * 64)

    remaining = handler.tell() - position
    handler.read(r - remaining)

    # result (image)
    r = []
    for i in range(jpg.sizey * jpg.sizex):
        if jpg.numcomponents == 3:
            r.append((0, 0, 0))
        if jpg.numcomponents == 1:
            r.append(0)
    jpg.image = r


def parseDHT(handler, jpg):
    position = handler.tell()
    r = read16(handler)

    def readtable():
        s = ord(handler.read(1))
        tid   = (s >> 0) & 0x0f
        ttype = (s >> 4) & 0x01  # 0: DC table, 1: AC table

        if (ttype != 0 and ttype != 1) or tid > 3:
            raise Exception(f"wrong huffman table type({ttype}) or id({tid})")

        print(f"table {tid} type:",  ["DC", "AC"][ttype])

        lengths = []
        symbols = []

        total = 0
        for i in range(16):
            c = ord(handler.read(1))
            total += c
            lengths.append(c)

        for i in range(total):
            symbols.append(ord(handler.read(1)))
        print("lengths:", lengths)
        print("symbols:", symbols)

        ht = HuffmanTree(lengths, symbols)
        jpg.HT[ttype][tid] = ht

    remaining = 1
    while remaining:
        readtable()
        remaining = r - (handler.tell() - position)


def initblocks(jpg):
    # stuffed size
    mcusy = jpg.nrows * (jpg.ysampling << 3)
    mcusx = jpg.ncols * (jpg.xsampling << 3)

    blocks = []
    for i in range(jpg.numcomponents):
        c = jpg.components[i]

        nrows = mcusy // ((jpg.ysampling // c.ysampling) * 8)
        ncols = mcusx // ((jpg.xsampling // c.xsampling) * 8)
        c.irows = nrows
        c.icols = ncols

        r = []
        for y in range(nrows * ncols):
            r.append([0] * 64)
        c.scan = r


def parseSOS(handler, jpg):
    position = handler.tell()
    r = read16(handler)

    s = ord(handler.read(1))
    if s != 1 and s != 3:
        raise Exception("bad number of components")

    component = None

    print(f"SOS: number of components {s}")
    corder = []
    for i in range(s):
        c = ord(handler.read(1))  # component ID
        j = ord(handler.read(1))

        n = findcomponent(jpg, c)
        if n == None:
            raise Exception("invalid component id")

        if n in corder:
            raise Exception("duplicate scan component")
        corder.append(n)

        jpg.scancomponent = n
        print(f"component {n}")

        ac = (j >> 0) & 0xf
        dc = (j >> 4) & 0xf
        if ac > 3 or dc > 3:
            raise Exception("bad huffman table index (not supported)")
        print(f"DC table {dc}")
        print(f"AC table {ac}")

        component = jpg.components[n]
        component.dchuffman = jpg.HT[0][dc]
        component.achuffman = jpg.HT[1][ac]
    jpg.corder = corder
    #if jpg.isrgb:
    #    print(jpg.corder)
    #    exit(0)

    jpg.sccount = s
    if jpg.isprogressive:
        ss = ord(handler.read(1))
        se = ord(handler.read(1))

        j = ord(handler.read(1))
        ah = (j >> 4) & 0xf
        al = (j >> 0) & 0xf

        v = True
        if ss == 0 or se == 0:
            if se or ss:
                v = False
        else:
            if ss > se:
                v = False
            else:
                if se > 63:
                    v = False

        if v == False:
            raise Exception("bad spectral selection")

        if ah > 13 or al > 13:
            raise Exception("bad succesive aproximation")

        print(f"spectral start {ss}, end: {se}")
        print(f"sucessive aproximation high {ah}")
        print(f"sucessive aproximation  low {al}")

        jpg.ss = ss
        jpg.se = se

        jpg.ah = ah
        jpg.al = al
        if ss == 0:
            isvalid = True
            if jpg.sccount != 1:
                for i in range(jpg.numcomponents):
                    c = jpg.components[i]
                    if c.dchuffman == None:
                        isvalid = False
            else:
                if component.dchuffman == None:
                    isvalid = False

            if isvalid == False:
                raise Exception("required DC huffman table not defined")

        else:
            if component.achuffman == None:
                raise Exception("required AC huffman table not defined")
    else:
        # skip 3 bytes
        handler.read(3)

    remaining = r - (handler.tell() - position)
    if remaining:
        raise Exception("invalid data")

    if jpg.npass == 0:
        jpg.isinterleaved = True
        if s != jpg.numcomponents:
            jpg.isinterleaved = False
        if jpg.isprogressive or jpg.isinterleaved == False:
            pass
        initblocks(jpg)

    if jpg.isprogressive == False:
        if jpg.isinterleaved == False:
            decode(handler, jpg, component)
        else:
            decode(handler, jpg)
    else:
        decodepass(handler, jpg)


def inittable():
    r = []
    for u in range(8):
        a = []
        for v in range(8):
            alpha = 0.5
            if v == 0:
                alpha = 0.35355339059327373
            a.append(math.cos(v * math.pi * (((u * 2) + 1) * 0.0625)) * alpha)
        r.append(a)
    return r


mm = inittable()


def IDCTblock(block, r, nmm=None):
    if nmm == None:
        nmm = mm

    for y in range(8):
        r[(y * 8) + 0] = round(IDCT(block, y, 0, nmm))
        r[(y * 8) + 1] = round(IDCT(block, y, 1, nmm))
        r[(y * 8) + 2] = round(IDCT(block, y, 2, nmm))
        r[(y * 8) + 3] = round(IDCT(block, y, 3, nmm))
        r[(y * 8) + 4] = round(IDCT(block, y, 4, nmm))
        r[(y * 8) + 5] = round(IDCT(block, y, 5, nmm))
        r[(y * 8) + 6] = round(IDCT(block, y, 6, nmm))
        r[(y * 8) + 7] = round(IDCT(block, y, 7, nmm))
    return r


def IDCT(block, y, x, nmm):
    r = 0
    mmx = nmm[x]
    mmy = nmm[y]
    for u in range(8):
        a = mmx[u]

        r += block[(u * 8) + 0] * mmy[0] * a
        r += block[(u * 8) + 1] * mmy[1] * a
        r += block[(u * 8) + 2] * mmy[2] * a
        r += block[(u * 8) + 3] * mmy[3] * a
        r += block[(u * 8) + 4] * mmy[4] * a
        r += block[(u * 8) + 5] * mmy[5] * a
        r += block[(u * 8) + 6] * mmy[6] * a
        r += block[(u * 8) + 7] * mmy[7] * a
    return r


zmatrix = [
     0,  2,  3,  9, 10, 20, 21, 35,
     1,  4,  8, 11, 19, 22, 34, 36,
     5,  7, 12, 18, 23, 33, 37, 48,
     6, 13, 17, 24, 32, 38, 47, 49,
    14, 16, 25, 31, 39, 46, 50, 57,
    15, 26, 30, 40, 45, 51, 56, 58,
    27, 29, 41, 44, 52, 55, 59, 62,
    28, 42, 43, 53, 54, 60, 61, 63
]


def decodeblock(jpg, component, block, update=True):
    dchuff = component.dchuffman
    achuff = component.achuffman

    for i in range(64):
        block[i] = 0

    # expand
    def decode(symbol, v):
        n = 2 ** (symbol - 1)
        if v >= n:
            return v
        return v - ((n * 2) - 1)  # v - ((n << 1) - 1)

    s = dchuff.decode()
    component.coff += decode(s, jpg.bitstream.fetch(s))
    block[0] = component.coff

    i = 1
    while i < 64:
        s = achuff.decode()
        if s == 0:
            break

        if s > 15:
            i += s >> 4
            s = s & 0x0f

        v = jpg.bitstream.fetch(s)
        if i < 64:
            c = decode(s, v)
            block[i] = c
            i += 1

    # decode
    if update == False:
        return
    for i in range(64):
        block[i] = block[i] * component.qtable[i]

    t0 = [0] * 64
    for i in range(64):
        t0[i] = block[zmatrix[i]]

    # reverse DCT and copy
    IDCTblock(t0, block)


def setdecoder(handler, jpg):
    # setup the huffman tables (set the input)
    bitstream = BitStream(handler)
    for i in range(jpg.numcomponents):
        # we use the same bitstream (input) for all the huffman tables
        ac = jpg.components[i].achuffman
        dc = jpg.components[i].dchuffman
        if ac:
            ac.bitstream = bitstream
        if dc:
            dc.bitstream = bitstream

    jpg.bitstream = bitstream


def transformcolor(r1, r2, r3, isrgb):
    if isrgb == False:
        r = (r3 * 1.4020000000000001) + r1
        b = (r2 * 1.772             ) + r1
        g = (r1 - (0.114 * b) - (0.299 * r)) * 1.7035775127768313

        r1 = r
        r2 = g
        r3 = b
    r1 = int(max(0, min(255, r1 + 128)))
    r2 = int(max(0, min(255, r2 + 128)))
    r3 = int(max(0, min(255, r3 + 128)))
    return (r1, r2, r3)


offsetmap = [
    [ # 1 1
        0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
        0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f,
        0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17,
        0x18, 0x19, 0x1a, 0x1b, 0x1c, 0x1d, 0x1e, 0x1f,
        0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27,
        0x28, 0x29, 0x2a, 0x2b, 0x2c, 0x2d, 0x2e, 0x2f,
        0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37,
        0x38, 0x39, 0x3a, 0x3b, 0x3c, 0x3d, 0x3e, 0x3f,
    ],
    [ # 1 2
        0x00, 0x00, 0x01, 0x01, 0x02, 0x02, 0x03, 0x03,
        0x08, 0x08, 0x09, 0x09, 0x0a, 0x0a, 0x0b, 0x0b,
        0x10, 0x10, 0x11, 0x11, 0x12, 0x12, 0x13, 0x13,
        0x18, 0x18, 0x19, 0x19, 0x1a, 0x1a, 0x1b, 0x1b,
        0x20, 0x20, 0x21, 0x21, 0x22, 0x22, 0x23, 0x23,
        0x28, 0x28, 0x29, 0x29, 0x2a, 0x2a, 0x2b, 0x2b,
        0x30, 0x30, 0x31, 0x31, 0x32, 0x32, 0x33, 0x33,
        0x38, 0x38, 0x39, 0x39, 0x3a, 0x3a, 0x3b, 0x3b,
    ],
    [ # 1 4
        0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0x01, 0x01,
        0x08, 0x08, 0x08, 0x08, 0x09, 0x09, 0x09, 0x09,
        0x10, 0x10, 0x10, 0x10, 0x11, 0x11, 0x11, 0x11,
        0x18, 0x18, 0x18, 0x18, 0x19, 0x19, 0x19, 0x19,
        0x20, 0x20, 0x20, 0x20, 0x21, 0x21, 0x21, 0x21,
        0x28, 0x28, 0x28, 0x28, 0x29, 0x29, 0x29, 0x29,
        0x30, 0x30, 0x30, 0x30, 0x31, 0x31, 0x31, 0x31,
        0x38, 0x38, 0x38, 0x38, 0x39, 0x39, 0x39, 0x39,
    ],
    [ # 2 1
        0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
        0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
        0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f,
        0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f,
        0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17,
        0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17,
        0x18, 0x19, 0x1a, 0x1b, 0x1c, 0x1d, 0x1e, 0x1f,
        0x18, 0x19, 0x1a, 0x1b, 0x1c, 0x1d, 0x1e, 0x1f,
    ],
    [ # 2 2
        0x00, 0x00, 0x01, 0x01, 0x02, 0x02, 0x03, 0x03,
        0x00, 0x00, 0x01, 0x01, 0x02, 0x02, 0x03, 0x03,
        0x08, 0x08, 0x09, 0x09, 0x0a, 0x0a, 0x0b, 0x0b,
        0x08, 0x08, 0x09, 0x09, 0x0a, 0x0a, 0x0b, 0x0b,
        0x10, 0x10, 0x11, 0x11, 0x12, 0x12, 0x13, 0x13,
        0x10, 0x10, 0x11, 0x11, 0x12, 0x12, 0x13, 0x13,
        0x18, 0x18, 0x19, 0x19, 0x1a, 0x1a, 0x1b, 0x1b,
        0x18, 0x18, 0x19, 0x19, 0x1a, 0x1a, 0x1b, 0x1b,
    ],
    [ # 2 4
        0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0x01, 0x01,
        0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0x01, 0x01,
        0x08, 0x08, 0x08, 0x08, 0x09, 0x09, 0x09, 0x09,
        0x08, 0x08, 0x08, 0x08, 0x09, 0x09, 0x09, 0x09,
        0x10, 0x10, 0x10, 0x10, 0x11, 0x11, 0x11, 0x11,
        0x10, 0x10, 0x10, 0x10, 0x11, 0x11, 0x11, 0x11,
        0x18, 0x18, 0x18, 0x18, 0x19, 0x19, 0x19, 0x19,
        0x18, 0x18, 0x18, 0x18, 0x19, 0x19, 0x19, 0x19,
    ],
    [ # 4 1
        0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
        0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
        0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
        0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
        0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f,
        0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f,
        0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f,
        0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f,
    ],
    [ # 4 2
        0x00, 0x00, 0x01, 0x01, 0x02, 0x02, 0x03, 0x03,
        0x00, 0x00, 0x01, 0x01, 0x02, 0x02, 0x03, 0x03,
        0x00, 0x00, 0x01, 0x01, 0x02, 0x02, 0x03, 0x03,
        0x00, 0x00, 0x01, 0x01, 0x02, 0x02, 0x03, 0x03,
        0x08, 0x08, 0x09, 0x09, 0x0a, 0x0a, 0x0b, 0x0b,
        0x08, 0x08, 0x09, 0x09, 0x0a, 0x0a, 0x0b, 0x0b,
        0x08, 0x08, 0x09, 0x09, 0x0a, 0x0a, 0x0b, 0x0b,
        0x08, 0x08, 0x09, 0x09, 0x0a, 0x0a, 0x0b, 0x0b,
    ],
    [ # 4 4, not used, more than 10 units per MCU
        0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0x01, 0x01,
        0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0x01, 0x01,
        0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0x01, 0x01,
        0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0x01, 0x01,
        0x08, 0x08, 0x08, 0x08, 0x09, 0x09, 0x09, 0x09,
        0x08, 0x08, 0x08, 0x08, 0x09, 0x09, 0x09, 0x09,
        0x08, 0x08, 0x08, 0x08, 0x09, 0x09, 0x09, 0x09,
        0x08, 0x08, 0x08, 0x08, 0x09, 0x09, 0x09, 0x09,
    ]
]


def setpixels3(jpg, y, x):
    origin = []
    for yo in range(jpg.ysampling):
        for xo in range(jpg.xsampling):
            origin.append([yo * 8, xo * 8])

    mcussizey = jpg.ysampling * 8
    mcussizex = jpg.xsampling * 8
    i = 0

    c1 = jpg.components[0]
    c2 = jpg.components[1]
    c3 = jpg.components[2]

    # LUT up-sample
    for v in origin:
        d1 = c1.offset[i]
        i1 = c1.bindex[i]
        d2 = c2.offset[i]
        d3 = c3.offset[i]
        i2 = c2.bindex[i]
        i3 = c3.bindex[i]

        row = y * mcussizey + v[0]
        for stepy in range(8):
            if row >= jpg.sizey:
                break

            col = x * mcussizex + v[1]
            for stepx in range(8):
                if col >= jpg.sizex:
                    break
                offset = (row * jpg.sizex) + col

                s = stepx + (stepy * 8)
                pixel = transformcolor(
                    c1.blocks[i1][c1.bmap[s] + d1],
                    c2.blocks[i2][c2.bmap[s] + d2],
                    c3.blocks[i3][c3.bmap[s] + d3], jpg.isrgb)
                jpg.image[offset] = pixel
                col += 1
            row += 1
        i += 1


def setpixels1(jpg, y, x, block):
    row = y * 8
    for stepy in range(8):
        if row >= jpg.sizey:
            break

        col = x * 8
        for stepx in range(8):
            if col >= jpg.sizex:
                break
            offset = (row * jpg.sizex) + col

            pixel = transformcolor(block[stepx + (stepy * 8)], 1.0, 1.0, True)
            jpg.image[offset] = pixel[0]
            col += 1
        row += 1


def checkrinterval(handler, jpg):
    m = ord(handler.read(1))
    if m != 0xff:
        raise Exception("invalid restart interval value")

    while True:
        m = ord(handler.read(1))
        if m != 0xff:
            break

    # reset the cofficients and the bitstream
    for i in range(jpg.numcomponents):
        c = jpg.components[i]
        c.coff = 0
        jpg.bitstream.bc = 0
        jpg.bitstream.bb = 0


def decode(handler, jpg, component=None):
    setdecoder(handler, jpg)

    # non interleaved component
    if component:
        rinterval = jpg.rinterval
        for y in range(component.nrows):
            for x in range(component.ncols):
                if jpg.rinterval:
                    if rinterval == 0:
                        checkrinterval(handler, jpg)
                        rinterval = jpg.rinterval
                    rinterval -= 1

                n = (y * component.icols) + x
                decodeblock(jpg, component, component.scan[n], False)
        return

    def docomponent(component):
        n = 0
        for ys in range(component.ysampling):
            for xs in range(component.xsampling):
                decodeblock(jpg, component, component.blocks[n])
                n += 1
    rinterval = jpg.rinterval

    if jpg.numcomponents == 1:
        c = jpg.components[0]
        for y in range(c.nrows):
            for x in range(c.ncols):
                decodeblock(jpg, c, c.blocks[0])
                setpixels1(jpg, y, x, c.blocks[0])

        jpg.decoded = True
        return

    for y in range(jpg.nrows):
        for x in range(jpg.ncols):
            if jpg.rinterval:
                if rinterval == 0:
                    checkrinterval(handler, jpg)
                    rinterval = jpg.rinterval
                rinterval -= 1

            for i in jpg.corder:
                docomponent(jpg.components[i])

            setpixels3(jpg, y, x)

    jpg.decoded = True
    print("decoding done")


###############################################################################
# Progressive decoding
###############################################################################


def decodefirstDC(jpg, component, block):
    dchuff = component.dchuffman

    def decode(symbol, v):
        n = 2 ** (symbol - 1)
        if v >= n:
            return v
        return v - ((n * 2) - 1)

    s = dchuff.decode()
    component.coff += decode(s, jpg.bitstream.fetch(s))
    block[0] = int(component.coff) << jpg.al


def readfirstDC(jpg):
    rinterval = jpg.rinterval

    def docomponent(c, y, x):
        y1 = y * c.ysampling
        x1 = x * c.xsampling
        for y2 in range(c.ysampling):
            offsety = y1 + y2
            for x2 in range(c.xsampling):
                n = (offsety * c.icols) + x1 + x2
                decodefirstDC(jpg, c, c.scan[n])

    singlecomponent = (jpg.numcomponents == 1) or (jpg.isinterleaved == False)
    totaly = jpg.nrows
    totalx = jpg.ncols

    c = jpg.components[jpg.scancomponent]
    if singlecomponent:
        totaly = c.nrows
        totalx = c.ncols

    for y in range(totaly):
        for x in range(totalx):
            if jpg.rinterval:
                if rinterval == 0:
                    checkrinterval(jpg.handler, jpg)
                    rinterval = jpg.rinterval
                rinterval -= 1

            if singlecomponent == False:
                for i in jpg.corder:
                    docomponent(jpg.components[i], y, x)
                continue

            n = (y * c.icols) + x
            decodefirstDC(jpg, c, c.scan[n])

    #for i in range(jpg.numcomponents):
    #    c = jpg.components[i + 1]
    #    print(f"component {i}")
    #    print(f"irows {c.irows}, icols {c.icols}")
    #    print(f"nrows {c.nrows}, ncols {c.ncols}")
    #    print(c.bmap)
    #    print(c.offset)
    #    print(c.bindex)
    #exit(0)

def refineDC(jpg):
    rinterval = jpg.rinterval

    def refine(block):
        s = jpg.bitstream.fetch(1)
        block[0] = block[0] | (s << jpg.al)

    def docomponent(c, y, x):
        y1 = y * c.ysampling
        x1 = x * c.xsampling
        for y2 in range(c.ysampling):
            offsety = y1 + y2
            for x2 in range(c.xsampling):
                n = (offsety * c.icols) + x1 + x2
                refine(c.scan[n])

    singlecomponent = (jpg.numcomponents == 1) or (jpg.isinterleaved == False)
    totaly = jpg.nrows
    totalx = jpg.ncols

    c = jpg.components[jpg.scancomponent]
    if singlecomponent:
        totaly = c.nrows
        totalx = c.ncols

    for y in range(totaly):
        for x in range(totalx):
            if jpg.rinterval:
                if rinterval == 0:
                    checkrinterval(jpg.handler, jpg)
                    rinterval = jpg.rinterval
                rinterval -= 1

            if singlecomponent == False:
                for i in jpg.corder:
                    docomponent(jpg.components[i], y, x)
                continue
            refine(c.scan[(y * c.icols) + x])


def decodefirstAC(jpg, component, block):
    achuff = component.achuffman
    if jpg.eobrun > 0:
        jpg.eobrun -= 1
        return

    def decode(symbol, v):
        n = 2 ** (symbol - 1)
        if v >= n:
            return v
        return v - ((2 * n) - 1)

    i = jpg.ss
    while i <= jpg.se:
        s = achuff.decode()

        a = (s >> 0) & 0xf
        b = (s >> 4)
        if a == 0:
            if b == 15:
                i += 16
            else:
                if b != 0:
                    s = jpg.bitstream.fetch(b)
                    jpg.eobrun = (1 << b) + s - 1
                    return
                break
        else:
            i += b
            if i >= 64:
                raise Exception("error: data out of range")

            v = jpg.bitstream.fetch(a)
            c = decode(a, v)

            block[i] = int(c) << jpg.al
            i += 1
    jpg.eobrun = 0


def readfirstAC(jpg):
    rinterval = jpg.rinterval

    # current pass component
    c = jpg.components[jpg.scancomponent]

    jpg.eobrun = 0
    for y in range(c.nrows):
        for x in range(c.ncols):
            if jpg.rinterval:
                if rinterval == 0:
                    checkrinterval(jpg.handler, jpg)
                    rinterval = jpg.rinterval
                rinterval -= 1

            n = (y * c.icols) + x
            decodefirstAC(jpg, c, c.scan[n])


def decoderefineAC(jpg, component, block):
    achuff = component.achuffman

    def refinecofficient(aproximation, value):
        nextbit = jpg.bitstream.fetch(1)
        if value > 0:
            if nextbit == 1:
                value +=  1 << aproximation
            return value
        if value < 0:
            if nextbit == 1:
                value += -1 << aproximation
            return value
        return value

    def decode(symbol, v):
        n = 2 ** (symbol - 1)
        if v >= n:
            return v
        return v - ((2 * n) - 1)

    i = jpg.ss

    if jpg.eobrun != 0:
        while i <= jpg.se:
            if block[i] != 0:
                block[i] = refinecofficient(jpg.al, block[i])
            i += 1
        jpg.eobrun -= 1
        return

    while i <= jpg.se:
        s = achuff.decode()

        a = (s >> 0) & 0xf  # size
        b = (s >> 4)        # run-length

        if a == 1:  # zero history
            newvalue = decode(1, jpg.bitstream.fetch(1)) << jpg.al
            while b > 0 or block[i] != 0:
                if block[i] != 0:
                    block[i] = refinecofficient(jpg.al, block[i])
                else:
                    b -= 1
                i += 1

            block[i] = newvalue
            i += 1
        else:
            if a == 0:
                if b < 15:
                    jpg.eobrun = jpg.bitstream.fetch(b) + (1 << b)
                    while i <= jpg.se:
                        if block[i] != 0:
                            block[i] = refinecofficient(jpg.al, block[i])
                        i += 1
                    jpg.eobrun -= 1
                    return
                else:
                    while b >= 0:
                        if block[i] != 0:
                            block[i] = refinecofficient(jpg.al, block[i])
                        else:
                            b -= 1
                        i += 1
            else:
                raise Exception("error")
    jpg.eobrun = 0


def refineAC(jpg):
    rinterval = jpg.rinterval

    # current pass component
    c = jpg.components[jpg.scancomponent]

    jpg.eobrun = 0
    for y in range(c.nrows):
        for x in range(c.ncols):
            if jpg.rinterval:
                if rinterval == 0:
                    checkrinterval(jpg.handler, jpg)
                    rinterval = jpg.rinterval
                rinterval -= 1

            n = (y * c.icols) + x
            decoderefineAC(jpg, c, c.scan[n])


def decodepass(handler, jpg):
    setdecoder(handler, jpg)

    if jpg.ss == 0:
        if jpg.se != 0:
            raise Exception("error, AC and DC data")

        if jpg.ah == 0:
            print("[pass]: first DC")
            readfirstDC(jpg)
        else:
            print("[pass]: refine DC")
            refineDC(jpg)
    else:
        if jpg.sccount != 1:
            raise Exception("more than 1 component in a progressive scan")

        if jpg.ah == 0:
            print("[pass]: read first AC")
            readfirstAC(jpg)
        else:
            print("[pass]: refine AC")
            refineAC(jpg)


def updateimage(jpg):
    def docomponent(c, y, x):
        y1 = y * c.ysampling
        x1 = x * c.xsampling
        j = 0
        for y2 in range(c.ysampling):
            offsety = y1 + y2
            for x2 in range(c.xsampling):
                n = (offsety * c.icols) + x1 + x2

                block = c.scan[n]

                t0 = [0] * 64
                for i in range(64):
                    t0[i] = block[zmatrix[i]] * c.qtable[zmatrix[i]]
                IDCTblock(t0, c.blocks[j])

                j += 1

    if jpg.numcomponents == 1:
        c = jpg.components[0]
        for y in range(c.nrows):
            for x in range(c.ncols):
                block = c.scan[y * c.icols + x]
                t0 = [0] * 64
                for i in range(64):
                    t0[i] = block[zmatrix[i]] * c.qtable[zmatrix[i]]
                IDCTblock(t0, block)

                setpixels1(jpg, y, x, block)
        return

    for y in range(jpg.nrows):
        for x in range(jpg.ncols):
            for i in range(jpg.numcomponents):
                docomponent(jpg.components[i], y, x)

            setpixels3(jpg, y, x)


def parseAPP2(handler, jpg):
    r = read16(handler)
    r -= 2

    # offset 0 is the profile size
    # offset 36 is the signature "acsp"
    m = handler.read(12)
    if m[:-1] != b"ICC_PROFILE":
        handler.read(r - 12)
        return

    s1 = ord(handler.read(1))
    s2 = ord(handler.read(1))
    if jpg.iccp == None:
        jpg.iccp = b""
    jpg.iccp += handler.read(r - 12 - 2)

    if s1 == s2:
        jpg.iccpsize = len(jpg.iccp)


def parseDRI(handler, jpg):
    r = read16(handler)
    if r != 4:
        raise Exception("DRI marker size != 4")

    i = read16(handler)
    jpg.rinterval = i


def parsesegments(handler):
    jpg = JPG(handler)

    while True:
        try:
            m = read16(handler)
        except:
            if jpg.decoded:
                print("end of input")
                return jpg
            raise
        s = ""
        if m in markers:
            s = markers[m]

        print(f"marker {m:00x} {s}")

        if m == APP0:
            parseAPP0(handler, jpg)
            continue

        if m in [SOF0, SOF1, SOF2]:
            if m == SOF2:
                print("progressive image")
                jpg.isprogressive = True

            parseSOF0(handler, jpg)
            continue

        if m in [SOF3, SOF5, SOF6, SOF7]:
            raise Exception("image type not supported")

        if m == DQT:
            parseDQT(handler, jpg)
            continue

        if m == DHT:
            parseDHT(handler, jpg)
            continue

        if m == SOS:
            parseSOS(handler, jpg)
            #if jpg.isprogressive:
            jpg.npass += 1
            #if jpg.npass == 5:
            #    updateimage(jpg)
            #    return jpg
            continue

        # end of image
        if m == EOI:
            if jpg.isprogressive:
                updateimage(jpg)
            else:
                if jpg.isinterleaved == False:
                    updateimage(jpg)
            return jpg

        if m == DRI:
            parseDRI(handler, jpg)
            continue

        # ICCP
        if m == APP2:
            parseAPP2(handler, jpg)
            continue

        # markers for frames using arithmetic coding
        if m in [SOF9, SOFA, SOFB, SOFD, SOFE, SOFF]:
            raise Exception("image not supported")

        # not length
        if (m >= 0xffd0 and m <= 0xffd9) or m == 0xff01:
            continue

        r = read16(handler) - 2
        if r < 0:
            raise Exception("invalid marker length")

        handler.read(r)
        continue


def parsefile(fpath):
    try:
        handler = open(fpath, "rb")
    except IOError:
        print("failed to open file")
        raise

    # check the header
    r = read16(handler)
    if r == 0xffd8:
        image = parsesegments(handler)
        return image

    raise Exception("invalid image file (not a JPG?)")


###############################################################################
# Test
###############################################################################


if __name__ == "__main__":
    from PIL import Image

    image = parsefile(sys.argv[1])

    mode = "RGB"
    if image.numcomponents == 1:
        mode = "L"
    a = Image.new(mode, (image.sizex, image.sizey))
    a.putdata(image.image)
    a.show()
