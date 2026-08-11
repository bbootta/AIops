"""기관코드 축 (INST-001) — 기관 원장·적용범위 판정·스펙 일괄 변환.

한 벌의 원장으로 여러 기관을 담으려면 산출 결과에 기관코드가 있어야 한다.
그러나 "모든 테이블에 기관코드"를 글자 그대로 적용하면 규정 원문·바젤 계수표·
코드 마스터처럼 기관이 달라도 값이 같은 표가 기관 수만큼 복제된다. 복제된
사본은 갈라지고, 갈라진 계수표는 어느 쪽이 원문인지 말할 수 없게 된다.

그래서 이 모듈은 표를 두 부류로 나눈다.

  기관 종속   익스포저·RWA·자본·ECL·한도·ALM 등 산출 결과와 그 입력.
              primary_key 앞에 institution_code 가 들어간다.
  공유 참조   규정 원문·감독 계수·코드 마스터·시장 공통 관측치.
              기관코드를 넣지 않는다. 목록은 SHARED_REFERENCE_TABLES 다.

판정 근거와 애매한 표는 `docs/기관축_적용범위.md` 에 전수로 남긴다. 그 문서는
`scope_markdown()` 의 출력이며 tests/test_institutions.py 가 일치를 확인한다.

기관별 난수 스트림은 `seed + seed_offset` 이고 seed_offset 은 원장 컬럼에서
온다. 파이썬 내장 hash() 는 실행마다 값이 바뀌므로 쓰지 않는다.
"""

from __future__ import annotations

import dataclasses
from typing import Iterable, Mapping

import pandas as pd

from risk_lib.datamodel.spec import (
    ColumnSpec as C, ForeignKey, TableSpec, Violation)
from risk_lib.limits_master import EVIDENCE_STATUS

# ---------------------------------------------------------------- 도메인

INSTITUTION_COLUMN = "institution_code"
AXIS_MASTER = "inst_master"

INSTITUTION_TYPES: tuple[str, ...] = ("은행", "증권")
DATA_ORIGINS: tuple[str, ...] = ("수기등록", "외부공시", "미확정")

# 기존 산출 원장 전체가 귀속되는 기관. 지금 저장소의 데이터는 국내 은행 표본
# 한 벌이므로 기관은 하나이며, 그 하나에 코드를 못 박는다.
PRIMARY_INSTITUTION = "KR_BANK_01"


# ---------------------------------------------------------------- 적용범위 판정
#
# 공유 참조 판정 기준 (셋을 모두 만족해야 한다):
#   1. 행 값이 기관의 산출·거래·조직에 의존하지 않는다.
#   2. 출처가 규정 원문·감독 서식·감독 계수표·표준 코드체계·시장 공통 관측치다.
#   3. 기관코드를 넣으면 같은 행이 기관 수만큼 복제된다.
#
# 하나라도 어긋나면 기관 종속으로 둔다. 잘못 종속시키면 사본이 늘 뿐이지만,
# 잘못 공유시키면 기관 A 의 값이 기관 B 의 화면에 그대로 나온다.

SHARED_REFERENCE_TABLES: dict[str, str] = {
    # 코드·규칙 마스터
    "rdm_code_master": "카탈로그 스펙에서 생성하는 코드셋 정본이다. 기관이 달라도 같은 행이다.",
    "rdm_dq_rule": "검증 규칙은 스펙에서 파생된다. 기관별로 갈리는 것은 결과(rdm_dq_result)다.",
    # 시장 공통 지표
    "rdm_macro_indicator_master": "거시·금융지표의 정의다. 지표는 시장 공통이며 기관이 소유하지 않는다.",
    "macro_indicator": "거시·금융지표 관측치다. 같은 시점 같은 지표는 기관과 무관하게 한 값이다.",
    # 신용 규제 계수·요건
    "crm_mitigation_param": "신용위험경감 규제계수(CRE22)다. 값이 원문에서 온다.",
    "crm_input_floor": "규제판본별 추정치 하한이다. 값이 원문에서 온다.",
    "crm_irb_scope": "규제판본별 자산군 적용 가부다. 값이 원문에서 온다.",
    "crm_rating_requirement": "[별표 3] 제4절 최소요건 원문이다.",
    # ALM 규제 계수·정의
    "alm_time_bucket": "[별표 9-1] <표2>·BCBS 시간버킷 정의다.",
    "alm_rate_shock_param": "통화별 감독 금리충격 모수다. 값이 원문에서 온다.",
    "alm_post_shock_floor": "충격후 금리하한이다. 값이 원문에서 온다.",
    "alm_scenario_def": "감독 금리 시나리오 구성식이다.",
    "alm_lcr_factor": "LCR 규제 계수·한도다.",
    "alm_nsfr_factor": "NSFR 규제 계수다.",
    "kr_retail_criteria": "[별표 9-1] 소매 유사 간주 판정기준 원문이다.",
    "kr_auto_option_param": "[별표 9-1] 자동금리옵션 모수 원문이다.",
    # 감독 서식
    "reg_form": "감독당국 서식 마스터(서식번호·주기·근거)다. 제출값은 reg_form_line 소관이다.",
}

