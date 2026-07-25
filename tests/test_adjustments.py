"""수동조정 원장 통제 테스트 (DAT-006).

핵심 명제: 통제를 통과하지 못한 조정은 **절대로 수치에 반영되지 않는다**.
"""

from __future__ import annotations

import pytest

from risk_lib.adjustments import (
    ManualAdjustment, AdjustmentLedger, AdjustmentError,
    reconcile, unrecorded_adjustments, demo_ledger,
    MATERIALITY_ABS, MATERIALITY_REL,
)

ASOF = "2026-06-11"


def _adj(**kw) -> ManualAdjustment:
    base = dict(
        adjustment_id="ADJ-X", figure_id="ecl.ttc_total", label="테스트",
        base_value=1_000_000_000.0, adjusted_value=1_001_000_000.0,
        reason="사유", evidence_ref="DOC-1",
        requester="요청자", approver="승인자",
        approval_date=ASOF, expires_on="2027-12-31",
    )
    base.update(kw)
    return ManualAdjustment(**base)


# ----- 등록 통제 -------------------------------------------------------------

def test_registration_requires_reason_and_evidence():
    led = AdjustmentLedger()
    with pytest.raises(AdjustmentError, match="사유·증빙"):
        led.add(_adj(reason=""))
    with pytest.raises(AdjustmentError, match="사유·증빙"):
        led.add(_adj(evidence_ref="  "))
    assert led.adjustments == []


def test_duplicate_id_rejected():
    led = AdjustmentLedger()
    led.add(_adj(adjustment_id="ADJ-1"))
    with pytest.raises(AdjustmentError, match="중복"):
        led.add(_adj(adjustment_id="ADJ-1"))


# ----- 직무분리 (SoD) --------------------------------------------------------

def test_sod_violation_blocks_application():
    led = AdjustmentLedger()
    led.add(_adj(requester="김OO", approver="김OO"))
    blocked = led.apply_all(ASOF)
    assert len(blocked) == 1 and "직무분리 위반" in blocked[0]
    assert led.applied() == []
    assert led.net_effect("ecl.ttc_total") == 0.0     # 수치 미반영


def test_sod_satisfied_applies():
    led = AdjustmentLedger()
    led.add(_adj(requester="김OO", approver="이OO"))
    assert led.apply_all(ASOF) == []
    assert len(led.applied()) == 1
    assert led.net_effect("ecl.ttc_total") == pytest.approx(1_000_000.0)


# ----- 중요성 임계 -----------------------------------------------------------

def test_material_adjustment_needs_senior_approval():
    led = AdjustmentLedger()
    big = _adj(base_value=1e12, adjusted_value=1e12 + MATERIALITY_ABS)
    led.add(big)
    blocked = led.apply_all(ASOF)
    assert "상위 승인 필요" in blocked[0]
    assert led.applied() == []


def test_material_with_senior_approval_applies():
    led = AdjustmentLedger()
    led.add(_adj(base_value=1e12, adjusted_value=1e12 + MATERIALITY_ABS,
                 senior_approval="CRO"))
    assert led.apply_all(ASOF) == []
    assert len(led.applied()) == 1


def test_unqualified_senior_approver_rejected():
    led = AdjustmentLedger()
    led.add(_adj(base_value=1e12, adjusted_value=1e12 + MATERIALITY_ABS,
                 senior_approval="팀장"))
    blocked = led.apply_all(ASOF)
    assert "상위 승인자 자격 미달" in blocked[0]


def test_materiality_uses_both_absolute_and_relative():
    """절대·상대 중 하나만 넘어도 중요 조정이다."""
    small_abs_big_rel = _adj(base_value=100.0,
                             adjusted_value=100.0 * (1 + MATERIALITY_REL * 2))
    assert small_abs_big_rel.is_material()
    big_abs_small_rel = _adj(base_value=1e15, adjusted_value=1e15 + MATERIALITY_ABS)
    assert big_abs_small_rel.rel_delta < MATERIALITY_REL
    assert big_abs_small_rel.is_material()


# ----- 유효기간 -------------------------------------------------------------

def test_expired_adjustment_is_blocked_and_marked():
    led = AdjustmentLedger()
    led.add(_adj(expires_on="2026-01-31"))
    blocked = led.apply_all(ASOF)
    assert "유효기간 만료" in blocked[0]
    assert led.adjustments[0].status == "expired"
    assert led.net_effect("ecl.ttc_total") == 0.0


def test_adjustment_valid_on_expiry_date_itself():
    """만료일 당일은 아직 유효 (경계)."""
    a = _adj(expires_on=ASOF)
    assert not a.is_expired(ASOF)
    assert a.is_expired("2026-06-12")


# ----- 적용·집계 -------------------------------------------------------------

def test_only_applied_adjustments_affect_values():
    led = AdjustmentLedger()
    led.add(_adj(adjustment_id="OK", requester="A", approver="B"))
    led.add(_adj(adjustment_id="BAD", requester="C", approver="C",
                 adjusted_value=2_000_000_000.0))
    led.apply_all(ASOF)
    base = 1_000_000_000.0
    # 통과분(+100만)만 반영, 차단분(+10억)은 무시
    assert led.adjusted("ecl.ttc_total", base) == pytest.approx(base + 1_000_000.0)


def test_rejected_adjustments_stay_rejected():
    led = AdjustmentLedger()
    led.add(_adj(status="rejected"))
    led.apply_all(ASOF)
    assert led.adjustments[0].status == "rejected"
    assert led.applied() == []


