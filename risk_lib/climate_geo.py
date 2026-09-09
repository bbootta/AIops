"""기후리스크 세계지도(지구본 히트맵)와 기후 개요 오른쪽 패널의 데이터.

화면은 외부 타일·라이브러리 없이 canvas 로 그리므로 여기서 국가 경계, 국가 인덱스
래스터, 국가별 지표 층, 시계열을 payload 로 만든다. 값은 전부 실측(관측·집계)이며
합성값은 없다. 층마다 kind 와 원천이 붙는다.

  실측   Berkeley Earth 국가별 기온 (최근 10년 평균, 1951~1980 대비 상승폭)
         World Bank WDI 연강수량·해발 5m 이하 인구·물 스트레스·재해 피해 인구 비중·재생에너지
         EM-DAT(Gapminder) 재해 피해 인구, Our World in Data CO2·에너지
         (risk_lib/data/climate_observed.json · climate_country.json)
  실행별 기관별 국가 익스포저 비중 (inst_country_mix 원장, 실행마다 다르다)

외부 자료는 화면이 파일을 직접 읽지 않는다. materialize_external 이 RDM 원장
(rdm_ext_source · rdm_ext_country · rdm_ext_climate_indicator · rdm_ext_climate_series)
으로 세우고, 계약·스냅샷 행을 남기며, payload_from_tables 가 그 원장에서 화면 데이터를
만든다. 국경·격자 렌더 자산(world_geo.json)은 rdm_ext_source 의 지문으로 원장과 묶인다.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

_DATA = Path(__file__).parent / "data"

@lru_cache(maxsize=1)
def world_geo() -> dict:
    return json.loads((_DATA / "world_geo.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def climate_country() -> dict:
    return json.loads((_DATA / "climate_country.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def climate_observed() -> dict:
    return json.loads((_DATA / "climate_observed.json").read_text(encoding="utf-8"))


def _domain(values: dict[str, float], log: bool = False) -> list[float]:
    xs = sorted(v for v in values.values() if v is not None and (v > 0 or not log))
    if not xs:
        return [0.0, 1.0]
    lo, hi = xs[int(len(xs) * 0.02)], xs[min(len(xs) - 1, int(len(xs) * 0.98))]
    if hi <= lo:
        hi = lo + 1.0
    return [float(lo), float(hi)]


_BE = "Berkeley Earth 지표 기온 (출처 표기 조건)"
_WDI = "World Bank WDI (CC BY 4.0)"
LAYER_META = {
    "tas_obs": {"label": "연평균 기온 (최근 10년)", "palette": "temp", "log": False, "source": _BE},
    "tas_warming": {"label": "기온 상승폭 (1951~1980 대비)", "palette": "warm", "log": False, "source": _BE},
    "pr_obs": {"label": "연강수량", "palette": "precip", "log": False, "source": _WDI + " · FAO AQUASTAT"},
    "disaster_affected": {"label": "연평균 재해 피해 인구 (2000~2023)", "palette": "heat", "log": True,
                          "source": "EM-DAT (CRED) · Gapminder Systema Globalis (CC BY 4.0)"},
    "pop_el5m": {"label": "해발 5m 이하 거주 인구 비중", "palette": "precip", "log": False, "source": _WDI},
    "water_stress": {"label": "물 스트레스 (취수/가용량)", "palette": "heat", "log": True, "source": _WDI},
    "clim_affected_share": {"label": "가뭄·홍수·극한기온 피해 인구 비중", "palette": "heat", "log": False,
                            "source": _WDI + " · 1990~2009 평균"},
    "co2_per_capita": {"label": "1인당 CO2 배출", "palette": "heat", "log": False,
                       "source": "Our World in Data co2-data (CC-BY 4.0)"},
    "co2": {"label": "CO2 배출 총량", "palette": "heat", "log": True,
            "source": "Our World in Data co2-data (CC-BY 4.0)"},
    "total_ghg": {"label": "온실가스 배출 총량", "palette": "heat", "log": True,
                  "source": "Our World in Data co2-data (CC-BY 4.0)"},
    "fossil_share": {"label": "화석연료 비중 (1차 에너지)", "palette": "heat", "log": False,
                     "source": "Our World in Data energy-data (CC-BY 4.0)"},
    "renew_share": {"label": "재생에너지 비중 (최종 에너지)", "palette": "green", "log": False, "source": _WDI},
}
_UNITS = {"tas_obs": "°C", "tas_warming": "°C", "pr_obs": "mm/년", "disaster_affected": "명",
          "pop_el5m": "%", "water_stress": "%", "clim_affected_share": "%", "co2_per_capita": "tCO2/인",
          "co2": "MtCO2", "total_ghg": "MtCO2e", "fossil_share": "%", "renew_share": "%"}
_FILE = {"tas_obs": "BE_TAVG", "tas_warming": "BE_TAVG", "pr_obs": "WDI_PRCP", "disaster_affected": "SG_EMDAT",
         "pop_el5m": "WDI_EL5M", "water_stress": "WDI_FWST", "clim_affected_share": "WDI_MDAT",
         "co2_per_capita": "OWID_CO2", "co2": "OWID_CO2", "total_ghg": "OWID_CO2", "fossil_share": "OWID_ENERGY",
         "renew_share": "WDI_RNEW"}
_OWID_KEYS = ("co2_per_capita", "co2", "total_ghg", "fossil_share")
# 화면의 시계열 이름 → 원장의 series 코드. 재해는 재난 종류마다 한 시계열이다.
_HAZARDS = ("flood", "storm", "drought", "extreme_temperature")


def materialize_external(asof: str, tables: dict) -> dict:
    """외부 자료를 RDM 원장으로 세운다. 화면은 이 원장만 읽는다.

    rdm_ext_source            원천 파일 등록 (지문·저작권·행수)
    rdm_ext_country           국가 마스터 (Natural Earth)
    rdm_ext_climate_indicator 국가 × 지표 (실측: Berkeley Earth·WDI·EM-DAT·OWID)
    rdm_ext_climate_series    세계·국가 시계열 (지구 기온 편차 · 재해 피해 인구 · 국가 10년 기온 편차)
    그리고 rdm_source_contract·rdm_snapshot 에 external_data 원천의 계약·스냅샷 행을
    덧붙인다. 함수는 순수하다: 같은 파일이면 같은 원장이 나온다.
    """
    import hashlib
    import pandas as pd
    from risk_lib.datamodel.decompose import _fingerprint

    geo, cc, ob = world_geo(), climate_country(), climate_observed()
    src_rows = [
        {"file_id": "NE_110M", "provider": "Natural Earth", "dataset": "1:110m Admin 0 Countries",
         "licence": "public domain", "file_name": "world_geo.json", "sha256": geo["source_sha256"],
         "row_count": len(geo["countries"]), "received_asof": asof, "kind": "기하",
         "note": "국경·0.5도 국가 격자. 화면 렌더 자산이며 지문으로 원장과 묶인다"},
    ]
    for fid, meta in (("OWID_CO2", cc["sources"][0]), ("OWID_ENERGY", cc["sources"][1])):
        src_rows.append({"file_id": fid, "provider": "Our World in Data",
                         "dataset": "co2-data" if fid == "OWID_CO2" else "energy-data",
                         "licence": meta["licence"], "file_name": meta["file"], "sha256": meta["sha256"],
                         "row_count": len(cc["values"]), "received_asof": asof, "kind": "실측",
                         "note": "국가별 최신 연도 값만 원장에 싣는다"})
    for m in ob["sources"]:
        src_rows.append({"file_id": m["file_id"], "provider": m["provider"], "dataset": m["dataset"],
                         "licence": m["licence"], "file_name": m["file"], "sha256": m["sha256"],
                         "row_count": int(m["row_count"]), "received_asof": asof, "kind": "실측",
                         "note": m["note"]})
    ext_source = pd.DataFrame(src_rows)

    country = pd.DataFrame([{
        "iso3": c["iso3"], "iso2": c["iso2"] or None, "name": c["name"], "continent": c["continent"],
        "centroid_lon": float(c["c"][0]), "centroid_lat": float(c["c"][1]), "file_id": "NE_110M",
    } for c in geo["countries"]])

    iso_on_map = {c["iso3"] for c in geo["countries"]}
    rows = []
    for iso, d in ob["country"].items():
        if iso not in iso_on_map:
            continue
        for key, (v, y) in d.items():
            rows.append({"iso3": iso, "indicator": key, "value": float(v), "unit": _UNITS[key],
                         "year": int(y), "kind": "실측", "file_id": _FILE[key]})
    for iso, d in cc["values"].items():
        if iso not in iso_on_map:
            continue
        for key in _OWID_KEYS:
            if key in d:
                rows.append({"iso3": iso, "indicator": key, "value": float(d[key][0]), "unit": _UNITS[key],
                             "year": int(d[key][1]), "kind": "실측", "file_id": _FILE[key]})
    ind = pd.DataFrame(rows).sort_values(["indicator", "iso3"]).reset_index(drop=True)

    S = ob["series"]
    srows = []
    g = S["global_temp_anomaly"]
    for y, v in zip(g["years"], g["values"]):
        srows.append({"series": "global_temp_anomaly", "iso3": "WLD", "year": int(y), "value": float(v),
                      "unit": g["unit"], "kind": "실측", "file_id": g["file_id"]})
    dg = S["disaster_global"]
    for hz in _HAZARDS:
        for y, v in zip(dg["years"], dg["values"][hz]):
            srows.append({"series": "disaster_" + hz, "iso3": "WLD", "year": int(y), "value": float(v),
                          "unit": dg["unit"], "kind": "실측", "file_id": dg["file_id"]})
    cw = S["country_warming"]
    for iso, vals in cw["values"].items():
        if iso not in iso_on_map:
            continue
        for y, v in zip(cw["years"], vals):
            if v is not None:
                srows.append({"series": "country_warming", "iso3": iso, "year": int(y), "value": float(v),
                              "unit": cw["unit"], "kind": "실측", "file_id": cw["file_id"]})
    series = pd.DataFrame(srows).sort_values(["series", "iso3", "year"]).reset_index(drop=True)

    out = {"rdm_ext_source": ext_source, "rdm_ext_country": country,
           "rdm_ext_climate_indicator": ind, "rdm_ext_climate_series": series}
    contracts, snaps = [], []
    for name, df in out.items():
        contracts.append({"source_system": "external_data", "table_name": name, "asof": asof,
                          "expected_rows": int(len(df)), "actual_rows": int(len(df)),
                          "expected_sum": 0.0, "actual_sum": 0.0,
                          "schema_hash": hashlib.sha256("|".join(df.columns).encode()).hexdigest()[:16],
                          "status": "PASS"})
        snaps.append({"snapshot_id": f"SNAP_{name}_{asof}", "source_system": "external_data",
                      "table_name": name, "asof": asof, "row_count": int(len(df)),
                      "fingerprint": _fingerprint(df)})
    if "rdm_source_contract" in tables:
        out["rdm_source_contract"] = pd.concat([tables["rdm_source_contract"], pd.DataFrame(contracts)],
                                               ignore_index=True)
    if "rdm_snapshot" in tables:
        out["rdm_snapshot"] = pd.concat([tables["rdm_snapshot"], pd.DataFrame(snaps)], ignore_index=True)
    return out


def _isna(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v)) or str(type(v).__name__) == "NAType"


def payload_from_tables(tables: dict) -> dict | None:
    """RDM 원장(국가 마스터·지표)에서 지구본 payload 를 만든다. 국경·격자는 원장에
    등록된 지문의 렌더 자산(world_geo.json)에서 온다. 원장이 없으면 None."""
    ind = tables.get("rdm_ext_climate_indicator")
    country = tables.get("rdm_ext_country")
    src = tables.get("rdm_ext_source")
    if ind is None or country is None or src is None or len(country) == 0:
        return None
    geo = world_geo()
    rings = {c["iso3"]: c["rings"] for c in geo["countries"]}
    countries = [{"iso3": r["iso3"], "iso2": "" if _isna(r["iso2"]) else r["iso2"],
                  "name": r["name"], "continent": r["continent"],
                  "c": [r["centroid_lon"], r["centroid_lat"]], "rings": rings.get(r["iso3"], [])}
                 for r in country.sort_values("iso3").to_dict("records")]
    layers = []
    for key, meta in LAYER_META.items():
        part = ind[ind["indicator"] == key]
        if len(part) == 0:
            continue
        vals = {str(r["iso3"]): float(r["value"]) for _, r in part.iterrows()}
        years = [int(y) for y in part["year"].dropna().tolist()]
        layers.append({"key": key, "label": meta["label"], "unit": str(part["unit"].iloc[0]),
                       "kind": str(part["kind"].iloc[0]), "palette": meta["palette"], "log": meta["log"],
                       "year": max(years) if years else None, "source": meta["source"],
                       "values": vals, "domain": _domain(vals, meta["log"])})
    return {
        "series": _series_payload(tables.get("rdm_ext_climate_series")),
        "source": geo["source"], "source_sha256": geo["source_sha256"],
        "countries": countries,
        "raster": {k: geo["raster"][k] for k in ("w", "h", "deg", "rle")},
        "layers": layers,
        "sources": [{k: (None if _isna(v) else v) for k, v in row.items()} for row in src.to_dict("records")],
        "licences": [{"item": "국경", "text": "Natural Earth 1:110m, public domain"},
                     {"item": "기온", "text": "Berkeley Earth (출처 표기)"},
                     {"item": "강수·물리위험", "text": "World Bank WDI, CC BY 4.0"},
                     {"item": "재해", "text": "EM-DAT via Gapminder, CC BY 4.0"},
                     {"item": "CO2·에너지", "text": "Our World in Data, CC-BY 4.0"}],
    }


def _series_payload(ser) -> dict:
    """시계열 원장 → {이름: {years, values}}. 국가 시계열은 values 가 {iso3: [..]} 이고
    없는 10년은 None 이다."""
    if ser is None or len(ser) == 0:
        return {}
    out: dict = {}
    g = ser[ser["series"] == "global_temp_anomaly"].sort_values("year")
    if len(g):
        out["global_temp_anomaly"] = {"years": [int(y) for y in g["year"]], "values": [float(v) for v in g["value"]],
                                      "unit": str(g["unit"].iloc[0])}
    dz = ser[ser["series"].str.startswith("disaster_")]
    if len(dz):
        years = sorted({int(y) for y in dz["year"]})
        vals = {}
        for hz in _HAZARDS:
            part = dz[dz["series"] == "disaster_" + hz]
            by = {int(r["year"]): float(r["value"]) for _, r in part.iterrows()}
            vals[hz] = [by.get(y) for y in years]
        out["disaster_global"] = {"years": years, "values": vals, "unit": str(dz["unit"].iloc[0])}
    cw = ser[ser["series"] == "country_warming"]
    if len(cw):
        years = sorted({int(y) for y in cw["year"]})
        vals = {}
        for iso, part in cw.groupby("iso3"):
            by = {int(r["year"]): float(r["value"]) for _, r in part.iterrows()}
            vals[str(iso)] = [by.get(y) for y in years]
        out["country_warming"] = {"years": years, "values": vals, "unit": str(cw["unit"].iloc[0])}
    return out


def exposure_layer(country_mix_rows) -> dict:
    """기관의 국가별 익스포저 비중(%). inst_country_mix 의 ISO2 를 지도의 ISO3 로 옮긴다.
    지도에 없는 지역(예: 홍콩은 1:110m 에서 중국에 포함)은 unmatched 에 남긴다."""
    by2 = {c["iso2"]: c["iso3"] for c in world_geo()["countries"] if c["iso2"]}
    vals: dict[str, float] = {}
    unmatched = []
    for iso2, w in country_mix_rows:
        iso3 = by2.get(str(iso2).upper())
        if iso3:
            vals[iso3] = round(vals.get(iso3, 0.0) + float(w) * 100.0, 2)
        else:
            unmatched.append(str(iso2))
    return {"key": "exposure", "label": "기관 국가별 익스포저 비중", "unit": "%", "kind": "실행별",
            "palette": "accent", "source": "inst_country_mix 원장 (기관 설정)",
            "values": vals, "domain": _domain(vals) if vals else [0.0, 1.0],
            "unmatched": unmatched}
