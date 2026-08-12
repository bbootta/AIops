"""연계 재시도·멱등성·오류 격리 (INT-008).

연계가 실패하면 다시 받아야 하는데, 다시 받은 것이 앞서 받은 것과 같은
회차인지 판단할 기준이 없으면 같은 데이터가 두 번 적재된다. 익스포저가
두 번 적재되면 EAD가 두 배가 되고 그 오류는 산출 뒤에 발견된다.

원장 세 장과 판정 두 개로 구성한다.

  int_retry_policy      피드 유형별 재시도 횟수·대기·격리 전환 기준
  int_delivery_attempt  멱등키별 수신 시도와 결과
  int_quarantine        격리된 수신분과 해제 여부

멱등키는 hashlib.sha256(피드·기준일·회차·내용지문)이다. 파이썬 내장 hash()는
프로세스마다 솔트가 달라 재시작하면 같은 수신분이 다른 키를 갖는다. 내용
지문을 키에 넣는 이유는, 같은 회차 번호로 내용이 바뀐 파일이 오면 그것을
교체로 처리해야 하기 때문이다.

대기 시간은 지수 백오프이며 벽시계를 읽지 않는다. 시도 번호만으로 정해지므로
같은 입력이면 같은 계획이 나온다.

이 모듈의 TableSpec은 아직 datamodel.catalog에 등재하지 않았다. 등재는 실체화
검증과 문서 수치 일치를 함께 만족해야 하므로 배선 단계에서 `SPECS`를 넘긴다.

참조: RYNTA BRD INT-008(재시도·멱등성·오류격리) · RDM-007(예외·조치),
BCBS 239 원칙 3(정확성·무결성) · 원칙 6(적응성).
"""

from __future__ import annotations

import hashlib

import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec

ATTEMPT_OUTCOMES = ("성공", "실패", "중복차단", "격리")
BACKOFF_MODES = ("지수", "고정")
CHANNEL_KINDS = ("파일", "API", "DB batch")


# ---------------------------------------------------------------- 스펙

RETRY_POLICY = TableSpec(
    name="int_retry_policy", korean="재시도 정책", product="PRD-RDM",
    grain="연계 유형 1개당 1행",
    columns=(
        C("channel_kind", "string", "연계 유형", nullable=False,
          allowed=CHANNEL_KINDS),
        C("max_attempts", "int", "최대 시도 횟수", nullable=False, unit="count",
          min_value=1),
        C("base_wait_seconds", "float", "기본 대기", nullable=False,
          unit="seconds", min_value=0.0),
        C("backoff_mode", "string", "대기 증가 방식", nullable=False,
          allowed=BACKOFF_MODES),
        C("basis", "text", "기준값 성격", nullable=False),
        C("owner_role", "text", "연계 소유 역할", nullable=False),
    ),
    primary_key=("channel_kind",),
    note="최대 시도 횟수를 넘긴 수신분은 재시도하지 않고 격리한다. 무한 재시도는 "
         "원천에 부하를 주면서 오류를 숨긴다.",
)

DELIVERY_ATTEMPT = TableSpec(
    name="int_delivery_attempt", korean="수신 시도", product="PRD-RDM",
    grain="멱등키 x 시도 1건당 1행",
    columns=(
        C("idempotency_key", "text", "멱등키", nullable=False),
        C("feed_id", "string", "피드 식별자", nullable=False),
        C("asof", "date", "기준일자", nullable=False),
        C("batch_seq", "int", "회차", nullable=False, unit="count", min_value=1),
        C("attempt_no", "int", "시도 번호", nullable=False, unit="count",
          min_value=1),
        C("outcome", "string", "결과", nullable=False, allowed=ATTEMPT_OUTCOMES),
        C("wait_seconds", "float", "다음 시도까지 대기", nullable=True,
          unit="seconds", min_value=0.0,
          note="다음 시도가 없으면 NULL이다"),
        C("reason", "text", "사유", nullable=False),
    ),
    primary_key=("idempotency_key", "attempt_no"),
)

