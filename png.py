# -*- coding: utf-8 -*-
import sys
import struct
import zlib


SIGNATURE = (0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a)


class PNG(object):
    """
    """
    
    def __init__(self):
        # image size
        self.sizey = 0
        self.sizex = 0
        
        self.bitdepth  = 0
        self.colortype = 0
        self.cmethod   = 0  # always zero, compression method
        self.filter    = 0  # always zero
        self.interlace = 0 
        
        self.palette      = []
        self.transparency = []
        self.havealpha   = False
        self.havepalette = False
        
        # raw image data
        self.rawdata = None
        # decoded image
        self.image   = None


def parseIHDR(png, handler, length):
    if length != 13:
        raise Exception("error bad header size")
    r = struct.unpack(">ii", handler.read(8))
    png.sizey = r[1]
    png.sizex = r[0]
    if png.sizey == 0 or png.sizex == 0:
        raise Exception("invalid image size")
    
    def check(depths):
        if not png.bitdepth in depths:
            raise Exception("invalid color mode or bitdepth")
    
    r = struct.unpack(">bbbbb", handler.read(5))
    png.bitdepth  = r[0]
    png.colortype = r[1]
    png.cmethod   = r[2]
    png.filter    = r[3]
    png.interlace = r[4]    
    if png.cmethod != 0 or png.filter != 0 or png.interlace > 1:
        raise Exception("invalid header values")
    
    # crc
    handler.read(4)
    if png.colortype == 0:  # grayscale
        check((1, 2, 4, 8, 16))
        return
    # RGB, grayscale + alpha, RGBA
    if png.colortype == 2 or png.colortype == 4 or png.colortype == 6:
        check((8, 16))
        return
    # indexed RGB
    if png.colortype == 3:
        check((1, 2, 4, 8))
        return


def parsetRNS(png, handler, length):
    handler.seek(length + 4, 1)
    return


def parsePLTE(png, handler, length):
    if png.colortype == 0 or png.colortype == 4:
        raise Exception("PLTE chunk error 1")
    
    total = length // 3
    if total == 0 or (length - total * 3) != 0:
        raise Exception("PLTE chunk error 2")
    r = []
    for i in range(total):
        a = handler.read(3)
        r.append((a[0], a[1], a[2]))
    png.palette = r
    
    # crc
    handler.read(4)


def parseIDAT(png, handler, length):
    if png.rawdata == None:
        png.rawdata = b""
    png.rawdata += handler.read(length)
    
    # crc
    handler.read(4)


def parsesBIT(png, handler, length):
    handler.seek(length + 4, 1)
    return


def expandrow(row, width, bbp):
    r = []
    i = 0
    j = 8 - bbp
    n = 0
    mask = (1 << bbp) - 1
    while n < width:
        if 0 > j:
            i += 1
            j  = 8 - bbp
        
        r.append((row[i] >> j) & mask)
        j -= bbp
        n += 1
    return r


def unfilter(fmode, currrow, offset, prev, rowsize, pelsize):
    r = []
    
    if fmode == 0:
        for i in range(rowsize * pelsize):
            r.append(currrow[offset + i])
        return r
    
    if fmode == 1:
        for i in range(pelsize):
            r.append(currrow[offset + i])
        
        for i in range(pelsize, rowsize * pelsize):
            r.append((r[-pelsize] + currrow[offset + i]) & 0xff)
        return r
    
    if fmode == 2:
        for i in range(0, rowsize * pelsize):
            r.append((prev[i] + currrow[offset + i]) & 0xff)
        return r
    
    if fmode == 3:
        for i in range(pelsize):
            r.append((currrow[offset + i] + (prev[i] >> 1)) & 0xff)
            
        for i in range(pelsize, rowsize * pelsize):
            a = (r[-pelsize] + prev[i]) >> 1
            r.append((currrow[offset + i] +  a) & 0xff)
        return r
    
    if fmode == 4:
        def paeth(a, b, c):
            p = a + b - c
            pa = abs(p - a)
            pb = abs(p - b)
            pc = abs(p - c)
            if pa <= pb and pa <= pc:
                return a
            else:
                if pb <= pc:
                    return b
            return c
        
        for i in range(pelsize):
            r.append((paeth(0, prev[i], 0) + currrow[offset + i]) & 0xff)
        for i in range(pelsize, rowsize * pelsize):
            a = paeth(r[-pelsize], prev[i], prev[i - pelsize])
            r.append((a + currrow[offset + i]) & 0xff)
        return r


ADAM7_IX = [0, 4, 0, 2, 0, 1, 0]  #x start values
ADAM7_IY = [0, 0, 4, 0, 2, 0, 1]  #y start values
ADAM7_DX = [8, 8, 4, 4, 2, 2, 1]  #x delta values
ADAM7_DY = [8, 8, 8, 4, 4, 2, 2]  #y delta values


