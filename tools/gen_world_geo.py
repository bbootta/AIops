"""Natural Earth 1:110m 국가 경계(공개 저작권, public domain)를 화면용 기하로
줄여 risk_lib/data/world_geo.json 을 만든다.

  - 외곽 링만, 좌표는 소수 둘째 자리(약 1 km)로 양자화한다.
  - 0.5도 격자의 국가 인덱스 래스터(0 = 바다)를 행별 런렝스로 넣는다. 화면이
    화소마다 다각형 판정을 하지 않고 이 격자를 찾아본다.
  - ISO 코드가 없는 지역(북키프로스·소말릴란드·코소보 등)은 ADM0_A3 로 둔다.

사용: python3 tools/gen_world_geo.py <ne_110m_admin_0_countries.geojson>
원본: https://github.com/nvkelso/natural-earth-vector (geojson/ne_110m_admin_0_countries.geojson)
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parent.parent / "risk_lib/data/world_geo.json"
DEG = 0.5


def _code(p: dict, *keys: str) -> str:
    for k in keys:
        v = p.get(k)
        if v and v != "-99":
            return str(v)
    return ""


def main(src: str) -> None:
    raw = Path(src).read_bytes()
    g = json.loads(raw)
    countries = []
    for f in g["features"]:
        p, geom = f["properties"], f["geometry"]
        polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
        rings = [[[round(x, 2), round(y, 2)] for x, y in poly[0]] for poly in polys]
        pts = np.array([q for r in rings for q in r])
        countries.append({
            "iso3": _code(p, "ISO_A3", "ISO_A3_EH", "ADM0_A3"),
            "iso2": _code(p, "ISO_A2", "ISO_A2_EH"),
            "name": p["ADMIN"], "continent": p["CONTINENT"],
            "c": [round(float(pts[:, 0].mean()), 2), round(float(pts[:, 1].mean()), 2)],
            "rings": rings,
        })
    countries.sort(key=lambda c: c["iso3"])

    W, H = int(360 / DEG), int(180 / DEG)
    lon = (np.arange(W) + 0.5) * DEG - 180
    lat = 90 - (np.arange(H) + 0.5) * DEG
    LON, LAT = np.meshgrid(lon, lat)
    idx = np.zeros((H, W), dtype=np.int16)
    for k, c in enumerate(countries, 1):
        for ring in c["rings"]:
            r = np.array(ring)
            sel = ((LON >= r[:, 0].min()) & (LON <= r[:, 0].max())
                   & (LAT >= r[:, 1].min()) & (LAT <= r[:, 1].max()))
            if not sel.any():
                continue
            px, py = LON[sel], LAT[sel]
            inside = np.zeros(px.shape, dtype=bool)
            xs, ys = r[:, 0], r[:, 1]
            for i in range(len(r) - 1):
                xi, yi, xj, yj = xs[i], ys[i], xs[i + 1], ys[i + 1]
                cond = (yi > py) != (yj > py)
                with np.errstate(divide="ignore", invalid="ignore"):
                    xint = (xj - xi) * (py - yi) / (yj - yi) + xi
                inside ^= cond & (px < xint)
            cur = idx[sel]
            cur[inside & (cur == 0)] = k
            idx[sel] = cur
    rle = []
    for row in idx:
        out, prev, n = [], int(row[0]), 0
        for v in row:
            v = int(v)
            if v == prev:
                n += 1
            else:
                out += [prev, n]
                prev, n = v, 1
        out += [prev, n]
        rle.append(out)

    doc = {
        "source": "Natural Earth 1:110m Admin 0 Countries (public domain)",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "generator": "tools/gen_world_geo.py",
        "countries": countries,
        "raster": {"w": W, "h": H, "deg": DEG, "rle": rle,
                   "note": "0.5도 격자의 국가 인덱스(1 기반, 0 = 바다), 행별 [값, 길이] 런렝스"},
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"{OUT}: 국가 {len(countries)}개 · 육지 셀 {int((idx > 0).sum())}/{W * H} · {OUT.stat().st_size:,} bytes")


if __name__ == "__main__":
    main(sys.argv[1])
