"""한도 정의 원장 검사.

한도값은 `pipeline._stage_limits_concentration`의 리스트 리터럴이었다. 이제
`lim_limit_definition` 원장이 정본이고 엔진 정의는 원장에서 만들어진다.

여기서 확인하는 것은 세 가지다.

1. 한도 임계가 빌더 안에만 있다. 소비 함수에는 숫자가 없다.
2. 원장 임계를 바꾸면 엔진 정의와 한도 판정이 따라 바뀐다.
3. 승인기구·승인일이 빈 내부한도가 조회 함수로 드러난다.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd
import pytest

from risk_lib import limits_master as lm
from risk_lib.datamodel.spec import validate
from risk_lib.limits.limit_engine import LimitDefinition, LimitEngine

_SRC = Path(lm.__file__).read_text(encoding="utf-8")
_TREE = ast.parse(_SRC)


@pytest.fixture(scope="module")
def ledger():
    return lm.build_limit_definitions()


# ----- 스펙 품질 --------------------------------------------------------------

def test_ledger_passes_its_spec(ledger):
    assert [str(v) for v in validate(ledger, lm.LIMIT_DEFINITION)] == []


def test_spec_declares_grain_primary_key_and_float_units():
    spec = lm.LIMIT_DEFINITION
    assert "1행" in spec.grain
    assert spec.primary_key == ("limit_id",)
    assert spec.product.startswith("PRD-")
    for col in spec.columns:
        if col.dtype == "float":
            assert col.unit, f"{col.name}: float unit 미기재"


def test_limit_ids_are_unique(ledger):
    assert ledger["limit_id"].is_unique


# ----- 하드코딩 제거 ----------------------------------------------------------

def _nodes_outside_builder() -> list[ast.AST]:
    inside = set()
    for node in ast.walk(_TREE):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("build_"):
            inside.update(id(n) for n in ast.walk(node))
    return [n for n in ast.walk(_TREE) if id(n) not in inside]


def test_threshold_values_appear_only_inside_the_builder(ledger):
    values = {float(v) for v in ledger["threshold_value"]}
    found = [n.value for n in _nodes_outside_builder()
             if isinstance(n, ast.Constant)
             and isinstance(n.value, float) and n.value in values]
    assert found == [], f"빌더 밖에 남은 한도 임계: {sorted(set(found))}"


def test_limit_ids_appear_only_inside_the_builder(ledger):
    ids = set(ledger["limit_id"])
    found = [n.value for n in _nodes_outside_builder()
             if isinstance(n, ast.Constant) and n.value in ids]
    assert found == [], f"빌더 밖에 남은 한도 식별자: {sorted(set(found))}"


def test_consumer_has_no_numeric_literal():
    """원장을 엔진 정의로 옮기는 함수에 실수가 있으면 원장이 정본이 아니다.

    정수는 보지 않는다. `stacklevel=2` 같은 호출 인자는 데이터가 아니다.
    """
    fn = next(n for n in _TREE.body
              if isinstance(n, ast.FunctionDef)
              and n.name == "limit_definitions")
    nums = [n.value for n in ast.walk(fn)
            if isinstance(n, ast.Constant) and isinstance(n.value, float)]
    assert nums == [], f"소비 함수에 남은 실수: {nums}"


# ----- 원장이 산출을 움직인다 -------------------------------------------------

def test_ledger_reproduces_the_five_engine_definitions(ledger):
    """원장에서 만든 정의가 파이프라인이 쓰던 5종과 같아야 이관이 성립한다."""
    got = lm.limit_definitions(ledger)
    assert got == [
        LimitDefinition("동일차주_Tier1_25pct", "obligor_id", None,
                        0.25, basis="pct_tier1"),
        LimitDefinition("섹터_총노출_2조", "sector", None,
                        2.0e12, basis="absolute"),
        LimitDefinition("국가_총노출_5조", "country", None,
                        5.0e12, basis="absolute"),
        LimitDefinition("자산군_총노출_7조", "asset_class", None,
                        7.0e12, basis="absolute"),
        LimitDefinition("등급_총노출_6조", "rating", None,
                        6.0e12, basis="absolute"),
    ]


def test_changing_a_threshold_changes_the_engine_definition(ledger):
    edited = ledger.copy()
    sel = edited["limit_id"] == "섹터_총노출_2조"
    edited.loc[sel, "threshold_value"] = edited.loc[sel, "threshold_value"] / 2
    got = {d.name: d.threshold for d in lm.limit_definitions(edited)}
    base = {d.name: d.threshold for d in lm.limit_definitions(ledger)}
    assert got["섹터_총노출_2조"] == base["섹터_총노출_2조"] / 2
    assert got["국가_총노출_5조"] == base["국가_총노출_5조"]


def test_changing_a_threshold_changes_the_breach_report(ledger):
    """원장을 조이면 위반이 늘어난다. 상수였다면 판정이 그대로다."""
    book = pd.DataFrame({
        "sector": ["제조", "건설", "도소매"],
        "ead": [1.5e12, 1.2e12, 0.8e12],
    })
    only_sector = ledger[ledger["limit_id"] == "섹터_총노출_2조"]
    engine = LimitEngine(lm.limit_definitions(only_sector))
    assert len(engine.report(book)) == 0

    tightened = only_sector.copy()
    tightened.loc[:, "threshold_value"] = 1.0e12
    tight_engine = LimitEngine(lm.limit_definitions(tightened))
    breaches = tight_engine.report(book)
    assert set(breaches["bucket"]) == {"제조", "건설"}


def test_changing_the_unit_changes_the_basis(ledger):
    edited = ledger.copy()
    edited.loc[edited["limit_id"] == "섹터_총노출_2조", "threshold_unit"] = \
        "ratio_tier1"
    got = {d.name: d.basis for d in lm.limit_definitions(edited)}
    assert got["섹터_총노출_2조"] == "pct_tier1"


def test_scope_key_comes_from_the_ledger(ledger):
    edited = ledger.copy()
    edited.loc[edited["limit_id"] == "국가_총노출_5조", "scope_key"] = "region"
    got = {d.name: d.dimension for d in lm.limit_definitions(edited)}
    assert got["국가_총노출_5조"] == "region"


# ----- 빈 칸은 건너뛰고 경고한다 ---------------------------------------------

def test_missing_threshold_is_skipped_with_a_warning(ledger):
    edited = ledger.copy()
    edited.loc[edited["limit_id"] == "등급_총노출_6조", "threshold_value"] = None
    with pytest.warns(lm.LimitLedgerWarning, match="등급_총노출_6조"):
        got = lm.limit_definitions(edited)
    assert "등급_총노출_6조" not in {d.name for d in got}
    assert len(got) == len(ledger) - 1


def test_unreadable_unit_is_skipped_with_a_warning(ledger):
    edited = ledger.copy()
    edited.loc[edited["limit_id"] == "섹터_총노출_2조", "threshold_unit"] = "USD"
    with pytest.warns(lm.LimitLedgerWarning, match="섹터_총노출_2조"):
        got = lm.limit_definitions(edited)
    assert "섹터_총노출_2조" not in {d.name for d in got}


# ----- 승인·근거가 드러난다 ---------------------------------------------------

def test_regulatory_limit_carries_a_citation(ledger):
    row = ledger[ledger["basis"] == "규정"].iloc[0]
    assert row["limit_id"] == "동일차주_Tier1_25pct"
    assert "은행법 제35조" in row["citation"]
    assert row["evidence_status"] == "원문미확인·현행계승"
    # 규정 분모는 자기자본이고 엔진은 기본자본을 쓴다. 그 차이가 원장에 있어야
    # 감사에서 산식 불일치가 발견되기 전에 보인다.
    assert "자기자본" in row["note"] and "기본자본" in row["note"]


def test_internal_limits_name_their_approval_body(ledger):
    internal = ledger[ledger["basis"] == "내부한도"]
    assert len(internal) == 4
    assert set(internal["approval_body"]) == {"리스크관리위원회"}
    assert set(internal["evidence_status"]) == {"내부가정"}


def test_internal_limits_without_an_approval_date_are_surfaced(ledger):
    gaps = lm.unapproved_limits(ledger)
    assert set(gaps["limit_id"]) == set(
        ledger[ledger["basis"] == "내부한도"]["limit_id"])
    assert gaps["approved_on"].isna().all()


def test_approving_a_limit_removes_it_from_the_gap_list(ledger):
    edited = ledger.copy()
    edited.loc[edited["limit_id"] == "섹터_총노출_2조", "approved_on"] = "2026-03-31"
    gaps = lm.unapproved_limits(edited)
    assert "섹터_총노출_2조" not in set(gaps["limit_id"])
    assert len(gaps) == 3


def test_regulatory_limit_is_not_counted_as_an_approval_gap(ledger):
    """법령 한도의 효력 근거는 법령이다. 내부 의결일을 요구하지 않는다."""
    assert "동일차주_Tier1_25pct" not in set(
        lm.unapproved_limits(ledger)["limit_id"])


# ----- 파이프라인 산출과의 연결 -----------------------------------------------

def test_ledger_covers_every_limit_the_pipeline_reports(result, ledger):
    """파이프라인이 판정한 한도가 원장에 전건 있어야 화면이 근거를 붙인다."""
    known = set(ledger["limit_id"])
    reported = set(result.limits["limit"]) | set(result.limits_full["limit"])
    assert reported <= known, f"원장에 없는 한도: {sorted(reported - known)}"


def test_ledger_scope_keys_exist_in_the_portfolio(ledger, portfolio):
    missing = set(ledger["scope_key"]) - set(portfolio.columns)
    assert missing == set(), f"포트폴리오에 없는 축: {sorted(missing)}"


# ----- 결정론 -----------------------------------------------------------------

def test_builder_is_deterministic():
    pd.testing.assert_frame_equal(lm.build_limit_definitions(),
                                  lm.build_limit_definitions())