def decodepass(png, cpass, data, offset):
    sizex = png.sizex
    sizey = png.sizey
    
    bpp = png.bitdepth
    rowsize = ((sizex * bpp) + 7) >> 3
    pelsize = 1
    if png.colortype == 2:
        pelsize = ((bpp + 7) >> 3) * 3
    
    # grayscale + alpha
    if png.colortype == 4:
        png.havealpha = True
        pelsize = ((bpp + 7) >> 3) * 2
    
    # rgb + alpha
    if png.colortype == 6:
        png.havealpha = True
        pelsize = ((bpp + 7) >> 3) * 4
    
    if cpass == 0:
        png.passinfo = []
        for i in range(7):
            passw = (sizex + ADAM7_DX[i] - ADAM7_IX[i] - 1) // ADAM7_DX[i]
            passh = (sizey + ADAM7_DY[i] - ADAM7_IY[i] - 1) // ADAM7_DY[i]
            if passw == 0:
                passh = 0;
            if passh == 0:
                passw = 0;
            png.passinfo.append((passw, passh))
    
    passw = png.passinfo[cpass][0]
    passh = png.passinfo[cpass][1]
    if passw == 0 or passh == 0:
        # empty pass
        return x
    
    prev = []
    for i in range(passw * pelsize):
        prev.append(0x00);
    
    if bpp < 8:
        rowsize = ((passw * bpp) + 7) >> 3
    else:
        rowsize = passw
    
    j = 0
    while j < passh:
        fmode = data[offset]
        row = unfilter(fmode, data, offset + 1, prev, rowsize, pelsize)
        if bpp < 8:
            row = expandrow(row, passw, bpp)
        prev = row
        offset += (rowsize * pelsize) + 1
        
        # expand to image
        m = 0
        i = 0
        if png.colortype == 3:
            ypos = (j * ADAM7_DY[cpass]) + ADAM7_IY[cpass]
            
            while i < passw:
                png.rows[ypos][ADAM7_IX[cpass] + m] = row[i]
                
                m += ADAM7_DX[cpass]
                i += 1
            j += 1
        
        else:
            ypos = (j * ADAM7_DY[cpass]) + ADAM7_IY[cpass]
            while i < passw:
                for n in range(pelsize):
                    xpos = ((ADAM7_IX[cpass] + m) * pelsize)
                    png.rows[ypos][xpos + n] = row[(i * pelsize) + n]
                m += ADAM7_DX[cpass]
                i += 1
            j += 1
    
    return offset


def decodeimage(png):
    sizex = png.sizex
    sizey = png.sizey
    
    bpp = png.bitdepth
    rowsize = ((sizex * bpp) + 7) >> 3
    pelsize = 1
    if png.colortype == 2:
        pelsize = ((bpp + 7) >> 3) * 3
    
    # grayscale + alpha
    if png.colortype == 4:
        png.havealpha = True
        pelsize = ((bpp + 7) >> 3) * 2
    
    # rgb + alpha
    if png.colortype == 6:
        png.havealpha = True
        pelsize = ((bpp + 7) >> 3) * 4
    
    data = zlib.decompress(png.rawdata)
    rows = []
    if png.interlace:
        print("progressive image")
        for i in range(sizey):
            r = []
            if png.colortype == 3:  # indexed
                for j in range(sizex):
                    r.append(0x00)
            else:
                for j in range(pelsize * rowsize):
                    r.append(0xff)
            rows.append(r)
        
        png.rows = rows
        offset = 0
        for cpass in range(7):
            offset = decodepass(png, cpass, data, offset)
        
        print("Decoding done")
        return
    
    # decoding
    prev = []
    for i in range(rowsize * pelsize):
        prev.append(0)
    
    offset = 0
    for i in range(0, sizey):
        fmode = data[offset]
        r = unfilter(fmode, data, offset + 1, prev, rowsize, pelsize)
        if bpp < 8:
            r = expandrow(r, sizex, bpp)
        rows.append(r)
        prev = r
        
        offset += (rowsize * pelsize) + 1
    
    png.rows = rows
    print("Decoding done")


def converttopixels(png):
    png.iformat = "L"
    png.image   = []
    if png.colortype == 0:
        for row in png.rows:
            for c in row:
                png.image.append(c)
        return
    
    if png.colortype == 2:
        png.iformat = "RGB"
        for row in png.rows:
            n = 0
            while len(row) > n:
                c = (row[n+0], row[n+1], row[n+2])
                png.image.append(c)
                n += 3
        return
        
    if png.colortype == 3:
        png.iformat = "RGB"
        for row in png.rows:
            for index in row:
                color = png.palette[index]
                c = (color[0], color[1], color[2])
                png.image.append(c)
        return
    
    if png.colortype == 4:
        png.iformat = "LA"
        for row in png.rows:
            n = 0
            while len(row) > n:
                c = (row[n+0], row[n+1])
                png.image.append(c)
                n += 2
    
    if png.colortype == 6:
        png.iformat = "RGBA"
        for row in png.rows:
            n = 0
            while len(row) > n:
                c = (row[n+0], row[n+1], row[n+2], row[n+3])
                png.image.append(c)
                n += 4
        return


chunkfns = {}
chunkfns[b"IHDR"] = parseIHDR
chunkfns[b"IDAT"] = parseIDAT
chunkfns[b"sBIT"] = parsesBIT
chunkfns[b"PLTE"] = parsePLTE
chunkfns[b"tRNS"] = parsetRNS


def parsefile(handler):
    try:
        signature = handler.read(8)
        for i in range(8):
            if signature[i] != SIGNATURE[i]:
                raise 
    except:
        raise Exception("bad file signature")
    
    png = PNG()
    while True:
        length = struct.unpack(">i", handler.read(4))[0]
        chnkid = handler.read(4)
        
        print(f"chunk {chnkid} {length}")
        if chnkid in chunkfns:
            chunkfns[chnkid](png, handler, length)
        else:
            handler.seek(length, 1)
            struct.unpack(">i", handler.read(4))[0]
        if chnkid == b"IEND":
            break
    
    decodeimage(png)
    converttopixels(png)
    return png
    

###############################################################################
# Test
###############################################################################

if __name__ == "__main__":
    from PIL import Image
    
    if len(sys.argv) != 2:
        print("usage: thisscript.py imagefile.png")
        exit(0)
    
    png = parsefile(open(sys.argv[1], "rb"))
    print(f"image format: {png.iformat}")
    a = Image.new(png.iformat, (png.sizex, png.sizey))
    a.putdata(png.image)
    #a.save("a.png")
    a.show()