# 어느 쪽으로도 읽히는 표. 택한 쪽과 그렇게 읽은 이유를 남긴다.
AMBIGUOUS_TABLES: dict[str, tuple[str, str]] = {
    "rdm_account_master": (
        "기관 종속",
        "계정과목 체계는 기관마다 다르다. 그룹 표준 계정을 강제하는 조직이면 공유 참조가 된다."),
    "rdm_product_master": (
        "기관 종속",
        "취급 상품 코드는 기관 고유다. 상품 유형 분류만 떼면 공유로 볼 여지가 있다."),
    "mkt_product": (
        "기관 종속",
        "상품 유형 명세는 시장 표준에 가깝지만 취급 여부와 복잡도 등급은 기관 판단이다."),
    "crm_backtest_criteria": (
        "기관 종속",
        "basis 가 전건 '내부기준'이다. 규정 수치가 확인되면 공유 참조로 옮길 후보다."),
    "alm_liquidity_stress_param": (
        "기관 종속",
        "유출률에 규정값이 없다(BCBS d144 는 원칙만). 내부 가정이 섞인다."),
    "st_shock_axis": (
        "기관 종속",
        "충격 축 목록은 감독 시나리오와 겹치지만 어느 축을 쓸지는 기관이 정한다."),
    "macro_scenario_link": (
        "기관 종속",
        "지표는 공유지만 시나리오 가정과 연결은 기관이 정한다."),
    "dat_retention_policy": (
        "기관 종속",
        "법정 최소 보존기간은 공통이나 세대수·익명화 시점은 기관 정책이다."),
    "gov_model_stage": (
        "기관 종속",
        "생애주기 단계 정의는 기관 거버넌스 규정 소관이다."),
    "icaap_risk_taxonomy": (
        "기관 종속",
        "리스크 인벤토리는 기관이 스스로 정하고 감독이 검토한다."),
    "opr_control": (
        "기관 종속",
        "PSMOR 원칙은 공통이나 매핑된 통제와 담당자는 기관 고유다."),
    "reg_form_line": (
        "기관 종속",
        "라인 정의는 서식 공통이지만 value·text_value 가 제출값이라 기관별로 갈린다. "
        "정의와 값을 두 표로 나누면 정의 쪽은 공유가 된다."),
    "ncr_component": (
        "기관 종속",
        "순자본비율은 금융투자업자 지표인데 현재 원장은 은행 표본 기관 아래에 있다. "
        "증권 기관이 등록되면 그쪽으로 옮겨야 한다."),
}

# 통화·국가 코드는 별도 표가 아니라 컬럼 허용값(ColumnSpec.allowed)으로만 있다.
# 표가 없으므로 축 판정 대상도 아니다. 표로 승격하면 공유 참조로 둔다.


def is_institution_scoped(table: str) -> bool:
    """이 표가 기관코드를 키로 가져야 하는가."""
    return table != AXIS_MASTER and table not in SHARED_REFERENCE_TABLES


def scope_verdict(table: str) -> str:
    if table == AXIS_MASTER:
        return "축 마스터"
    return "공유 참조" if table in SHARED_REFERENCE_TABLES else "기관 종속"


