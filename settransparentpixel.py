# -*- coding: utf-8 -*-
import sys
import struct
import binascii


SIGNATURE = (0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a)


def parsefile(color, source, target):
    sfile = open(source, "rb")
    tfile = open(target, "wb")
    
    try:
        signature = sfile.read(8)
        for i in range(8):
            if signature[i] != SIGNATURE[i]:
                raise
    except:
        raise Exception("bad file signature")
    
    tfile.write(signature)
    
    colortype  = 1
    headerdone = False
    insertrns  = False
    while (1):
        length = struct.unpack(">i", sfile.read(4))[0]
        chnkid = sfile.read(4)
        
        if chnkid == b"IHDR":
            if headerdone or length ^ 13:
                raise Exception("bad or duplicate header")
            
            s = sfile.read(13 + 4)
            colortype = s[9]  #
            
            if colortype == 2 or colortype == 0:
                print(f"colortype: {['grayscale', '', 'rgb'][colortype]}")
                insertrns = True
            headerdone = True
            
            tfile.write(struct.pack(">i", length))
            tfile.write(chnkid)
            tfile.write(s)
            
            if insertrns:
                s = b"tRNS"
                if colortype == 0:
                    tfile.write(struct.pack(">i", 2))
                    s += struct.pack(">h", color[0])
                    
                if colortype == 2:
                    tfile.write(struct.pack(">i", 6))
                    s += struct.pack(">hhh", color[0], color[1], color[2])
                s += struct.pack(">I", binascii.crc32(s))
                tfile.write(s)
        else:
            if insertrns and chnkid == "tRNS":
                sfile.read(length + 4)
                continue
            
            s = sfile.read(length + 4)
            tfile.write(struct.pack(">i", length))
            tfile.write(chnkid)
            tfile.write(s)
        
        if chnkid == b"IEND":
            break
    tfile.close()
    sfile.close()


if __name__ == "__main__":
    if len(sys.argv) != 6:
        print("usage: thisscript.py r g b imagefile.png target.png")
        exit(0)
    color = [0, 0, 0]
    try:
        color[0] = int(sys.argv[1])
        color[1] = int(sys.argv[2])
        color[2] = int(sys.argv[3])
        
        if color[0] > 0xffff or color[0] < 0: raise
        if color[1] > 0xffff or color[1] < 0: raise
        if color[2] > 0xffff or color[2] < 0: raise
    except:
        print("Error: invalid color value")
    
    parsefile(color, sys.argv[4], sys.argv[5])
    print("done")