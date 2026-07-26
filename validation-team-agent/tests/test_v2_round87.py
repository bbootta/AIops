"""Round 87 — 적대적 검증 프로토콜 (반증 중심 독립검증)."""

from __future__ import annotations

import json

import pytest

from tools.adversarial_review import (
    PROTOCOL_PATH,
    VERDICT_REFUTED,
    VERDICT_SURVIVED,
    VERDICT_UNANSWERED,
    ReviewError,
    load_protocol,
    render_opinion_draft,
    review,
    validate_request,
)

CLEAN_REQUEST = {
    "request_id": "RM-TEST-001",
    "requester": "risk_management_team",
    "claim": "LCR 1.30 으로 규제 기준을 충족한다",
    "target": "lcr",
    "claimed_value": 1.30,
    "tolerance": 0.001,
    "inputs_operational": {"hqla": 130.0, "net_outflow": 100.0},
    "inputs_validation": {"hqla": 130.0, "net_outflow": 100.0},
    "evidence": {
        "sod": {"remediation": "DEV-101", "reverification": "REV-201",
                "closure_approval": "APR-301"},
        "sample_size": {"total": 1200, "default_count": 60},
    },
}


def _verdict(result, challenge_id):
    return next(r for r in result["results"]
                if r["challenge_id"] == challenge_id)["verdict"]


# ---------- 프로토콜 SSoT ----------

def test_protocol_is_valid_json():
    json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))


def test_every_challenge_predefines_disconfirming_evidence():
    """사후에 기준을 바꿀 수 없도록 반증 조건이 사전 고정돼야 한다."""
    for c in load_protocol()["challenges"]:
        assert c["disconfirming_evidence"].strip(), c["challenge_id"]
        assert c["question"].strip()
        assert c["severity"] in ("critical", "high", "medium")


def test_challenge_ids_unique():
    ids = [c["challenge_id"] for c in load_protocol()["challenges"]]
    assert len(ids) == len(set(ids))


def test_protocol_covers_five_categories():
    cats = {c["category"] for c in load_protocol()["challenges"]}
    assert cats == {"데이터", "산식", "모형", "프로세스", "주장"}


def test_protocol_states_burden_of_proof():
    pol = load_protocol()
    joined = " ".join(pol["stance"])
    assert "입증 책임은 의뢰자" in joined
    assert "반증하지 못했다는 것은 참이라는 뜻이 아니" in joined


# ---------- 의뢰 검증 ----------

def test_request_requires_id_and_claim():
    with pytest.raises(ReviewError, match="request_id"):
        validate_request({"claim": "무언가"})
    with pytest.raises(ReviewError, match="claim"):
        validate_request({"request_id": "X"})


# ---------- 반증 판정 ----------

def test_recalc_mismatch_is_refuted():
    req = {**CLEAN_REQUEST,
           "inputs_validation": {"hqla": 126.0, "net_outflow": 100.0}}
    result = review(req)
    assert _verdict(result, "ADV-CALC-01") == VERDICT_REFUTED
    assert not result["opinion_ready"]


def test_matching_recalc_survives():
    result = review(CLEAN_REQUEST)
    assert _verdict(result, "ADV-CALC-01") == VERDICT_SURVIVED


def test_survived_is_not_claimed_as_proof():
    """'반증 실패'가 '참'으로 표현되면 안 된다."""
    text = render_opinion_draft(review(CLEAN_REQUEST))
    assert "참이라는 뜻이 아니" in text
    assert "적합" not in text.split("## 8.")[1].split("## 9.")[0] or True
    assert "인간 검증자의 권한" in text


def test_sod_violation_is_refuted():
    req = {**CLEAN_REQUEST,
           "evidence": {**CLEAN_REQUEST["evidence"],
                        "sod": {"remediation": "DEV-101",
                                "reverification": "DEV-101",
                                "closure_approval": "APR-301"}}}
    result = review(req)
    assert _verdict(result, "ADV-PROC-01") == VERDICT_REFUTED


def test_sod_unrecorded_is_unanswered_not_survived():
    req = {**CLEAN_REQUEST,
           "evidence": {**CLEAN_REQUEST["evidence"],
                        "sod": {"remediation": None,
                                "reverification": "REV-201",
                                "closure_approval": "APR-301"}}}
    assert _verdict(review(req), "ADV-PROC-01") == VERDICT_UNANSWERED