QUARANTINE = TableSpec(
    name="int_quarantine", korean="오류 격리", product="PRD-RDM",
    grain="격리된 수신분 1건당 1행",
    columns=(
        C("idempotency_key", "text", "멱등키", nullable=False),
        C("feed_id", "string", "피드 식별자", nullable=False),
        C("asof", "date", "기준일자", nullable=False),
        C("n_attempts", "int", "누적 시도 횟수", nullable=False, unit="count",
          min_value=1),
        C("reason", "text", "격리 사유", nullable=False),
        C("notified_role", "text", "통지 대상 역할", nullable=False),
        C("released", "bool", "해제 여부", nullable=False),
    ),
    primary_key=("idempotency_key",),
    note="격리된 수신분은 산출에 들어가지 않는다. 격리 사실을 통지하지 않으면 "
         "데이터가 조용히 빠진 채로 산출이 끝난다.",
)

SPECS: tuple[TableSpec, ...] = (RETRY_POLICY, DELIVERY_ATTEMPT, QUARANTINE)


# ---------------------------------------------------------------- 정책 적재
#
# 이 표가 이 모듈의 유일한 적재 지점이다. 판정 함수는 표를 직접 읽지 않고
# 인자로 받은 DataFrame만 본다.
#
# 재시도 횟수와 대기는 **내부 운영값이다.** 감독규정이 연계 재시도 횟수를 정한
# 조문은 없다. 그 사실을 basis에 적어 두고 규제 근거인 것처럼 쓰지 않는다.
_BASIS = "내부 운영값. 감독규정이 재시도 횟수를 정하지 않는다"

# (연계유형, 최대시도, 기본대기, 대기방식, 소유역할)
_POLICIES = (
    ("파일", 3, 300.0, "지수", "리스크데이터관리자"),
    ("API", 5, 30.0, "지수", "리스크데이터관리자"),
    ("DB batch", 2, 600.0, "고정", "리스크데이터관리자"),
)


def build_retry_policy() -> pd.DataFrame:
    return pd.DataFrame([{
        "channel_kind": p[0], "max_attempts": int(p[1]),
        "base_wait_seconds": float(p[2]), "backoff_mode": p[3],
        "basis": _BASIS, "owner_role": p[4],
    } for p in _POLICIES], columns=[c.name for c in RETRY_POLICY.columns]
    ).astype({"max_attempts": "int64", "base_wait_seconds": "float64"})


# ---------------------------------------------------------------- 멱등키

def idempotency_key(feed_id: str, asof: str, batch_seq: int,
                    content_fingerprint: str) -> str:
    """수신분 1건의 멱등키. 같은 내용이면 같은 키가 나온다.

    내용 지문을 키에 넣으므로, 같은 회차 번호로 다른 내용이 오면 다른 키가
    되어 중복으로 차단되지 않는다. 회차 번호만으로 키를 만들면 원천이
    수정본을 같은 번호로 보냈을 때 그 수정본이 버려진다.
    """
    h = hashlib.sha256()
    for part in (feed_id, asof, str(int(batch_seq)), content_fingerprint):
        h.update(part.encode("utf-8"))
        h.update(b"\x1f")
    return h.hexdigest()[:32]


def wait_seconds(policy_row, attempt_no: int) -> float:
    """다음 시도까지 대기. 시도 번호만으로 정해지므로 결정론이다."""
    base = float(policy_row["base_wait_seconds"])
    if policy_row["backoff_mode"] == "고정":
        return base
    return base * float(2 ** (int(attempt_no) - 1))


# ---------------------------------------------------------------- 판정

