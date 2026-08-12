"""비정형 Adaptive UI — 프롬프트 → 레이아웃 제안 → 정책검증 (PLT-011~013).

프롬프트는 **화면 구성안**만 만든다. 승인되지 않은 필드, 행 수준 개인정보,
규제산출 변경, 판단 확정은 하지 않는다. 세 가지 검증(필드권한·스키마/단위·
집계 최소단위)을 모두 통과해야 사람이 승인할 수 있고, 승인 전에는 화면에
반영되지 않는다. Rollback 대상은 제안 원장에 남는다.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

import pandas as pd

# 허용 시각화 — 여기 없는 유형은 제안 자체가 거부된다.
ALLOWED_VIZ = ("bar", "table", "kpi", "line")
_VIZ_KEYWORDS = (
    ("막대", "bar"), ("bar", "bar"), ("기여도", "bar"),
    ("추이", "line"), ("시계열", "line"), ("line", "line"),
    ("표", "table"), ("테이블", "table"), ("목록", "table"), ("table", "table"),
    ("카드", "kpi"), ("지표", "kpi"), ("kpi", "kpi"),
)
DEFAULT_ROW_LIMIT = 500


@dataclass(frozen=True)
class LayoutProposal:
    proposal_id: str
    view_id: str
    prompt: str
    blocks: tuple[tuple[str, str], ...]     # (viz, 제목)
    columns: tuple[str, ...]
    row_limit: int
    field_policy_pass: bool
    schema_pass: bool
    aggregation_pass: bool
    status: str
    rejected_fields: tuple[str, ...] = ()
    rollback_of: str | None = None

    @property
    def all_pass(self) -> bool:
        return (self.field_policy_pass and self.schema_pass
                and self.aggregation_pass)

    def layout_text(self) -> str:
        blocks = " → ".join(f"{v}:{t}" for v, t in self.blocks)
        return f"[{blocks}] cols=({', '.join(self.columns)}) limit={self.row_limit}"


def compose(prompt: str, *, view_id: str, fields: pd.DataFrame,
            row_limit: int = DEFAULT_ROW_LIMIT,
            proposal_id: str | None = None,
            rollback_of: str | None = None) -> LayoutProposal:
    """프롬프트에서 레이아웃 제안을 만들고 정책을 검증한다.

    `fields`는 해당 View의 ui_field_policy 행. 프롬프트가 짚은 컬럼 중 허용되지
    않은 것은 제거하지 않고 **거부 목록에 남긴다** — 조용히 빼면 사용자는
    자기가 요청한 열이 왜 없는지 알 수 없다.
    """
    label_to_field, masked, denied = {}, set(), set()
    for _, r in fields.iterrows():
        for label in (str(r["korean"]), str(r["field_name"])):
            label_to_field[label] = str(r["field_name"])
        if str(r["masking"]) == "mask":
            masked.add(str(r["field_name"]))
        if str(r["masking"]) == "deny" or not bool(r["permitted"]):
            denied.add(str(r["field_name"]))

    picked, rejected = [], []
    for label in sorted(label_to_field, key=len, reverse=True):
        if label and label in prompt:
            f = label_to_field[label]
            if f in denied:
                rejected.append(f)
            elif f not in picked:
                picked.append(f)

    blocks: list[tuple[str, str]] = []
    for kw, viz in _VIZ_KEYWORDS:
        if kw in prompt.lower() and all(v != viz for v, _ in blocks):
            blocks.append((viz, {"bar": "기여도", "line": "추이",
                                 "table": "검토 표", "kpi": "핵심 지표"}[viz]))
    if not blocks:
        blocks.append(("table", "검토 표"))

    m = re.search(r"(?:상위|top)\s*(\d+)", prompt, re.IGNORECASE)
    limit = min(int(m.group(1)), row_limit) if m else row_limit

    field_policy_pass = not rejected
    schema_pass = bool(picked) and all(v for v, _ in blocks)
    # 마스킹 필드를 열로 세우면 행 단위 노출이 된다 — 집계 최소단위 위반.
    aggregation_pass = not (set(picked) & masked)
    pid = proposal_id or "LP-" + hashlib.sha256(
        f"{view_id}|{prompt}".encode()).hexdigest()[:10].upper()
    all_ok = field_policy_pass and schema_pass and aggregation_pass
    return LayoutProposal(
        proposal_id=pid, view_id=view_id, prompt=prompt,
        blocks=tuple(blocks), columns=tuple(picked), row_limit=limit,
        field_policy_pass=field_policy_pass, schema_pass=schema_pass,
        aggregation_pass=aggregation_pass,
        status="previewed" if all_ok else "rejected",
        rejected_fields=tuple(rejected), rollback_of=rollback_of,
    )


def approve(proposal: LayoutProposal, *, approver: str) -> LayoutProposal:
    """사람 승인. 검증 하나라도 실패하면 승인 자체가 성립하지 않는다."""
    if not proposal.all_pass:
        raise ValueError(
            f"정책검증 미통과 제안은 승인할 수 없다: {proposal.proposal_id}")
    if not approver:
        raise ValueError("승인자 없이 적용할 수 없다 (PLT-012)")
    return LayoutProposal(**{**proposal.__dict__, "status": "approved"})


def proposal_frame(proposals: list[LayoutProposal]) -> pd.DataFrame:
    return pd.DataFrame([{
        "proposal_id": p.proposal_id, "view_id": p.view_id, "prompt": p.prompt,
        "layout": p.layout_text(),
        "field_policy_pass": p.field_policy_pass,
        "schema_pass": p.schema_pass,
        "aggregation_pass": p.aggregation_pass,
        "human_approved": p.status == "approved",
        "status": p.status, "rollback_of": p.rollback_of,
    } for p in proposals], columns=[
        "proposal_id", "view_id", "prompt", "layout", "field_policy_pass",
        "schema_pass", "aggregation_pass", "human_approved", "status",
        "rollback_of"])
