"""거시·금융지표 마스터·충격 원장 검사.

이 파일이 지키려는 것은 세 가지다.

1. 지표 정의와 충격 배수가 **소스가 아니라 원장**에 있다. 리터럴은 빌더
   함수 안에만 있고 엔진 함수 본문에는 없다.
2. 원장 값을 바꾸면 산출이 따라 바뀐다. 모듈 상수였다면 바뀌지 않는다.
3. 승인자·승인일이 빈 행이 조회 함수로 드러난다. 비어 있음이 보여야 통제다.
"""

from __future__ import annotations

import ast
import warnings
from pathlib import Path

import pandas as pd
import pytest

from risk_lib import macro_monitor as mm
from risk_lib.datamodel import catalog as cat
from risk_lib.datamodel.spec import check_refs, validate

_SRC = Path(mm.__file__).read_text(encoding="utf-8")
_TREE = ast.parse(_SRC)
_ASOF = "2026-06-30"


@pytest.fixture(scope="module")
def master():
    return mm.build_macro_indicator_master()


@pytest.fixture(scope="module")
def shock(master):
    return mm.build_macro_scenario_shock(master)


@pytest.fixture(scope="module")
def obs(master):
    return mm.observations(_ASOF, seed=42, master=master)


# ----- 스펙 품질 --------------------------------------------------------------

def test_both_ledgers_pass_their_spec(master, shock):
    assert [str(v) for v in validate(master, mm.INDICATOR_MASTER)] == []
    assert [str(v) for v in validate(shock, mm.SCENARIO_SHOCK_LEDGER)] == []


def test_specs_declare_grain_primary_key_and_float_units():
    for spec in mm.MACRO_MASTER_TABLES:
        assert spec.grain.strip() and "1행" in spec.grain, spec.name
        assert spec.primary_key, spec.name
        assert spec.product.startswith("PRD-"), spec.name
        for col in spec.columns:
            if col.dtype == "float":
                assert col.unit, f"{spec.name}.{col.name}: float unit 미기재"


def test_shock_foreign_key_resolves_to_the_master(master, shock):
    tables = {mm.INDICATOR_MASTER.name: master,
              mm.SCENARIO_SHOCK_LEDGER.name: shock}
    specs = {s.name: s for s in mm.MACRO_MASTER_TABLES}
    assert [str(v) for v in check_refs(tables, specs)] == []


def test_vocabulary_matches_the_observation_table_in_catalog():
    """마스터와 관측치의 허용값이 갈라지면 조인이 조용히 끊긴다."""
    assert mm.MACRO_SOURCES == cat.MACRO_SOURCES
    assert mm.MACRO_CATEGORIES == cat.MACRO_CATEGORIES
    assert mm.MACRO_FREQ == cat.MACRO_FREQ
    assert mm.SCENARIOS == cat.SCENARIOS


# ----- 하드코딩 제거 ----------------------------------------------------------

def _nodes_outside_builders() -> list[ast.AST]:
    """빌더(`build_*`) 함수 밖의 모든 노드.

    데이터는 빌더 안에만 있어야 한다. 엔진 함수와 모듈 최상단에 지표 식별자나
    충격 배수가 남아 있으면 원장을 바꿔도 그 자리는 안 바뀐다.
    """
    out: list[ast.AST] = []
    for node in ast.walk(_TREE):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("build_"):
            continue
        out.append(node)
    inside = set()
    for node in ast.walk(_TREE):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("build_"):
            inside.update(id(n) for n in ast.walk(node))
    return [n for n in out if id(n) not in inside]


def test_indicator_ids_appear_only_inside_the_builder(master):
    ids = set(master["indicator_id"])
    found = [n.value for n in _nodes_outside_builders()
             if isinstance(n, ast.Constant) and n.value in ids]
    assert found == [], f"빌더 밖에 남은 지표 식별자: {sorted(set(found))}"


def test_shock_multipliers_appear_only_inside_the_builder(shock):
    mults = {abs(float(m)) for m in shock["multiplier"] if float(m) != 0.0}
    found = [n.value for n in _nodes_outside_builders()
             if isinstance(n, ast.Constant)
             and isinstance(n.value, float) and abs(n.value) in mults]
    assert found == [], f"빌더 밖에 남은 충격 배수: {sorted(set(found))}"


