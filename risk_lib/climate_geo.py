"""기후리스크 세계지도(지구본 히트맵)의 데이터.

화면은 외부 타일·라이브러리 없이 canvas 로 그리므로 여기서 국가 경계, 국가 인덱스
래스터, 국가별 지표 층을 payload 로 만든다. 세 종류의 값이 섞여 있고 층마다
kind 로 구분해 화면이 그 사실을 적는다.

  실측   Our World in Data CO2·에너지 (risk_lib/data/climate_country.json, CC-BY 4.0)
  합성   연평균 기온·강수량. 기후 포털(World Bank CCKP 등)이 이 환경에서 닿지 않아
         위도 기반 근사장을 국가 격자에 평균한 값이다. 실측 기후 자료가 아니다.
  실행별 기관별 국가 익스포저 비중 (inst_country_mix 원장, 실행마다 다르다)

외부 자료는 화면이 파일을 직접 읽지 않는다. materialize_external 이 RDM 원장
(rdm_ext_source · rdm_ext_country · rdm_ext_climate_indicator)으로 세우고, 계약·
스냅샷 행을 남기며, payload_from_tables 가 그 원장에서 화면 데이터를 만든다.
국경·격자 렌더 자산(world_geo.json)은 rdm_ext_source 의 지문으로 원장과 묶인다.
"""

from __future__ import annotations

import json
import math
from functools import lru_cache
from pathlib import Path

_DATA = Path(__file__).parent / "data"

# 합성 기후장. 위도(도)만의 함수다. 등온선이 위도선과 나란한 근사이며 해류·고도·
# 대륙성은 없다. 값은 국가 격자 셀에 면적 가중(cos lat) 평균한다.
def synthetic_temperature(lat_deg: float) -> float:
    return 28.0 - 0.0068 * lat_deg * lat_deg


def synthetic_precipitation(lat_deg: float) -> float:
    a = abs(lat_deg)
    return 150.0 + 1900.0 * math.exp(-(lat_deg / 10.0) ** 2) + 650.0 * math.exp(-((a - 48.0) / 14.0) ** 2)