def scope_reason(table: str) -> str:
    if table == AXIS_MASTER:
        return "기관 축의 마스터 자신이다. institution_code 가 이미 기본키다."
    if table in SHARED_REFERENCE_TABLES:
        return SHARED_REFERENCE_TABLES[table]
    if table in AMBIGUOUS_TABLES:
        return AMBIGUOUS_TABLES[table][1]
    return "산출 결과 또는 그 입력이다. 기관이 바뀌면 값이 바뀐다."


# ---------------------------------------------------------------- 기관 원장

INST_MASTER = TableSpec(
    name=AXIS_MASTER, korean="기관 원장", product="PRD-RDM",
    grain="기관 1개당 1행",
    columns=(
        C("institution_code", "string", "기관코드", nullable=False,
          note="모든 기관 종속 원장의 선행 키. 값을 바꾸면 기존 산출의 귀속이 끊긴다"),
        C("name_ko", "string", "기관명(한글)", nullable=True,
          note="국내 기관은 필수다. check_names 가 확인한다"),
        C("name_en", "string", "기관명(영문)", nullable=True,
          note="국외 기관은 필수다. check_names 가 확인한다"),
        C("institution_type", "string", "업권", nullable=False,
          allowed=INSTITUTION_TYPES,
          note="업권이 다르면 적용 규정과 건전성 지표가 다르다(은행 BIS · 증권 NCR)"),
        C("region", "string", "지역", nullable=False),
        C("country", "string", "소재국", nullable=False,
          citation="ISO 3166-1 alpha-2"),
        C("currency", "string", "보고통화", nullable=False, citation="ISO 4217"),
        C("is_domestic", "bool", "국내 여부", nullable=False),
        C("regulatory_regime", "string", "적용 감독규정", nullable=False),
        C("size_tier", "string", "규모 구분", nullable=True,
          note="근거를 못 대면 비운다. 채우면 그 순간 근거가 사라진다"),
        C("seed_offset", "int", "난수 오프셋", nullable=False, min_value=0,
          note="기관별 seed = seed + seed_offset. 원장이 오프셋의 유일한 출처이며 "
               "파이썬 hash() 를 쓰지 않는다"),
        C("data_origin", "string", "등록 경로", nullable=False,
          allowed=DATA_ORIGINS),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
        C("note", "text", "비고", nullable=True),
    ),
    primary_key=("institution_code",),
    note="기관 축의 마스터. 기관 종속 원장의 institution_code 는 이 표를 참조한다.",
)


def build_inst_master() -> pd.DataFrame:
    """기관 원장을 만든다. 지금 등록된 기관은 국내 은행 표본 한 곳이다.

    실명·규모 구분은 이 저장소가 근거를 가지고 있지 않다. 그래서 name_ko 는
    보고서가 쓰는 자리표시자 그대로 두고 size_tier 는 비운다. 채워 넣으면
    없는 근거가 있는 것처럼 보인다.
    """
    rows = [{
        "institution_code": PRIMARY_INSTITUTION,
        "name_ko": "(기관명)",
        "name_en": None,
        "institution_type": "은행",
        "region": "국내",
        "country": "KR",
        "currency": "KRW",
        "is_domestic": True,
        "regulatory_regime": "은행업감독규정",
        "size_tier": None,
        "seed_offset": 0,
        "data_origin": "수기등록",
        "evidence_status": "미확인",
        "note": ("기존 산출 원장 전체가 귀속되는 기관이다. 실명은 미기재이며 "
                 "배포 시 기재한다. seed_offset 0 은 기존 (asof, seed) 산출을 "
                 "그대로 재현하기 위한 값이다."),
    }]
    df = pd.DataFrame(rows, columns=list(INST_MASTER.column_names))
    return df.astype({"seed_offset": "int64", "is_domestic": "bool"})


def check_names(master: pd.DataFrame) -> list[Violation]:
    """이름 규칙. 국내 기관은 한글명, 국외 기관은 영문명이 있어야 한다.

    국외 기관을 한글 음차로만 적으면 감독 제출본과 대조가 되지 않고, 국내
    기관을 영문으로만 적으면 국내 서식에 그대로 쓸 수 없다.
    """
    out: list[Violation] = []
    if not {"is_domestic", "name_ko", "name_en"} <= set(master.columns):
        return out
    domestic = master["is_domestic"].fillna(False).astype(bool)
    miss_ko = int((domestic & master["name_ko"].isna()).sum())
    if miss_ko:
        out.append(Violation(INST_MASTER.name, "name_ko_required", "name_ko",
                             miss_ko, "국내 기관에 한글명이 없다"))
    miss_en = int(((~domestic) & master["name_en"].isna()).sum())
    if miss_en:
        out.append(Violation(INST_MASTER.name, "name_en_required", "name_en",
                             miss_en, "국외 기관에 영문명이 없다"))
    return out


