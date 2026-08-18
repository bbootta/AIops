"""사업성 계산(COM)·연계 정책(INT-008) — 가정 파생·이중계상 방지·결정론.

사업성 수치는 규제 산출물이 아니지만 같은 규율을 받는다: 모든 값은 가정
원장에서 계산으로만 나오고, 재현 가능해야 하며, 편익은 한 번만 계상된다.
"""

from __future__ import annotations

import pytest

from risk_lib import commercial as com
from risk_lib.integrations import RetryPolicy, idempotency_key


def test_quote_is_fully_assumption_derived():
    """견적의 모든 금액이 가정 원장 값에서 계산으로 재구성된다 (COM-002·006).

    화면의 숫자를 가정에서 손으로 다시 계산해 일치를 본다 — 계산식 안에
    박힌 숫자(가정 밖 금액)가 하나라도 생기면 여기서 어긋난다.
    """
    a = {x[0]: x[2] for x in com.ASSUMPTIONS}
    q = com.quote("PKG-BANK")
    assert q.build_cost == a["A-BANK-PD"] * a["A-RATE"]
    assert q.lifecycle_annual == q.build_cost * a["A-LIFE"] + a["A-INFRA"]
    assert q.year1_total == q.build_cost + q.lifecycle_annual
    assert q.tco_3y == (q.build_cost + 3 * q.lifecycle_annual) * (1 - a["A-DISC"])


def test_quotes_are_deterministic():
    f1, f2 = com.quote_frame(), com.quote_frame()
    assert f1.equals(f2)
    assert len(f1) == len(com.PRESETS) == 3


def test_double_counting_is_caught():
    """같은 가정을 두 편익이 참조하면 검증이 잡는다 (COM-007)."""
    assert com.check_no_double_counting() == []
    # 일부러 중복을 만들면 잡혀야 한다 — 잡는 능력 자체를 검증한다.
    orig = com.ROI_BENEFITS
    try:
        com.ROI_BENEFITS = orig + (("B-DUP", "중복 편익", orig[0][2]),)
        dup = com.check_no_double_counting()
        assert dup and "B-DUP" in dup[0]
    finally:
        com.ROI_BENEFITS = orig


def test_roi_benefits_each_have_one_assumption():
    ids = {a[0] for a in com.ASSUMPTIONS}
    for bid, _, aid in com.ROI_BENEFITS:
        assert aid in ids, f"{bid} — 출처 가정 {aid} 이 원장에 없다"


def test_retry_policy_is_deterministic():
    """재시도 계획은 산출물이다 — 지터 없이 같은 정책은 같은 대기열 (INT-008)."""
    p = RetryPolicy(max_attempts=4, base_delay_s=2.0, factor=2.0)
    assert p.delays() == [2.0, 4.0, 8.0]
    assert p.delays() == p.delays()
    # 상한이 걸린다
    assert RetryPolicy(max_attempts=6, base_delay_s=20, factor=3,
                       max_delay_s=60).delays() == [20, 60, 60, 60, 60]


def test_idempotency_key_is_stable_and_payload_sensitive():
    k1 = idempotency_key("slack", "RUN-1", "digest-a")
    assert k1 == idempotency_key("slack", "RUN-1", "digest-a")   # 재전송 = 같은 키
    assert k1 != idempotency_key("slack", "RUN-1", "digest-b")   # 다른 내용 = 다른 키
    assert k1 != idempotency_key("email", "RUN-1", "digest-a")   # 다른 채널 = 다른 키