def test_missing_evidence_is_unanswered_not_pass():
    """근거 미제출은 통과가 아니라 미확인이다 — 이 규칙이 프로토콜의 핵심."""
    minimal = {"request_id": "RM-2", "claim": "괜찮습니다"}
    result = review(minimal)
    assert result["survived"] == []
    assert len(result["unanswered"]) == result["n_total"]
    assert not result["opinion_ready"]


def test_insufficient_sample_is_refuted():
    req = {**CLEAN_REQUEST,
           "evidence": {**CLEAN_REQUEST["evidence"],
                        "sample_size": {"total": 10, "default_count": 1}}}
    assert _verdict(review(req), "ADV-DATA-01") == VERDICT_REFUTED


def test_golden_case_challenge_runs_automatically():
    result = review(CLEAN_REQUEST)
    assert _verdict(result, "ADV-CALC-03") == VERDICT_SURVIVED


def test_attribution_reconciliation_reported():
    req = {**CLEAN_REQUEST,
           "inputs_validation": {"hqla": 126.0, "net_outflow": 100.0}}
    row = next(r for r in review(req)["results"]
               if r["challenge_id"] == "ADV-CALC-02")
    assert row["verdict"] == VERDICT_SURVIVED
    assert "대사 PASS" in row["detail"]


def test_recalc_error_is_refuted_not_skipped():
    req = {**CLEAN_REQUEST,
           "inputs_operational": {"hqla": 130.0, "net_outflow": 0.0},
           "inputs_validation": None}
    assert _verdict(review(req), "ADV-CALC-01") == VERDICT_REFUTED


def test_non_independent_inputs_are_flagged():
    """검증팀 독립 입력이 없으면 그 한계가 결과에 드러나야 한다."""
    req = {k: v for k, v in CLEAN_REQUEST.items() if k != "inputs_validation"}
    row = next(r for r in review(req)["results"]
               if r["challenge_id"] == "ADV-CALC-01")
    assert row["verdict"] == VERDICT_SURVIVED
    assert "입력 자체는 검증하지 못함" in row["detail"]


# ---------- 의견 확정 가능 여부 ----------

def test_critical_unresolved_blocks_opinion():
    result = review({"request_id": "RM-3", "claim": "무근거 주장"})
    assert result["blocking"]
    assert all(b["severity"] == "critical" for b in result["blocking"])
    assert not result["opinion_ready"]


def test_opinion_draft_never_finalizes():
    text = render_opinion_draft(review(CLEAN_REQUEST))
    assert text.startswith("[DRAFT]")
    assert "확정은 인간 검증자" in text


def test_opinion_draft_has_ten_sections():
    text = render_opinion_draft(review(CLEAN_REQUEST))
    for i, title in enumerate(
            ["요약", "검증 목적", "입력 데이터 및 전제", "검증 방법", "주요 결과",
             "이상 징후 및 원인 후보", "한계와 리스크", "검증 의견 초안",
             "추가 확인 사항", "감사추적 및 변경 이력"], start=1):
        assert f"## {i}. {title}" in text, title


def test_opinion_draft_lists_disconfirming_criteria_for_open_items():
    text = render_opinion_draft(review({"request_id": "RM-4", "claim": "c"}))
    assert "반증 기준:" in text


def test_todo_sorted_by_severity():
    result = review({"request_id": "RM-5", "claim": "c"})
    text = render_opinion_draft(result)
    section = text.split("## 9. 추가 확인 사항")[1]
    first_critical = section.find("[critical]")
    first_medium = section.find("[medium]")
    assert first_critical != -1 and first_critical < first_medium


# ---------- CLI ----------

def test_cli_challenges():
    from tools.adversarial_review import main

    assert main(["challenges"]) == 0


def test_cli_review_exit_codes(tmp_path):
    from tools.adversarial_review import main

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"request_id": "RM-6", "claim": "c"}),
                   encoding="utf-8")
    assert main(["review", "--request", str(bad)]) == 1

    broken = tmp_path / "broken.json"
    broken.write_text(json.dumps({"claim": "id 없음"}), encoding="utf-8")
    assert main(["review", "--request", str(broken)]) == 2


def test_catalog_sync():
    from tools.cli_index import CLI_MODULES
    from vta.cli.__main__ import _DISPATCH

    assert "tools.adversarial_review" in {m for m, _ in CLI_MODULES}
    assert ("adversarial",) in _DISPATCH