def process_deliveries(policy: pd.DataFrame, deliveries, *,
                       seen_keys: set[str] | None = None
                       ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """수신 시도를 순서대로 처리해 시도 원장과 격리 원장을 만든다.

    deliveries는 dict의 열거이며 다음을 갖는다.
      feed_id · asof · batch_seq · channel_kind · content_fingerprint ·
      ok(bool) · reason

    처리 규칙은 셋이다.
      1. 이미 본 멱등키는 '중복차단'이다. 다시 적재하지 않는다
      2. ok가 참이면 '성공'이고 그 키를 본 것으로 기록한다
      3. ok가 거짓이면 '실패'이며 시도 번호를 올린다. 정책의 최대 시도 횟수에
         이르면 '격리'로 바꾸고 격리 원장에 남긴다

    정책 원장에 연계 유형이 없으면 재시도하지 않고 즉시 격리한다. 근거 없이
    반복 호출하면 원천에 부하만 준다.
    """
    pol = policy.set_index("channel_kind")
    owner = policy.set_index("channel_kind")["owner_role"].to_dict()
    seen: set[str] = set(seen_keys or ())
    attempts: dict[str, int] = {}
    # 이미 격리된 키가 또 들어오면 시도는 남기되 격리 원장에는 한 번만 적는다.
    # 격리 원장의 입도는 수신분 1건이므로 같은 키가 두 행이 되면 기본키가 깨진다.
    quarantined: set[str] = set()
    attempt_rows, quarantine_rows = [], []

    for item in deliveries:
        key = idempotency_key(item["feed_id"], item["asof"],
                              item["batch_seq"], item["content_fingerprint"])
        channel = item["channel_kind"]
        base = {"idempotency_key": key, "feed_id": item["feed_id"],
                "asof": item["asof"], "batch_seq": int(item["batch_seq"])}
        if key in seen:
            attempts[key] = attempts.get(key, 0) + 1
            attempt_rows.append({**base, "attempt_no": attempts[key],
                                 "outcome": "중복차단", "wait_seconds": None,
                                 "reason": "이미 적재된 멱등키다"})
            continue
        attempts[key] = attempts.get(key, 0) + 1
        n = attempts[key]
        if item.get("ok"):
            seen.add(key)
            attempt_rows.append({**base, "attempt_no": n, "outcome": "성공",
                                 "wait_seconds": None,
                                 "reason": item.get("reason", "수신 성공")})
            continue
        reason = item.get("reason", "수신 실패")
        if channel not in pol.index:
            attempt_rows.append({**base, "attempt_no": n, "outcome": "격리",
                                 "wait_seconds": None,
                                 "reason": f"재시도 정책에 연계 유형 {channel} 가 없다"})
            if key not in quarantined:
                quarantined.add(key)
                quarantine_rows.append({**base, "n_attempts": n,
                                        "reason": f"정책 없음. {reason}",
                                        "notified_role": "리스크데이터관리자",
                                        "released": False})
            continue
        row = pol.loc[channel]
        if n >= int(row["max_attempts"]):
            attempt_rows.append({**base, "attempt_no": n, "outcome": "격리",
                                 "wait_seconds": None,
                                 "reason": f"최대 {int(row['max_attempts'])}회 시도 초과. {reason}"})
            if key not in quarantined:
                quarantined.add(key)
                quarantine_rows.append({**base, "n_attempts": n, "reason": reason,
                                        "notified_role": owner.get(channel, "미지정"),
                                        "released": False})
        else:
            attempt_rows.append({**base, "attempt_no": n, "outcome": "실패",
                                 "wait_seconds": wait_seconds(row, n),
                                 "reason": reason})

    attempt_cols = [c.name for c in DELIVERY_ATTEMPT.columns]
    quarantine_cols = [c.name for c in QUARANTINE.columns]
    attempt_frame = pd.DataFrame(attempt_rows, columns=attempt_cols).astype(
        {"batch_seq": "int64", "attempt_no": "int64", "wait_seconds": "float64"})
    # 빈 결과에서도 컬럼 타입을 스펙과 맞춘다. object로 남으면 격리 건이
    # 하나도 없을 때만 스펙 검증이 실패한다.
    quarantine_frame = pd.DataFrame(
        [{k: v for k, v in q.items() if k in quarantine_cols}
         for q in quarantine_rows], columns=quarantine_cols
    ).astype({"n_attempts": "int64", "released": "bool"})
    return attempt_frame, quarantine_frame


def build_resilience(deliveries, *, seen_keys: set[str] | None = None
                     ) -> dict[str, pd.DataFrame]:
    """연계 복원력 원장 3장을 만든다."""
    policy = build_retry_policy()
    attempts, quarantine = process_deliveries(policy, deliveries,
                                              seen_keys=seen_keys)
    return {"int_retry_policy": policy,
            "int_delivery_attempt": attempts,
            "int_quarantine": quarantine}