def test_series_shape_values_appear_only_inside_the_builder(master):
    """계열의 모양을 정하는 값(기준점·변동성·회귀속도·잡음배율) 전부.

    정수 리터럴은 보지 않는다. 슬라이스 폭·표시 자릿수처럼 데이터가 아닌
    정수가 우연히 같은 값이 되는 일을 결함으로 셀 이유가 없다.
    """
    anchors = set()
    for col in ("level", "vol", "mean_reversion", "noise_scale"):
        anchors |= {float(v) for v in master[col]}
    found = [n.value for n in _nodes_outside_builders()
             if isinstance(n, ast.Constant)
             and isinstance(n.value, float) and n.value in anchors]
    assert found == [], f"빌더 밖에 남은 계열 모수: {sorted(set(found))}"


def test_no_module_level_indicator_or_shock_constant():
    """구 상수 `INDICATORS`·`SCENARIO_SHOCK`이 대입문으로 남으면 안 된다."""
    assigned = set()
    for node in _TREE.body:
        if isinstance(node, ast.Assign):
            assigned.update(t.id for t in node.targets
                            if isinstance(t, ast.Name))
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target,
                                                           ast.Name):
            assigned.add(node.target.id)
    assert "INDICATORS" not in assigned
    assert "SCENARIO_SHOCK" not in assigned


def test_deprecated_names_still_answer_but_warn():
    """옛 이름으로 읽는 소비처가 남아 있는 동안 경고로 그 사실을 드러낸다."""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        specs = mm.INDICATORS
        shocks = mm.SCENARIO_SHOCK
    assert len(specs) == 12 and set(shocks) == set(mm.SCENARIOS)
    assert [w.category for w in caught] == [DeprecationWarning] * 2


def test_unknown_attribute_still_raises():
    with pytest.raises(AttributeError):
        mm.존재하지않는속성


# ----- 원장이 산출을 움직인다 -------------------------------------------------

def test_changing_vol_changes_the_scenario_shock(master, obs):
    """마스터의 vol을 바꾸면 충격폭이 따라 바뀐다. 상수였다면 안 바뀐다."""
    base = mm.scenario_links(obs, master=master)
    row = base[(base["scenario"] == "adverse")
               & (base["indicator_id"] == "GDP_YOY")].iloc[0]

    edited = master.copy()
    edited.loc[edited["indicator_id"] == "GDP_YOY", "vol"] *= 2.0
    after = mm.scenario_links(obs, master=edited)
    row2 = after[(after["scenario"] == "adverse")
                 & (after["indicator_id"] == "GDP_YOY")].iloc[0]

    assert row2["shock"] == pytest.approx(row["shock"] * 2.0, rel=1e-6)


def test_changing_multiplier_changes_the_scenario_value(master, obs, shock):
    base = mm.scenario_links(obs, master=master, shock_ledger=shock)
    edited = shock.copy()
    sel = ((edited["scenario"] == "adverse")
           & (edited["indicator_id"] == "UNEMP"))
    edited.loc[sel, "multiplier"] = edited.loc[sel, "multiplier"] * 3.0
    after = mm.scenario_links(obs, master=master, shock_ledger=edited)

    b = base[(base["scenario"] == "adverse")
             & (base["indicator_id"] == "UNEMP")].iloc[0]
    a = after[(after["scenario"] == "adverse")
              & (after["indicator_id"] == "UNEMP")].iloc[0]
    assert a["shock"] == pytest.approx(b["shock"] * 3.0, rel=1e-6)


def test_changing_level_changes_the_observed_series(master):
    edited = master.copy()
    edited.loc[edited["indicator_id"] == "KOSPI", "level"] += 500.0
    base = mm.observations(_ASOF, seed=42, master=master)
    after = mm.observations(_ASOF, seed=42, master=edited)
    b = base[base["indicator_id"] == "KOSPI"]["value"].to_numpy()
    a = after[after["indicator_id"] == "KOSPI"]["value"].to_numpy()
    assert (a > b).all()
    # 다른 지표는 전용 난수 스트림이라 흔들리지 않는다.
    other = "USDKRW"
    assert (base[base["indicator_id"] == other]["value"].to_numpy()
            == after[after["indicator_id"] == other]["value"].to_numpy()).all()


def test_removing_an_indicator_removes_its_rows(master):
    edited = master[master["indicator_id"] != "CDS_5Y"]
    out = mm.observations(_ASOF, seed=42, master=edited)
    assert "CDS_5Y" not in set(out["indicator_id"])
    assert set(out["indicator_id"]) == set(edited["indicator_id"])


def test_alert_drives_come_from_the_master(obs, master):
    edited = master.copy()
    edited["drives"] = "축을 바꿔 적었다"
    hits = mm.alerts(obs, z_threshold=1.5, master=edited)
    assert hits, "이탈 지표가 없으면 이 검사가 아무것도 확인하지 못한다"
    assert {h["drives"] for h in hits} == {"축을 바꿔 적었다"}


