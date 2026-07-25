"""자연어 조회조건 컴파일러 (PLT-009 · RDM-008).

자연어 → Filter AST → 정책 검증 → 실행 가능한 조회계획. LLM에 SQL을 맡기지
않는다 — 승인된 View의 필드·연산자·값 형식만 인식하는 **제한 문법**으로
파싱하고, 인식하지 못한 필드는 조용히 무시하지 않고 **차단 사유로 남긴다**.
그래야 "무엇이 조회되지 않았는지"가 화면 밖으로 새지 않는다.

지원 문법 (한 조건):

    <필드> <값> <연산자>        예) "LTV 70% 초과", "잔액 100억 이상"
    <필드> <값>                  예) "건전성 분류 고정"   → 등호

조건은 `그리고 · 및 · ,` 로 연결하며 모두 AND다. OR·괄호는 지원하지 않는다 —
지원하지 않는 것을 지원하는 척하면 조회 결과가 조용히 틀린다.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

import pandas as pd

# 연산자 키워드 → 파이썬 비교. 긴 것부터 매칭해야 "이상"이 "이"로 잘리지 않는다.
_OPERATORS: tuple[tuple[str, str], ...] = (
    ("초과", ">"), ("이상", ">="), ("미만", "<"), ("이하", "<="),
    ("아님", "!="), ("아닌", "!="), ("같음", "=="), ("이면", "=="),
)
_CONJUNCTIONS = re.compile(r"\s*(?:그리고|및|,|·|\bAND\b)\s*", re.IGNORECASE)

# 값 단위 — 한국 실무 표기를 그대로 받는다.
_SCALES: tuple[tuple[str, float], ...] = (
    ("조", 1e12), ("억", 1e8), ("만", 1e4), ("원", 1.0),
)


class QueryError(Exception):
    """조회계획을 만들 수 없다 — 사유를 반드시 남긴다."""


@dataclass(frozen=True)
class Condition:
    field: str
    label: str
    op: str
    value: object

    def to_ast(self) -> str:
        v = self.value
        return f"({self.field} {self.op} {v!r})"

    def describe(self) -> str:
        sym = {">": ">", ">=": "≥", "<": "<", "<=": "≤",
               "==": "=", "!=": "≠"}[self.op]
        v = self.value
        if isinstance(v, float):
            v = f"{v:,.4g}"
        return f"{self.label} {sym} {v}"


@dataclass(frozen=True)
class QueryPlan:
    plan_id: str
    view_id: str
    asof: str
    utterance: str
    intent: str
    population: str
    conditions: tuple[Condition, ...]
    policy: str
    query_hash: str
    status: str                 # validated · blocked
    block_reason: str | None = None
    n_rows: int = 0

    @property
    def condition_ast(self) -> str:
        if not self.conditions:
            return "TRUE"
        return " AND ".join(c.to_ast() for c in self.conditions)


def _parse_value(raw: str) -> object:
    """'70%' → 0.70 · '100억' → 1e10 · '고정' → '고정'."""
    s = raw.strip().replace(",", "")
    m = re.fullmatch(r"(-?\d+(?:\.\d+)?)\s*(%|퍼센트)", s)
    if m:
        return float(m.group(1)) / 100.0
    for suffix, scale in _SCALES:
        m = re.fullmatch(rf"(-?\d+(?:\.\d+)?)\s*{suffix}", s)
        if m:
            return float(m.group(1)) * scale
    m = re.fullmatch(r"-?\d+(?:\.\d+)?", s)
    if m:
        return float(s)
    return s.strip("\"'")


def _field_index(fields: pd.DataFrame) -> list[tuple[str, str, str]]:
    """(라벨, 필드명, 사유) — 사유가 빈 문자열이면 조건으로 쓸 수 있다.

    마스킹 필드를 **조건**으로 쓰면 특정 개체를 지목해 행 단위 결과를 되받을
    수 있다. 최소 집계단위가 1보다 큰 필드는 조회조건으로 허용하지 않는다.
    """
    idx: list[tuple[str, str, str]] = []
    for _, r in fields.iterrows():
        if not bool(r["permitted"]) or str(r["masking"]) == "deny":
            reason = "미승인 필드"
        elif int(r["min_aggregation"]) > 1:
            reason = (f"집계 최소단위 {int(r['min_aggregation'])} 필드는 "
                      f"조회조건으로 쓸 수 없음")
        else:
            reason = ""
        idx.append((str(r["korean"]), str(r["field_name"]), reason))
        idx.append((str(r["field_name"]), str(r["field_name"]), reason))
    return sorted(set(idx), key=lambda t: -len(t[0]))


def compile_query(utterance: str, *, view_id: str, asof: str,
                  fields: pd.DataFrame, population: str = "전체",
                  intent: str | None = None,
                  policy: str = "Read-only · PII Mask",
                  plan_id: str | None = None) -> QueryPlan:
    """자연어 문장을 조회계획으로 컴파일한다.

    `fields`는 ui_field_policy에서 해당 View의 행만 걸러 넘긴다. 여기 없는
    필드를 문장이 참조하면 계획은 blocked가 되며 실행되지 않는다.
    """
    index = _field_index(fields)
    conds: list[Condition] = []
    blocked: list[str] = []

    for clause in _CONJUNCTIONS.split(utterance):
        clause = clause.strip()
        if not clause:
            continue
        label, field, reason = None, None, ""
        for lbl, fld, why in index:
            if lbl and lbl in clause:
                label, field, reason = lbl, fld, why
                break
        if field is None:
            continue                      # 조건절이 아닌 서술(의도·모집단) — 무시
        if reason:
            blocked.append(f"{reason}: {label}")
            continue
        rest = clause.split(label, 1)[1]
        op = "=="
        for kw, sym in _OPERATORS:
            if kw in rest:
                op = sym
                rest = rest.split(kw, 1)[0]
                break
        # 조사·군더더기를 걷어내고 값 토큰만 남긴다.
        token = re.sub(r"^[\s이가은는을를의]+", "", rest).strip()
        token = re.sub(r"[\s인]+$", "", token)
        if not token:
            blocked.append(f"값 없는 조건: {label}")
            continue
        conds.append(Condition(field, label, op, _parse_value(token)))

    # 문장이 필드를 하나도 짚지 못하면 '전건 조회'로 통과시키지 않는다 —
    # 조건 없는 대량 추출이 자연어 오인식으로 발생하는 경로를 막는다.
    if not conds and not blocked:
        blocked.append("인식 가능한 조회조건 없음 — 승인 필드로 조건을 명시할 것")

    ast = " AND ".join(c.to_ast() for c in conds) if conds else "TRUE"
    qh = hashlib.sha256(
        f"{view_id}|{asof}|{policy}|{ast}".encode()).hexdigest()[:12].upper()
    return QueryPlan(
        plan_id=plan_id or f"QP-{qh}",
        view_id=view_id, asof=asof, utterance=utterance,
        intent=intent or (utterance[:40] if utterance else "조회"),
        population=population, conditions=tuple(conds), policy=policy,
        query_hash=qh,
        status="blocked" if blocked else "validated",
        block_reason="; ".join(blocked) if blocked else None,
    )


def execute(plan: QueryPlan, df: pd.DataFrame, *, row_limit: int
            ) -> tuple[pd.DataFrame, QueryPlan]:
    """검증된 계획만 실행한다. 차단된 계획은 빈 결과를 돌려준다."""
    if plan.status != "validated":
        return df.head(0), plan
    out = df
    for c in plan.conditions:
        if c.field not in out.columns:
            return df.head(0), QueryPlan(
                **{**plan.__dict__, "status": "blocked",
                   "block_reason": f"View에 없는 필드: {c.field}", "n_rows": 0})
        col = out[c.field]
        if c.op == ">":
            out = out[col > c.value]
        elif c.op == ">=":
            out = out[col >= c.value]
        elif c.op == "<":
            out = out[col < c.value]
        elif c.op == "<=":
            out = out[col <= c.value]
        elif c.op == "!=":
            out = out[col != c.value]
        else:
            out = out[col == c.value]
    n = int(len(out))
    # 행 상한은 잘라서 보여주되 **모집단 건수는 그대로 남긴다** — 잘린 걸
    # 모르면 "3건뿐"이라고 잘못 읽는다.
    return out.head(row_limit), QueryPlan(**{**plan.__dict__, "n_rows": n})
