"""정규 데이터모델 — 스펙·검증·DDL·분해 (RDM-002/003/004 · DAT-001).

원칙: 모든 검증 규칙은 **위반 케이스로 발동을 확인**한다. 발동하지 않는
규칙은 통제가 아니라 장식이다.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd
import pytest

from risk_lib import datamodel as dm
from risk_lib.datamodel import catalog as cat
from risk_lib.datamodel.spec import (
    ColumnSpec, TableSpec, ForeignKey, SchemaError, validate, check_refs, ddl,
)

ASOF = "2026-06-11"


def _spec(**kw) -> TableSpec:
    base = dict(
        name="t_demo", korean="데모", grain="행 1건",
        columns=(ColumnSpec("id", "string", nullable=False),
                 ColumnSpec("amt", "float", unit="KRW", min_value=0.0),
                 ColumnSpec("kind", "string", allowed=("a", "b"))),
        primary_key=("id",))
    base.update(kw)
    return TableSpec(**base)


# ----- 스펙 정의 자체의 방어 -------------------------------------------------

def test_spec_rejects_missing_grain():
    """입도를 한 문장으로 못 쓰면 테이블 설계가 안 된 것이다."""
    with pytest.raises(SchemaError, match="grain"):
        _spec(grain="   ")


def test_spec_rejects_nullable_primary_key():
    with pytest.raises(SchemaError, match="PK 컬럼은 nullable"):
        TableSpec(name="t", korean="k", grain="g",
                  columns=(ColumnSpec("id", "string", nullable=True),),
                  primary_key=("id",))


def test_spec_rejects_duplicate_columns_and_bad_keys():
    with pytest.raises(SchemaError, match="컬럼명 중복"):
        _spec(columns=(ColumnSpec("id", "string", nullable=False),
                       ColumnSpec("id", "float")), primary_key=())
    with pytest.raises(SchemaError, match="PK에 없는 컬럼"):
        _spec(primary_key=("nope",))
    with pytest.raises(SchemaError, match="FK에 없는 컬럼"):
        _spec(foreign_keys=(ForeignKey(("nope",), "other", ("x",)),))


def test_column_spec_rejects_impossible_constraints():
    with pytest.raises(SchemaError, match="미지원 타입"):
        ColumnSpec("x", "복소수")
    with pytest.raises(SchemaError, match="min > max"):
        ColumnSpec("x", "float", min_value=10, max_value=1)
    with pytest.raises(SchemaError, match="빈 집합"):
        ColumnSpec("x", "string", allowed=())


# ----- 검증 규칙이 실제로 발동하는가 (mutation) ------------------------------

def _good() -> pd.DataFrame:
    return pd.DataFrame({"id": ["A", "B"], "amt": [1.0, 2.0],
                         "kind": ["a", "b"]})


def test_clean_frame_has_no_violations():
    assert validate(_good(), _spec()) == []


def test_not_null_rule_fires():
    df = _good(); df.loc[0, "id"] = None
    v = validate(df, _spec())
    assert any(x.rule == "not_null" and x.column == "id" for x in v)


def test_allowed_rule_fires():
    df = _good(); df.loc[0, "kind"] = "z"
    v = validate(df, _spec())
    assert any(x.rule == "allowed" and "z" in x.detail for x in v)


def test_range_rule_fires_on_both_bounds():
    s = _spec(columns=(ColumnSpec("id", "string", nullable=False),
                       ColumnSpec("amt", "float", min_value=0.0, max_value=10.0),
                       ColumnSpec("kind", "string", allowed=("a", "b"))))
    low = _good(); low.loc[0, "amt"] = -1.0
    high = _good(); high.loc[0, "amt"] = 11.0
    assert any(x.rule == "range_min" for x in validate(low, s))
    assert any(x.rule == "range_max" for x in validate(high, s))


def test_record_lists_every_check_that_ran():
    """수행한 점검을 적어야 '위반 없음'과 '점검 안 함'이 구별된다."""
    s = _spec(columns=(ColumnSpec("id", "string", nullable=False),
                       ColumnSpec("amt", "float", min_value=0.0, max_value=10.0),
                       ColumnSpec("kind", "string", allowed=("a", "b"))))
    rec: list[tuple[str, str, str]] = []
    assert validate(_good(), s, record=rec) == []
    got = {(c, r) for _, c, r in rec}
    assert ("id", "not_null") in got
    assert ("amt", "dtype") in got
    assert ("amt", "range_min") in got and ("amt", "range_max") in got
    assert ("kind", "allowed") in got


def test_every_violation_was_also_recorded_as_a_check():
    """적힌 점검 목록이 실제 점검과 어긋나면 통과 이력이 거짓이 된다.

    위반이 났는데 그 점검이 목록에 없으면, 그 규칙은 '수행하지 않은 것'으로
    남아 통과 이력에서 조용히 빠진다. 규칙마다 위반을 만들어 확인한다.
    """
    s = _spec(columns=(ColumnSpec("id", "string", nullable=False),
                       ColumnSpec("amt", "float", min_value=0.0, max_value=10.0),
                       ColumnSpec("kind", "string", allowed=("a", "b"))))
    bad = pd.DataFrame({"id": [None, "B"], "amt": [-1.0, 11.0],
                        "kind": ["z", "b"]})
    rec: list[tuple[str, str, str]] = []
    vs = validate(bad, s, record=rec)
    assert vs, "위반이 하나도 없으면 이 검사가 무의미하다"
    got = {(t, c, r) for t, c, r in rec}
    for v in vs:
        assert (v.table, v.column, v.rule) in got, (
            f"{v.rule} 위반이 났는데 점검 목록에 없다")


def test_both_bounds_violated_at_once_stay_distinguishable():
    """두 위반을 한 규칙 이름으로 묶으면 rdm_dq_result 의 기본키가 겹친다.

    기본키가 (기준일, 원장, 컬럼, 규칙)이라, 최솟값과 최댓값 위반을 둘 다
    'range' 로 적으면 결과 원장이 스스로 기본키 중복이 된다.
    """
    s = _spec(columns=(ColumnSpec("id", "string", nullable=False),
                       ColumnSpec("amt", "float", min_value=0.0, max_value=10.0),
                       ColumnSpec("kind", "string", allowed=("a", "b"))))
    df = _good()
    df.loc[0, "amt"] = -1.0
    df.loc[1, "amt"] = 11.0
    rules = [x.rule for x in validate(df, s) if x.column == "amt"]
    assert sorted(rules) == ["range_max", "range_min"]
    assert len(set(rules)) == len(rules)


def test_dtype_rule_fires():
    df = _good(); df["amt"] = df["amt"].astype(str)
    assert any(x.rule == "dtype" and x.column == "amt"
               for x in validate(df, _spec()))


def test_pk_uniqueness_rule_fires():
    df = pd.DataFrame({"id": ["A", "A"], "amt": [1.0, 2.0], "kind": ["a", "b"]})
    v = validate(df, _spec())
    assert any(x.rule == "pk_unique" and x.n_rows == 1 for x in v)


def test_missing_and_unknown_columns_reported():
    df = _good().drop(columns=["amt"]).assign(extra=1)
    v = validate(df, _spec())
    assert any(x.rule == "missing_column" and x.column == "amt" for x in v)
    extra = [x for x in v if x.rule == "unknown_column"]
    assert extra and extra[0].severity == "WARN"


def test_referential_integrity_fires_on_orphan():
    parent = TableSpec(name="p", korean="부모", grain="1행",
                       columns=(ColumnSpec("k", "string", nullable=False),),
                       primary_key=("k",))
    child = TableSpec(name="c", korean="자식", grain="1행",
                      columns=(ColumnSpec("k", "string", nullable=False),),
                      foreign_keys=(ForeignKey(("k",), "p", ("k",)),))
    tables = {"p": pd.DataFrame({"k": ["A"]}), "c": pd.DataFrame({"k": ["A", "B"]})}
    v = check_refs(tables, {"p": parent, "c": child})
    assert any(x.rule == "fk_orphan" and x.n_rows == 1 for x in v)
    # 고아가 없으면 위반도 없어야 한다 (상시 발동이 아님)
    tables["c"] = pd.DataFrame({"k": ["A"]})
    assert check_refs(tables, {"p": parent, "c": child}) == []


# ----- DDL -------------------------------------------------------------------

def test_ddl_is_syntactically_well_formed():
    """컬럼 줄의 쉼표가 주석에 삼켜지면 안 된다 (초기 구현의 결함)."""
    d = ddl(cat.EXPOSURE)
    block = d.split("CREATE TABLE")[1].split(");")[0]
    lines = [l for l in block.split("\n")[1:] if l.strip()]
    for l in lines[:-1]:
        assert re.match(r"^\s+\S.*?,(\s+--.*)?$", l), f"쉼표 누락/오배치: {l}"
    assert not lines[-1].rstrip().endswith(","), "마지막 줄에 쉼표"
    assert "PRIMARY KEY (exposure_id)" in d
    assert "FOREIGN KEY (obligor_id) REFERENCES rdm_obligor" in d


def test_ddl_carries_constraints_and_provenance():
    d = ddl(cat.EXPOSURE)
    assert "CHECK (asset_class IN (" in d          # 허용값
    assert "chk_rdm_exposure_ead_rng" in d         # 범위
    assert "CRE20" in d                            # 규정 출처가 DDL에 남는다
    assert "입도:" in d


def test_every_catalog_table_generates_ddl():
    for spec in cat.ALL_TABLES:
        d = ddl(spec)
        assert d.startswith("--") and d.rstrip().endswith(";")
        assert f"CREATE TABLE {spec.name}" in d


# ----- 카탈로그 품질 ----------------------------------------------------------

def test_every_table_declares_grain_and_product():
    for s in cat.ALL_TABLES:
        assert len(s.grain) > 5, f"{s.name}: 입도 서술 불충분"
        assert s.product.startswith("PRD-"), f"{s.name}: 담당 Product 미표기"


def test_key_columns_carry_units_or_citations():
    """금액·비율 컬럼은 단위가, 규제 파생 컬럼은 출처가 있어야 재현된다."""
    for s in cat.ALL_TABLES:
        for c in s.columns:
            if c.dtype == "float":
                assert c.unit, f"{s.name}.{c.name}: 단위 미기재"


def test_foreign_keys_point_at_existing_tables():
    names = {s.name for s in cat.ALL_TABLES}
    for s in cat.ALL_TABLES:
        for fk in s.foreign_keys:
            assert fk.ref_table in names, f"{s.name}: 미등록 참조 {fk.ref_table}"


# ----- 분해 엔진 --------------------------------------------------------------

@pytest.fixture(scope="module")
def tables(portfolio):
    return dm.decompose(portfolio, asof=ASOF)


def test_decomposition_validates_clean(tables):
    """스펙과 실제 분해 결과가 갈라지면 카탈로그는 문서일 뿐이다."""
    v = dm.validate_all(tables)
    assert v == [], "\n".join(str(x) for x in v)


def test_decomposition_preserves_exposure_count(tables, portfolio):
    assert len(tables["rdm_exposure"]) == len(portfolio)
    assert tables["rdm_exposure"]["ead"].sum() == pytest.approx(
        float(portfolio["ead"].sum()), rel=1e-12)


def test_obligor_table_is_deduplicated(tables, portfolio):
    assert len(tables["rdm_obligor"]) == portfolio["obligor_id"].nunique()
    assert not tables["rdm_obligor"]["obligor_id"].duplicated().any()


def test_group_mapping_aggregates_corporates(tables):
    ob = tables["rdm_obligor"]
    corp = ob[ob["asset_class"] == "corporate"]
    assert corp["group_id"].str.startswith("GRP_").all()
    # 그룹 단위가 차주 수보다 적어야 집계 의미가 있다
    assert corp["group_id"].nunique() < len(corp)


def test_default_flag_follows_90dpd_definition(tables):
    d = tables["rdm_delinquency"]
    expected = (d["dpd"] >= 90).astype(int)
    pd.testing.assert_series_equal(d["default_flag"], expected,
                                   check_names=False)


def test_snapshot_fingerprints_are_recorded_per_table(tables):
    snap = tables["rdm_snapshot"]
    assert set(snap["table_name"]) == {
        "rdm_obligor", "rdm_exposure", "rdm_collateral", "rdm_delinquency"}
    assert (snap["fingerprint"].str.len() == 64).all()
    assert snap["row_count"].gt(0).all()


def test_decomposition_is_deterministic(portfolio):
    a = dm.decompose(portfolio, asof=ASOF, seed=42)
    b = dm.decompose(portfolio, asof=ASOF, seed=42)
    for k in a:
        pd.testing.assert_frame_equal(a[k], b[k])


def test_injected_corruption_is_caught(tables):
    """분해 결과를 오염시키면 검증이 잡아야 한다 — 통과가 상시가 아님을 확인."""
    bad = {k: v.copy() for k, v in tables.items()}
    bad["rdm_exposure"].loc[0, "ead"] = -1.0                  # 범위 위반
    bad["rdm_collateral"].loc[0, "exposure_id"] = "NOT_EXIST"  # 고아
    v = dm.validate_all(bad)
    assert any(x.rule == "range_min" for x in v)
    assert any(x.rule == "fk_orphan" for x in v)


def test_dq_result_frame_matches_its_own_spec(tables):
    v = dm.validate_all(tables)
    df = dm.dq_result_frame(v, asof=ASOF)
    assert list(df.columns) == cat.DQ_RESULT.column_names
    # 위반을 주입하면 결과 프레임도 스펙을 만족해야 한다
    bad = {k: x.copy() for k, x in tables.items()}
    bad["rdm_exposure"].loc[0, "ead"] = -1.0
    df2 = dm.dq_result_frame(dm.validate_all(bad), asof=ASOF)
    assert len(df2) > 0
    assert validate(df2, cat.DQ_RESULT, strict_columns=False) == []


def test_a_clean_run_still_leaves_a_dq_ledger(tables):
    """위반 0건이어도 통과 이력이 남아야 한다 (RDM-004).

    빈 원장은 '점검했고 깨끗했다'와 '점검하지 않았다'를 구별하지 못한다.
    마감 절차 CL-02 가 이 원장의 행수로 점검 수행 여부를 판정하므로, 비면
    깨끗한 실행일수록 마감이 미완료로 찍힌다.
    """
    rec: list[tuple[str, str, str]] = []
    v = dm.validate_all(tables, record=rec)
    df = dm.dq_result_frame(v, asof=ASOF, checks=rec)
    assert len(df) > 0
    assert (df["severity"] == "PASS").any()
    assert validate(df, cat.DQ_RESULT, strict_columns=False) == []
    # 통과 이력이 위반을 덮지 않는다. 한 점검은 한 행이다.
    assert not df.duplicated(subset=list(cat.DQ_RESULT.primary_key)).any()


def test_a_violated_check_is_not_also_recorded_as_passed(tables):
    """같은 점검이 위반과 통과로 동시에 남으면 기본키가 겹치고 뜻도 반대다."""
    bad = {k: x.copy() for k, x in tables.items()}
    bad["rdm_exposure"].loc[0, "ead"] = -1.0
    rec: list[tuple[str, str, str]] = []
    v = dm.validate_all(bad, record=rec)
    df = dm.dq_result_frame(v, asof=ASOF, checks=rec)
    row = df[(df["table_name"] == "rdm_exposure")
             & (df["column_name"] == "ead") & (df["rule"] == "range_min")]
    assert len(row) == 1
    assert row.iloc[0]["severity"] == "FAIL"
    assert not df.duplicated(subset=list(cat.DQ_RESULT.primary_key)).any()


def test_violations_come_before_pass_history(tables):
    """위반이 통과 이력 6천 행 밑에 깔리면 화면에서 사라진다."""
    bad = {k: x.copy() for k, x in tables.items()}
    bad["rdm_exposure"].loc[0, "ead"] = -1.0
    rec: list[tuple[str, str, str]] = []
    df = dm.dq_result_frame(dm.validate_all(bad, record=rec), asof=ASOF,
                            checks=rec)
    first_pass = int((df["severity"] == "PASS").idxmax())
    assert (df.iloc[:first_pass]["severity"] != "PASS").all()


def test_every_table_declares_a_primary_key():
    """PK 없는 테이블이 없다 — 없으면 유일성 검증 자체를 안 받는다.

    `rdm_dq_result`가 107장 중 유일하게 PK가 없었고, 선언 그레인
    ("검증 규칙 × 테이블 × 기준일")도 실제 행 구분과 달랐다 — 컬럼 단위 규칙이
    있어 같은 조합에 여러 행이 선다. 스펙이 그레인을 1급으로 강제하는 저장소에서
    한 장만 그 밖에 있으면, 그 한 장이 다음 결함의 자리가 된다.
    """
    from risk_lib.datamodel import catalog as cat

    missing = [t.name for t in cat.ALL_TABLES if not t.primary_key]
    assert not missing, f"PK 미선언 테이블: {missing}"


def test_primary_key_columns_are_non_nullable():
    """PK 컬럼은 NULL일 수 없다 — NULL은 행을 구분하지 못한다."""
    from risk_lib.datamodel import catalog as cat

    bad = []
    for t in cat.ALL_TABLES:
        cols = {c.name: c for c in t.columns}
        for k in t.primary_key:
            c = cols.get(k)
            if c is None:
                bad.append(f"{t.name}.{k} (컬럼 없음)")
            elif c.nullable:
                bad.append(f"{t.name}.{k} (nullable)")
    assert not bad, "PK 컬럼 결함:\n  " + "\n  ".join(bad)
