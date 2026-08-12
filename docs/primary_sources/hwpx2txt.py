"""HWPX(OWPML) 텍스트 추출. HWPX는 zip 안에 Contents/section*.xml 이 들어 있고
본문 텍스트가 <hp:t> 요소에 담긴다. 표는 셀 단위 문단으로 흩어지므로 줄바꿈으로
잇는다."""
import zipfile, re, sys, xml.etree.ElementTree as ET

def extract(path):
    z = zipfile.ZipFile(path)
    names = sorted(n for n in z.namelist()
                   if re.match(r'Contents/section\d+\.xml$', n))
    out = []
    for n in names:
        root = ET.fromstring(z.read(n))
        for el in root.iter():
            tag = el.tag.split('}')[-1]
            if tag == 't' and el.text:
                out.append(el.text)
            elif tag == 'p':
                out.append('\n')
    return re.sub(r'\n{3,}', '\n\n', ''.join(out))

if __name__ == '__main__':
    print(extract(sys.argv[1]))
