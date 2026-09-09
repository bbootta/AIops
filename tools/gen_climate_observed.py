"""실측 기후 자료를 국가 단위로 뽑아 risk_lib/data/climate_observed.json 을 만든다.

지구본 히트맵과 기후 개요의 오른쪽 패널이 쓰는 값이다. 전부 관측·집계 자료이고
합성값은 없다. 화면은 이 파일을 직접 읽지 않는다: risk_lib.climate_geo 가 RDM 원장
(rdm_ext_source · rdm_ext_climate_indicator · rdm_ext_climate_series)으로 세운다.

  국가 지표 (rdm_ext_climate_indicator)
    tas_obs               최근 10년 연평균 기온 (°C, 마지막 연도 2020 또는 2015)  Berkeley Earth TAVG
    tas_warming           1951~1980 대비 최근 10년 기온 상승 (°C)                Berkeley Earth TAVG
    pr_obs                연강수량 (mm/년, FAO AQUASTAT)              World Bank WDI AG.LND.PRCP.MM
    pop_el5m              해발 5m 이하 거주 인구 비중 (%)             World Bank WDI EN.POP.EL5M.ZS
    clim_affected_share   가뭄·홍수·극한기온 피해 인구 비중 (%)       World Bank WDI EN.CLC.MDAT.ZS
    water_stress          물 스트레스 (담수 취수 / 가용량, %)          World Bank WDI ER.H2O.FWST.ZS
    renew_share           최종 에너지 중 재생에너지 비중 (%)          World Bank WDI EG.FEC.RNEW.ZS
    disaster_affected     연평균 재해 피해 인구 2000~2023 (명)         EM-DAT (Gapminder Systema Globalis)

  시계열 (rdm_ext_climate_series)
    global_temp_anomaly   지구 평균 기온 편차 1850~ (°C, 1951~1980 기준)  Berkeley Earth Land+Ocean
    disaster_*            세계 재해 피해 인구 연도별 (홍수·폭풍·가뭄·극한기온)
    country_warming       국가별 10년 평균 기온 편차 (1900년대~2010년대)

원천 (이 환경에서 닿는 미러):
  Berkeley Earth  berkeley-earth-temperature.s3.us-west-1.amazonaws.com/Regional/TAVG/<국가>-TAVG-Trend.txt,
                  Global/Land_and_Ocean_summary.txt
  World Bank WDI  github.com/open-numbers/ddf--open_numbers--world_development_indicators (CC BY 4.0)
  EM-DAT          github.com/open-numbers/ddf--gapminder--systema_globalis (CC BY 4.0, 원자료 CRED EM-DAT)

사용: python3 tools/gen_climate_observed.py <입력 디렉터리>
  <dir>/be/<ISO3>.txt, <dir>/Land_and_Ocean_summary.txt,
  <dir>/wdi/{ag_lnd_prcp_mm,en_pop_el5m_zs,en_clc_mdat_zs,er_h2o_fwst_zs,eg_fec_rnew_zs,geo}.csv,
  <dir>/sg/{flood,storm,drought,extreme_temperature}_affected_annual_number.csv, <dir>/sg/geo.csv
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "risk_lib/data/climate_observed.json"
GEO = Path(__file__).resolve().parent.parent / "risk_lib/data/world_geo.json"

RECENT = (2011, 2020)                     # Berkeley Earth 국가 파일은 2020년까지 완결
DISASTER = (2000, 2023)
DECADES = list(range(1900, 2020, 10))

WDI = {
    "pr_obs": ("ag_lnd_prcp_mm", "mm/년", "WDI_PRCP", "AG.LND.PRCP.MM"),
    "pop_el5m": ("en_pop_el5m_zs", "%", "WDI_EL5M", "EN.POP.EL5M.ZS"),
    "clim_affected_share": ("en_clc_mdat_zs", "%", "WDI_MDAT", "EN.CLC.MDAT.ZS"),
    "water_stress": ("er_h2o_fwst_zs", "%", "WDI_FWST", "ER.H2O.FWST.ZS"),
    "renew_share": ("eg_fec_rnew_zs", "%", "WDI_RNEW", "EG.FEC.RNEW.ZS"),
}
HAZARDS = ("flood", "storm", "drought", "extreme_temperature")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _num(s: str) -> float | None:
    try:
        v = float(s)
    except ValueError:
        return None
    return None if math.isnan(v) else v


def _mean(xs: list[float]) -> float | None:
    return round(sum(xs) / len(xs), 3) if xs else None


def parse_be_country(path: Path) -> dict | None:
    """연 편차(6월 행의 Annual 열)와 1951~1980 절대 기온을 뽑는다."""
    base = None
    annual: dict[int, float] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "absolute temperature (C):" in line and "monthly" not in line:
            base = _num(line.split(":")[1].split("+/-")[0])
            continue
        if not line or line.startswith("%"):
            continue
        p = line.split()
        if len(p) < 6 or p[1] != "6":
            continue
        v = _num(p[4])
        if v is not None:
            annual[int(p[0])] = v
    if base is None or not annual:
        return None
    # 파일마다 마지막 연도가 다르다(2015 또는 2020). 마지막 연도로 끝나는 10년 창을 쓴다.
    last = min(max(annual), RECENT[1])
    recent = [annual[y] for y in range(last - 9, last + 1) if y in annual]
    if len(recent) < 8:
        return None
    warming = _mean(recent)
    decades = []
    for d in DECADES:
        xs = [annual[y] for y in range(d, d + 10) if y in annual]
        decades.append(_mean(xs) if len(xs) >= 5 else None)
    return {"base": base, "warming": warming, "tas": round(base + warming, 2), "year": last, "decades": decades}


def parse_be_global(path: Path) -> tuple[list[int], list[float]]:
    years, vals = [], []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line or line.startswith("%"):
            continue
        p = line.split()
        if len(p) >= 2 and p[0].isdigit():
            v = _num(p[1])
            if v is not None:
                years.append(int(p[0]))
                vals.append(v)
    return years, vals


def ddf_geo(path: Path) -> dict[str, str]:
    out = {}
    for r in csv.DictReader(path.open(encoding="utf-8")):
        if r.get("iso3166_1_alpha3"):
            out[r["country"]] = r["iso3166_1_alpha3"].upper()
    return out


def ddf_points(path: Path, col: str) -> dict[str, dict[int, float]]:
    out: dict[str, dict[int, float]] = {}
    for r in csv.DictReader(path.open(encoding="utf-8")):
        v = _num(r[col]) if r[col] != "" else None
        if v is not None:
            out.setdefault(r["geo"], {})[int(r["time"])] = v
    return out


def main(src: str) -> None:
    root = Path(src)
    iso_on_map = [c["iso3"] for c in json.loads(GEO.read_text(encoding="utf-8"))["countries"]]
    country: dict[str, dict[str, list]] = {}
    sources = []

    # Berkeley Earth 국가 파일. 하나의 원천으로 등록하고 지문은 파일 지문을 ISO3 순으로 이어 붙인 것이다.
    be_files = sorted((root / "be").glob("*.txt"))
    warming_path: dict[str, list] = {}
    for f in be_files:
        iso = f.stem
        if iso not in iso_on_map:
            continue
        d = parse_be_country(f)
        if d is None:
            continue
        country.setdefault(iso, {})["tas_obs"] = [d["tas"], d["year"]]
        country[iso]["tas_warming"] = [d["warming"], d["year"]]
        warming_path[iso] = d["decades"]
    joined = "".join(_sha(f) for f in be_files).encode()
    sources.append({"file_id": "BE_TAVG", "provider": "Berkeley Earth", "dataset": "Regional TAVG (국가별 지표 기온)",
                    "licence": "출처 표기 조건 (berkeleyearth.org/data 이용 조건 확인)",
                    "file": f"Regional/TAVG/*-TAVG-Trend.txt ({len(be_files)}개 파일)",
                    "sha256": hashlib.sha256(joined).hexdigest(), "row_count": len(warming_path),
                    "note": "1951~1980 절대 기온 + 연 편차. 파일의 마지막 10년 평균으로 기온·상승폭을 낸다 (2020 또는 2015 까지)"})
    gy, gv = parse_be_global(root / "Land_and_Ocean_summary.txt")
    sources.append({"file_id": "BE_GLOBAL", "provider": "Berkeley Earth", "dataset": "Land + Ocean 지구 평균 기온 편차",
                    "licence": "출처 표기 조건 (berkeleyearth.org/data 이용 조건 확인)",
                    "file": "Global/Land_and_Ocean_summary.txt", "sha256": _sha(root / "Land_and_Ocean_summary.txt"),
                    "row_count": len(gy), "note": "연 편차, 1951~1980 기준, 해빙 위는 기온 외삽 판"})

    # World Bank WDI (open-numbers 미러). 국가별 최신 연도 값.
    wgeo = ddf_geo(root / "wdi/geo.csv")
    for key, (col, unit, fid, code) in WDI.items():
        f = root / "wdi" / f"{col}.csv"
        pts = ddf_points(f, col)
        n = 0
        for g, ys in pts.items():
            iso = wgeo.get(g)
            if iso not in iso_on_map:
                continue
            y = max(ys)
            country.setdefault(iso, {})[key] = [round(ys[y], 3), y]
            n += 1
        sources.append({"file_id": fid, "provider": "World Bank", "dataset": f"WDI {code}",
                        "licence": "CC BY 4.0 (World Bank WDI, open-numbers DDF 미러)", "file": f.name,
                        "sha256": _sha(f), "row_count": n, "note": "국가별 최신 연도 값만 원장에 싣는다"})

    # EM-DAT (Gapminder Systema Globalis). 국가별 2000~2023 연평균 피해 인구와 세계 합계 시계열.
    sgeo = ddf_geo(root / "sg/geo.csv")
    dis_years = list(range(1970, DISASTER[1] + 1))
    dis_global: dict[str, list[float]] = {}
    per_country: dict[str, float] = {}
    sg_shas = []
    for hz in HAZARDS:
        f = root / "sg" / f"{hz}_affected_annual_number.csv"
        pts = ddf_points(f, f"{hz}_affected_annual_number")
        tot = [0.0] * len(dis_years)
        n = 0
        for g, ys in pts.items():
            iso = sgeo.get(g)
            for k, y in enumerate(dis_years):
                tot[k] += ys.get(y, 0.0)
            if iso in iso_on_map:
                span = [ys.get(y, 0.0) for y in range(DISASTER[0], DISASTER[1] + 1)]
                per_country[iso] = per_country.get(iso, 0.0) + sum(span) / len(span)
                n += 1
        dis_global[hz] = [round(x) for x in tot]
        sg_shas.append(_sha(f))
    for iso, v in per_country.items():
        country.setdefault(iso, {})["disaster_affected"] = [round(v), DISASTER[1]]
    sources.append({"file_id": "SG_EMDAT", "provider": "Gapminder (원자료 CRED EM-DAT)",
                    "dataset": "Systema Globalis 재해 피해 인구 (홍수·폭풍·가뭄·극한기온)",
                    "licence": "CC BY 4.0 (Gapminder) · EM-DAT 이용약관 별도",
                    "file": ", ".join(f"{hz}_affected_annual_number.csv" for hz in HAZARDS),
                    "sha256": hashlib.sha256("".join(sg_shas).encode()).hexdigest(), "row_count": len(per_country),
                    "note": "연도별 피해 인구 4종. 국가별 2000~2023 연평균 합계와 세계 합계 시계열"})

    doc = {
        "generator": "tools/gen_climate_observed.py",
        "sources": sources,
        "country": {iso: country[iso] for iso in sorted(country)},
        "series": {
            "global_temp_anomaly": {"file_id": "BE_GLOBAL", "unit": "°C", "years": gy, "values": gv},
            "disaster_global": {"file_id": "SG_EMDAT", "unit": "명", "years": dis_years, "values": dis_global},
            "country_warming": {"file_id": "BE_TAVG", "unit": "°C", "years": DECADES,
                                "values": {iso: warming_path[iso] for iso in sorted(warming_path)}},
        },
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(OUT, len(country), "countries", OUT.stat().st_size, "bytes")


if __name__ == "__main__":
    main(sys.argv[1])
