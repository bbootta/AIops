#!/usr/bin/env python3
"""index.html + css + js 를 파일 하나로 묶는다 (호스팅·공유용).

외부 요청이 막힌 환경에서도 그대로 돌아가야 하므로 stylesheet 와 script 를
전부 인라인으로 심는다. 출력물은 <!doctype>/<html>/<head>/<body> 없이
페이지 내용만 담는다 — 배포 시 그 골격이 씌워지기 때문.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).parent
OUT = ROOT / 'dist' / 'nail-simulator.html'


def read(rel):
    return (ROOT / rel).read_text(encoding='utf-8')


def main():
    html = read('index.html')

    # <head> 안에서 필요한 것만 남긴다: title, 인라인 CSS
    title = re.search(r'<title>(.*?)</title>', html, re.S).group(1)
    body = re.search(r'<body>(.*?)</body>', html, re.S).group(1)

    css = read('css/style.css')
    scripts = re.findall(r'<script src="([^"]+)"></script>', body)
    if not scripts:
        sys.exit('index.html 에서 script 태그를 찾지 못했습니다.')

    # body 안의 script 태그들을 인라인 코드로 교체
    body = re.sub(r'\s*<script src="[^"]+"></script>', '', body)
    inline = '\n'.join(
        '<script>\n%s\n</script>' % read(src).rstrip() for src in scripts
    )

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(
        '<title>%s</title>\n<style>\n%s\n</style>\n%s\n%s\n'
        % (title, css.rstrip(), body.strip(), inline),
        encoding='utf-8',
    )
    print('%s (%.0f KB, script %d개 인라인)'
          % (OUT.relative_to(ROOT), OUT.stat().st_size / 1024, len(scripts)))


if __name__ == '__main__':
    main()
