"""기후 지구본의 데이터는 RDM 원장을 거친다 (risk_lib/climate_geo.py).

외부 자료(Natural Earth 국경, Berkeley Earth 기온, World Bank WDI 강수·물리위험, EM-DAT 재해,
Our World in Data CO2·에너지)는 materialize_external 이 rdm_ext_* 원장과 계약·스냅샷 행으로
세우고, 화면은 payload_from_tables 로 그 원장만 읽는다. 지표는 전부 실측이고 합성값은 없다.
실행별 익스포저 층까지 kind 가 없는 층은 없어야 한다.
"""

from __future__ import annotations

import pandas as pd

from risk_lib import climate_geo as cg
from risk_lib.datamodel import catalog as cat
from risk_lib.datamodel.decompose import validate_all


EXT = ("rdm_ext_source", "rdm_ext_country", "rdm_ext_climate_indicator", "rdm_ext_climate_series")


def _ext():
    base = {"rdm_source_contract": pd.DataFrame(columns=[c.name for c in cat.SOURCE_CONTRACT.columns]),
            "rdm_snapshot": pd.DataFrame(columns=[c.name for c in next(
                s for s in cat.ALL_TABLES if s.name == "rdm_snapshot").columns])}
    return cg.materialize_external("2026-06-30", base)


def test_external_ledgers_are_registered_and_valid():
    t = _ext()
    names = {s.name for s in cat.ALL_TABLES}
    for n in EXT:
        assert n in names
    bad = [v for v in validate_all({k: t[k] for k in EXT})]
    assert bad == [], bad[:5]


def test_country_master_and_indicators():
    t = _ext()
    c = t["rdm_ext_country"]
    assert len(c) == 177 and c["iso3"].is_unique and {"KOR", "USA", "CHN", "DEU", "BRA"} <= set(c["iso3"])
    ind = t["rdm_ext_climate_indicator"]
    assert set(ind["indicator"]) == set(cat.EXT_INDICATORS)
    assert set(ind["kind"]) == {"실측"}                       # 합성 지표는 없다
    assert ind["year"].notna().all() and ind["year"].min() >= 2009
    n = ind.groupby("indicator").size()
    assert n["tas_obs"] >= 170 and n["pr_obs"] >= 160 and n["disaster_affected"] >= 160
    kor = ind[ind["iso3"] == "KOR"].set_index("indicator")["value"]
    assert 10 < kor["tas_obs"] < 16 and 1000 < kor["pr_obs"] < 1600 and kor["tas_warming"] > 0
    src = t["rdm_ext_source"]
    assert set(ind["file_id"]) <= set(src["file_id"])         # 지표는 등록된 파일에서만 온다
    ser = t["rdm_ext_climate_series"]
    assert set(ser["series"]) == set(cat.EXT_SERIES)
    g = ser[ser["series"] == "global_temp_anomaly"]
    assert (g["iso3"] == "WLD").all() and g["year"].min() == 1850 and g["year"].max() >= 2024
    assert ser[ser["series"] == "country_warming"]["iso3"].nunique() >= 170


def test_contract_and_snapshot_rows_are_appended_for_external_data():
    t = _ext()
    con = t["rdm_source_contract"]
    assert set(con[con["source_system"] == "external_data"]["table_name"]) == set(EXT)
    assert (con["status"] == "PASS").all()
    snap = t["rdm_snapshot"]
    assert len(snap[snap["source_system"] == "external_data"]) == 4
    assert snap["fingerprint"].str.len().eq(64).all()


def test_payload_comes_from_the_ledgers_and_declares_kinds():
    t = _ext()
    p = cg.payload_from_tables(t)
    assert p is not None and len(p["countries"]) == 177
    assert all(c["rings"] for c in p["countries"])
    r = p["raster"]
    assert (r["w"], r["h"], r["deg"]) == (720, 360, 0.5) and len(r["rle"]) == r["h"]
    assert all(sum(row[1::2]) == r["w"] for row in r["rle"])
    assert {l["kind"] for l in p["layers"]} == {"실측"}
    assert [l["key"] for l in p["layers"]] == list(cat.EXT_INDICATORS)
    for l in p["layers"]:
        assert l["source"] and l["unit"] and l["values"] and l["domain"][0] < l["domain"][1] and l["year"]
    tas = next(l for l in p["layers"] if l["key"] == "tas_obs")["values"]
    assert tas["BRA"] > tas["KOR"] > tas["RUS"]
    S = p["series"]
    assert set(S) == {"global_temp_anomaly", "disaster_global", "country_warming"}
    assert len(S["global_temp_anomaly"]["years"]) == len(S["global_temp_anomaly"]["values"]) >= 170
    assert set(S["disaster_global"]["values"]) == {"flood", "storm", "drought", "extreme_temperature"}
    assert len(S["country_warming"]["values"]["KOR"]) == len(S["country_warming"]["years"]) == 12
    assert {s["item"] for s in p["licences"]} >= {"국경", "기온", "재해"}
    assert cg.payload_from_tables({}) is None


def test_exposure_layer_maps_iso2_and_reports_unmatched():
    e = cg.exposure_layer([("KR", 0.5), ("JP", 0.3), ("HK", 0.2)])
    assert e["values"] == {"KOR": 50.0, "JPN": 30.0}
    assert e["unmatched"] == ["HK"]
    assert e["kind"] == "실행별"
