"""독립검증 응답 작성·검증 도구.

응답이 2선 게이트(check_gate)에서 거절될 사유를 3선이 먼저 잡는지 본다.
게이트가 거절하는 조건(run_id·request_id 불일치, 재계산 미보고, 불일치를
적합으로 넘김)마다 음성 통제를 둔다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import ivr_response as ivr

ROOT = Path(__file__).resolve().parent.parent
SAMPLE_REQUEST = ROOT.parent / "docs" / "independent_validation" / "RUN-20260630-42.request.json"

REQUEST = {
    "request_id": "IVR-0123456789AB",
    "run_id": "RUN-20260630-42",
    "recalc_targets": [
        {"key": "lcr", "korean": "LCR", "value": 1.18, "citation": "LCR20.1"},
        {"key": "cet1_ratio", "korean": "CET1", "value": 0.081, "citation": "규정 제26조"},
    ],
}


def _finding(fid="F-001", severity="경부적합", target="lcr", **kw):
    return {"finding_id": fid, "severity": severity, "target": target,
            "detail": "할인율 가정 문서화 미흡", **kw}


def _good():
    return ivr.build(REQUEST, matches={"lcr": True, "cet1_ratio": True},
                     findings=[_finding()], validated_at="2026-09-01T00:00:00+00:00")


def test_build_derives_the_verdict_from_findings():
    resp = _good()
    assert resp["verdict"] == "경부적합"
    assert ivr.violations(resp, REQUEST) == []
    assert ivr.derive_verdict([]) == "적합"
    assert ivr.derive_verdict([_finding(severity="중부적합"),
                               _finding("F-002")]) == "중부적합"


def test_response_matches_the_shape_the_gate_reads():
    """2선 ValidationResponse 의 필드와 정확히 같아야 read() 가 된다."""
    resp = _good()
    assert set(resp) == {"request_id", "run_id", "verdict", "validated_by",
                         "validated_at", "recalc_matches", "findings"}
    assert set(resp["findings"][0]) <= {"finding_id", "severity", "target",
                                        "detail", "recomputed", "reported"}


# ---- 음성 통제: 게이트가 거절하는 조건마다 하나씩

def test_missing_recalc_target_is_a_violation():
    with pytest.raises(ValueError, match="재계산 미보고 1/2건: cet1_ratio"):
        ivr.build(REQUEST, matches={"lcr": True}, findings=[])


def test_unrequested_target_is_a_violation():
    resp = _good()
    resp["recalc_matches"]["nsfr"] = True
    assert any("요청에 없는 재계산 대상: nsfr" in v for v in ivr.violations(resp, REQUEST))


def test_run_id_and_request_id_must_match():
    resp = _good()
    other = {**REQUEST, "run_id": "RUN-20260331-42", "request_id": "IVR-FFFFFFFFFFFF"}
    bad = ivr.violations(resp, other)
    assert any("run_id 불일치" in v for v in bad)
    assert any("request_id 불일치" in v for v in bad)


def test_hand_written_verdict_that_contradicts_findings_is_a_violation():
    resp = _good()
    resp["verdict"] = "적합"          # 경부적합 지적이 있는데 적합이라 적음
    assert any("파생된 값 경부적합" in v for v in ivr.violations(resp, REQUEST))


def test_mismatch_without_a_major_finding_is_a_violation():
    """재계산이 어긋났는데 지적이 없으면 불일치를 조용히 넘기는 응답이다."""
    resp = _good()
    resp["recalc_matches"]["cet1_ratio"] = False
    assert any("재계산 불일치 cet1_ratio 를 설명하는 중부적합 지적이 없다" in v
               for v in ivr.violations(resp, REQUEST))
    resp["findings"].append(_finding("F-002", "중부적합", "cet1_ratio",
                                     recomputed=0.079, reported=0.081))
    resp["verdict"] = "중부적합"
    assert ivr.violations(resp, REQUEST) == []


def test_duplicate_finding_ids_are_a_violation():
    resp = _good()
    resp["findings"].append(_finding("F-001"))
    assert any("finding_id 중복: F-001" in v for v in ivr.violations(resp, REQUEST))


def test_numeric_finding_must_point_at_a_requested_target():
    resp = _good()
    resp["findings"].append(_finding("F-002", target="nsfr", recomputed=1.0, reported=1.0))
    assert any("요청 대상이 아니다" in v for v in ivr.violations(resp, REQUEST))


def test_schema_rejects_unknown_severity_and_extra_fields():
    resp = _good()
    resp["findings"][0]["severity"] = "부적합"
    assert any(v.startswith("스키마") for v in ivr.violations(resp, REQUEST))
    resp = _good()
    resp["note"] = "extra"
    assert any(v.startswith("스키마") for v in ivr.violations(resp, REQUEST))


# ---- 실제 교환 파일과 CLI

@pytest.mark.skipif(not SAMPLE_REQUEST.exists(), reason="교환 디렉터리 없음")
def test_committed_response_is_validated_against_its_request():
    request = json.loads(SAMPLE_REQUEST.read_text(encoding="utf-8"))
    keys = ivr.request_target_keys(request)
    resp = ivr.build(request, matches={k: True for k in keys}, findings=[])
    assert resp["verdict"] == "적합"
    assert len(resp["recalc_matches"]) == len(keys)


def test_cli_validate_exits_nonzero_on_violation(tmp_path, capsys):
    req = tmp_path / "r.request.json"
    req.write_text(json.dumps(REQUEST, ensure_ascii=False), encoding="utf-8")
    resp = _good()
    del resp["recalc_matches"]["cet1_ratio"]
    rp = tmp_path / "r.response.json"
    rp.write_text(json.dumps(resp, ensure_ascii=False), encoding="utf-8")
    assert ivr.main(["validate", "--request", str(req), "--response", str(rp)]) == 1
    assert "재계산 미보고" in capsys.readouterr().out


def test_cli_build_writes_a_valid_response(tmp_path):
    req = tmp_path / "r.request.json"
    req.write_text(json.dumps(REQUEST, ensure_ascii=False), encoding="utf-8")
    out = tmp_path / "r.response.json"
    rc = ivr.main(["build", "--request", str(req),
                   "--matches", '{"lcr": true, "cet1_ratio": true}',
                   "--out", str(out)])
    assert rc == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["verdict"] == "적합"
    assert ivr.main(["validate", "--request", str(req), "--response", str(out)]) == 0
