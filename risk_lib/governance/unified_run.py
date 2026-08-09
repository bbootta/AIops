"""통합 런 컨텍스트 (PLT-014).

산출이 도메인별로 따로 돌면 신용 수치는 A판, 시장 수치는 B판을 보게 되고,
그 상태로 만든 보고서는 어느 시점의 은행도 설명하지 못한다. 한 번의 실행이
전 도메인을 관통했다는 사실 자체가 원장으로 남아야 한다.

원장 두 장이다.

  gov_unified_run   실행 1건. 기준일·seed·코드리비전·도메인 수·행수·지문
  gov_run_domain    실행 x 도메인. 원장 수·행수·지문·산출 여부

세 가지를 검사한다.

  도메인 누락   선언한 도메인 중 원장이 하나도 없는 도메인
  run_id 혼입   원장의 run_id 컬럼에 다른 실행 식별자가 섞였는지
  지문          도메인별 지문과 실행 전체 지문. 두 실행이 같은지 한 값으로 대조

이 모듈의 TableSpec은 아직 datamodel.catalog에 등재하지 않았다. 등재는 실체화
검증과 문서 수치 일치를 함께 만족해야 하므로 배선 단계에서 `SPECS`를 넘긴다.
스펙 품질 기준(입도·기본키·float 단위·FK 대상 존재)은 지금부터 지킨다.

참조: RYNTA BRD PLT-014(Unified Run Context) · GOV-001(기준시점 통제),
BCBS 239 원칙 3(정확성·무결성) · 원칙 5(적시성).
"""

from __future__ import annotations

import hashlib

import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec

DOMAIN_STATUSES = ("산출", "미산출")


UNIFIED_RUN = TableSpec(
    name="gov_unified_run", korean="통합 실행 원장", product="PRD-VAL",
    grain="실행(run_id) 1건당 1행",
    columns=(
        C("run_id", "string", "실행 식별자", nullable=False),
        C("asof", "date", "기준일자", nullable=False),
        C("seed", "int", "난수 시드", nullable=False, unit="count", min_value=0),
        C("code_revision", "text", "코드 리비전", nullable=False),
        C("n_domains_declared", "int", "선언 도메인 수", nullable=False,
          unit="count", min_value=1),
        C("n_domains_built", "int", "산출 도메인 수", nullable=False,
          unit="count", min_value=0),
        C("n_tables", "int", "원장 수", nullable=False, unit="count", min_value=0),
        C("n_rows", "int", "총 행수", nullable=False, unit="count", min_value=0),
        C("run_fingerprint", "text", "실행 지문(SHA-256 앞 16자)", nullable=False),
        C("is_complete", "bool", "전 도메인 관통 여부", nullable=False),
    ),
    primary_key=("run_id",),
    note="is_complete=False면 이 실행 하나로 전사 수치를 설명할 수 없다.",
)

RUN_DOMAIN = TableSpec(
    name="gov_run_domain", korean="실행 도메인 원장", product="PRD-VAL",
    grain="실행 x 도메인 1건당 1행",
    columns=(
        C("run_id", "string", "실행 식별자", nullable=False),
        C("domain", "string", "도메인", nullable=False),
        C("domain_label", "text", "도메인 명칭", nullable=False),
        C("n_tables", "int", "원장 수", nullable=False, unit="count", min_value=0),
        C("n_rows", "int", "행수", nullable=False, unit="count", min_value=0),
        C("domain_fingerprint", "text", "도메인 지문(SHA-256 앞 16자)",
          nullable=False),
        C("status", "string", "산출 여부", nullable=False, allowed=DOMAIN_STATUSES),
    ),
    primary_key=("run_id", "domain"),
    foreign_keys=(FK(("run_id",), "gov_unified_run", ("run_id",)),),
)

SPECS: tuple[TableSpec, ...] = (UNIFIED_RUN, RUN_DOMAIN)


# 선언 도메인과 원장 접두어. 이 표가 곧 "무엇을 관통해야 하는가"의 정의다.
# 접두어가 길수록 먼저 맞아야 하므로 판정에서 길이 내림차순으로 본다.
_DOMAINS = (
    ("RDM", "리스크데이터", ("rdm_", "dat_")),
    ("CRE", "신용리스크", ("crm_", "ecl_")),
    ("CAP", "자본적정성", ("rwa_", "cap_", "lev_")),
    # ccr_(증거금·담보)와 int_(시장데이터 피드)도 시장·평가 도메인에 속한다.
    ("MKT", "시장·평가", ("mkt_", "ccr_", "int_")),
    ("OPR", "운영리스크", ("opr_",)),
    ("ALM", "자산부채·유동성", ("alm_", "liq_")),
    ("STR", "위기상황분석", ("st_",)),
    ("VAL", "검증·거버넌스", ("val_", "gov_", "chg_", "aig_", "agent_", "ui_")),
    ("REG", "감독보고", ("form_", "fss_", "pru_", "reg_")),
)