# ----- 빈 칸은 건너뛰고 경고한다 ---------------------------------------------

def test_missing_level_skips_the_indicator_with_a_warning(master):
    edited = master.copy()
    edited.loc[edited["indicator_id"] == "UNEMP", "level"] = None
    with pytest.warns(mm.MacroLedgerWarning, match="UNEMP"):
        out = mm.observations(_ASOF, seed=42, master=edited)
    assert "UNEMP" not in set(out["indicator_id"])


def test_missing_multiplier_leaves_the_value_unadjusted(master, obs, shock):
    edited = shock.copy()
    sel = ((edited["scenario"] == "severely_adverse")
           & (edited["indicator_id"] == "KOSPI"))
    edited.loc[sel, "multiplier"] = None
    with pytest.warns(mm.MacroLedgerWarning, match="KOSPI"):
        out = mm.scenario_links(obs, master=master, shock_ledger=edited)
    row = out[(out["scenario"] == "severely_adverse")
              & (out["indicator_id"] == "KOSPI")].iloc[0]
    assert row["shock"] == 0.0 and row["scenario_value"] == row["latest"]


def test_unsupported_freq_skips_the_indicator_with_a_warning(master):
    """freq가 원장에서 오므로 표기가 없는 주기가 들어올 수 있다.

    마스터의 freq 어휘는 '연'을 허용하는데 관측치 period 표기(YYYY-MM ·
    YYYY-Qn)에는 연 라벨 자리가 없다. 조용히 월로 처리하면 라벨이 사실과
    달라지므로 건너뛰어야 한다.
    """
    edited = master.copy()
    edited.loc[edited["indicator_id"] == "GDP_YOY", "freq"] = "연"
    with pytest.warns(mm.MacroLedgerWarning, match="GDP_YOY"):
        out = mm.observations(_ASOF, seed=42, master=edited)
    assert "GDP_YOY" not in set(out["indicator_id"])
    assert "연" not in set(mm._SUPPORTED_FREQ)
    assert set(mm._SUPPORTED_FREQ) <= set(mm.MACRO_FREQ)


def test_shock_map_drops_null_multipliers(shock):
    edited = shock.copy()
    sel = ((edited["scenario"] == "adverse")
           & (edited["indicator_id"] == "GDP_YOY"))
    edited.loc[sel, "multiplier"] = None
    table = mm.scenario_shock_map(edited)
    assert "GDP_YOY" not in table["adverse"]


# ----- 승인·근거가 드러난다 ---------------------------------------------------

def test_every_master_row_is_unapproved_and_says_so(master):
    gaps = mm.unapproved_indicators(master)
    assert len(gaps) == len(master), "승인 이력이 없는데 승인된 것처럼 보이면 안 된다"
    assert master["approved_by"].isna().all()
    assert master["approved_on"].isna().all()
    assert set(master["evidence_status"]) == {"미확인"}
    assert master["citation"].notna().all()


def test_scenario_shock_is_declared_an_internal_assumption(shock):
    assert set(shock["evidence_status"]) == {"내부가정"}
    assert len(mm.unapproved_scenario_shocks(shock)) == len(shock)
    assert shock["citation"].notna().all()


def test_zero_shock_rows_are_present_and_labelled(shock):
    """충격이 없는 조합도 원장에 남는다. 행이 없는 것과 0인 것은 다르다."""
    base = shock[shock["scenario"] == "baseline"]
    assert len(base) == 12
    assert (base["multiplier"] == 0.0).all()
    assert base["direction_rule"].str.contains("충격 없음").all()


def test_shock_ledger_covers_every_indicator_in_every_scenario(master, shock):
    assert len(shock) == len(master) * len(mm.SCENARIOS)
    assert set(shock["indicator_id"]) == set(master["indicator_id"])


# ----- 결정론 -----------------------------------------------------------------

def test_same_asof_and_seed_give_the_same_series(master):
    a = mm.observations(_ASOF, seed=42, master=master)
    b = mm.observations(_ASOF, seed=42, master=master)
    pd.testing.assert_frame_equal(a, b)
    c = mm.observations(_ASOF, seed=7, master=master)
    assert not a["value"].equals(c["value"])


def test_builders_are_deterministic():
    pd.testing.assert_frame_equal(mm.build_macro_indicator_master(),
                                  mm.build_macro_indicator_master())
    pd.testing.assert_frame_equal(mm.build_macro_scenario_shock(),
                                  mm.build_macro_scenario_shock())


def test_ledger_bundle_is_keyed_by_table_name():
    bundle = mm.build_macro_master_ledgers()
    assert set(bundle) == {s.name for s in mm.MACRO_MASTER_TABLES}
