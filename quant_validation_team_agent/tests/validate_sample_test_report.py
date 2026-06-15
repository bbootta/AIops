#!/usr/bin/env python3
"""Validate the full sample test HTML report."""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "outputs" / "sample_test_report.html"
SAMPLE_PATH = ROOT / "samples" / "risk_domain_samples.json"

REQUIRED_TEXT = [
    "전체 샘플 테스트 상세 결과 보고서",
    "종합 상태",
    "PASS",
    "케이스별 상세 검증 결과",
    "case_fingerprint",
    "decision_stage",
    "explanation_summary",
    "validate_output_artifacts.py",
    "validate_risk_domain_samples.py",
]


def main() -> None:
    assert REPORT_PATH.exists() and REPORT_PATH.stat().st_size > 0, "sample test HTML report is missing"
    html = REPORT_PATH.read_text(encoding="utf-8")
    for text in REQUIRED_TEXT:
        assert text in html, f"sample test HTML report missing text: {text}"
    samples = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))["samples"]
    for sample in samples:
        assert sample["case_id"] in html, f"sample test HTML report missing case {sample['case_id']}"
    print(f"validated sample test HTML report for {len(samples)} samples")


if __name__ == "__main__":
    main()