# ---------------------------------------------------------------- 결정론

def seed_offsets(master: pd.DataFrame | None = None) -> dict[str, int]:
    """기관코드 → 난수 오프셋. 원장이 유일한 출처다."""
    m = build_inst_master() if master is None else master
    offsets = {str(r.institution_code): int(r.seed_offset)
               for r in m.itertuples()}
    dup = len(offsets) != len(set(offsets.values()))
    if dup:
        raise ValueError("seed_offset 이 기관 간 중복이다. 두 기관이 같은 "
                         "난수 스트림을 쓰면 산출이 서로를 재현한다")
    return offsets


def institution_seed(seed: int, code: str,
                     master: pd.DataFrame | None = None) -> int:
    """기관별 시드. seed + 원장의 오프셋이며 벽시계·hash() 를 쓰지 않는다."""
    offsets = seed_offsets(master)
    if code not in offsets:
        raise ValueError(f"기관 원장에 없는 기관코드: {code}")
    return int(seed) + offsets[code]


# ---------------------------------------------------------------- 스펙 변환

def institution_column() -> C:
    """기관 종속 표에 붙일 선행 키 컬럼."""
    return C(INSTITUTION_COLUMN, "string", "기관코드", nullable=False,
             note="inst_master 참조. 기관 축의 선행 키",
             citation="INST-001 기관코드 축")


def with_institution_axis(spec: TableSpec, *,
                          scoped: Iterable[str] | None = None) -> TableSpec:
    """표 하나에 기관 축을 적용한다. 공유 참조 표는 그대로 돌려준다.

    scoped 는 기관코드를 함께 쓰는 표 이름의 집합이며, 그 대상을 가리키는
    외래키는 기관코드까지 묶어 넓힌다. 넓히지 않으면 기관 A 의 자식이 기관 B 의
    부모를 참조해도 참조무결성이 통과한다.
    """
    if not is_institution_scoped(spec.name):
        return spec
    if INSTITUTION_COLUMN in spec.column_names:
        return spec
    targets = frozenset(scoped) if scoped is not None else frozenset()
    out = spec.with_key_prefix(institution_column(), propagate_to=targets,
                               grain="기관 × " + spec.grain)
    # 기관 원장 참조를 붙인다. 붙이지 않으면 원장에 없는 기관코드가 들어와도
    # 참조무결성이 통과하고, 그 행은 어느 화면에도 뜨지 않은 채 합계에만 남는다.
    axis_fk = ForeignKey((INSTITUTION_COLUMN,), AXIS_MASTER,
                         (INSTITUTION_COLUMN,))
    return dataclasses.replace(out, foreign_keys=out.foreign_keys + (axis_fk,))


def apply_institution_axis(specs: Iterable[TableSpec]) -> tuple[TableSpec, ...]:
    """카탈로그 전체에 기관 축을 일괄 적용한다.

    표 한 장씩 손으로 고치면 빠뜨린 장이 생기고, 빠뜨린 장은 기관이 둘이 된
    다음에야 드러난다. 제외는 SHARED_REFERENCE_TABLES 한 곳에서만 정한다.
    """
    specs = tuple(specs)
    scoped = frozenset(s.name for s in specs if is_institution_scoped(s.name))
    return tuple(with_institution_axis(s, scoped=scoped) for s in specs)


# ---------------------------------------------------------------- 원장 채우기

def stamp(df: pd.DataFrame, code: str) -> pd.DataFrame:
    """기관코드를 맨 앞 컬럼으로 채운 사본을 돌려준다."""
    if INSTITUTION_COLUMN in df.columns:
        existing = set(df[INSTITUTION_COLUMN].dropna().unique())
        if existing - {code}:
            raise ValueError(f"이미 다른 기관코드가 있다: {sorted(existing)}")
        return df.copy()
    out = df.copy()
    out.insert(0, INSTITUTION_COLUMN, code)
    return out


