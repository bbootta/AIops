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


def test_narrow_offset_gap_is_rejected():
    """오프셋 값이 서로 달라도 간격이 좁으면 스트림이 겹친다.

    간격이 1000 이던 때 KR_BANK_01 의 alm_contract(0+1101)와 APAC_BANK_01 의
    balance_sheet(1000+101)가 seed+1143 으로 같았다. 값 중복 검사만으로는
    그 상태를 잡지 못한다.
    """
    m = inst.build_inst_master().copy()
    m.loc[len(m)] = {**m.iloc[0].to_dict(), "institution_code": "KR_BANK_02",
                     "seed_offset": 1000}
    with pytest.raises(ValueError, match="간격"):
        inst.seed_offsets(m)


# ----- 난수 스트림 겹침 --------------------------------------------------------
#
# 기관별 스트림은 `기관시드 + 모듈오프셋` 이다. 모듈 오프셋을 소스에서 걷고
# 기관 오프셋과 곱해 전 스트림을 모은 뒤 중복을 센다. 중복이 하나라도 있으면
# 기관 A 의 어떤 모듈과 기관 B 의 다른 모듈이 같은 난수열을 쓴다.

_RISK_LIB = Path(inst.__file__).parent


def _int_consts(tree) -> dict[str, int]:
    """모듈 상단의 정수 상수. 튜플 대입과 타입 표기를 함께 읽는다."""
    import ast

    out: dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) \
                and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, int):
            out[node.target.id] = node.value.value
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and isinstance(node.value, ast.Constant) \
                        and isinstance(node.value.value, int):
                    out[t.id] = node.value.value
                elif isinstance(t, ast.Tuple) and isinstance(node.value, ast.Tuple):
                    for name, val in zip(t.elts, node.value.elts):
                        if isinstance(name, ast.Name) \
                                and isinstance(val, ast.Constant) \
                                and isinstance(val.value, int):
                            out[name.id] = val.value
    return out


def _offset_bound(expr, consts: dict[str, int], local: dict) -> int | None:
    """오프셋 식의 상한. 못 읽으면 None 이며 시험이 그 자리를 알린다."""
    import ast

    if isinstance(expr, ast.Constant) and isinstance(expr.value, int):
        return expr.value
    if isinstance(expr, ast.Name):
        if expr.id in consts:
            return consts[expr.id]
        if expr.id in local:
            return _offset_bound(local[expr.id], consts, local)
        return None
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Mod):
        right = _offset_bound(expr.right, consts, local)
        return None if right is None else right - 1
    return None