# ----- 재현성 지문 -----------------------------------------------------------

def test_fingerprint_changes_with_content_and_status():
    led = AdjustmentLedger()
    led.add(_adj(requester="A", approver="B"))
    before = led.fingerprint()
    led.apply_all(ASOF)                      # status pending → applied
    assert led.fingerprint() != before, "승인 전후 지문이 같으면 구분 불가"

    other = AdjustmentLedger()
    other.add(_adj(requester="A", approver="B", adjusted_value=1_002_000_000.0))
    other.apply_all(ASOF)
    assert other.fingerprint() != led.fingerprint()


def test_fingerprint_is_order_independent():
    a, b = AdjustmentLedger(), AdjustmentLedger()
    x = _adj(adjustment_id="ADJ-1", requester="A", approver="B")
    y = _adj(adjustment_id="ADJ-2", requester="A", approver="B")
    a.add(x); a.add(y)
    b.add(_adj(adjustment_id="ADJ-2", requester="A", approver="B"))
    b.add(_adj(adjustment_id="ADJ-1", requester="A", approver="B"))
    assert a.fingerprint() == b.fingerprint()


def test_empty_ledger_fingerprint_is_stable():
    assert AdjustmentLedger().fingerprint() == AdjustmentLedger().fingerprint()


def test_json_roundtrip(tmp_path):
    led = AdjustmentLedger()
    led.add(_adj(requester="A", approver="B"))
    led.apply_all(ASOF)
    p = led.export_json(tmp_path / "adj.json")
    back = AdjustmentLedger.load(p)
    assert back.fingerprint() == led.fingerprint()
    assert len(back.applied()) == 1


# ----- 대사 -----------------------------------------------------------------

def test_reconcile_detects_unrecorded_adjustment():
    led = AdjustmentLedger()
    led.add(_adj(requester="A", approver="B"))
    led.apply_all(ASOF)
    engine = {"ecl.ttc_total": 1_000_000_000.0}
    honest = {"ecl.ttc_total": 1_001_000_000.0}          # 원장과 일치
    tampered = {"ecl.ttc_total": 1_005_000_000.0}        # 원장에 없는 +400만

    ok = reconcile(led, engine, honest)
    assert bool(ok.iloc[0]["reconciles"]) is True
    assert unrecorded_adjustments(ok).empty

    bad = reconcile(led, engine, tampered)
    assert bool(bad.iloc[0]["reconciles"]) is False
    assert bad.iloc[0]["residual"] == pytest.approx(4_000_000.0)
    assert list(unrecorded_adjustments(bad)["figure_id"]) == ["ecl.ttc_total"]


def test_unreconciled_is_not_reported_as_pass():
    """보고값을 주지 않으면 '대사 통과'가 아니라 미대사(pd.NA)여야 한다."""
    import pandas as pd
    led = AdjustmentLedger()
    rec = reconcile(led, {"ecl.ttc_total": 1.0})
    assert pd.isna(rec.iloc[0]["reconciles"])
    assert unrecorded_adjustments(rec).empty      # NA는 위반으로 세지 않는다


# ----- manifest 연동 ---------------------------------------------------------

def test_manifest_records_ledger_fingerprint(result, portfolio):
    from datetime import datetime, timezone
    from risk_lib.repro import build_manifest
    now = datetime.now(timezone.utc)
    led = demo_ledger(result, asof=ASOF)

    without = build_manifest(portfolio=portfolio, parameters={"seed": 42},
                             result=result, start_utc=now, end_utc=now)
    with_adj = build_manifest(portfolio=portfolio, parameters={"seed": 42},
                              result=result, start_utc=now, end_utc=now,
                              adjustment_ledger=led)
    # '조정 없음'과 '조정 있음'이 구분되어야 한다
    assert without.parameters["adjustment_fingerprint"] == "none"
    assert with_adj.parameters["adjustment_fingerprint"] == led.fingerprint()
    assert with_adj.parameters["adjustments_applied"] == len(led.applied())


# ----- 데모 원장 · 보고서 -----------------------------------------------------

def test_demo_ledger_shows_both_pass_and_block(result):
    led = demo_ledger(result, asof=ASOF)
    assert len(led.adjustments) == 4
    assert len(led.applied()) == 2, "통과 사례가 있어야 통제 작동을 보인다"
    blocked = [a for a in led.adjustments if a.status != "applied"]
    assert len(blocked) == 2, "차단 사례가 있어야 통제가 실재함을 보인다"


def test_adjustment_page_renders_blocked_reasons(result):
    from risk_lib.ops_pages.governance import page_manual_adjustments
    html = page_manual_adjustments(result)
    assert "수동조정 원장" in html
    assert "직무분리" in html
    # 차단 사유가 숨겨지지 않고 노출돼야 한다
    assert "직무분리 위반" in html
    assert "상위 승인 필요" in html


def test_adjustment_page_registered():
    from risk_lib.page_registry import PAGES
    specs = [p for p in PAGES if p.filename == "65_manual_adjustments.html"]
    assert len(specs) == 1
    assert callable(specs[0].resolve())


def test_coverage_marks_dat006_covered():
    from risk_lib import rynta
    df = rynta.coverage_frame().set_index("id")
    assert df.loc["DAT-006", "status"] == "covered"
    assert "adjustments" in df.loc["DAT-006", "modules"]