def stamp_all(tables: Mapping[str, pd.DataFrame], code: str
              ) -> dict[str, pd.DataFrame]:
    """기관 종속 원장에만 기관코드를 채운다. 공유 참조 원장은 손대지 않는다."""
    return {name: (stamp(df, code) if is_institution_scoped(name) else df)
            for name, df in tables.items()}


# ---------------------------------------------------------------- 적용범위 문서

def scope_frame(specs: Iterable[TableSpec] | None = None) -> pd.DataFrame:
    """전수 판정표. 카탈로그의 모든 표와 기관 원장 자신을 한 행씩 담는다."""
    if specs is None:
        from risk_lib.datamodel import catalog as cat
        specs = tuple(cat.ALL_TABLES) + (INST_MASTER,)
    rows = [{
        "table": s.name,
        "korean": s.korean,
        "product": s.product,
        "verdict": scope_verdict(s.name),
        "ambiguous": s.name in AMBIGUOUS_TABLES,
        "reason": scope_reason(s.name),
    } for s in specs]
    df = pd.DataFrame(rows)
    return df.sort_values(["product", "table"]).reset_index(drop=True)


def scope_markdown(specs: Iterable[TableSpec] | None = None) -> str:
    """`docs/기관축_적용범위.md` 의 본문. 문서를 손으로 고치지 않는다."""
    f = scope_frame(specs)
    n_scoped = int((f["verdict"] == "기관 종속").sum())
    n_shared = int((f["verdict"] == "공유 참조").sum())
    n_master = int((f["verdict"] == "축 마스터").sum())

    L: list[str] = []
    L.append("# 기관코드 축 적용범위 (INST-001)")
    L.append("")
    L.append("이 문서는 `risk_lib.institutions.scope_markdown()` 의 출력이다. "
             "손으로 고치지 말고 다시 생성한다.")
    L.append("")
    L.append("## 판정 기준")
    L.append("")
    L.append("**공유 참조**로 두려면 셋을 모두 만족해야 한다.")
    L.append("")
    L.append("1. 행 값이 기관의 산출·거래·조직에 의존하지 않는다.")
    L.append("2. 출처가 규정 원문·감독 서식·감독 계수표·표준 코드체계·시장 공통 관측치다.")
    L.append("3. 기관코드를 넣으면 같은 행이 기관 수만큼 복제된다.")
    L.append("")
    L.append("하나라도 어긋나면 **기관 종속**으로 둔다. 잘못 종속시키면 사본이 늘 뿐이지만, "
             "잘못 공유시키면 기관 A 의 값이 기관 B 의 화면에 나온다.")
    L.append("")
    L.append("통화·국가 코드는 별도 표가 아니라 컬럼 허용값으로만 있으므로 판정 대상에 없다. "
             "표로 승격하면 공유 참조로 둔다.")
    L.append("")
    L.append("## 집계")
    L.append("")
    L.append("| 판정 | 표 수 |")
    L.append("|---|---|")
    L.append(f"| 기관 종속 | {n_scoped} |")
    L.append(f"| 공유 참조 | {n_shared} |")
    L.append(f"| 축 마스터 | {n_master} |")
    L.append(f"| 합계 | {len(f)} |")
    L.append("")
    L.append("## 애매한 표")
    L.append("")
    L.append("어느 쪽으로도 읽히는 표다. 택한 쪽과 이유를 남긴다.")
    L.append("")
    L.append("| 표 | 택한 판정 | 이유 |")
    L.append("|---|---|---|")
    for name in sorted(AMBIGUOUS_TABLES):
        side, why = AMBIGUOUS_TABLES[name]
        L.append(f"| `{name}` | {side} | {why} |")
    L.append("")
    L.append("## 전수 판정")
    L.append("")
    L.append("| 표 | 이름 | Product | 판정 | 애매 | 근거 |")
    L.append("|---|---|---|---|---|---|")
    for r in f.itertuples():
        mark = "○" if r.ambiguous else ""
        L.append(f"| `{r.table}` | {r.korean} | {r.product} | {r.verdict} | "
                 f"{mark} | {r.reason} |")
    L.append("")
    return "\n".join(L)
