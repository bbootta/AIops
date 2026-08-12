"""전송 마스킹·전구간 로그 테스트 (AIG-006 · AIG-007).

각 통제가 위반 사례에서 실제로 발동하는지 확인한다. 마스킹 규칙은 실제 값을
잡아야 하고, 사슬은 변조와 삭제를 잡아야 하며, 차단 규칙은 본문을 남기지
않아야 한다.
"""

from __future__ import annotations

import pandas as pd
import pytest

from risk_lib.aig.trace import (
    AGENT_TRACE, REDACTION_RULE, TraceRecorder, build_redaction_rules,
    build_trace_from_activity, redact, verify_chain,
)
from risk_lib.datamodel.spec import validate

ASOF = "2026-06-11"
RUN = "RUN-TEST-001"


@pytest.fixture(scope="module")
def rules() -> pd.DataFrame:
    return build_redaction_rules()


def test_rule_ledger_validates_and_is_unique(rules):
    assert not validate(rules, REDACTION_RULE)
    assert len(rules) == len(rules["rule_code"].unique())


def test_masking_catches_identifiers_in_free_text(rules):
    text = ("차주 OBL_CORP_00042 담당자 kim@bank.co.kr 연락처 010-1234-5678 "
            "계좌 110-234-567890")
    out, hits, blocked = redact(text, rules, target="prompt")
    assert not blocked
    for token in ("OBL_CORP_00042", "kim@bank.co.kr", "010-1234-5678",
                  "110-234-567890"):
        assert token not in out
    assert {h.rule_code for h in hits} >= {"DLP-OBLIGOR", "DLP-EMAIL",
                                           "DLP-PHONE", "DLP-ACCT"}


def test_blocking_rule_reports_that_the_payload_must_not_be_sent(rules):
    out, hits, blocked = redact("주민번호 900101-1234567", rules, target="prompt")
    assert blocked
    assert "900101-1234567" not in out
    assert any(h.action == "차단" for h in hits)


def test_rule_order_in_the_ledger_decides_which_pattern_wins(rules):
    """전화번호와 계좌번호는 표기가 겹친다. 순서가 원장에 있어야 결과가 설명된다."""
    text = "연락처 010-1234-5678"
    _, hits, _ = redact(text, rules, target="prompt")
    assert {h.rule_code for h in hits} == {"DLP-PHONE"}

    swapped = rules.copy()
    phone = swapped.loc[swapped["rule_code"] == "DLP-PHONE", "seq"].iloc[0]
    acct = swapped.loc[swapped["rule_code"] == "DLP-ACCT", "seq"].iloc[0]
    swapped.loc[swapped["rule_code"] == "DLP-PHONE", "seq"] = acct
    swapped.loc[swapped["rule_code"] == "DLP-ACCT", "seq"] = phone
    _, hits2, _ = redact(text, swapped, target="prompt")
    assert {h.rule_code for h in hits2} == {"DLP-ACCT"}


def test_clean_text_is_untouched(rules):
    text = "기업 세그먼트 PD 보정 결과를 등급별로 비교한다"
    out, hits, blocked = redact(text, rules, target="prompt")
    assert out == text and not hits and not blocked


def test_blocked_payload_is_not_stored_in_the_log(rules):
    rec = TraceRecorder(run_id=RUN, asof=ASOF, rules=rules)
    row = rec.append(actor="조회 에이전트", phase="prompt", gate="대기",
                     prompt_text="차주 900101-1234567 의 등급을 조회",
                     prompt_source="사용자")
    assert row["prompt_text"] == "[BLOCKED]"
    assert row["gate"] == "차단"
    assert row["redaction_hits"] >= 1
    # 원본 지문은 남아 무엇이 들어왔는지 대조할 수 있다.
    assert len(row["raw_sha256"]) == 64
    assert row["raw_sha256"] != row["masked_sha256"]


def test_trace_frame_validates_against_its_spec(rules):
    rec = TraceRecorder(run_id=RUN, asof=ASOF, rules=rules)
    rec.append(actor="조회 에이전트", phase="prompt", gate="통과",
               prompt_text="세그먼트별 부도율을 보여줘", prompt_source="사용자")
    rec.append(actor="조회 에이전트", phase="tool_call", gate="통과",
               tool="정형조회", payload_text="table=crm_dev_sample")
    rec.append(actor="리스크관리부장", phase="approval", gate="대기")
    assert not validate(rec.frame(), AGENT_TRACE)


def test_chain_detects_a_modified_row(rules):
    rec = TraceRecorder(run_id=RUN, asof=ASOF, rules=rules)
    for i in range(5):
        rec.append(actor="조회 에이전트", phase="tool_call", gate="통과",
                   tool="정형조회", payload_text=f"step-{i}")
    df = rec.frame()
    assert verify_chain(df) is None
    tampered = df.copy()
    tampered.loc[2, "payload_text"] = "step-변조"
    tampered.loc[2, "masked_sha256"] = "0" * 64
    assert verify_chain(tampered) == 3


def test_chain_detects_a_deleted_row(rules):
    rec = TraceRecorder(run_id=RUN, asof=ASOF, rules=rules)
    for i in range(4):
        rec.append(actor="조회 에이전트", phase="output", gate="통과",
                   payload_text=f"out-{i}")
    df = rec.frame()
    shortened = df.drop(index=1).reset_index(drop=True)
    assert verify_chain(shortened) == 3


def test_recorder_is_deterministic(rules):
    def run() -> pd.DataFrame:
        rec = TraceRecorder(run_id=RUN, asof=ASOF, rules=rules)
        rec.append(actor="조회 에이전트", phase="prompt", gate="통과",
                   prompt_text="등급 분포", prompt_source="사용자")
        rec.append(actor="조회 에이전트", phase="output", gate="통과",
                   payload_text="17등급 분포")
        return rec.frame()
    pd.testing.assert_frame_equal(run(), run())


def test_unknown_phase_is_rejected(rules):
    rec = TraceRecorder(run_id=RUN, asof=ASOF, rules=rules)
    with pytest.raises(ValueError):
        rec.append(actor="a", phase="thinking", gate="통과")


def test_activity_rows_expand_into_two_phases_without_invented_prompts(rules):
    activity = pd.DataFrame([
        {"activity_id": "ACT-1", "run_id": RUN, "seq": 1,
         "actor": "신용리스크 에이전트", "tool": "정형조회",
         "output": "신용 검증 12건", "gate": "통과"},
        {"activity_id": "ACT-2", "run_id": RUN, "seq": 2,
         "actor": "리스크담당임원(CRO) 위임자", "tool": "승인 워크벤치",
         "output": "제출본 최종 확정", "gate": "대기"},
    ])
    t = build_trace_from_activity(activity, rules, asof=ASOF, run_id=RUN)
    assert len(t) == 2 * len(activity)
    assert t["prompt_text"].isna().all(), (
        "언어모형 호출이 없는 산출에 프롬프트 본문을 지어 넣으면 안 된다")
    assert (t["prompt_source"] == "없음(결정론 산출)").all()
    assert verify_chain(t) is None
    assert not validate(t, AGENT_TRACE)
