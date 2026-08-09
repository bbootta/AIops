"""감사기록 불변성 (NFR-004).

이 저장소의 감사 원장(val_audit_ledger·gov_approval·aig_adjustment)은 값과
근거를 남기지만, **나중에 고쳐도 티가 나지 않는다**. 행 하나를 조용히 바꾸면
그 행이 원래 무엇이었는지 증명할 방법이 없다.

해시체인으로 그 구멍을 닫는다. 기록 n의 해시는 기록 n-1의 해시를 입력으로
받으므로, 중간 한 건을 고치면 그 뒤 모든 해시가 어긋난다. 마지막 해시(체인
헤드)를 manifest에 실으면 원장 전체가 그 한 값으로 봉인된다.

  append 전용   갱신·삭제 메서드를 두지 않는다. 정정은 상쇄 기록을 덧붙인다
  연결 검증     prev_hash 불일치 탐지
  내용 검증     저장된 필드로 record_hash를 재계산해 대조

hashlib.sha256을 쓴다. 파이썬 내장 hash()는 프로세스마다 솔트가 달라 같은
원장이 실행마다 다른 지문을 낸다.

이 모듈의 TableSpec은 아직 datamodel.catalog에 등재하지 않았다. 등재는 실체화
검증과 문서 수치 일치를 함께 만족해야 하므로 배선 단계에서 `SPECS`를 넘긴다.
스펙 품질 기준(입도·기본키·float 단위·FK 대상 존재)은 지금부터 지킨다.

참조: RYNTA BRD NFR-004(감사로그 불변성) · GOV-009(Evidence·감사 통제),
전자금융감독규정 제15조(전산자료 보호), BCBS 239 원칙 6(적시성·완전성).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, TableSpec

EVENT_TYPES = ("산출", "승인", "수동조정", "검증", "접근판정", "적재", "정정")

GENESIS = "0" * 64          # 최초 기록의 prev_hash. 체인의 시작점을 고정한다.


AUDIT_CHAIN = TableSpec(
    name="gov_audit_chain", korean="감사기록 해시체인", product="PRD-AIG",
    grain="감사 사건 1건당 1행. seq는 1부터 빈틈 없이 증가한다",
    columns=(
        C("seq", "int", "일련번호", nullable=False, unit="count", min_value=1),
        C("record_id", "text", "사건 식별자", nullable=False),
        C("event_type", "string", "사건 유형", nullable=False, allowed=EVENT_TYPES),
        C("actor", "text", "행위자", nullable=False),
        C("occurred_asof", "date", "사건 기준일", nullable=False),
        C("source_ledger", "string", "원천 원장", nullable=False),
        C("payload_digest", "text", "내용 지문(SHA-256)", nullable=False),
        C("prev_hash", "text", "직전 기록 해시", nullable=False),
        C("record_hash", "text", "이 기록의 해시", nullable=False),
    ),
    primary_key=("seq",),
    note="갱신·삭제를 하지 않는다. 정정은 event_type='정정' 기록을 덧붙여 표현한다.",
)

SPECS: tuple[TableSpec, ...] = (AUDIT_CHAIN,)


def canonical_digest(payload: dict) -> str:
    """내용 지문. 키 정렬·구분자 고정으로 같은 내용이 항상 같은 지문을 낸다."""
    blob = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def record_hash(seq: int, prev: str, record_id: str, event_type: str,
                actor: str, occurred_asof: str, source_ledger: str,
                payload_digest: str) -> str:
    """기록 해시. 체인에 실리는 모든 필드를 입력으로 넣는다.

    일부 필드를 빼면 그 필드는 고쳐도 해시가 그대로여서 봉인 밖에 남는다.
    """
    parts = (str(seq), prev, record_id, event_type, actor, occurred_asof,
             source_ledger, payload_digest)
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


class AuditChainError(ValueError):
    """체인 무결성 위반, 또는 append 이외의 변경 시도."""


@dataclass
class AuditChain:
    """append 전용 감사기록 체인."""
    records: list[dict] = field(default_factory=list)

    @property
    def head(self) -> str:
        return self.records[-1]["record_hash"] if self.records else GENESIS

    def append(self, *, record_id: str, event_type: str, actor: str,
               occurred_asof: str, source_ledger: str,
               payload: dict) -> dict:
        if event_type not in EVENT_TYPES:
            raise AuditChainError(f"알 수 없는 사건 유형: {event_type!r}")
        seq = len(self.records) + 1
        prev = self.head
        digest = canonical_digest(payload)
        rec = {
            "seq": seq, "record_id": record_id, "event_type": event_type,
            "actor": actor, "occurred_asof": occurred_asof,
            "source_ledger": source_ledger, "payload_digest": digest,
            "prev_hash": prev,
            "record_hash": record_hash(seq, prev, record_id, event_type, actor,
                                       occurred_asof, source_ledger, digest),
        }
        self.records.append(rec)
        return rec

    def to_frame(self) -> pd.DataFrame:
        return pd.DataFrame(self.records,
                            columns=[c.name for c in AUDIT_CHAIN.columns])


def verify_chain(frame: pd.DataFrame) -> list[str]:
    """체인 검증. 위반 사유 목록을 돌려주고 비어 있으면 무결하다.

    세 가지를 본다. 일련번호가 빈틈 없이 이어지는가, prev_hash가 직전
    record_hash와 같은가, 저장된 필드로 재계산한 해시가 저장값과 같은가.
    """
    problems: list[str] = []
    if frame.empty:
        return problems
    df = frame.sort_values("seq").reset_index(drop=True)

    expected_seq = list(range(1, len(df) + 1))
    if [int(x) for x in df["seq"]] != expected_seq:
        problems.append(f"일련번호 불연속: {list(df['seq'])[:10]}")

    prev = GENESIS
    for _, r in df.iterrows():
        if str(r["prev_hash"]) != prev:
            problems.append(
                f"seq {int(r['seq'])}: prev_hash 불일치 (기대 {prev[:12]}, "
                f"실제 {str(r['prev_hash'])[:12]})")
        want = record_hash(int(r["seq"]), str(r["prev_hash"]), str(r["record_id"]),
                           str(r["event_type"]), str(r["actor"]),
                           str(r["occurred_asof"]), str(r["source_ledger"]),
                           str(r["payload_digest"]))
        if want != str(r["record_hash"]):
            problems.append(
                f"seq {int(r['seq'])}: 기록 해시 불일치. 저장 후 내용이 바뀌었다")
        prev = str(r["record_hash"])
    return problems


def chain_head(frame: pd.DataFrame) -> str:
    """체인 헤드. manifest에 실어 원장 전체를 한 값으로 봉인한다."""
    if frame.empty:
        return GENESIS
    return str(frame.sort_values("seq").iloc[-1]["record_hash"])


# ---------------------------------------------------------------- 수집

# 감사 사건을 뽑아 올 원장과 그 해석 규칙.
#
# (원장명, 사건유형, 식별자 컬럼, 행위자 컬럼, 기준일 컬럼, 행위자 기본값)
# 행위자 컬럼이 None이면 엔진이 남긴 기록이라는 뜻이며 기본값을 쓴다.
# 기준일 컬럼이 None이면 그 원장이 자체 시점을 갖지 않으므로 산출 기준일을 쓴다.
_SOURCES = (
    ("gov_approval", "승인", "approval_id", "approver", None, ""),
    ("aig_adjustment", "수동조정", "adjustment_id", "approver", "approval_date", ""),
    ("gov_access_decision", "접근판정", "decision_id", "user_id", "asof", ""),
    ("val_check", "검증", "check_name", None, "asof", "자체검증 엔진"),
    ("val_audit_ledger", "산출", "figure_id", None, None, "산출 엔진"),
)


def collect_events(tables: dict[str, pd.DataFrame], *, asof: str
                   ) -> tuple[list[dict], list[str]]:
    """원장에서 감사 사건을 뽑는다. (사건 목록, 기록) 을 돌려준다.

    두 번째 반환값에는 건너뛴 원장과 대체한 값이 모두 들어간다. 대체를 적어
    두지 않으면 체인이 완전한 것처럼 보이면서 실제로는 빈 칸을 메운 것이 된다.
    """
    events: list[dict] = []
    notes: list[str] = []
    for name, kind, id_col, actor_col, date_col, actor_default in _SOURCES:
        df = tables.get(name)
        if df is None or not isinstance(df, pd.DataFrame) or df.empty:
            notes.append(f"{name}: 원장 없음 또는 빈 원장")
            continue
        if id_col not in df.columns:
            notes.append(f"{name}: 식별자 컬럼 {id_col} 없음. 사건을 만들지 않는다")
            continue
        use_actor = actor_col if actor_col and actor_col in df.columns else None
        if actor_col and use_actor is None:
            notes.append(f"{name}: 행위자 컬럼 {actor_col} 없음. "
                         f"기본값 {actor_default or '(빈값)'}을 쓴다")
        use_date = date_col if date_col and date_col in df.columns else None
        if date_col and use_date is None:
            notes.append(f"{name}: 기준일 컬럼 {date_col} 없음. 산출 기준일을 쓴다")
        for _, r in df.iterrows():
            actor = str(r[use_actor]) if use_actor else actor_default
            occurred = str(r[use_date])[:10] if use_date else asof
            events.append({
                "record_id": f"{name}:{r[id_col]}",
                "event_type": kind,
                "actor": actor or actor_default or "(미기재)",
                "occurred_asof": occurred or asof,
                "source_ledger": name,
                "payload": {k: r[k] for k in sorted(df.columns)},
            })
    return events, notes


def build_audit_chain(tables: dict[str, pd.DataFrame], *, asof: str
                      ) -> tuple[pd.DataFrame, list[str]]:
    """원장에서 사건을 모아 체인을 만든다. (체인 원장, 수집 기록)을 돌려준다.

    정렬은 (기준일, 원장명, 식별자)로 고정한다. 원장 순회 순서에 체인이
    의존하면 같은 입력이 실행마다 다른 헤드를 낸다.
    """
    events, notes = collect_events(tables, asof=asof)
    events.sort(key=lambda e: (e["occurred_asof"], e["source_ledger"],
                               e["record_id"]))
    chain = AuditChain()
    for e in events:
        chain.append(record_id=e["record_id"], event_type=e["event_type"],
                     actor=e["actor"], occurred_asof=e["occurred_asof"],
                     source_ledger=e["source_ledger"], payload=e["payload"])
    return chain.to_frame(), notes