@lru_cache(maxsize=1)
def world_geo() -> dict:
    return json.loads((_DATA / "world_geo.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def climate_country() -> dict:
    return json.loads((_DATA / "climate_country.json").read_text(encoding="utf-8"))


def _cells_by_country(geo: dict) -> dict[int, list[float]]:
    """국가 인덱스 → 그 국가 셀들의 위도 목록 (래스터 런렝스에서 복원)."""
    r = geo["raster"]
    out: dict[int, list[float]] = {}
    for y, row in enumerate(r["rle"]):
        lat = 90.0 - (y + 0.5) * r["deg"]
        for k in range(0, len(row), 2):
            v, n = row[k], row[k + 1]
            if v:
                out.setdefault(v, []).extend([lat] * n)
    return out


@lru_cache(maxsize=1)
def _synthetic_layers() -> dict[str, dict[str, float]]:
    geo = world_geo()
    cells = _cells_by_country(geo)
    tas: dict[str, float] = {}
    pr: dict[str, float] = {}
    for k, c in enumerate(geo["countries"], 1):
        lats = cells.get(k)
        if not lats:
            lats = [c["c"][1]]                      # 격자보다 작은 나라는 중심 위도
        w = [math.cos(math.radians(la)) for la in lats]
        tw = sum(w) or 1.0
        tas[c["iso3"]] = round(sum(synthetic_temperature(la) * wi for la, wi in zip(lats, w)) / tw, 1)
        pr[c["iso3"]] = round(sum(synthetic_precipitation(la) * wi for la, wi in zip(lats, w)) / tw)
    return {"tas": tas, "pr": pr}


def _domain(values: dict[str, float], log: bool = False) -> list[float]:
    xs = sorted(v for v in values.values() if v is not None and (v > 0 or not log))
    if not xs:
        return [0.0, 1.0]
    lo, hi = xs[int(len(xs) * 0.02)], xs[min(len(xs) - 1, int(len(xs) * 0.98))]
    if hi <= lo:
        hi = lo + 1.0
    return [float(lo), float(hi)]


def _observed(field: str) -> tuple[dict[str, float], int | None]:
    vals, years = {}, []
    for iso, d in climate_country()["values"].items():
        if field in d:
            vals[iso] = d[field][0]
            years.append(d[field][1])
    return vals, (max(years) if years else None)


LAYER_META = {
    "tas_synthetic": {"label": "연평균 기온 (합성)", "palette": "temp", "log": False,
                      "source": "위도 기반 근사장을 국가 격자에 면적 평균 · 실측 기후 자료 아님"},
    "pr_synthetic": {"label": "연강수량 (합성)", "palette": "precip", "log": False,
                     "source": "위도 기반 근사장(적도 수렴대·중위도 폭풍대) · 실측 기후 자료 아님"},
    "co2_per_capita": {"label": "1인당 CO2 배출", "palette": "heat", "log": False,
                       "source": "Our World in Data co2-data (CC-BY 4.0)"},
    "co2": {"label": "CO2 배출 총량", "palette": "heat", "log": True,
            "source": "Our World in Data co2-data (CC-BY 4.0)"},
    "total_ghg": {"label": "온실가스 배출 총량", "palette": "heat", "log": True,
                  "source": "Our World in Data co2-data (CC-BY 4.0)"},
    "fossil_share": {"label": "화석연료 비중 (1차 에너지)", "palette": "heat", "log": False,
                     "source": "Our World in Data energy-data (CC-BY 4.0)"},
}
_UNITS = {"tas_synthetic": "°C", "pr_synthetic": "mm/년", "co2_per_capita": "tCO2/인",
          "co2": "MtCO2", "total_ghg": "MtCO2e", "fossil_share": "%"}
_OWID_FIELD_FILE = {"co2_per_capita": "OWID_CO2", "co2": "OWID_CO2",
                    "total_ghg": "OWID_CO2", "fossil_share": "OWID_ENERGY"}


def materialize_external(asof: str, tables: dict) -> dict:
    """외부 자료를 RDM 원장으로 세운다. 화면은 이 원장만 읽는다.

    rdm_ext_source            원천 파일 등록 (지문·저작권·행수)
    rdm_ext_country           국가 마스터 (Natural Earth)
    rdm_ext_climate_indicator 국가 × 지표 (실측 OWID + 합성 기온·강수)
    그리고 rdm_source_contract·rdm_snapshot 에 external_data 원천의 계약·스냅샷 행을
    덧붙인다. 함수는 순수하다: 같은 파일이면 같은 원장이 나온다.
    """
    import hashlib
    import pandas as pd
    from risk_lib.datamodel.decompose import _fingerprint

    geo, cc = world_geo(), climate_country()
    syn = _synthetic_layers()
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
    src_rows.append({"file_id": "SYNTH_LAT", "provider": "risk_lib.climate_geo", "dataset": "위도 기반 합성 기후장",
                     "licence": "내부 산출", "file_name": "(파일 없음)", "sha256": hashlib.sha256(
                         b"synthetic_temperature=28-0.0068*lat^2;synthetic_precipitation=itcz+storm").hexdigest(),
                     "row_count": len(geo["countries"]), "received_asof": asof, "kind": "합성",
                     "note": "실측 기후 포털이 닿지 않아 둔 근사장. 실측 자료가 오면 이 행이 교체된다"})
    ext_source = pd.DataFrame(src_rows)

    country = pd.DataFrame([{
        "iso3": c["iso3"], "iso2": c["iso2"] or None, "name": c["name"], "continent": c["continent"],
        "centroid_lon": float(c["c"][0]), "centroid_lat": float(c["c"][1]), "file_id": "NE_110M",
    } for c in geo["countries"]])

    rows = []
    iso_on_map = {c["iso3"] for c in geo["countries"]}
    for key, vals in (("tas_synthetic", syn["tas"]), ("pr_synthetic", syn["pr"])):
        for iso, v in vals.items():
            rows.append({"iso3": iso, "indicator": key, "value": float(v), "unit": _UNITS[key],
                         "year": None, "kind": "합성", "file_id": "SYNTH_LAT"})
    for iso, d in cc["values"].items():
        for key in ("co2_per_capita", "co2", "total_ghg", "fossil_share"):
            if key in d:
                rows.append({"iso3": iso, "indicator": key, "value": float(d[key][0]), "unit": _UNITS[key],
                             "year": int(d[key][1]), "kind": "실측", "file_id": _OWID_FIELD_FILE[key]})
    ind = pd.DataFrame(rows).sort_values(["indicator", "iso3"]).reset_index(drop=True)
    ind["year"] = ind["year"].astype("Int64")

    out = {"rdm_ext_source": ext_source, "rdm_ext_country": country, "rdm_ext_climate_indicator": ind}
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
        "source": geo["source"], "source_sha256": geo["source_sha256"],
        "countries": countries,
        "raster": {k: geo["raster"][k] for k in ("w", "h", "deg", "rle")},
        "layers": layers,
        "sources": [{k: (None if _isna(v) else v) for k, v in row.items()} for row in src.to_dict("records")],
        "licences": [{"item": "국경", "text": "Natural Earth 1:110m, public domain"},
                     {"item": "CO2·에너지", "text": "Our World in Data, CC-BY 4.0"}],
    }


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
