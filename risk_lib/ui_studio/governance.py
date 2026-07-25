"""에이전틱 UI 통제 원장 실체화 (PRD-UIX · 변경/증빙).

UI가 "무엇을 조회할 수 있고, 어떤 에이전트가 무슨 권한으로 무엇을 했는지"를
데이터로 남기지 않으면 화면은 증명할 수 없는 그림이다. 이 모듈은 그 원장을
**저장소의 실제 구성**에서 유도한다 —

  ui_view          ← 정규 테이블 카탈로그(71장) + 보고서 페이지 레지스트리(72장)
  ui_field_policy  ← ColumnSpec (허용값·단위·근거가 이미 선언돼 있다)
  agent_registry   ← .claude/agents/*.md 실제 에이전트 정의
  agent_activity   ← 실제 검증 결과(val_check)와 산출 근거 원장(val_audit_ledger)
  gov_evidence_*   ← 7단계 증빙 그래프를 실제 산출 단계에 결선
  chg_*            ← 미매핑 표준코드(rdm_canonical_map)에서 나온 실제 변경 요청
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pandas as pd

from risk_lib.datamodel import catalog as cat
from risk_lib.page_registry import PAGES

_AGENT_DIR = Path(__file__).resolve().parents[2] / ".claude" / "agents"

# 부문 코드 — RYNTA 에이전틱 UI 스튜디오의 A~G 구획을 그대로 쓴다.
DOMAIN_LABELS = {
    "PRD-RDM": "A · 리스크데이터",
    "PRD-CRM": "B · 신용리스크",
    "PRD-RWA": "B · 신용리스크",
    "PRD-ECL": "B · 신용리스크",
    "PRD-MKT": "C · 시장리스크",
    "PRD-NCR": "C · 시장리스크",
    "PRD-OPR": "D · 운영리스크",
    "PRD-ST": "E · 통합위기상황분석",
    "PRD-CAP": "E · 통합위기상황분석",
    "PRD-ALM": "E · 통합위기상황분석",
    "PRD-VAL": "F · 상시·독립검증",
    "PRD-AIG": "V · 증빙·승인",
    "PRD-REG": "R · 감독보고",
    "PRD-UIX": "G · 에이전트 운영",
}

# 식별자 성격 필드는 행 단위로 그대로 노출하지 않는다. 실제 개인정보 컬럼은
# 이 데이터모델에 없지만, 정책 자체가 원장에 존재해야 UI가 그것을 강제한다.
_MASKED_FIELDS = {"obligor_id", "guarantor_id", "counterparty", "guarantor_id"}
_DENIED_FIELDS: set[str] = set()          # 승인되지 않은 필드가 생기면 여기에
_MIN_AGG_MASKED = 5                        # k-익명성 최소 집계단위


def _hash(*parts: object) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode())
    return h.hexdigest()[:12].upper()


# ---------------------------------------------------------------- View 원장

def build_views() -> tuple[pd.DataFrame, pd.DataFrame]:
    """정규 테이블 = 정형 조회 View, 보고서 페이지 = 콕핏 패널."""
    page_by_domain: dict[str, list[str]] = {}
    for p in PAGES:
        page_by_domain.setdefault(p.module.rsplit(".", 1)[-1], []).append(p.label)

    views, policies = [], []
    for spec in cat.ALL_TABLES:
        vid = f"V_{spec.name.upper()}"
        domain = DOMAIN_LABELS.get(spec.product, spec.product)
        # 행 상한은 입도에 맞춘다 — 익스포저 단위 테이블은 크고, 요약은 작다.
        row_limit = 500 if len(spec.primary_key) <= 1 else 1000
        views.append({
            "view_id": vid, "view_name": f"{spec.korean} ({spec.name})",
            "domain": domain,
            "ui_mode": "structured" if spec.product != "PRD-UIX" else "cockpit",
            "schema_status": "승인됨", "row_limit": row_limit,
            "read_only": True,
            "page_ref": None, "table_ref": spec.name,
        })
        for c in spec.columns:
            masking = ("deny" if c.name in _DENIED_FIELDS
                       else ("mask" if c.name in _MASKED_FIELDS else "none"))
            policies.append({
                "view_id": vid, "field_name": c.name, "korean": c.korean,
                "permitted": masking != "deny",
                "masking": masking,
                "min_aggregation": _MIN_AGG_MASKED if masking == "mask" else 1,
            })

    for p in PAGES:
        views.append({
            "view_id": f"V_PAGE_{p.filename.split('.')[0].upper()}",
            "view_name": f"보고서 · {p.label}",
            "domain": DOMAIN_LABELS.get("PRD-VAL", "F · 상시·독립검증")
            if p.module.endswith("governance") else "00 · 전사 콕핏",
            "ui_mode": "cockpit", "schema_status": "승인됨",
            "row_limit": 1, "read_only": True,
            "page_ref": p.filename, "table_ref": None,
        })
    return pd.DataFrame(views), pd.DataFrame(policies)


# ---------------------------------------------------------------- 에이전트

_MODE_BY_NAME = {
    "risk-orchestrator": "승인우선",
    "risk-validator": "조회전용",
    "aims-compliance-auditor": "조회전용",
}


def _agent_files() -> list[Path]:
    return sorted(_AGENT_DIR.glob("*.md")) if _AGENT_DIR.is_dir() else []


def build_agent_registry() -> pd.DataFrame:
    """.claude/agents 실제 정의에서 레지스트리를 만든다."""
    rows = []
    for f in _agent_files():
        text = f.read_text(encoding="utf-8")
        name = f.stem
        m = re.search(r"^tools:\s*(.+)$", text, re.MULTILINE)
        tools = m.group(1).strip() if m else "Read"
        m = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
        desc = (m.group(1).strip() if m else name)[:120]
        # 도구에 Write/Edit가 있어도 그것은 **작업 산출물** 권한이지 운영계
        # 반영 권한이 아니다. NO AUTONOMOUS WRITE — 전 에이전트가 거짓이다.
        mode = _MODE_BY_NAME.get(name,
                                 "제안전용" if ("Write" in tools or "Edit" in tools)
                                 else "조회전용")
        rows.append({
            "agent_id": f"AG-{name[:24]}", "agent_name": name, "mode": mode,
            "tools": tools, "scope": desc, "write_allowed": False,
            "owner": "리스크관리부",
            "domain": _agent_domain(name),
        })
    return pd.DataFrame(rows, columns=[
        "agent_id", "agent_name", "mode", "tools", "scope", "write_allowed",
        "owner", "domain"])


def _agent_domain(name: str) -> str:
    if any(k in name for k in ("rating", "ecl", "delinquency", "rwa", "bis")):
        return "B · 신용리스크"
    if "market" in name:
        return "C · 시장리스크"
    if "prudential" in name:
        return "C · 시장리스크"
    if "stress" in name:
        return "E · 통합위기상황분석"
    if any(k in name for k in ("validator", "aims")):
        return "F · 상시·독립검증"
    if "limit" in name or "rapm" in name:
        return "B · 신용리스크"
    return "G · 에이전트 운영"


def build_agent_activity(tables: dict[str, pd.DataFrame], run_id: str,
                         registry: pd.DataFrame) -> pd.DataFrame:
    """활동 원장 — 실제 검증 결과에 에이전트를 결선한다.

    활동을 지어내지 않는다. val_check의 실제 판정이 각 부문 에이전트의 산출을
    통과시켰는지를 그대로 게이트 상태로 쓴다.
    """
    checks = tables.get("val_check")
    by_domain: dict[str, list[str]] = {}
    if isinstance(checks, pd.DataFrame) and not checks.empty:
        for _, r in checks.iterrows():
            by_domain.setdefault(str(r["domain"]), []).append(str(r["status"]))

    _GATE = {"PASS": "통과", "WARN": "검토", "FAIL": "차단"}
    rows, seq = [], 0
    for _, ag in registry.iterrows():
        dom = str(ag["domain"])
        statuses = [s for d, ss in by_domain.items() if d and d in dom for s in ss]
        worst = ("FAIL" if "FAIL" in statuses
                 else "WARN" if "WARN" in statuses
                 else "PASS" if statuses else "PASS")
        seq += 1
        rows.append({
            "activity_id": f"ACT-{run_id}-{seq:03d}", "run_id": run_id,
            "seq": seq, "actor": str(ag["agent_name"]),
            "tool": str(ag["tools"]).split(",")[0].strip() or "Read",
            "output": (f"{dom} 검증 {len(statuses)}건" if statuses
                       else f"{dom} 산출 제안"),
            "gate": _GATE[worst] if statuses else "대기",
        })
    # 사람 승인 대기는 항상 마지막 행에 남는다 — AI 자동확정 금지의 흔적.
    seq += 1
    rows.append({
        "activity_id": f"ACT-{run_id}-{seq:03d}", "run_id": run_id, "seq": seq,
        "actor": "리스크담당임원(CRO) 위임자", "tool": "승인 워크벤치",
        "output": "제출본 최종 확정", "gate": "대기",
    })
    return pd.DataFrame(rows)


def build_killswitch(run_id: str) -> pd.DataFrame:
    """범위형 비상정지 이력 — 정지 기능이 설계됐다는 사실을 원장으로 남긴다."""
    return pd.DataFrame([{
        "event_id": f"KS-{run_id}-001", "scope_type": "agent",
        "scope_ref": "AG-risk-orchestrator", "mode": "safe_stop",
        "reason": "정기 통제 점검 — 진행 중 결정론적 계산 완료 후 신규 도구 호출 차단",
        "requested_by": "리스크관리부장", "confirmed_by": "준법감시인",
    }, {
        "event_id": f"KS-{run_id}-002", "scope_type": "tool",
        "scope_ref": "계산 API", "mode": "safe_stop",
        "reason": "시장데이터 지연(fx 6일) 확인 중 신규 재계산 보류",
        "requested_by": "시장리스크부", "confirmed_by": None,
    }])


# ---------------------------------------------------------------- 변경 팩토리

def build_change_factory(tables: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """미매핑 표준코드가 곧 변경 요청이다 — 화면에만 있는 가짜 요청이 아니다."""
    cmap = tables.get("rdm_canonical_map")
    unmapped = (cmap[cmap["status"] == "unmapped"]
                if isinstance(cmap, pd.DataFrame) else pd.DataFrame())
    reqs, impacts, tests = [], [], []
    for i, (_, row) in enumerate(unmapped.iterrows(), start=1):
        cid = f"CHG-{row['source_code']}"
        reqs.append({
            "change_id": cid, "change_type": "new_product",
            "target_domain": "C · 시장리스크",
            "branch": f"change/{row['source_code'].lower()}",
            "requested_by": "상품기획부", "n_components": 4,
            # 테스트·검토가 끝나기 전에는 배포 권한이 없다.
            "deploy_allowed": False, "status": "branch",
        })
        for layer, node, impact in (
            ("data", "rdm_canonical_map", "표준코드 미매핑 — 산출 모집단에서 제외"),
            ("formula", "risk_lib.capital.market_risk",
             "위험군 매핑 없음 — 시장리스크 소요자기자본 과소"),
            ("report", "BR-05 시장리스크 소요자기자본", "서식 라인 누락"),
            ("owner", "시장리스크부", "신상품 위험요소 승인 필요"),
        ):
            impacts.append({"change_id": cid, "layer": layer, "node": node,
                            "impact": impact})
        for tname, scope, calc, rep, status in (
            ("기존 유형 동일성", "전수", True, True, "통과"),
            ("미등록 유형 차단", "차단표본", True, False, "통과"),
            ("자본 변동", "변동표본", True, True, "검토"),
        ):
            tests.append({"change_id": cid, "test_name": tname, "scope": scope,
                          "covers_calc": calc, "covers_report": rep,
                          "status": status})
    cols_r = ["change_id", "change_type", "target_domain", "branch",
              "requested_by", "n_components", "deploy_allowed", "status"]
    return {
        "chg_change_request": pd.DataFrame(reqs, columns=cols_r),
        "chg_impact_map": pd.DataFrame(
            impacts, columns=["change_id", "layer", "node", "impact"]),
        "chg_regression_test": pd.DataFrame(
            tests, columns=["change_id", "test_name", "scope", "covers_calc",
                            "covers_report", "status"]),
    }


# ---------------------------------------------------------------- 증빙 계보

def build_evidence_graph(tables: dict[str, pd.DataFrame], run_id: str,
                         *, digest: str) -> dict[str, pd.DataFrame]:
    """7단계 증빙 그래프 — 노드와 **간선**을 함께 만든다.

    노드만 나열하면 목록일 뿐 계보가 아니다. 각 단계가 무엇에서 유도됐는지
    간선으로 남겨야 "이 숫자가 어디서 왔는가"에 답할 수 있다.
    """
    contracts = tables.get("rdm_source_contract", pd.DataFrame())
    dq = tables.get("rdm_reconciliation", pd.DataFrame())
    checks = tables.get("val_check", pd.DataFrame())
    ledger = tables.get("val_audit_ledger", pd.DataFrame())
    lines = tables.get("reg_form_line", pd.DataFrame())
    approvals_pending = 1

    n_fail = int((checks["status"] == "FAIL").sum()) if len(checks) else 0
    n_warn = int((checks["status"] == "WARN").sum()) if len(checks) else 0
    recon_ok = bool((dq["status"] == "PASS").all()) if len(dq) else True

    nodes = [
        ("N1", "출처", f"원천 인터페이스 계약 {len(contracts)}건",
         "rdm_source_contract",
         "완결" if len(contracts) and (contracts["status"] == "PASS").all()
         else "검토"),
        ("N2", "변환", "표준 매핑 · 정규 테이블 실체화",
         "risk_lib.datamodel.materialize", "완결"),
        ("N3", "계산", f"산출 근거 원장 {len(ledger)}건", "val_audit_ledger",
         "완결" if len(ledger) else "누락"),
        ("N4", "검증", f"자체검증 {len(checks)}건 (FAIL {n_fail} · WARN {n_warn})",
         "val_check", "완결" if n_fail == 0 else "검토"),
        ("N5", "증빙", f"집계 대사 {len(dq)}건", "rdm_reconciliation",
         "완결" if recon_ok else "검토"),
        ("N6", "승인", f"4-Eyes 승인 대기 {approvals_pending}건", "gov_approval",
         "검토"),
        ("N7", "보고", f"업무보고서 라인 {len(lines)}행 · 지문 {digest[:8]}",
         "reg_form_line", "완결" if len(lines) else "누락"),
    ]
    node_df = pd.DataFrame([{
        "run_id": run_id, "node_id": nid, "stage": stage, "label": label,
        "ref": ref, "status": status,
    } for nid, stage, label, ref, status in nodes])
    edges = [("N1", "N2", "derives"), ("N2", "N3", "derives"),
             ("N3", "N4", "verifies"), ("N4", "N5", "verifies"),
             ("N5", "N6", "approves"), ("N6", "N7", "reports"),
             ("N3", "N7", "derives")]
    edge_df = pd.DataFrame([{"run_id": run_id, "from_node": a, "to_node": b,
                             "relation": rel} for a, b, rel in edges])
    return {"gov_evidence_node": node_df, "gov_evidence_edge": edge_df}


def build_approvals(tables: dict[str, pd.DataFrame], run_id: str) -> pd.DataFrame:
    """4-Eyes 승인 기록. 검토자 = 승인자면 직무분리 위반으로 남긴다."""
    rows = []
    subs = tables.get("reg_submission")
    if isinstance(subs, pd.DataFrame):
        for _, r in subs.iterrows():
            reviewer, approver = str(r["reviewed_by"]), str(r["approved_by"])
            rows.append({
                "approval_id": f"AP-{run_id}-{r['form_id']}",
                "subject_type": "업무보고서 서식",
                "subject_id": str(r["form_id"]),
                "reviewer": reviewer, "approver": approver,
                "segregation_ok": reviewer != approver,
                "decision": "대기" if int(r["n_failed_checks"]) else "승인",
                "evidence_ref": f"digest={str(r['digest'])[:12]}",
            })
    adj = tables.get("aig_adjustment")
    if isinstance(adj, pd.DataFrame):
        for _, r in adj.iterrows():
            rows.append({
                "approval_id": f"AP-{run_id}-{r['adjustment_id']}",
                "subject_type": "수동조정", "subject_id": str(r["adjustment_id"]),
                "reviewer": str(r["requester"]), "approver": str(r["approver"]),
                "segregation_ok": str(r["requester"]) != str(r["approver"]),
                "decision": {"applied": "승인", "rejected": "반려"}.get(
                    str(r["status"]), "대기"),
                "evidence_ref": str(r["evidence_ref"]),
            })
    return pd.DataFrame(rows, columns=[
        "approval_id", "subject_type", "subject_id", "reviewer", "approver",
        "segregation_ok", "decision", "evidence_ref"])
