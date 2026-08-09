import olefile, zlib, struct, sys
def extract(path):
    f = olefile.OleFileIO(path)
    hdr = f.openstream('FileHeader').read()
    comp = bool(hdr[36] & 1)
    out = []
    for s in f.listdir():
        if s[0] != 'BodyText': continue
        data = f.openstream('/'.join(s)).read()
        if comp: data = zlib.decompress(data, -15)
        i = 0
        while i < len(data) - 4:
            h = struct.unpack('<I', data[i:i+4])[0]
            tag = h & 0x3FF; sz = (h >> 20) & 0xFFF
            i += 4
            if sz == 0xFFF:
                sz = struct.unpack('<I', data[i:i+4])[0]; i += 4
            if tag == 67:
                raw = data[i:i+sz]; buf=[]; j=0
                while j + 1 < len(raw):
                    c = struct.unpack('<H', raw[j:j+2])[0]
                    if c in (0,10,13): buf.append('\n'); j += 2
                    elif c in (1,2,3,11,12,14,15,16,17,18,21,22,23): j += 16
                    elif c in (4,5,6,7,8,9,19,20): j += 2
                    else: buf.append(chr(c)); j += 2
                out.append(''.join(buf))
            i += sz
    return '\n'.join(out)
if __name__ == '__main__':
    print(extract(sys.argv[1]))