_PREFIX_TO_DOMAIN = tuple(sorted(
    ((prefix, code) for code, _label, prefixes in _DOMAINS for prefix in prefixes),
    key=lambda x: -len(x[0])))


def domain_of(table_name: str) -> str | None:
    for prefix, code in _PREFIX_TO_DOMAIN:
        if table_name.startswith(prefix):
            return code
    return None


def _fingerprint(pairs) -> str:
    """(원장명, 행수, 컬럼수) 목록의 지문. 정렬해 순회 순서를 제거한다."""
    h = hashlib.sha256()
    for name, n_rows, n_cols in sorted(pairs):
        h.update(f"{name}\x1f{n_rows}\x1f{n_cols}\x1e".encode("utf-8"))
    return h.hexdigest()[:16]


def check_run_id_consistency(tables: dict[str, pd.DataFrame], run_id: str
                             ) -> list[str]:
    """원장의 run_id 컬럼에 다른 실행 식별자가 섞였는지 본다.

    섞여 있으면 그 원장은 이 실행의 산물이 아니거나 이전 실행분이 남은 것이다.
    """
    problems = []
    for name in sorted(tables):
        df = tables[name]
        if not isinstance(df, pd.DataFrame) or "run_id" not in df.columns:
            continue
        others = sorted(set(df["run_id"].dropna().astype(str)) - {run_id})
        if others:
            problems.append(f"{name}: 다른 run_id 혼입 {others[:3]}")
    return problems


def build_unified_run(tables: dict[str, pd.DataFrame], *, run_id: str,
                      asof: str, seed: int, code_revision: str
                      ) -> tuple[dict[str, pd.DataFrame], list[str]]:
    """통합 실행 원장 2장을 만든다. (원장, 문제 목록)을 돌려준다.

    문제 목록에는 미산출 도메인과 run_id 혼입이 들어간다. 비어 있어야 이
    실행 하나로 전사 수치를 설명할 수 있다.
    """
    per_domain: dict[str, list[tuple[str, int, int]]] = {c: [] for c, _l, _p in _DOMAINS}
    unmapped: list[str] = []
    for name in sorted(tables):
        df = tables[name]
        if not isinstance(df, pd.DataFrame):
            continue
        code = domain_of(name)
        if code is None:
            unmapped.append(name)
            continue
        per_domain[code].append((name, int(len(df)), int(df.shape[1])))

    rows = []
    for code, label, _prefixes in _DOMAINS:
        items = per_domain[code]
        rows.append({
            "run_id": run_id, "domain": code, "domain_label": label,
            "n_tables": len(items),
            "n_rows": sum(n for _n, n, _c in items),
            "domain_fingerprint": _fingerprint(items),
            "status": "산출" if items else "미산출",
        })
    domain_frame = pd.DataFrame(rows, columns=[c.name for c in RUN_DOMAIN.columns])

    problems = [f"도메인 미산출: {r['domain']} ({r['domain_label']})"
                for r in rows if r["status"] == "미산출"]
    problems += check_run_id_consistency(tables, run_id)
    if unmapped:
        problems.append(f"도메인 미매핑 원장 {len(unmapped)}장: {unmapped[:5]}")

    all_items = [it for items in per_domain.values() for it in items]
    run_frame = pd.DataFrame([{
        "run_id": run_id, "asof": asof, "seed": int(seed),
        "code_revision": code_revision,
        "n_domains_declared": len(_DOMAINS),
        "n_domains_built": sum(1 for r in rows if r["status"] == "산출"),
        "n_tables": len(all_items),
        "n_rows": sum(n for _n, n, _c in all_items),
        "run_fingerprint": _fingerprint(all_items),
        "is_complete": all(r["status"] == "산출" for r in rows) and not problems,
    }], columns=[c.name for c in UNIFIED_RUN.columns])

    return {"gov_unified_run": run_frame,
            "gov_run_domain": domain_frame}, problems
