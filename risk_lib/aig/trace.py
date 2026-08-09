"""전송 마스킹(DLP)과 프롬프트·도구·출력 로그 (AIG-006 · AIG-007).

**무엇이 있었고 무엇이 없었나.** `ui_field_policy`는 화면에 어떤 필드를 어떤
집계단위로 보일지를 정한다. 화면에서 막아도 같은 값이 프롬프트나 도구 인자로
모형 제공자에게 나가면 통제가 성립하지 않는다. `agent_activity`는 수행 주체·
도구·결과 한 줄을 남기지만 프롬프트 본문도, 입력·출력의 지문도, 사후 변조를
탐지할 수단도 없다.

이 모듈이 만드는 것은 세 가지다.

  전송 전 마스킹. `redact`는 규칙 원장(`aig_redaction_rule`)의 정규식으로
  본문을 훑어 치환하고, 무엇이 몇 건 걸렸는지 돌려준다. 규칙이 원장에 있으므로
  규칙을 늘리는 일과 코드를 고치는 일이 분리된다.

  전구간 로그. `TraceRecorder`가 프롬프트·도구호출·도구결과·출력·승인을 같은
  실행(run_id) 아래 순서대로 쌓는다. 본문은 마스킹 후에 적재되고, 원본 지문은
  SHA-256으로 남아 마스킹 전후를 대조할 수 있다.

  변조 탐지. 각 행은 직전 행의 사슬 해시를 포함해 해시된다. 가운데 한 행을
  고치면 그 지점부터 사슬이 끊기고 `verify_chain`이 첫 파손 위치를 돌려준다.
  파이썬 내장 `hash()`는 실행마다 솔트가 달라 재현되지 않으므로 쓰지 않는다.

**벽시계 시각을 쓰지 않는다.** 로그의 시각 축은 기준일(asof)과 순번(seq)이다.
`datetime.now()`로 찍으면 같은 입력이 실행마다 다른 원장을 만든다.

**이 원장을 누가 채우는가.** 이 저장소의 산출은 결정론 계산이며 실행 중 언어
모형을 호출하지 않는다. 따라서 여기서 나오는 행의 프롬프트 칸은 대부분 비어
있고 `prompt_source='없음(결정론 산출)'`로 남는다. 실제 프롬프트 본문은 에이전트
런타임이 `TraceRecorder`를 호출해 적재해야 하며, 그 런타임은 이 저장소 밖에
있다. 원장과 사슬·마스킹은 준비돼 있고 채우는 쪽이 남았다는 것이 현재 상태다.

**미등재.** TableSpec은 배선 단계에서 카탈로그에 등재한다.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, TableSpec

__all__ = [
    "TRACE_PHASES", "REDACTION_ACTIONS", "REDACTION_TARGETS", "PROMPT_SOURCES",
    "REDACTION_RULE", "AGENT_TRACE", "AIG_TABLES", "RedactionHit",
    "build_redaction_rules", "redact", "TraceRecorder", "verify_chain",
    "build_trace_from_activity",
]

TRACE_PHASES: tuple[str, ...] = (
    "prompt", "tool_call", "tool_result", "output", "approval")
REDACTION_ACTIONS: tuple[str, ...] = ("마스킹", "차단")
REDACTION_TARGETS: tuple[str, ...] = ("prompt", "output", "both")
PROMPT_SOURCES: tuple[str, ...] = ("사용자", "시스템", "없음(결정론 산출)")

# 사슬의 첫 행이 물릴 자리. 상수 문자열이며 계수가 아니다.
_GENESIS = "0" * 64


def _sha256(*parts: object) -> str:
    """재현 가능한 지문. 내장 hash()는 프로세스마다 솔트가 달라 쓸 수 없다."""
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8"))
        h.update(b"\x1f")          # 필드 경계. 없으면 인접 필드가 붙어 충돌한다
    return h.hexdigest()


# ---------------------------------------------------------------- 스펙

REDACTION_RULE = TableSpec(
    name="aig_redaction_rule", korean="전송 마스킹 규칙", product="PRD-AIG",
    grain="마스킹 규칙 1건당 1행",
    columns=(
        C("rule_code", "string", "규칙코드", nullable=False),
        C("seq", "int", "적용 순서", nullable=False, min_value=1,
          note="정규식이 겹치면 먼저 적용된 규칙이 이긴다. 전화번호와 계좌번호는 "
               "표기가 겹치므로 순서가 결과를 바꾼다. 순서를 원장에 두지 않으면 "
               "무엇이 무엇을 가렸는지 코드를 읽어야 알 수 있다"),
        C("korean", "text", "규칙명", nullable=False),
        C("pattern", "text", "탐지 정규식", nullable=False),
        C("replacement", "text", "치환 문자열", nullable=False),
        C("action", "string", "조치", nullable=False, allowed=REDACTION_ACTIONS,
          note="차단은 해당 본문을 전송하지 않는다는 뜻이며 마스킹보다 강하다"),
        C("applies_to", "string", "적용 구간", nullable=False,
          allowed=REDACTION_TARGETS),
        C("rationale", "text", "근거", nullable=False),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=("원문확인", "재량·미규정", "미확인")),
    ),
    primary_key=("rule_code",),
    note="규칙이 코드에 있으면 무엇을 막고 있는지 화면에서 볼 수 없다. "
         "정규식 자체는 식별자 표기 형식이며 규제가 정한 값이 아니다.",
)

AGENT_TRACE = TableSpec(
    name="aig_agent_trace", korean="프롬프트·도구·출력 로그", product="PRD-AIG",
    grain="실행 × 순번 1행",
    columns=(
        C("run_id", "string", "실행 식별자", nullable=False),
        C("seq", "int", "순번", nullable=False, min_value=1),
        C("asof", "date", "기준일", nullable=False,
          note="시각 축은 기준일과 순번이다. 벽시계를 찍으면 같은 입력이 "
               "실행마다 다른 원장을 만든다"),
        C("actor", "text", "수행 주체", nullable=False),
        C("phase", "string", "구간", nullable=False, allowed=TRACE_PHASES),
        C("tool", "text", "도구", nullable=True),
        C("prompt_source", "string", "프롬프트 출처", nullable=False,
          allowed=PROMPT_SOURCES),
        C("prompt_text", "text", "프롬프트 본문(마스킹 후)", nullable=True),
        C("payload_text", "text", "도구 인자·출력 본문(마스킹 후)", nullable=True),
        C("redaction_hits", "int", "마스킹 건수", nullable=False, min_value=0),
        C("redaction_rules", "text", "적용 규칙", nullable=True),
        C("raw_sha256", "text", "마스킹 전 지문", nullable=False,
          note="본문은 마스킹 후만 보관하고 원본은 지문으로만 남긴다. "
               "원본을 그대로 보관하면 로그가 새 유출 경로가 된다"),
        C("masked_sha256", "text", "마스킹 후 지문", nullable=False),
        C("prev_hash", "text", "직전 사슬 해시", nullable=False),
        C("chain_hash", "text", "사슬 해시", nullable=False),
        C("gate", "string", "게이트", nullable=False,
          allowed=("통과", "검토", "차단", "대기")),
    ),
    primary_key=("run_id", "seq"),
    note="EU AI Act 제12조·ISO/IEC 42001 A.6.2.8이 요구하는 기록의 구조. "
         "사슬 해시로 사후 변조가 드러난다.",
)

AIG_TABLES = (REDACTION_RULE, AGENT_TRACE)


# ---------------------------------------------------------------- 규칙 빌더

# (규칙코드, 규칙명, 정규식, 치환, 조치, 적용구간, 근거)
_RULES: tuple[tuple[str, str, str, str, str, str, str], ...] = (
    ("DLP-RRN", "주민등록번호", r"\b\d{6}[-\s]?[1-4]\d{6}\b", "[RRN]",
     "차단", "both", "고유식별정보는 외부 전송 자체를 막는다"),
    ("DLP-CARD", "카드번호", r"\b(?:\d{4}[-\s]?){3}\d{4}\b", "[CARD]",
     "차단", "both", "카드번호는 전송 시 즉시 결제수단이 된다"),
    ("DLP-EMAIL", "이메일", r"\b[\w.+-]+@[\w-]+\.[\w.]+\b", "[EMAIL]",
     "마스킹", "both", "담당자 식별 정보"),
    ("DLP-PHONE", "전화번호", r"\b01[016789][-\s]?\d{3,4}[-\s]?\d{4}\b",
     "[PHONE]", "마스킹", "both",
     "담당자 식별 정보. 계좌번호 규칙보다 먼저 적용해야 한다. 두 표기가 "
     "겹쳐서 순서가 뒤바뀌면 전화번호가 계좌번호로 기록된다"),
    ("DLP-ACCT", "계좌번호", r"\b\d{2,6}-\d{2,6}-\d{2,8}\b", "[ACCT]",
     "마스킹", "both", "계좌 식별자는 차주 재식별 경로가 된다"),
    ("DLP-OBLIGOR", "차주 식별자", r"\bOBL_[A-Z]+_\d+\b", "[OBLIGOR]",
     "마스킹", "both",
     "ui_field_policy가 화면에서 가리는 필드와 같은 값이다. 화면에서 가리고 "
     "프롬프트로 내보내면 통제가 성립하지 않는다"),
)


def build_redaction_rules() -> pd.DataFrame:
    """전송 마스킹 규칙 원장.

    정규식은 식별자 표기 형식이고 조치 수준(마스킹·차단)은 내부 정책이다.
    규제가 정한 값이 아니므로 근거 상태는 '재량·미규정'이다.
    """
    rows = [{
        "rule_code": code, "seq": i + 1, "korean": korean, "pattern": pattern,
        "replacement": repl, "action": action, "applies_to": target,
        "rationale": rationale, "evidence_status": "재량·미규정",
    } for i, (code, korean, pattern, repl, action, target, rationale)
        in enumerate(_RULES)]
    return pd.DataFrame(rows, columns=REDACTION_RULE.column_names)


@dataclass(frozen=True)
class RedactionHit:
    rule_code: str
    action: str
    count: int


def redact(text: str | None, rules: pd.DataFrame, *, target: str
           ) -> tuple[str | None, list[RedactionHit], bool]:
    """본문을 마스킹한다.

    돌려주는 세 번째 값은 차단 여부다. 차단 규칙에 걸린 본문은 마스킹만 하고
    보내면 안 되므로, 호출부가 전송을 포기했는지를 원장에 남길 수 있어야 한다.
    """
    if text is None:
        return None, [], False
    out = str(text)
    hits: list[RedactionHit] = []
    blocked = False
    for r in rules.sort_values("seq").itertuples(index=False):
        if r.applies_to not in ("both", target):
            continue
        out, n = re.subn(r.pattern, r.replacement, out)
        if n:
            hits.append(RedactionHit(r.rule_code, r.action, int(n)))
            if r.action == "차단":
                blocked = True
    return out, hits, blocked


# ---------------------------------------------------------------- 기록기

@dataclass
class TraceRecorder:
    """실행 하나의 로그를 순서대로 쌓는다.

    본문은 마스킹 후만 보관하고 원본은 지문으로만 남긴다. 사슬 해시는 직전 행의
    해시를 포함하므로 중간 행을 고치면 그 뒤가 전부 어긋난다.
    """
    run_id: str
    asof: str
    rules: pd.DataFrame
    rows: list[dict] = field(default_factory=list)
    _prev: str = _GENESIS

    def append(self, *, actor: str, phase: str, gate: str,
               tool: str | None = None,
               prompt_text: str | None = None,
               payload_text: str | None = None,
               prompt_source: str = "없음(결정론 산출)") -> dict:
        if phase not in TRACE_PHASES:
            raise ValueError(f"알 수 없는 구간 {phase!r}")
        if prompt_source not in PROMPT_SOURCES:
            raise ValueError(f"알 수 없는 프롬프트 출처 {prompt_source!r}")
        raw = _sha256(prompt_text, payload_text)
        p_text, p_hits, p_block = redact(prompt_text, self.rules, target="prompt")
        d_text, d_hits, d_block = redact(payload_text, self.rules, target="output")
        hits = p_hits + d_hits
        if p_block or d_block:
            # 차단 규칙에 걸린 본문은 로그에도 남기지 않는다. 지문과 규칙만 남아
            # 무엇이 걸렸는지는 확인되고 값은 재구성되지 않는다.
            p_text = None if prompt_text is None else "[BLOCKED]"
            d_text = None if payload_text is None else "[BLOCKED]"
            gate = "차단"
        masked = _sha256(p_text, d_text)
        seq = len(self.rows) + 1
        row = {
            "run_id": self.run_id, "seq": seq, "asof": self.asof,
            "actor": actor, "phase": phase, "tool": tool,
            "prompt_source": prompt_source,
            "prompt_text": p_text, "payload_text": d_text,
            "redaction_hits": int(sum(h.count for h in hits)),
            "redaction_rules": (",".join(sorted({h.rule_code for h in hits}))
                                or None),
            "raw_sha256": raw, "masked_sha256": masked,
            "prev_hash": self._prev,
        }
        row["chain_hash"] = _sha256(
            row["prev_hash"], row["run_id"], row["seq"], row["asof"],
            row["actor"], row["phase"], row["tool"], row["prompt_source"],
            row["raw_sha256"], row["masked_sha256"], gate)
        row["gate"] = gate
        self._prev = row["chain_hash"]
        self.rows.append(row)
        return row

    def frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.rows, columns=AGENT_TRACE.column_names)


def verify_chain(trace: pd.DataFrame) -> int | None:
    """사슬을 검증하고 첫 파손 순번을 돌려준다. 이상이 없으면 None이다."""
    if trace.empty:
        return None
    prev = _GENESIS
    for r in trace.sort_values("seq").itertuples(index=False):
        if r.prev_hash != prev:
            return int(r.seq)
        expect = _sha256(r.prev_hash, r.run_id, r.seq, r.asof, r.actor,
                         r.phase, r.tool, r.prompt_source, r.raw_sha256,
                         r.masked_sha256, r.gate)
        if expect != r.chain_hash:
            return int(r.seq)
        prev = r.chain_hash
    return None


def build_trace_from_activity(activity: pd.DataFrame, rules: pd.DataFrame, *,
                              asof: str, run_id: str) -> pd.DataFrame:
    """기존 활동 원장을 전구간 로그 구조로 옮긴다.

    `agent_activity`는 수행 주체·도구·결과 한 줄만 갖는다. 그 한 줄을 도구호출과
    출력 두 구간으로 펴고 지문·사슬을 붙인다. 프롬프트 본문은 만들어 넣지
    않는다. 이 저장소의 산출은 언어모형을 호출하지 않으므로 프롬프트가 존재하지
    않으며, 없는 본문을 채워 넣으면 그 행은 실제로 오간 내용을 기록한 것이
    아니게 된다.
    """
    rec = TraceRecorder(run_id=run_id, asof=asof, rules=rules)
    if activity.empty:
        return rec.frame()
    for a in activity.sort_values("seq").itertuples(index=False):
        rec.append(actor=str(a.actor), phase="tool_call", gate="대기",
                   tool=str(a.tool), payload_text=None)
        rec.append(actor=str(a.actor), phase="output", gate=str(a.gate),
                   tool=str(a.tool), payload_text=str(a.output))
    return rec.frame()
