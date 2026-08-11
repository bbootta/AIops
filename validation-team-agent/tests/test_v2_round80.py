"""Round 80 — PRD-VAL 요건 커버리지 매트릭스 (근거 없는 구현 주장 차단)."""

from __future__ import annotations

import copy
import json

import pytest

from tools.val_coverage import (
    COVERAGE_PATH,
    VALID_STATUS,
    load,
    render_report,
    summarize,
    verify,
)


@pytest.fixture(scope="module")
def data():
    return load()


# ---------- SSoT 형태 ----------

def test_matrix_covers_all_18_requirements(data):
    ids = [r["id"] for r in data["requirements"]]
    assert ids == [f"VAL-{i:03d}" for i in range(1, 19)]


def test_every_requirement_has_phase_and_title(data):
    for r in data["requirements"]:
        assert r["title"].strip()
        assert r["phase"].strip()
        assert r["status"] in VALID_STATUS


def test_phases_match_asis_tobe_six_stages(data):
    phases = {r["phase"] for r in data["requirements"]}
    assert len(phases) == 6
    for p in phases:
        assert p[:2].isdigit(), p


# ---------- 핵심: 근거 실재성 강제 ----------

def test_current_matrix_verifies_clean(data):
    assert verify(data) == []


def test_all_evidence_paths_exist(data):
    from tools.val_coverage import ROOT

    for r in data["requirements"]:
        for e in r["evidence"]:
            assert (ROOT / e).exists(), f"{r['id']} 근거 부재: {e}"


def test_implemented_without_evidence_is_rejected(data):
    """근거 없이 '구현됨' 을 주장하면 검증이 실패해야 한다.

    규칙을 검증하는 테스트이므로 실제 매트릭스의 상태 분포에 의존하지 않는다
    (미구현 항목이 0 이 되어도 규칙 검증은 계속 성립해야 한다).
    """
    bad = copy.deepcopy(data)
    bad["requirements"][0].update(status="implemented", evidence=[],
                                  gap="근거 없는 구현 주장")
    problems = verify(bad)
    assert any("evidence 가 없다" in p for p in problems), problems


def test_nonexistent_evidence_is_rejected(data):
    """근거 파일이 사라지면 검증이 실패해야 한다 (문서 드리프트 차단)."""
    bad = copy.deepcopy(data)
    target = next(r for r in bad["requirements"] if r["status"] != "missing")
    target["evidence"] = ["tools/does_not_exist_xyz.py"]
    assert any("evidence 파일 부재" in p for p in verify(bad))


def test_missing_with_evidence_is_rejected(data):
    bad = copy.deepcopy(data)
    bad["requirements"][0].update(status="missing",
                                  evidence=["tools/val_coverage.py"],
                                  gap="미구현인데 근거 보유")
    assert any("evidence 가 있다" in p for p in verify(bad))


def test_partial_without_gap_is_rejected(data):
    bad = copy.deepcopy(data)
    target = next(r for r in bad["requirements"] if r["status"] == "partial")
    target["gap"] = "   "
    assert any("gap 서술이 없다" in p for p in verify(bad))


def test_dropped_requirement_is_rejected(data):
    """요건을 조용히 빼면 ID 불연속으로 잡힌다."""
    bad = copy.deepcopy(data)
    bad["requirements"] = [r for r in bad["requirements"] if r["id"] != "VAL-005"]
    assert any("불연속" in p for p in verify(bad))


def test_invalid_status_is_rejected(data):
    bad = copy.deepcopy(data)
    bad["requirements"][0]["status"] = "완료"
    assert any("잘못된 status" in p for p in verify(bad))


# ---------- 요약 ----------

def test_summary_counts_and_score(data):
    s = summarize(data)
    assert s["total"] == 18
    assert sum(s["counts"].values()) == 18
    # partial 은 0.5 가중 — 과대·과소 표기 방지
    expected = (s["counts"]["implemented"] + 0.5 * s["counts"]["partial"])
    assert s["coverage_score"] == pytest.approx(expected)
    assert 0 <= s["coverage_pct"] <= 100


def test_report_lists_gaps_for_missing(data):
    text = render_report(data)
    for r in data["requirements"]:
        if r["status"] == "missing":
            assert r["id"] in text
    assert "공백:" in text


# ---------- CLI / 카탈로그 ----------

def test_cli_verify_exit_zero():
    from tools.val_coverage import main

    assert main(["verify"]) == 0


def test_cli_report_json(capsys):
    from tools.val_coverage import main

    assert main(["report", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["total"] == 18


def test_coverage_file_is_valid_json():
    json.loads(COVERAGE_PATH.read_text(encoding="utf-8"))


def test_catalog_sync():
    from tools.cli_index import CLI_MODULES
    from vta.cli.__main__ import _DISPATCH

    assert "tools.val_coverage" in {m for m, _ in CLI_MODULES}
    assert ("coverage",) in _DISPATCH
