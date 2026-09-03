"""차세대 UI 의 payload 확장 (설계 사양 3장 레지스트리, 6장 거버넌스, A10, A11, A22, A23).

`app._payload` 가 싣지 않는 x_ 키를 만든다. 값은 전부 `Studio.tables`,
`Studio.result`, `Studio.iv_request`, `Studio.iv_gate`, `independent.RECALC_SCOPE`,
`independent.dispatched`, 선택 인자인 추이 원장 경로에서 온다. 수치 리터럴도
벽시계도 없다. 게이트는 `Studio.iv_gate` 에서 읽기만 하고 다시 판정하지 않는다.

화면 레지스트리(`registry/groups.json`, `registry/<slug>.json`)는 데이터다.
`load_registry()` 가 읽고 검증해 `SCREEN_REGISTRY` 로 내놓는다. 검증에 실패하면
`RegistryError`(ValueError 이자 ImportError)다. 레지스트리가 깨진 채로 화면이
그려지는 일은 없다.
"""

from __future__ import annotations

import json
import math
import os
import re
from pathlib import Path

import pandas as pd

from risk_lib import data_gen_intl as _intl
from risk_lib.datamodel import catalog as cat
from risk_lib.ui_studio import app as _app
from risk_lib.validation import independent

# 테스트가 임시 사본을 가리킬 때만 쓰는 우회. 기본은 이 패키지의 registry/ 와
# static/screens/ 다.
NEXT_ROOT = Path(os.environ.get("RYNTA_NEXT_ROOT") or Path(__file__).parent)

# 카탈로그 밖이지만 화면이 이름을 부를 수 있는 프레임: 기관 축 원장 5장,
# 한도엔진 산출 프레임, 업무요건 추적.
NON_CATALOG_TABLES = frozenset(_app._INST_TABLES) | {"limits_full", "req_trace"}

# sec11.md 의 기존 nav 리프 수. 흡수 라벨이 이 수와 다르면 화면이 사라졌거나
# 두 번 흡수된 것이다.
LEGACY_LABEL_COUNT = 83

