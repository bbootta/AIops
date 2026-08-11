"""기관코드 축 (INST-001) 시험.

축을 세우는 작업에서 조용히 틀리는 곳은 셋이다.
  - 적용범위 판정: 규정·계수표에 기관코드를 붙여 사본을 늘린다.
  - 외래키: 자식만 기관코드를 받고 참조는 그대로 두어, 기관 A 의 자식이
    기관 B 의 부모를 참조해도 통과한다.
  - 원장 채우기: 스펙만 바꾸고 기존 행을 채우지 않아 전 원장이 검증에서 떨어진다.
셋을 각각 확인하고, 마지막에 실제 산출 원장 267장으로 끝에서 끝까지 본다.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from risk_lib import institutions as inst
from risk_lib.datamodel import catalog as cat
from risk_lib.datamodel.spec import (
    ColumnSpec, ForeignKey, SchemaError, TableSpec, check_refs, validate)

DOC = Path(__file__).parent.parent / "docs" / "기관축_적용범위.md"


# ----- 기관 원장 --------------------------------------------------------------

def test_inst_master_matches_its_spec():
    m = inst.build_inst_master()
    assert validate(m, inst.INST_MASTER) == []
    assert inst.INST_MASTER.primary_key == ("institution_code",)
    assert inst.INST_MASTER.grain.startswith("기관 1개당")


def test_inst_master_is_deterministic():
    pd.testing.assert_frame_equal(inst.build_inst_master(),
                                  inst.build_inst_master())


def test_inst_master_has_one_row_per_institution():
    m = inst.build_inst_master()
    assert not m["institution_code"].duplicated().any()
    assert inst.PRIMARY_INSTITUTION in set(m["institution_code"])


def test_unconfirmed_fields_stay_empty():
    """실명·규모 구분은 근거가 없다. 채우면 없는 근거가 있는 것처럼 보인다."""
    m = inst.build_inst_master().set_index("institution_code")
    row = m.loc[inst.PRIMARY_INSTITUTION]
    assert pd.isna(row["size_tier"])
    assert row["evidence_status"] == "미확인"


# ----- 이름 규칙 --------------------------------------------------------------

def test_domestic_institution_carries_korean_name():
    assert inst.check_names(inst.build_inst_master()) == []


def test_foreign_institution_without_english_name_is_caught():
    m = inst.build_inst_master().copy()
    m.loc[len(m)] = {**m.iloc[0].to_dict(), "institution_code": "XX_BANK_01",
                     "is_domestic": False, "name_en": None, "seed_offset": 1}
    v = inst.check_names(m)
    assert [x.rule for x in v] == ["name_en_required"]


def test_domestic_institution_without_korean_name_is_caught():
    m = inst.build_inst_master().copy()
    m.loc[0, "name_ko"] = None
    v = inst.check_names(m)
    assert [x.rule for x in v] == ["name_ko_required"]


# ----- 결정론 ----------------------------------------------------------------

def test_institution_seed_comes_from_the_ledger_offset():
    m = inst.build_inst_master()
    off = int(m.loc[0, "seed_offset"])
    assert inst.institution_seed(42, inst.PRIMARY_INSTITUTION, m) == 42 + off


def test_primary_institution_offset_is_zero():
    """기존 (asof, seed) 산출이 그대로 재현돼야 한다."""
    assert inst.seed_offsets()[inst.PRIMARY_INSTITUTION] == 0


def test_unknown_institution_has_no_seed():
    with pytest.raises(ValueError):
        inst.institution_seed(42, "NOT_REGISTERED")


def test_duplicate_offsets_are_rejected():
    """두 기관이 같은 스트림을 쓰면 한쪽이 다른 쪽을 재현한다."""
    m = inst.build_inst_master().copy()
    m.loc[len(m)] = {**m.iloc[0].to_dict(), "institution_code": "KR_BANK_02"}
    with pytest.raises(ValueError):
        inst.seed_offsets(m)


def test_seed_derivation_does_not_use_builtin_hash():
    """내장 hash()는 실행마다 값이 달라 같은 (asof, seed)를 재현하지 못한다."""
    import ast

    tree = ast.parse(Path(inst.__file__).read_text(encoding="utf-8"))
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "hash" not in called


# ----- 적용범위 판정 ----------------------------------------------------------

def test_every_catalog_table_is_classified():
    f = inst.scope_frame()
    assert len(f) == len(cat.ALL_TABLES) + 1        # 기관 원장 자신
    assert set(f["verdict"]) <= {"기관 종속", "공유 참조", "축 마스터"}
    assert f["reason"].str.len().gt(10).all()


def test_shared_reference_list_only_names_registered_tables():
    names = {s.name for s in cat.ALL_TABLES}
    unknown = sorted(set(inst.SHARED_REFERENCE_TABLES) - names)
    assert not unknown, f"카탈로그에 없는 표를 제외 목록에 적었다: {unknown}"


def test_ambiguous_list_only_names_registered_tables():
    names = {s.name for s in cat.ALL_TABLES}
    unknown = sorted(set(inst.AMBIGUOUS_TABLES) - names)
    assert not unknown
    for name, (side, why) in inst.AMBIGUOUS_TABLES.items():
        assert side in ("기관 종속", "공유 참조"), name
        assert len(why) > 10, name
        assert inst.scope_verdict(name) == side, name


def test_regulatory_parameter_ledgers_stay_shared():
    """규정·계수 원장에 기관코드를 붙이면 원문 한 벌이 기관 수만큼 갈라진다."""
    for name in ("alm_rate_shock_param", "alm_lcr_factor", "crm_input_floor",
                 "crm_mitigation_param", "crm_rating_requirement",
                 "kr_auto_option_param", "rdm_code_master"):
        assert not inst.is_institution_scoped(name), name


def test_calculated_ledgers_are_institution_scoped():
    for name in ("rdm_exposure", "rwa_result", "ecl_result", "cap_stack",
                 "alm_irrbb_result", "lex_position", "val_check"):
        assert inst.is_institution_scoped(name), name


# ----- 스펙 일괄 변환 ---------------------------------------------------------

@pytest.fixture(scope="module")
def axis():
    return {s.name: s for s in cat.inst_axis_tables()}


def test_axis_catalog_covers_every_table_plus_the_master(axis):
    assert len(axis) == len(cat.ALL_TABLES) + 1
    assert inst.AXIS_MASTER in axis


def test_scoped_tables_lead_their_key_with_the_institution(axis):
    for s in cat.ALL_TABLES:
        got = axis[s.name]
        if not inst.is_institution_scoped(s.name):
            continue
        assert got.primary_key[0] == "institution_code", s.name
        assert got.column_names[0] == "institution_code", s.name
        assert got.primary_key[1:] == s.primary_key, s.name
        assert len(got.columns) == len(s.columns) + 1, s.name


def test_shared_tables_are_returned_untouched(axis):
    for name in inst.SHARED_REFERENCE_TABLES:
        assert axis[name] is next(s for s in cat.ALL_TABLES if s.name == name)


def test_foreign_keys_to_scoped_parents_carry_the_institution(axis):
    exposure = axis["rdm_exposure"]
    fk = next(f for f in exposure.foreign_keys if f.ref_table == "rdm_obligor")
    assert fk.columns == ("institution_code", "obligor_id")
    assert fk.ref_columns == ("institution_code", "obligor_id")


def test_foreign_keys_to_shared_parents_are_left_alone():
    child = TableSpec(
        name="t_child", korean="자식", grain="1행", product="PRD-RDM",
        columns=(ColumnSpec("k", "string", nullable=False),
                 ColumnSpec("code", "string", nullable=False)),
        primary_key=("k",),
        foreign_keys=(ForeignKey(("code",), "rdm_code_master", ("code",)),))
    got = inst.with_institution_axis(child, scoped={"t_child"})
    ref = next(f for f in got.foreign_keys if f.ref_table == "rdm_code_master")
    assert ref.columns == ("code",)


def test_every_scoped_table_points_at_the_institution_ledger(axis):
    for name, s in axis.items():
        if not inst.is_institution_scoped(name):
            continue
        assert any(f.ref_table == inst.AXIS_MASTER for f in s.foreign_keys), name


def test_axis_catalog_keeps_the_spec_quality_rules(axis):
    names = set(axis)
    for s in axis.values():
        assert len(s.grain) > 5, s.name
        assert s.product.startswith("PRD-"), s.name
        assert s.primary_key, s.name
        for k in s.primary_key:
            assert not s.column(k).nullable, f"{s.name}.{k}"
        for c in s.columns:
            if c.dtype == "float":
                assert c.unit, f"{s.name}.{c.name}"
        for f in s.foreign_keys:
            assert f.ref_table in names, f"{s.name} → {f.ref_table}"


def test_axis_is_idempotent(axis):
    twice = inst.apply_institution_axis(axis.values())
    for a, b in zip(sorted(axis.values(), key=lambda s: s.name),
                    sorted(twice, key=lambda s: s.name)):
        assert a.primary_key == b.primary_key
        assert len(a.columns) == len(b.columns)


def test_key_prefix_refuses_a_nullable_axis_column():
    col = ColumnSpec("institution_code", "string", nullable=True)
    with pytest.raises(SchemaError):
        cat.OBLIGOR.with_key_prefix(col)


def test_key_prefix_refuses_a_duplicate_column():
    col = ColumnSpec("obligor_id", "string", nullable=False)
    with pytest.raises(SchemaError):
        cat.OBLIGOR.with_key_prefix(col)


def test_key_prefix_leaves_the_original_spec_alone():
    before = cat.OBLIGOR.primary_key
    cat.OBLIGOR.with_key_prefix(inst.institution_column())
    assert cat.OBLIGOR.primary_key == before
    assert "institution_code" not in cat.OBLIGOR.column_names


# ----- 원장 채우기 ------------------------------------------------------------

def test_stamp_puts_the_institution_first():
    df = pd.DataFrame({"a": [1, 2]})
    out = inst.stamp(df, inst.PRIMARY_INSTITUTION)
    assert out.columns[0] == "institution_code"
    assert set(out["institution_code"]) == {inst.PRIMARY_INSTITUTION}
    assert list(df.columns) == ["a"]           # 원본은 그대로


def test_stamp_refuses_to_overwrite_another_institution():
    df = pd.DataFrame({"institution_code": ["OTHER"], "a": [1]})
    with pytest.raises(ValueError):
        inst.stamp(df, inst.PRIMARY_INSTITUTION)


def test_stamp_all_skips_shared_reference_tables():
    tables = {"rwa_result": pd.DataFrame({"a": [1]}),
              "alm_lcr_factor": pd.DataFrame({"factor": [0.5]})}
    out = inst.stamp_all(tables, inst.PRIMARY_INSTITUTION)
    assert "institution_code" in out["rwa_result"].columns
    assert "institution_code" not in out["alm_lcr_factor"].columns


# ----- 문서 ------------------------------------------------------------------

def test_scope_document_matches_the_code():
    """판정 목록이 문서와 갈라지면 문서는 주장일 뿐이다."""
    assert DOC.exists(), f"{DOC} 없음"
    assert DOC.read_text(encoding="utf-8") == inst.scope_markdown()


# ----- 실제 산출 원장 ---------------------------------------------------------

@pytest.fixture(scope="module")
def stamped(result, portfolio):
    from risk_lib.ui_studio.studio import build_studio
    tables = build_studio(result, portfolio).tables
    out = inst.stamp_all(tables, inst.PRIMARY_INSTITUTION)
    out[inst.AXIS_MASTER] = inst.build_inst_master()
    return out


def test_existing_output_belongs_to_one_institution(stamped):
    for name, df in stamped.items():
        if not inst.is_institution_scoped(name) or df.empty:
            continue
        assert set(df["institution_code"]) == {inst.PRIMARY_INSTITUTION}, name


def test_stamped_ledgers_validate_against_the_axis_catalog(stamped, axis):
    v = []
    for name, df in stamped.items():
        if name in axis:
            v += validate(df, axis[name])
    v += check_refs(stamped, {k: s for k, s in axis.items() if k in stamped})
    assert v == [], "\n".join(str(x) for x in v[:20])


def test_an_unregistered_institution_code_is_caught(stamped, axis):
    """참조무결성이 실제로 발동하는지 확인한다. 통과가 상시면 통제가 아니다."""
    bad = dict(stamped)
    bad["rdm_exposure"] = stamped["rdm_exposure"].copy()
    bad["rdm_exposure"].loc[0, "institution_code"] = "KR_BANK_99"
    v = check_refs(bad, {k: s for k, s in axis.items() if k in bad})
    assert any(x.rule == "fk_orphan" and x.table == "rdm_exposure" for x in v)