def _scan_module_offsets() -> tuple[set[int], list[str]]:
    """`default_rng(시드 + 오프셋)` 의 오프셋 집합과 못 읽은 자리 목록."""
    import ast

    offsets: set[int] = set()
    unread: list[str] = []
    for path in sorted(_RISK_LIB.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        consts = _int_consts(tree)
        funcs = [n for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and node.args
                    and ast.unparse(node.func).endswith("default_rng")):
                continue
            arg = node.args[0]
            if not (isinstance(arg, ast.BinOp) and isinstance(arg.op, ast.Add)):
                continue                 # 시드 자체이거나 절대 시드다
            owner = None
            for fn in funcs:
                if fn.lineno <= node.lineno <= (fn.end_lineno or fn.lineno):
                    if owner is None or fn.lineno > owner.lineno:
                        owner = fn
            local = {}
            if owner is not None:
                for n in ast.walk(owner):
                    if isinstance(n, ast.Assign):
                        for t in n.targets:
                            if isinstance(t, ast.Name):
                                local[t.id] = n.value
            bound = _offset_bound(arg.right, consts, local)
            where = f"{path.relative_to(_RISK_LIB.parent)}:{node.lineno}"
            if bound is None:
                unread.append(f"{where} · {ast.unparse(arg)}")
            else:
                offsets.add(bound)
    return offsets, unread


def test_every_module_offset_is_readable_and_fits_the_stride():
    """오프셋을 못 읽으면 겹침을 셀 수 없다. 조용히 넘기지 않는다."""
    offsets, unread = _scan_module_offsets()
    assert not unread, "모듈 오프셋을 읽지 못한 자리:\n" + "\n".join(unread)
    assert len(offsets) > 40, f"오프셋을 {len(offsets)}개만 찾았다. 훑기가 깨졌다"
    over = sorted(o for o in offsets if o >= inst.SEED_STRIDE)
    assert not over, (f"모듈 오프셋이 기관 간격({inst.SEED_STRIDE}) 이상이다: "
                      f"{over}. 간격을 넓히거나 오프셋을 줄인다")


# ----- 리터럴 시드 (기관 시드를 타지 않는 자리) --------------------------------
#
# 위 훑기는 `default_rng(시드 + 오프셋)` 만 읽는다. 리터럴 정수 시드를 넘기는
# 자리는 그 형태가 아니라서 조용히 빠졌고, 빠진 자리는 기관이 바뀌어도 같은
# 난수열을 쓴다. 즉 전 기관이 그 스트림을 공유한다. 아래 훑기가 그 자리를
# 잡고, `_LITERAL_SEED_SITES` 가 그것을 알려진 예외로 못박는다. 새 자리가
# 생기면 목록과 어긋나 실패한다.

_LITERAL_SEED_BASE = 42          # 국내 표본 산출이 쓰는 기준 시드


def _rng_seeded_functions(trees) -> dict[str, tuple[str, int | None]]:
    """`default_rng(<파라미터>)` 로 난수를 여는 risk_lib 함수.

    함수이름 → (파라미터 이름, 그 파라미터의 리터럴 기본값 또는 None).
    호출부가 그 파라미터에 리터럴을 넘기거나 생략하면 리터럴 시드가 된다.
    """
    import ast

    out: dict[str, tuple[str, int | None]] = {}
    for tree in trees.values():
        for fn in ast.walk(tree):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            a = fn.args
            pos = [x.arg for x in a.posonlyargs + a.args]
            kwo = [x.arg for x in a.kwonlyargs]
            for node in ast.walk(fn):
                if not (isinstance(node, ast.Call) and node.args
                        and ast.unparse(node.func).endswith("default_rng")):
                    continue
                arg = node.args[0]
                if not isinstance(arg, ast.Name):
                    continue
                if arg.id in pos:
                    k = pos.index(arg.id) - (len(pos) - len(a.defaults))
                    dflt = a.defaults[k] if k >= 0 else None
                elif arg.id in kwo:
                    dflt = a.kw_defaults[kwo.index(arg.id)]
                else:
                    continue
                lit = (dflt.value if isinstance(dflt, ast.Constant)
                       and isinstance(dflt.value, int) else None)
                out[fn.name] = (arg.id, lit)
    return out


def _scan_literal_seed_sites(trees=None) -> dict[str, list[str]]:
    """리터럴 정수 시드가 난수기에 닿는 자리 → 그 자리의 `파일:행` 목록.

    잡는 형태는 셋이다.
      - `default_rng(<정수>)`                     — 절대 시드를 직접 연다
      - `f(..., seed=<정수>)`                     — 시드 파라미터에 리터럴
      - `f(...)` 에서 시드 생략 + 리터럴 기본값    — 기본값이 그대로 시드다
    `params.get("seed", 42)` 처럼 값이 리터럴이 아닌 자리는 잡지 않는다.
    그 자리는 시드를 **읽는** 것이지 박은 것이 아니다.
    """
    import ast

    if trees is None:
        trees = {p: ast.parse(p.read_text(encoding="utf-8"))
                 for p in sorted(_RISK_LIB.rglob("*.py"))}
    seeded = _rng_seeded_functions(trees)
    sites: dict[str, list[str]] = {}

    def _add(key: str, path, lineno: int) -> None:
        sites.setdefault(key, []).append(
            f"{path.relative_to(_RISK_LIB.parent)}:{lineno}")

    for path, tree in trees.items():
        rel = path.relative_to(_RISK_LIB.parent)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = ast.unparse(node.func).split(".")[-1]
            if name == "default_rng":
                if node.args and isinstance(node.args[0], ast.Constant) \
                        and isinstance(node.args[0].value, int):
                    _add(f"{rel} · default_rng({node.args[0].value})",
                         path, node.lineno)
                continue
            if name not in seeded:
                continue
            param, lit = seeded[name]
            given = {k.arg: k.value for k in node.keywords}.get(param)
            if given is None:
                if lit is not None:      # 생략 → 리터럴 기본값이 시드가 된다
                    _add(f"{rel} · {name}({param}={lit} 기본)", path, node.lineno)
            elif isinstance(given, ast.Constant) and isinstance(given.value, int):
                _add(f"{rel} · {name}({param}={given.value})", path, node.lineno)
    return sites


# 잡힌 자리와 그것을 그대로 두는 근거. 근거 없이 늘리지 않는다.
#
# 넷 다 기관 시드를 타지 않는다. 앞의 둘은 `run_pipeline` 안에 있어 기관마다
# 돌므로 **전 기관이 실제로 같은 난수열을 공유한다**. 고치지 않는 이유는
# 국내 표본 수치가 바뀌기 때문이며, 아래 값은 직접 돌려 측정한 것이다.
_LITERAL_SEED_SITES: dict[str, str] = {
    "risk_lib/pipeline.py · split_train_test(seed=7 기본)":
        "PD 모형의 학습·검증 분할. 기관 시드를 태우면 분할 마스크가 바뀌어 "
        "국내 표본 CET1 이 8.119291% 에서 8.364940% 로 움직인다(seed=999 로 "
        "직접 측정). 재현 고정이 우선이므로 두고, 전 기관이 같은 분할을 쓴다는 "
        "사실을 여기 남긴다.",
    "risk_lib/pipeline.py · permutation_importance(seed=42)":
        "변수중요도 셔플. 시드를 바꿔도 국내 표본 CET1 은 8.119291% 로 같았으나 "
        "explain 표의 중요도 수치열이 바뀐다. 전 기관이 같은 셔플 순열을 쓴다.",
    "risk_lib/explainability.py · default_rng(42)":
        "shapley_attribution 의 rng 미지정 기본값. ops_pages/governance.py 가 "
        "rng 를 넘기지 않아 전 기관이 같은 연합 표본을 쓴다. 규제자본 산출이 "
        "아니라 화면 설명용 근사다.",
    "risk_lib/datamodel/lineage.py · generate_portfolio(seed=42)":
        "DATA_FLOW.md 의 행수를 붙이기 위한 문서 기준 실행. 기관 산출 경로가 "
        "아니며 시드 고정이 목적이다.",
}


_SCAN_PROBE = '''
import numpy as np


def opens(df, seed: int = 7):
    return np.random.default_rng(seed)


def caller(df, a):
    np.random.default_rng(31337)
    opens(df, seed=99)
    opens(df)
    opens(df, seed=a + 1)
'''


def test_the_scan_reads_all_three_literal_seed_forms():
    """세 형태를 다 읽는지 합성 조각으로 본다. 소스 사정과 무관하게 성립한다.

    이전 훑기는 `default_rng(시드 + 오프셋)` 만 읽어 아래 셋을 전부 놓쳤고,
    놓친 자리는 시험에 잡히지 않은 채 전 기관이 공유하는 스트림이 됐다.
    """
    import ast

    got = _scan_literal_seed_sites(
        {_RISK_LIB / "_scan_probe.py": ast.parse(_SCAN_PROBE)})
    assert set(got) == {
        "risk_lib/_scan_probe.py · default_rng(31337)",     # 절대 시드
        "risk_lib/_scan_probe.py · opens(seed=99)",         # 인자에 리터럴
        "risk_lib/_scan_probe.py · opens(seed=7 기본)",      # 생략 → 리터럴 기본값
    }, got
    # `seed=a + 1` 은 리터럴이 아니다. 호출자가 넘긴 값을 타므로 잡지 않는다.


def test_every_literal_seed_site_is_a_listed_known_exception():
    """잡힌 자리는 전부 근거와 함께 적혀 있어야 한다. 늘어나면 실패한다."""
    sites = _scan_literal_seed_sites()
    added = sorted(set(sites) - set(_LITERAL_SEED_SITES))
    gone = sorted(set(_LITERAL_SEED_SITES) - set(sites))
    assert not added, (
        "기관 시드를 타지 않는 리터럴 시드 자리가 늘었다. 기관 시드로 "
        "돌리거나 근거와 함께 _LITERAL_SEED_SITES 에 적어라:\n"
        + "\n".join(f"{k}  ({', '.join(sites[k])})" for k in added))
    assert not gone, ("목록에만 있고 소스에 없는 자리다. 고쳤으면 목록에서 "
                      f"지워라: {gone}")
    for k, why in _LITERAL_SEED_SITES.items():
        assert len(why) > 30, k
        assert len(sites[k]) == 1, (k, sites[k])   # 같은 자리 복제도 새 자리다


def test_the_literal_seed_sites_give_every_institution_one_shared_stream():
    """리터럴 시드 자리가 기관을 안 탄다는 사실을 값으로 보인다."""
    import inspect
    from risk_lib import data_gen_intl as intl
    from risk_lib.data_gen import split_train_test
    from risk_lib.models.explain import permutation_importance

    m = intl.build_inst_master_intl()
    codes = sorted(inst.seed_offsets(m))
    assert len(codes) >= 9
    df = pd.DataFrame({"x": range(400)})

    # (1) 파이프라인 호출부는 seed 를 넘기지 않는다. 기관이 무엇이든 같은 분할이다.
    shared = {tuple(split_train_test(df)[0]["x"]) for _ in codes}
    assert len(shared) == 1
    assert shared == {tuple(split_train_test(df, seed=7)[0]["x"])}

    # (2) 기관 시드를 넘겼다면 기관마다 갈렸을 것이다. 그 차이가 지금은 없다.
    per_inst = {tuple(split_train_test(
        df, seed=inst.institution_seed(_LITERAL_SEED_BASE, c, m))[0]["x"])
        for c in codes}
    assert len(per_inst) == len(codes)

    # (3) 변수중요도 셔플도 같은 자리다. 서명의 기본값과 호출부가 둘 다 42 다.
    assert inspect.signature(
        permutation_importance).parameters["seed"].default == 42
    assert ("risk_lib/pipeline.py · permutation_importance(seed=42)"
            in _scan_literal_seed_sites())


def test_no_two_institutions_share_a_random_stream():
    """`기관시드 + 모듈오프셋` 스트림을 모아 중복을 센다. 0 이어야 한다.

    이 셈의 범위는 기관 시드를 타는 자리뿐이다. 리터럴 시드 자리는 애초에
    기관 시드를 안 타므로 여기 들어오지 않으며, 그중 `run_pipeline` 안의 둘은
    전 기관이 실제로 공유하는 스트림이다. 아래 마지막 검사가 그 둘을 여기서도
    드러낸다. 이 시험만 보고 "겹침 0" 이라고 적으면 안 된다.
    """
    from collections import Counter
    from risk_lib import data_gen_intl as intl

    module_offsets, _ = _scan_module_offsets()
    inst_offsets = inst.seed_offsets(intl.build_inst_master_intl())
    streams = Counter(base + off for base in inst_offsets.values()
                      for off in module_offsets)
    shared = [s for s, n in streams.items() if n > 1]
    assert not shared, (
        f"기관이 다른데 같은 난수 스트림을 쓴다: {sorted(shared)[:5]} "
        f"(총 {len(shared)}건)")
    assert len(streams) == len(inst_offsets) * len(module_offsets)
    # 이 셈 밖에서 전 기관이 공유하는 자리. 지금은 2 건이다.
    in_pipeline = sorted(k for k in _LITERAL_SEED_SITES
                         if k.startswith("risk_lib/pipeline.py"))
    assert len(in_pipeline) == 2, in_pipeline


def test_the_stream_count_catches_a_narrow_stride():
    """검사가 실제로 발동하는지 본다. 통과가 상시면 통제가 아니다."""
    from collections import Counter

    module_offsets, _ = _scan_module_offsets()
    narrow = {f"INST_{i}": i * 1000 for i in range(9)}   # 고치기 전의 간격
    streams = Counter(base + off for base in narrow.values()
                      for off in module_offsets)
    assert [s for s, n in streams.items() if n > 1], \
        "간격 1000 에서도 겹침이 없다면 이 시험은 아무것도 지키지 않는다"


def test_the_reported_stream_collision_is_gone():
    """지적이 든 예: KR 의 alm_contract 와 APAC 의 balance_sheet."""
    from risk_lib import data_gen_intl as intl

    m = intl.build_inst_master_intl()
    kr = inst.institution_seed(42, "KR_BANK_01", m) + 1101
    apac = inst.institution_seed(42, "APAC_BANK_01", m) + 101
    assert kr != apac, f"두 스트림이 같은 시드({kr})를 쓴다"


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