_ID_RE = re.compile(r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$")


class RegistryError(ValueError, ImportError):
    """레지스트리 검증 실패. 이 모듈을 쓸 수 없는 상태이므로 ImportError 이기도 하다."""


# ---------------------------------------------------------------- 상수

# 도메인 -> 역할. 어느 원장에도 도메인·역할 조인 컬럼이 없어 UI 가 가정한다.
# 화면은 이 값을 '소관 (UI 가정)' 으로만 적는다 (A23).
DOMAIN_ROLE_MAP = {"RDM": "R-DAT", "CRE": "R-CRD", "MKT": "R-MKT", "ALM": "R-ALM",
                   "OPR": "R-OPR", "VAL": "R-VAL", "CAP": "R-CRO", "STR": "R-CRO",
                   "REG": "R-CRO"}
OWNERSHIP_SOURCE = "ui_constant DOMAIN_ROLE_MAP, no ledger column"
# 레지스트리 products 코드 -> gov_run_domain 도메인. 도메인 브라우저 화면의
# 소관을 풀 때만 쓴다. products 가 빈 화면은 소관 미확인이다.
PRODUCT_DOMAIN_MAP = {"PRD-RDM": "RDM", "PRD-CRM": "CRE", "PRD-RWA": "CRE",
                      "PRD-ECL": "CRE", "PRD-MKT": "MKT", "PRD-OPR": "OPR",
                      "PRD-ALM": "ALM"}
# 보류 사유 종류 -> gov_alert_policy.alert_type. 정책 원장에 행이 있는 종류만.
HOLD_ALERT_MAP = {"self_fail": "자체검증 실패"}
HOLD_PREFIXES = (("3선 게이트 미확인", "gate_unknown"), ("3선 게이트", "gate"),
                 ("자체검증 FAIL", "self_fail"), ("규제 미달", "reg_shortfall"),
                 ("서식검증 실패", "form_check"))
# LCR 원장의 구분 표기 통일. alm_lcr_item 은 영문, alm_lcr_flow 는 한글이다.
SECTION_ALIASES = {"HQLA": "HQLA", "OUTFLOW": "outflow", "INFLOW": "inflow",
                   "유출": "outflow", "유입": "inflow"}
HQLA_LEVELS = ("level2a", "level2b", "level1")     # 접두 일치 순서 (2a 가 1 보다 먼저)
CONDITIONAL_TEXT = ("conditional approval record required: no catalog ledger "
                    "stores the ConditionalApproval fields; the studio does not "
                    "read file records")
TONES = ("good", "warn", "bad", "blocked", "not-run", "synthetic", "neutral")
GLYPHS = {"good": "●", "warn": "◆", "bad": "✕", "blocked": "⊘",
          "not-run": "○", "synthetic": "▧", "explanatory": "≈"}
CLOSE_EVIDENCE_KIND = {"CL-10": "게이트형", "CL-11": "승인형", "CL-12": "제출형"}
EXCEPTION_RANK = {"중대": 0, "경미": 1}
CAPITAL_TARGETS = ("cet1_ratio", "total_ratio", "leverage_ratio",
                   "stress_trough_cet1")
TIER_LABEL = {"CET1": "CET1", "AT1": "Tier1 (누적)", "T2": "Total (누적)"}

# 상태 어휘 -> 톤 (설계 사양 6장). 화면은 이 표만 본다 (NG.tone(source, value)).
SEVERITY_MAP: dict[str, dict[str, str]] = {
    "val_check.status": {"PASS": "good", "WARN": "warn", "FAIL": "bad",
                         "WARN+blocks_approval": "bad", "_not_run": "not-run",
                         "is_identity": "neutral"},
    "independent.status": {"적합": "good", "조건부": "warn", "응답대기": "blocked",
                           "요청됨": "blocked", "부적합": "bad",
                           "3선 게이트 미확인": "blocked"},
    "gov_approval.decision": {"승인": "good", "반려": "bad", "대기": "blocked"},
    "hold.reason_kind": {"gate": "blocked", "gate_unknown": "blocked",
                         "self_fail": "bad", "reg_shortfall": "bad", "form_check": "bad"},
    "reg_submission.status": {"submitted": "good", "approved": "good",
                              "reviewed": "warn", "draft": "warn"},
    "kri.grade": {"GREEN": "good", "WATCH": "warn", "AMBER": "warn", "RED": "bad"},
    "limit.severity": {"OK": "good", "WARN": "warn", "BREACH": "bad", "CRITICAL": "bad"},
    "exception.severity": {"경미": "warn", "중대": "bad"},
    "exception.status": {"종결": "good", "완료차단": "blocked", "접수": "warn", "조치중": "warn"},
    "close_gate.decision": {"진행가능": "good", "차단": "blocked", "순서위반": "bad"},
    "close_task.status": {"완료": "good", "미완료": "blocked"},
    "evidence_node.status": {"완결": "good", "검토": "warn", "누락": "bad"},
    "agent.gate": {"통과": "good", "검토": "warn", "대기": "blocked", "차단": "bad"},
    "change_gate.decision": {"배포가능": "good", "배포불가": "blocked"},
    "recalc.state": {"일치": "good", "불일치": "bad", "미보고": "not-run",
                     "이전 요청 응답": "blocked", "범위밖": "neutral"},
    "data_origin": {_intl.SYNTHETIC_ORIGIN: "synthetic"},
}

# 수치 계보: figure_id -> (원장, pk, 컬럼, 지키는 검사, 3선 재계산 대상, 화면).
# pk 값 None 은 실행 기준일이다. 라벨은 val_audit_ledger 의 label, 없으면
# RECALC_SCOPE 의 korean, 그것도 없으면 _FIGURE_LABELS 에서 온다.
_A = {"asof": None}
_FIGURES: dict[str, tuple] = {
    "rwa.final_total": ("rwa_output_floor", _A, "floored_rwa",
        ("rwa_components_reconcile", "output_floor_applied", "rwa_matches_bis_input"),
        "rwa_final_total", "credit-rwa"),
    "rwa_fund": ("rwa_fund_result", _A, "adopted_rwa", ("xd_rwa_components_sum",),
        "rwa_fund", "funds"),
    "rwa_securitisation": ("rwa_sec_result", _A, "adopted_rwa",
        ("xd_rwa_components_sum",), "rwa_securitisation", "securitisation"),
    "bis.cet1": ("cap_stack", {**_A, "tier": "CET1"}, "ratio",
        ("bis_cet1_ratio_plausible", "bis_buffer_requirement"), "cet1_ratio",
        "capital-verdict"),
    "bis.cet1_surplus": ("cap_stack", {**_A, "tier": "CET1"}, "surplus",
        ("bis_buffer_requirement",), None, "capital-verdict"),
    "bis.tier1": ("cap_stack", {**_A, "tier": "AT1"}, "ratio",
        ("bis_tier1_ratio_plausible",), None, "capital-verdict"),
    "bis.total": ("cap_stack", {**_A, "tier": "T2"}, "ratio",
        ("bis_total_ratio_plausible", "bis_buffer_requirement"), "total_ratio",
        "capital-verdict"),
    "leverage": ("val_audit_ledger", {"figure_id": "leverage"}, "value",
        ("leverage_min_3pct",), "leverage_ratio", "capital-verdict"),
    "ecl.ttc_total": ("ecl_result", _A, "ecl", ("ecl_nonneg",
        "ecl_stage_coverage_monotone"), "ecl_total", "ecl"),
    "ecl.pit_weighted": ("val_audit_ledger", {"figure_id": "ecl.pit_weighted"}, "value",
        ("ecl_ttc_pit_gap", "macro_weighted_in_range"), "ecl_weighted_total", "ecl"),
    "alm.lcr": ("alm_result", {**_A, "metric": "LCR"}, "value", ("lcr_min_100pct",
        "lcr_inflow_cap"), "lcr", "liquidity"),
    "alm.nsfr": ("alm_result", {**_A, "metric": "NSFR"}, "value", ("nsfr_min_100pct",),
        "nsfr", "liquidity"),
    "alm.irrbb_worst_pct_tier1": ("alm_irrbb_result", _A, "delta_eve_to_tier1",
        ("irrbb_outlier_basis_tier1_15pct", "alm_delta_eve_independent_recalc",
        "alm_irrbb_engine_single_source"), "irrbb_worst_pct_tier1", "irrbb"),
    "irrbb_delta_nii_parallel": ("alm_nii_result", _A, "delta_nii",
        ("irrbb_headline_not_repealed",), "irrbb_delta_nii_parallel", "irrbb"),
    "survival_days": ("alm_survival_path", {**_A, "scenario": "기관고유"}, "day", (),
        "survival_days", "survival"),
    "stress.trough_cet1": ("st_capital_path", {"scenario": "severely_adverse"},
        "cet1_ratio", ("stress_trough_meets_requirement",
        "stress_path_trough_ordering"), "stress_trough_cet1", "stress"),
    "reverse_stress.severity": ("val_audit_ledger", {"figure_id":
        "reverse_stress.severity"}, "value", ("reverse_stress_solved",),
        "reverse_critical_severity", "reverse-stress"),
    "reserve_shortfall": ("rdm_asset_quality", _A, "reserve_shortfall",
        ("cross_form_대손준비금 소요액",), "reserve_shortfall", "ecl"),
    "kr_irrbb_table6_max_delta_eve": ("disc_irrbb_table6", {**_A, "col_code":
        "당기_ΔEVE"}, "value", ("kr_irrbb_national_ledgers_present",),
        "kr_irrbb_table6_max_delta_eve", "kr-irrbb"),
    "kr_irrbb_table6_max_delta_nii": ("disc_irrbb_table6", {**_A, "col_code":
        "당기_ΔNII"}, "value", ("kr_irrbb_national_ledgers_present",),
        "kr_irrbb_table6_max_delta_nii", "kr-irrbb"),
    "lgd_backtest_bias": ("crm_lgd_backtest", _A, "bias",
        ("lgd_ccf_backtest_censoring_reported",), "lgd_backtest_bias",
        "lgd-ead-backtest"),
    "lgd_backtest_n_censored": ("crm_lgd_backtest", _A, "n_censored",
        ("lgd_ccf_backtest_censoring_reported",), "lgd_backtest_n_censored",
        "lgd-ead-backtest"),
    "ccf_realised_mean": ("crm_ccf_backtest", _A, "ccf_realized_mean",
        ("lgd_ccf_backtest_censoring_reported",), "ccf_realised_mean", "ccf-estimate"),
    "val_check.summary": ("val_check", _A, "status", (), None, "validation"),
    "reg_form_check.summary": ("reg_form_check", {}, "status", (), None, "reg-forms"),
    "raf.worst": ("val_audit_ledger", {"figure_id": "raf.worst"}, "value", (), None,
        "exec-report"),
}
_FIGURE_LABELS = {"bis.cet1_surplus": "보통주자본 여유", "bis.tier1": "기본자본비율 (누적)",
                  "val_check.summary": "자체검증 집계",
                  "reg_form_check.summary": "업무보고서 대사 집계"}
FIGURE_MAP: dict[str, dict] = {
    fid: dict(table=table, pk=pk, column=column, checks=list(checks),
              recalc=recalc, screen=screen)
    for fid, (table, pk, column, checks, recalc, screen) in _FIGURES.items()}
# kpis[0..5] 의 계보 (app._kpis 순서) 와 종합보고서가 읽는 executive.facts 키의
# 닫힌 목록 (A11).
KPI_FIGURES = ("bis.cet1", "stress.trough_cet1", "ecl.ttc_total", "alm.lcr",
               "val_check.summary", "reg_form_check.summary")
FACTS_MAP = {"cet1": "bis.cet1", "cet1_surplus_pp": "bis.cet1_surplus",
             "sev": "stress.trough_cet1", "rev_severity": "reverse_stress.severity",
             "lcr": "alm.lcr", "nsfr": "alm.nsfr", "raf_red": "raf.worst",
             "raf_amber": "raf.worst"}


def _check_figure_map() -> None:
    """RECALC_SCOPE 의 모든 대상이 계보 하나를 갖고, 원장은 카탈로그 안이어야 한다."""
    targets = {f["recalc"] for f in FIGURE_MAP.values()}
    missing = [k for k, _, _ in independent.RECALC_SCOPE if k not in targets]
    names = {sp.name for sp in cat.ALL_TABLES}
    bad = sorted(f["table"] for f in FIGURE_MAP.values() if f["table"] not in names)
    if missing or bad:
        raise ValueError(f"FIGURE_MAP: 재계산 대상 계보 없음 {missing}; "
                         f"카탈로그 밖 테이블 {bad}")


_check_figure_map()


# ---------------------------------------------------------------- 레지스트리

def load_registry(root: str | Path | None = None) -> list[dict]:
    """registry/groups.json 과 registry/<slug>.json 을 읽어 검증한다 (A22)."""
    root = Path(root) if root is not None else NEXT_ROOT
    read = lambda name: json.loads((root / "registry" / name).read_text(encoding="utf-8"))
    groups = sorted(read("groups.json")["groups"], key=lambda g: int(g["order"]))
    entries: list[dict] = []
    for g in groups:
        for e in read(f"{g['slug']}.json"):
            entry = {**e, "group": g["label_ko"], "group_en": g["label_en"],
                     "slug": g["slug"], "module": g["module"]}
            entry["ledgers"] = list(entry.get("tables", []))
            entries.append(entry)
    _validate_registry(groups, entries, root)
    return entries


def _validate_registry(groups: list[dict], entries: list[dict], root: Path) -> None:
    errors: list[str] = []
    slugs = [g["slug"] for g in groups]
    if len(set(slugs)) != len(slugs):
        errors.append(f"groups.json slug 중복: {slugs}")
    errors += [f"모듈 파일 없음: {g['module']}" for g in groups
               if not (root / "static" / "screens" / Path(g["module"]).name).exists()]
    ids = [e["id"] for e in entries]
    errors += [f"id 중복: {sorted({i for i in ids if ids.count(i) > 1})}"] * (
        len(set(ids)) != len(ids))
    errors += [f"id 가 ascii kebab-case 가 아니다: {i!r}" for i in ids if not _ID_RE.match(i)]
    legacy = [lab for e in entries for lab in e.get("legacy", [])]
    dup = sorted({lab for lab in legacy if legacy.count(lab) > 1})
    if dup:
        errors.append(f"기존 라벨 중복 흡수: {dup}")
    if len(legacy) != LEGACY_LABEL_COUNT:
        errors.append(f"기존 라벨 {len(legacy)}개 (기대 {LEGACY_LABEL_COUNT})")
    names = {sp.name for sp in cat.ALL_TABLES}
    products = {sp.product for sp in cat.ALL_TABLES}
    union: set[str] = set()
    for e in entries:
        errors += [f"{e['id']}: {k} 없음" for k in ("products", "domains", "min_svg")
                   if k not in e]
        if not isinstance(e.get("min_svg", 0), int) or e.get("min_svg", 0) < 0:
            errors.append(f"{e['id']}: min_svg 가 0 이상 정수가 아니다")
        for name in e.get("tables", []):
            if name in names:
                union.add(name)
            elif name not in NON_CATALOG_TABLES:
                errors.append(f"{e['id']}: 알 수 없는 테이블 {name}")
        for p in e.get("products", []):
            if p not in products:
                errors.append(f"{e['id']}: 알 수 없는 product {p}")
            union.update(sp.name for sp in cat.by_product(p))
    if len(union) != len(cat.ALL_TABLES):
        errors.append(f"카탈로그 합집합 {len(union)} != {len(cat.ALL_TABLES)}; "
                      f"빠진 테이블 {sorted(names - union)}")
    if errors:
        raise RegistryError("화면 레지스트리 검증 실패:\n  " + "\n  ".join(errors))


def _screen_tables(entry: dict) -> list[str]:
    """레지스트리 tables 에 products 확장(cat.by_product)을 더해 이름순으로."""
    names = set(entry.get("tables", []))
    for p in entry.get("products", []):
        names.update(sp.name for sp in cat.by_product(p))
    return sorted(names)


def legacy_labels(registry: list[dict] | None = None) -> list[str]:
    reg = SCREEN_REGISTRY if registry is None else registry
    return [lab for e in reg for lab in e.get("legacy", [])]


def nav_tree(registry: list[dict] | None = None) -> list[dict]:
    """그룹 -> (화면 | 하위그룹) 트리. 하위그룹 이름과 같은 제목의 leaf_parent
    화면이 있으면 그 화면이 하위그룹의 머리다."""
    reg = SCREEN_REGISTRY if registry is None else registry
    groups: list[dict] = []
    for e in reg:
        if not groups or groups[-1]["slug"] != e["slug"]:
            groups.append({"slug": e["slug"], "label_ko": e["group"],
                           "label_en": e["group_en"], "module": e["module"],
                           "items": []})
        items, sub = groups[-1]["items"], e.get("sub")
        if sub is None:
            items.append({"id": e["id"]})
            continue
        node = next((n for n in items if n.get("sub") == sub), None)
        if node is None:
            head = next((x["id"] for x in reg if x["slug"] == e["slug"]
                         and x.get("leaf_parent") and x["title_ko"] == sub), None)
            node = {"sub": sub, "leaf_parent": head, "items": []}
            items.append(node)
        node["items"].append({"id": e["id"]})
    return groups


SCREEN_REGISTRY: list[dict] = load_registry()


# ---------------------------------------------------------------- 공통

_c = _app._cell


def _records(df: pd.DataFrame, cols: list[str] | None = None) -> list[dict]:
    cols = cols or [str(c) for c in df.columns]
    return [{c: _c(v) for c, v in zip(cols, row)}
            for row in df[cols].itertuples(index=False)]


def _counts(series: pd.Series, keys: tuple[str, ...]) -> dict[str, int]:
    vc = series.astype(str).value_counts()
    return {k: int(vc.get(k, 0)) for k in keys}


def _group_n(df: pd.DataFrame, col: str) -> list[dict]:
    return [{col: _c(k), "n": int(v)} for k, v in df.groupby(col, sort=True).size().items()]


def _flag(v) -> bool:
    return bool(v) if not pd.isna(v) else False


def _first(df: pd.DataFrame | None) -> pd.Series | None:
    return df.iloc[0] if isinstance(df, pd.DataFrame) and len(df) else None


_SCOPE = {k for k, _, _ in independent.RECALC_SCOPE}


# ---------------------------------------------------------------- x_gate

def _self_tally(vc: pd.DataFrame) -> dict:
    """A10: is_identity 먼저, 다음 _not_run, 다음 status (PASS/WARN/FAIL 만)."""
    n = {"pass": 0, "warn": 0, "fail": 0, "not_run": 0, "identity_excluded": 0}
    blocks, blocking = 0, []
    for i, r in vc.iterrows():
        name, status = str(r["check_name"]), str(r["status"])
        if _flag(r["is_identity"]):
            n["identity_excluded"] += 1
            continue
        blocks += _flag(r["blocks_approval"])
        if name.endswith("_not_run"):
            n["not_run"] += 1
        elif status in ("PASS", "WARN", "FAIL"):
            n[status.lower()] += 1
        else:
            raise ValueError(f"val_check row {i} ({name}): status {status!r} 는 "
                             "PASS / WARN / FAIL 중 하나가 아니다")
        if _flag(r["blocks_approval"]) or status == "FAIL":
            blocking.append({"check_name": name, "status": status,
                             "detail": _c(r["detail"]), "domain": _c(r["domain"])})
    tone = "bad" if n["fail"] or blocks else "warn" if n["warn"] else "good"
    return {**n, "blocks": int(blocks), "total": int(len(vc)),
            "blocking_checks": blocking, "tone": tone}


def _gate_kind(gate) -> str:
    if gate is None:
        return "unknown"
    if gate.status != "부적합":
        return {"적합": "approved", "조건부": "conditional"}.get(gate.status, "pending")
    resp, req = gate.response, gate.request
    foreign = (resp is None or resp.run_id != req.run_id
               or resp.request_id != req.request_id)
    return "procedural" if foreign else "substantive"


def _independent(studio, iv_dir) -> dict:
    row, gate = _first(studio.tables.get("val_independent_request")), studio.iv_gate
    out = {"ledger_present": row is not None}
    for col in ("status", "reason", "request_id", "run_id", "asof", "requested_to",
                "branch", "headline_digest"):
        out[col] = _c(row[col]) if row is not None else None
    for col in ("n_recalc_targets", "n_self_fail", "n_self_warn"):
        out[col] = int(row[col]) if row is not None else None
    if row is None and gate is not None:
        out["status"], out["reason"] = gate.status, gate.reason
    directory = independent.DEFAULT_DIR if iv_dir is None else iv_dir
    out["dispatched"] = (independent.dispatched(studio.iv_request, directory=directory)
                         if studio.iv_request is not None else None)
    out["dispatch_dir"] = Path(directory).as_posix()
    resp = gate.response if gate is not None else None
    out["response"] = None if resp is None else {
        k: getattr(resp, k) for k in ("request_id", "run_id", "verdict",
                                      "validated_by", "validated_at")}
    out["kind"] = _gate_kind(gate)
    out["tone"] = {"approved": "good", "conditional": "warn", "procedural": "bad",
                   "substantive": "bad"}.get(out["kind"], "blocked")
    return out


def _recalc(studio, indep: dict) -> dict:
    tgt = studio.tables.get("val_independent_target")
    resp_id = indep["response"]["request_id"] if indep["response"] else None
    rows, counts = [], {"일치": 0, "불일치": 0, "미보고": 0, "stale": 0}
    for _, r in (tgt.iterrows() if isinstance(tgt, pd.DataFrame) else ()):
        recomputed = _c(r["recomputed"])
        if recomputed is None:
            state = "미보고"
        elif resp_id != str(r["request_id"]):
            state = "이전 요청 응답"
        else:
            state = "일치" if _flag(r["matched"]) else "불일치"
        counts["stale" if state == "이전 요청 응답" else state] += 1
        rows.append({"target": str(r["target"]), "korean": _c(r["korean"]),
                     "reported": _c(r["reported"]), "recomputed": recomputed,
                     "matched": _c(r["matched"]), "state": state,
                     "in_scope": str(r["target"]) in _SCOPE,
                     "citation": _c(r["citation"])})
    return {"rows": rows, "counts": counts, "response_request_id": resp_id}


def _hold_kind(reason: str) -> str:
    return next((kind for prefix, kind in HOLD_PREFIXES if reason.startswith(prefix)),
                "other")


def _approvals(ga: pd.DataFrame) -> dict:
    holds: dict[tuple[str, str], dict] = {}
    for _, r in ga.iterrows():
        ref = str(r["evidence_ref"])
        if "보류: " not in ref:
            continue
        for reason in filter(None, map(str.strip, ref.split("보류: ", 1)[1].split(" / "))):
            h = holds.setdefault((_hold_kind(reason), reason), {
                "reason_kind": _hold_kind(reason), "reason_text": reason, "n": 0,
                "subject_types": set()})
            h["n"] += 1
            h["subject_types"].add(str(r["subject_type"]))
    return {
        **_counts(ga["decision"], ("대기", "승인", "반려")), "total": int(len(ga)),
        "holds": [{**h, "subject_types": sorted(h["subject_types"])}
                  for _, h in sorted(holds.items())],
        # 보류 사유의 가짓수. 화면이 holds 를 세면 브라우저가 총계를 만드는
        # 셈이라 A12 가 막는다. 세는 일은 여기서 한 번만 한다.
        "n_hold_kinds": int(len(holds)),
        "segregation_violations": int((~ga["segregation_ok"].astype(bool)).sum()),
        "by_subject_type": {str(k): int(v) for k, v in sorted(
            ga["subject_type"].astype(str).value_counts().items())},
    }


def _submission(rs: pd.DataFrame, ga: pd.DataFrame) -> dict:
    forms = ga[ga["subject_type"] == "업무보고서 서식"]
    by_form = []
    for _, r in rs.iterrows():
        hit = _first(forms[forms["subject_id"].astype(str) == str(r["form_id"])])
        by_form.append({
            **{c: _c(r[c]) for c in ("form_id", "status", "n_failed_checks", "digest",
                                     "prepared_by", "reviewed_by", "approved_by")},
            "decision": _c(hit["decision"]) if hit is not None else None,
            "segregation_ok": _c(hit["segregation_ok"]) if hit is not None else None})
    return {**_counts(rs["status"], ("draft", "reviewed", "approved", "submitted")),
            "total": int(len(rs)), "by_form": by_form}


def _x_gate(studio, iv_dir) -> dict:
    t = studio.tables
    self_ = _self_tally(t["val_check"])
    indep = _independent(studio, iv_dir)
    status, kind = indep["status"], indep["kind"]
    if status == "부적합":
        tone = "bad"
    elif (status in ("응답대기", "요청됨") or not indep["ledger_present"]
          or kind == "unknown"):
        tone = "blocked"
    elif status == "조건부":
        tone = "warn"
    elif status == "적합" and self_["fail"] == 0 and self_["blocks"] == 0:
        tone = "good"
    else:
        tone = "bad"
    if not indep["ledger_present"] or kind == "unknown":
        status = "3선 게이트 미확인"
    return {
        "self": self_, "independent": indep, "recalc": _recalc(studio, indep),
        "approvals": _approvals(t["gov_approval"]),
        "submission": _submission(t["reg_submission"], t["gov_approval"]),
        "conditional": {"required": status == "조건부", "ledger_record": None,
                        "file_record_read": False, "text": CONDITIONAL_TEXT},
        "overall": {"status": status, "tone": tone, "blocks_approval": tone != "good"},
    }


# ---------------------------------------------------------------- x_screen_gate · x_screens

def _x_screen_gate(studio, gate: dict) -> dict:
    vc = studio.tables["val_check"]
    cols = ["check_name", "status", "blocks_approval", "is_identity", "domain", "detail"]
    out = {"checks": {}, "targets": {}, "scope": {}}
    for e in SCREEN_REGISTRY:
        hit = vc[vc["check_name"].isin(e["checks"])
                 | vc["domain"].astype(str).isin(e["domains"])]
        out["checks"][e["id"]] = _records(hit, cols)
        out["targets"][e["id"]] = [r for r in gate["recalc"]["rows"]
                                   if r["target"] in e["recalc"]]
        figs = set(e["recalc"]) | set(e.get("headline_figures", []))
        out["scope"][e["id"]] = {"in_scope": len(figs & _SCOPE),
                                 "out_of_scope": len(figs - _SCOPE)}
    return out


def _x_screens(studio, ownership: dict) -> dict:
    t = studio.tables
    # D.data 에 실리는 행수: app._payload 와 같은 예산 규칙 (ui_view 가 가리키는 표만).
    shown: dict[str, int] = {}
    for tref in t["ui_view"]["table_ref"]:
        if isinstance(tref, str) and tref in t:
            full = (tref in _app.DEMO_TABLES or tref in _app.ALM_FULL_TABLES
                    or tref in _app.NEW_SCREEN_FULL_TABLES)
            shown[tref] = int(min(len(t[tref]), _app.INTERACTIVE_ROWS_DEMO if full
                                  else _app.INTERACTIVE_ROWS))
    spec = {sp.name: sp for sp in cat.ALL_TABLES}
    master = studio.inst_tables.get("inst_master")
    row = (_first(master[master["institution_code"] == studio.institution_code])
           if isinstance(master, pd.DataFrame) else None)
    synthetic = row is not None and _c(row["data_origin"]) == _intl.SYNTHETIC_ORIGIN
    out = {}
    for e in SCREEN_REGISTRY:
        ledgers = []
        for name in _screen_tables(e):
            sp = spec.get(name)
            df = t.get(name, studio.inst_tables.get(name))
            if df is None and name == "limits_full":
                df = studio.result.limits_full
            ledgers.append({
                "table": name, "product": sp.product if sp else None,
                "korean": sp.korean if sp else None, "shown": shown.get(name, 0),
                "total": int(len(df)) if isinstance(df, pd.DataFrame) else 0,
                "pk": list(sp.primary_key) if sp else [],
                "fk": [{"column": ", ".join(fk.columns), "ref_table": fk.ref_table,
                        "ref_column": ", ".join(fk.ref_columns)}
                       for fk in (sp.foreign_keys if sp else ())]})
        domains = sorted({PRODUCT_DOMAIN_MAP[p] for p in e["products"]
                          if p in PRODUCT_DOMAIN_MAP})
        own = ownership["by_domain"].get(domains[0]) if len(domains) == 1 else None
        out[e["id"]] = {
            "ledgers": ledgers, "products": list(e["products"]), "synthetic": synthetic,
            "explanatory": bool(e["explanatory"]), "density": e["density"],
            "min_svg": int(e["min_svg"]),
            "ownership": None if own is None else {
                "domain": domains[0], "role_name": own["role_name"],
                "org_unit": own["org_unit"], "source": OWNERSHIP_SOURCE}}
    return out


# ---------------------------------------------------------------- x_queue · x_close · x_evidence

def _x_queue(studio, gate: dict) -> dict:
    t = studio.tables
    vc = t["val_check"]
    live = vc[~vc["is_identity"].astype(bool)]
    policy = t["gov_alert_policy"]
    holds = []
    for h in gate["approvals"]["holds"]:
        kind = h["reason_kind"]
        hit = (live[live["status"] == "FAIL"] if kind == "self_fail"
               else live[live["blocks_approval"].astype(bool)] if kind == "reg_shortfall"
               else live.iloc[0:0])
        prow = _first(policy[policy["alert_type"] == HOLD_ALERT_MAP.get(kind)])
        holds.append({**h, "checks": _records(hit, ["check_name", "status", "detail",
                                                    "domain", "blocks_approval"]),
                      "unblock": None if prow is None else {
                          c: _c(prow[c]) for c in ("alert_type", "bound_action",
                                                   "owner_role", "sla_days",
                                                   "blocks_submission")}})
    ex = t["gov_exception_action"].copy()
    ex["_rank"] = ex["severity"].astype(str).map(EXCEPTION_RANK).fillna(len(EXCEPTION_RANK))
    ex = ex.sort_values(["_rank", "due_days", "exception_id"], kind="stable")
    by_source = (ex.groupby("source_ledger", sort=True)
                 .agg(n=("exception_id", "size"), owner_role=("owner_role", "first"))
                 .reset_index())
    dq, rc, sc, cm = (t["rdm_dq_result"], t["rdm_reconciliation"],
                      t["rdm_source_contract"], t["rdm_canonical_map"])
    issues = t["gov_run_issue"]
    return {
        "holds": holds,
        "exceptions": {
            "total": int(len(ex)), "by_severity": _group_n(ex, "severity"),
            "by_due": _group_n(ex, "due_days"),
            "by_source": _records(by_source, ["source_ledger", "n", "owner_role"]),
            "rows": _records(ex, ["exception_id", "source_ledger", "source_key",
                                  "severity", "finding", "action", "owner_role",
                                  "status", "due_days"])},
        "dq": {"fail_by_rule": _group_n(dq[dq["severity"].astype(str) == "FAIL"], "rule"),
               "total": int(len(dq))},
        "recon": {"fail": _records(rc[rc["status"].astype(str) == "FAIL"],
                                   ["recon_id", "axis", "status"]), "total": int(len(rc))},
        "contracts": {"not_pass": _records(sc[sc["status"].astype(str) != "PASS"],
                                           ["source_system", "table_name", "status"]),
                      "total": int(len(sc))},
        "canonical": {"unmapped": int((cm["status"].astype(str) == "unmapped").sum()),
                      "total": int(len(cm))},
        "submissions": {k: gate["submission"][k] for k in
                        ("draft", "reviewed", "approved", "submitted", "total")},
        "close_blockers": _records(issues[issues["stage"].astype(str) == "마감"],
                                   ["stage", "seq", "kind", "detail"]),
    }


def _x_close(studio) -> dict:
    t = studio.tables
    gates = t["opr_close_gate"].set_index("task_id")
    rows = []
    for _, r in t["opr_close_task"].iterrows():
        tid = str(r["task_id"])
        g = gates.loc[tid] if tid in gates.index else None
        rows.append({**{c: _c(v) for c, v in r.items()},
                     **{c: _c(g[c]) if g is not None else None
                        for c in ("decision", "blocked_by", "reason")},
                     "evidence_kind": CLOSE_EVIDENCE_KIND.get(tid, "행수형")})
    sub = t["reg_submission"]["status"].astype(str)
    return {"tasks": rows,
            "issues": _records(t["gov_run_issue"], ["stage", "seq", "kind", "detail"]),
            "statements": {"cl12_structural": not bool((sub == "submitted").any()),
                           "conditional_asymmetry": True,
                           "submitted_count": int((sub == "submitted").sum())}}


def _x_evidence(studio, gate: dict) -> dict:
    t, ap = studio.tables, gate["approvals"]
    n6 = {"label": f"4-Eyes 대기 {ap['대기']} · 승인 {ap['승인']} · 반려 {ap['반려']}",
          "status": "검토" if ap["대기"] or ap["반려"] else "완결",
          "대기": ap["대기"], "승인": ap["승인"], "반려": ap["반려"]}
    nodes = _records(t["gov_evidence_node"], ["node_id", "stage", "label", "ref", "status"])
    for n in nodes:
        if n["node_id"] == "N6":
            n["label"], n["status"] = n6["label"], n6["status"]
    return {"nodes": nodes,
            "edges": _records(t["gov_evidence_edge"], ["from_node", "to_node", "relation"]),
            "n6": n6, "complete": sum(1 for n in nodes if n["status"] == "완결"),
            "total": len(nodes)}


# ---------------------------------------------------------------- x_capital · x_limits · x_lcr

def _x_capital(studio, gate: dict, screen_gate: dict) -> dict:
    from risk_lib.capital.bis import BIS_MINIMUMS
    r, t = studio.result, studio.tables
    ss = {k: float(v) for k, v in r.bis.surplus_shortfall.items()}
    # cap_stack 의 amount 는 그 계층에 **새로 더해지는 상품** 금액이고 (AT1
    # 1,400억, T2 2,400억), ratio 는 그 상품까지 **누적한** 자본의 비율이다.
    # 두 열의 성질이 다르므로 한 행에 나란히 두면 "Tier1 (누적) 1,400억" 처럼
    # 읽히는데, 그것은 기본자본이 아니라 AT1 상품 금액이다 (검수 F2 의 재발).
    # 누적 금액을 따로 세고 상품 금액은 이름을 붙여 남긴다.
    tiers, running = [], 0.0
    for _, x in t["cap_stack"].iterrows():
        instrument = float(x["amount"])
        running += instrument
        tiers.append({
            "label": TIER_LABEL.get(str(x["tier"]), str(x["tier"])),
            "source_tier": str(x["tier"]),
            # amount 는 label 과 같은 성질(누적)이다. 상품 금액은 instrument_amount.
            "amount": running,
            "instrument_amount": instrument,
            "instrument": str(x["tier"]),
            **{c: float(x[c]) for c in ("ratio", "required", "surplus")},
            "tone": "good" if float(x["surplus"]) >= 0 else "bad"})
    path = t["st_capital_path"]
    checks = screen_gate["checks"].get("capital-verdict", gate["self"]["blocking_checks"])
    blocking = [{k: c[k] for k in ("check_name", "status", "detail")} for c in checks
                if c["status"] == "FAIL" or c.get("blocks_approval", True)]
    mda = any(x["surplus"] < 0 for x in tiers)
    return {
        "binding_tier": min(ss, key=ss.get), "tiers": tiers,
        "required": {k: float(v) for k, v in r.bis.required.items()},
        "minimums": {k: float(v) for k, v in BIS_MINIMUMS.items()},
        "buffers": {k: float(v) for k, v in (r.meta.get("buffers") or {}).items()},
        "mda_zone": mda,
        "leverage": {"ratio": float(r.leverage.leverage_ratio),
                     "required": float(r.leverage.required),
                     "exposure_measure": float(r.leverage.exposure_measure)},
        "stress_path": _records(path, ["scenario", "quarter", "severity", "cet1_ratio",
                                       "tier1_ratio", "total_ratio", "binding", "passes"]),
        "n_fail_quarters": int((~path["passes"].astype(bool)).sum()),
        "kri_cet1_grade": next((k.grade for k in r.raf.kris if k.name == "CET1 비율"), None),
        "blocking_checks": blocking,
        "targets": [x for x in gate["recalc"]["rows"] if x["target"] in CAPITAL_TARGETS],
        "tone": "bad" if mda or blocking else "good",
    }


def _engine_breaches(limits: pd.DataFrame | None) -> int | None:
    """consistency._check_large_exposure_sources 의 한도엔진 규칙 그대로."""
    if limits is None or limits.empty:
        return None
    return int(len(limits[limits["limit"].astype(str).str.contains("동일차주")
                          & limits["severity"].isin(["BREACH", "CRITICAL"])]))


def _severity_counts(df: pd.DataFrame | None) -> dict:
    if df is None or df.empty:
        return {"total": 0, "breach": 0, "warn": 0, "critical": 0, "ok": 0}
    c = _counts(df["severity"], ("BREACH", "WARN", "CRITICAL", "OK"))
    return {"total": int(len(df)), **{k.lower(): v for k, v in c.items()}}


def _x_limits(studio) -> dict:
    t, r = studio.tables, studio.result
    fw_law, fw_engine = "은행법35조_동일차주", "감독규정26조_기본자본"
    law = next((f for f in _app._lex_dict(studio).get("frameworks", [])
                if f["framework"] == fw_law), None)
    agg = t.get("lex_aggregate")
    eng = _first(agg[agg["framework"] == fw_engine]) if isinstance(agg, pd.DataFrame) else None
    vc = t["val_check"]
    chk = _first(vc[vc["check_name"] == "large_exposure_two_sources"])
    full = _severity_counts(r.limits_full)
    full["dimensions"] = (sorted(r.limits_full["dimension"].astype(str).unique())
                          if full["total"] else [])
    return {
        "two_sources": {
            "state": "unresolved",
            "law": None if law is None else {
                "framework": fw_law, "basis": law["denominator_basis"],
                "n_breach": law["n_breach"], "citation": law["limit_citation"]},
            "engine": {
                "basis": _c(eng["denominator_basis"]) if eng is not None else None,
                "n_breach": _engine_breaches(r.limits),
                "source": ("result.limits rows whose limit label contains 동일차주 "
                           "with severity BREACH or CRITICAL "
                           "(consistency._check_large_exposure_sources rule); "
                           "null rendered 미산출")},
            "check": None if chk is None else {
                "check_name": str(chk["check_name"]), "status": str(chk["status"]),
                "blocks_approval": _flag(chk["blocks_approval"]),
                "detail": _c(chk["detail"])}},
        "populations": {"limits": _severity_counts(r.limits), "limits_full": full},
        "breach_action_ledger": {"name": "lim_breach_action",
                                 "exists": "lim_breach_action" in t,
                                 "fields": ["위반 ID", "원인", "대응책", "담당", "기한", "상태"]},
    }


def _lcr_side(df: pd.DataFrame, caps) -> dict | None:
    from risk_lib.alm.lcr import apply_hqla_caps
    sec = df["section"].astype(str).map(SECTION_ALIASES)
    parts = {k: df[sec == k] for k in ("HQLA", "outflow", "inflow")}
    levels: dict[str, list[float]] = {k: [] for k in HQLA_LEVELS}
    for c, w in parts["HQLA"].groupby("category")["weighted"].sum().items():
        key = re.sub(r"[\s_]", "", str(c)).lower()
        hit = next((k for k in HQLA_LEVELS if key.startswith(k)), None)
        if hit:
            levels[hit].append(float(w))
    if any(p.empty for p in parts.values()) or any(not v for v in levels.values()):
        return None
    hqla = apply_hqla_caps(sum(levels["level1"]), sum(levels["level2a"]),
                           sum(levels["level2b"]), caps)[0]
    outflow = float(parts["outflow"]["weighted"].sum())
    inflow = float(parts["inflow"]["weighted"].sum())
    capped = min(inflow, caps.inflow * outflow)
    if outflow - capped == 0:
        return None
    return {"hqla_raw": float(parts["HQLA"]["weighted"].sum()), "hqla": hqla,
            "outflow": outflow, "inflow": inflow, "inflow_capped": capped,
            "lcr": hqla / (outflow - capped)}


def _x_lcr(studio) -> dict:
    from risk_lib.alm.lcr import resolve_caps
    t = studio.tables
    out = dict.fromkeys(("item", "flow", "result", "caps", "diff_item_result_num",
                         "diff_item_result_den", "diff_flow_result_num",
                         "diff_flow_result_den", "diff_item_flow", "reason"))
    out.update(state="not computable",
               tolerance={"method": "math.isclose", "rel_tol": "default"})
    try:
        caps = resolve_caps(t["alm_lcr_factor"])
    except (KeyError, ValueError) as exc:
        out["reason"] = str(exc)
        return out
    out["caps"] = {"l2b": caps.l2b, "l2": caps.l2, "inflow": caps.inflow,
                   "source": "alm_lcr_factor 한도 via risk_lib.alm.lcr.resolve_caps"}
    item = _lcr_side(t["alm_lcr_item"], caps) if "alm_lcr_item" in t else None
    fl = t.get("alm_lcr_flow")
    flow = (_lcr_side(fl[fl["scenario"].astype(str) == "base"], caps)
            if isinstance(fl, pd.DataFrame) else None)
    ar = t.get("alm_result")
    res = _first(ar[ar["metric"].astype(str) == "LCR"]) if isinstance(ar, pd.DataFrame) else None
    out["item"], out["flow"] = item, None if flow is None else {"scenario": "base", **flow}
    if res is not None:
        out["result"] = {"lcr": float(res["value"]), "numerator": float(res["numerator"]),
                         "denominator": float(res["denominator"])}
    if item is None or flow is None or res is None:
        out["reason"] = "section or LCR result row missing"
        return out
    num, den = out["result"]["numerator"], out["result"]["denominator"]
    out.update(diff_item_result_num=item["hqla"] - num,
               diff_item_result_den=(item["outflow"] - item["inflow_capped"]) - den,
               diff_flow_result_num=flow["hqla"] - num,
               diff_flow_result_den=(flow["outflow"] - flow["inflow_capped"]) - den,
               diff_item_flow=item["lcr"] - flow["lcr"])
    ok = all(math.isclose(a, b) for a, b in (
        (item["hqla"], num), (item["outflow"] - item["inflow_capped"], den),
        (flow["hqla"], num), (flow["outflow"] - flow["inflow_capped"], den)))
    out["state"] = "reconciled" if ok else "not reconciled"
    return out


# ---------------------------------------------------------------- x_trend · x_lineage · x_audit · x_ownership

def _x_trend(studio, ledger_path) -> dict:
    out = {"ledger_path": None if ledger_path is None else str(ledger_path),
           "n_periods": 0, "periods": [], "frame": {"columns": [], "rows": []}, "flags": [],
           "qoq_yoy": {}, "digest_matches_latest": None, "has_gate_history": False,
           "single_period": True}
    if ledger_path is None:
        return out
    from risk_lib.timeseries_ledger import HEADLINE_SPEC, TimeSeriesLedger
    led = TimeSeriesLedger(snapshots=[s for s in TimeSeriesLedger.load(ledger_path)
                                      .snapshots if s.asof <= studio.asof])
    if not led.snapshots:
        return out
    frame = led.to_frame()
    out.update(n_periods=len(led.snapshots), single_period=len(led.snapshots) < 2,
               frame=_app._frame(frame, len(frame)),
               periods=[{"period": s.period, "asof": s.asof, "digest": s.headline_digest,
                         "seed": int(s.seed),
                         "validation_summary": dict(s.validation_summary)}
                        for s in led.snapshots])
    if len(led.snapshots) >= 2:
        flags = led.trend_flags().rename(columns={"trend": "trend_state"})
        out["flags"] = _records(flags, ["metric", "label", "latest", "qoq", "floor",
                                        "direction", "trend_state", "consecutive_breaches"])
    for mid in HEADLINE_SPEC:
        q = led.qoq_yoy(mid).rename(columns={mid: "value"})
        out["qoq_yoy"][mid] = _records(q, ["period", "value", "qoq", "yoy"])
    req = _first(studio.tables.get("val_independent_request"))
    latest = led.snapshots[-1].headline_digest
    if req is not None and latest and str(req["headline_digest"]):
        out["digest_matches_latest"] = str(req["headline_digest"]) == latest
    return out


def _x_lineage(studio, gate: dict) -> dict:
    audit = studio.tables.get("val_audit_ledger")
    scope = {k: ko for k, ko, _ in independent.RECALC_SCOPE}
    state = {r["target"]: r["state"] for r in gate["recalc"]["rows"]}
    figures = {}
    for fid, f in FIGURE_MAP.items():
        arow = (_first(audit[audit["figure_id"].astype(str) == fid])
                if isinstance(audit, pd.DataFrame) else None)
        label = (_c(arow["label"]) if arow is not None
                 else scope.get(f["recalc"], _FIGURE_LABELS.get(fid, fid)))
        figures[fid] = {
            "label": label, "table": f["table"],
            "pk": [{"column": c, "value": studio.asof if v is None else v}
                   for c, v in f["pk"].items()],
            "column": f["column"], "check_names": list(f["checks"]),
            "recalc_target": f["recalc"], "in_scope": f["recalc"] in scope,
            "gate_state": state.get(f["recalc"], "범위밖"),
            "audit": None if arow is None else {
                c: _c(arow[c]) for c in ("code_module", "code_function", "citation")},
            "screen": f["screen"]}
    return {"figures": figures, "kpi_map": list(KPI_FIGURES), "facts_map": dict(FACTS_MAP)}


def _x_audit(studio) -> dict:
    t = studio.tables
    chain = t["gov_audit_chain"].sort_values("seq", kind="stable")
    prev_hash, first_break = None, None
    for _, r in chain.iterrows():
        if prev_hash is not None and str(r["prev_hash"]) != prev_hash:
            first_break = int(r["seq"])
            break
        prev_hash = str(r["record_hash"])
    run = _first(t.get("gov_unified_run"))
    return {"chain_ok": first_break is None, "n_records": int(len(chain)),
            "first_break_seq": first_break,
            "run": None if run is None else {c: _c(v) for c, v in run.items()}}


def _x_ownership(studio) -> dict:
    t = studio.tables
    roles = t["gov_role"].set_index("role_id")
    by_domain, unresolved = {}, []
    for _, d in t["gov_run_domain"].iterrows():
        code, rid = str(d["domain"]), DOMAIN_ROLE_MAP.get(str(d["domain"]))
        if rid is None or rid not in roles.index:
            by_domain[code] = None
            unresolved.append(code)
            continue
        by_domain[code] = {"domain_label": _c(d["domain_label"]), "role_id": rid,
                           "role_name": _c(roles.loc[rid, "role_name"]),
                           "org_unit": _c(roles.loc[rid, "org_unit"]),
                           "source": OWNERSHIP_SOURCE}
    return {"by_domain": by_domain, "unresolved": unresolved,
            "source": OWNERSHIP_SOURCE, "ledger_has_domain_role_join": False}


# ---------------------------------------------------------------- 진입점

def _x_kpi(studio) -> dict:
    """헤드라인 카드 중 금액인 것의 **숫자**. 카드 값은 app._kpis 가 한국어
    단위로 이미 서식한 문자열이라(예: 975억원) 영문 화면에서 그대로 나온다.
    숫자를 함께 실어 화면이 언어에 맞춰 다시 서식하게 한다. 라벨은 닫힌
    여섯 개라 용어집에 있고, sub 문장은 값이 섞인 산문이라 아직 한국어다.
    """
    from risk_lib.ui_studio import app as _app
    numeric: dict[str, dict] = {}
    for i, k in enumerate(_app._kpis(studio)):
        if str(k.get("label", "")).startswith("기대신용손실"):
            numeric[str(i)] = {"kind": "money",
                               "value": float(studio.result.ecl["total"])}
    return {"numeric": numeric,
            "sub_is_korean_prose": True,
            "note": ("app._kpis 가 만든 sub 문장은 값이 섞인 산문이라 "
                     "용어집 대상이 아니다. 영문 화면에서 한국어로 남는다")}


def build_ext(studio, ledger_path=None, iv_dir=None) -> dict:
    """x_ 키 전부. 게이트는 Studio.iv_gate 에서 읽기만 한다."""
    gate = _x_gate(studio, iv_dir)
    screen_gate = _x_screen_gate(studio, gate)
    ownership = _x_ownership(studio)
    return {
        "x_gate": gate, "x_screen_gate": screen_gate,
        "x_screens": _x_screens(studio, ownership),
        "x_queue": _x_queue(studio, gate), "x_close": _x_close(studio),
        "x_evidence": _x_evidence(studio, gate),
        "x_capital": _x_capital(studio, gate, screen_gate),
        "x_limits": _x_limits(studio), "x_lcr": _x_lcr(studio),
        "x_severity": {"tones": list(TONES),
                       "map": [{"source": src, "value": v, "tone": tone}
                               for src, vals in SEVERITY_MAP.items()
                               for v, tone in vals.items()],
                       "glyphs": dict(GLYPHS)},
        "x_trend": _x_trend(studio, ledger_path),
        "x_lineage": _x_lineage(studio, gate), "x_audit": _x_audit(studio),
        "x_ownership": ownership, "x_kpi": _x_kpi(studio),
    }


def strip_base(payload: dict) -> dict:
    """executive.kris[*] 의 spark 와 trend 를 지운다 (Q16: 합성 이력은 싣지 않는다)."""
    for k in (payload.get("executive") or {}).get("kris", []):
        k.pop("spark", None)
        k.pop("trend", None)
    return payload
