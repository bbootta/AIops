#!/usr/bin/env python3
"""Validate generated validation output artifacts.

The test validates file presence and package structure only. It does not inspect
or calculate risk metrics.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "outputs"
SAMPLE_PATH = ROOT / "samples" / "risk_domain_samples.json"

EXPECTED_REPORT_STEMS = ["practitioner_report", "executive_report"]
EXPECTED_REPORT_EXTENSIONS = ["md", "html", "hwpx", "pdf"]
EXPECTED_XLSX_SHEETS = ["README", "Case_Register", "Evidence_Gaps", "Action_Notices", "Audit_Trail", "Reproducibility", "Explainability"]
EXPECTED_VALIDATION_OBJECT_TYPES = [
    "credit_rating_model",
    "credit_risk_parameter",
    "risk_factor_validation",
    "aggregation_reporting",
    "hybrid_risk_output",
]
REQUIRED_NOTICE_PHRASES = ["최종 승인", "수치 계산", "재현가능성", "설명가능성"]
FINGERPRINT_FIELDS = [
    "request_type",
    "validation_object_type",
    "risk_output_domain",
    "primary_risk_output_domain",
    "secondary_risk_output_domains",
    "scope_statement",
    "policy_reference",
    "regulatory_source_reference",
    "calculation_engine_result_reference",
]


RISK_DOMAIN_ALIASES = {
    "credit_risk": "credit_risk",
    "credit risk": "credit_risk",
    "credit-risk": "credit_risk",
    "신용리스크": "credit_risk",
    "신용 위험": "credit_risk",
    "market_risk": "market_risk",
    "market risk": "market_risk",
    "market-risk": "market_risk",
    "시장리스크": "market_risk",
    "시장 위험": "market_risk",
    "operational_risk": "operational_risk",
    "operational risk": "operational_risk",
    "operational-risk": "operational_risk",
    "운영리스크": "operational_risk",
    "interest_rate_risk": "interest_rate_risk",
    "interest rate risk": "interest_rate_risk",
    "interest-rate-risk": "interest_rate_risk",
    "irrbb": "interest_rate_risk",
    "금리리스크": "interest_rate_risk",
    "liquidity_risk": "liquidity_risk",
    "liquidity risk": "liquidity_risk",
    "liquidity-risk": "liquidity_risk",
    "유동성리스크": "liquidity_risk",
    "strategic_risk": "strategic_risk",
    "strategic risk": "strategic_risk",
    "strategic-risk": "strategic_risk",
    "전략리스크": "strategic_risk",
    "reputational_risk": "reputational_risk",
    "reputational risk": "reputational_risk",
    "reputational-risk": "reputational_risk",
    "평판리스크": "reputational_risk",
    "capital_adequacy_aggregation": "capital_adequacy_aggregation",
    "capital adequacy aggregation": "capital_adequacy_aggregation",
    "capital-adequacy-aggregation": "capital_adequacy_aggregation",
    "자본적정성 집계": "capital_adequacy_aggregation",
    "multi_risk_or_unclear": "multi_risk_or_unclear",
    "multi risk or unclear": "multi_risk_or_unclear",
    "multi-risk-or-unclear": "multi_risk_or_unclear",
    "복합 불명확": "multi_risk_or_unclear",
}
RISK_DOMAIN_FIELDS = {"risk_output_domain", "primary_risk_output_domain", "secondary_risk_output_domains"}


def normalize_risk_domain(value: object) -> object:
    if not isinstance(value, str):
        return value
    key = " ".join(value.strip().lower().replace("_", " ").replace("-", " ").split())
    compact = key.replace(" ", "")
    return RISK_DOMAIN_ALIASES.get(value.strip(), RISK_DOMAIN_ALIASES.get(key, RISK_DOMAIN_ALIASES.get(compact, value.strip())))


def canonicalize_field(field: str, value: object) -> object:
    if isinstance(value, list):
        values = [normalize_risk_domain(item) if field in RISK_DOMAIN_FIELDS else item for item in value]
        return sorted(dict.fromkeys(values))
    if field in RISK_DOMAIN_FIELDS:
        return normalize_risk_domain(value)
    if isinstance(value, str):
        return " ".join(value.strip().split())
    return value


def fingerprint(sample: dict[str, object]) -> str:
    payload = {field: canonicalize_field(field, sample.get(field)) for field in FINGERPRINT_FIELDS}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def assert_zip_contains(path: Path, members: list[str]) -> None:
    assert zipfile.is_zipfile(path), f"{path} must be a zip package"
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
    missing = [member for member in members if member not in names]
    assert not missing, f"{path} missing members: {missing}"


def validate_xlsx(sample_count: int, path: Path | None = None) -> None:
    if path is None:
        path = OUTPUT_DIR / "validation_workbook.xlsx"
    assert_zip_contains(path, ["xl/workbook.xml", "xl/worksheets/sheet1.xml", "xl/worksheets/sheet2.xml"])
    with zipfile.ZipFile(path) as zf:
        workbook_xml = zf.read("xl/workbook.xml").decode("utf-8")
        case_sheet_xml = zf.read("xl/worksheets/sheet2.xml").decode("utf-8")
        reproducibility_sheet_xml = zf.read("xl/worksheets/sheet6.xml").decode("utf-8")
        explainability_sheet_xml = zf.read("xl/worksheets/sheet7.xml").decode("utf-8")
    for sheet in EXPECTED_XLSX_SHEETS:
        assert f'name="{sheet}"' in workbook_xml, f"Workbook missing sheet {sheet}"
    assert case_sheet_xml.count("<row ") == sample_count + 1, "Case_Register row count must match samples plus header"
    assert "case_fingerprint" in case_sheet_xml and "decision_stage" in case_sheet_xml
    assert reproducibility_sheet_xml.count("<row ") == sample_count + 1
    assert explainability_sheet_xml.count("<row ") == sample_count + 1


def validate_reports(output_dir: Path = OUTPUT_DIR) -> None:
    for stem in EXPECTED_REPORT_STEMS:
        for ext in EXPECTED_REPORT_EXTENSIONS:
            path = output_dir / f"{stem}.{ext}"
            assert path.exists() and path.stat().st_size > 0, f"Missing or empty artifact: {path}"
        md = (output_dir / f"{stem}.md").read_text(encoding="utf-8")
        html = (output_dir / f"{stem}.html").read_text(encoding="utf-8")
        for phrase in REQUIRED_NOTICE_PHRASES:
            assert phrase in md, f"{stem}.md missing phrase: {phrase}"
        assert "문서번호" in md and "시행일자" in md and "수신" in md, f"{stem}.md must use public memo fields"
        assert "<html" in html and "문서번호" in html, f"{stem}.html must be valid-looking HTML memo"
        assert "|---|" not in html, f"{stem}.html must not render markdown separator rows as text"
        assert_zip_contains(output_dir / f"{stem}.hwpx", ["mimetype", "version.xml", "Contents/content.hpf", "Contents/section0.xml"])
        pdf_bytes = (output_dir / f"{stem}.pdf").read_bytes()
        assert pdf_bytes.startswith(b"%PDF-"), f"{stem}.pdf missing PDF header"
        assert pdf_bytes.rstrip().endswith(b"%%EOF"), f"{stem}.pdf missing EOF marker"


def validate_manifest(samples: list[dict[str, object]]) -> None:
    manifest_path = OUTPUT_DIR / "artifact_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["document_number"].startswith("리스크감리-양검-"), "manifest document number mismatch"
    expected_artifact_count = len(EXPECTED_REPORT_STEMS) * len(EXPECTED_REPORT_EXTENSIONS) + 1
    expected_artifact_count += 1 + len(EXPECTED_VALIDATION_OBJECT_TYPES) * (len(EXPECTED_REPORT_STEMS) * len(EXPECTED_REPORT_EXTENSIONS) + 1)
    assert len(manifest["artifacts"]) == expected_artifact_count, "manifest must list integrated package plus 1-axis packages"
    assert set(manifest["axis_packages"]) == {"_summary", *EXPECTED_VALIDATION_OBJECT_TYPES}
    expected_fingerprints = {str(sample["case_id"]): fingerprint(sample) for sample in samples}
    assert manifest["sample_fingerprints"] == expected_fingerprints
    assert all(len(value) == 64 for value in manifest["sample_fingerprints"].values())
    assert set(manifest["explainability_index"]) == set(manifest["sample_fingerprints"])
    assert manifest["fingerprint_fields"] == FINGERPRINT_FIELDS
    for artifact in manifest["artifacts"]:
        assert (ROOT / artifact).exists(), f"manifest references missing artifact {artifact}"


def validate_axis_packages(samples: list[dict[str, object]]) -> None:
    base_dir = OUTPUT_DIR / "by_validation_object_type"
    summary = base_dir / "README.md"
    assert summary.exists() and "1축(validation_object_type)" in summary.read_text(encoding="utf-8")
    for object_type in EXPECTED_VALIDATION_OBJECT_TYPES:
        object_samples = [sample for sample in samples if sample["validation_object_type"] == object_type]
        object_dir = base_dir / object_type
        assert object_samples, f"Missing sample for {object_type}"
        assert object_dir.exists(), f"Missing 1-axis output directory for {object_type}"
        validate_xlsx(len(object_samples), object_dir / "validation_workbook.xlsx")
        validate_reports(object_dir)
        practitioner_md = (object_dir / "practitioner_report.md").read_text(encoding="utf-8")
        assert object_type in practitioner_md, f"{object_type} report must contain its validation_object_type"


def main() -> None:
    samples = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))["samples"]
    validate_xlsx(len(samples))
    validate_reports()
    validate_axis_packages(samples)
    validate_manifest(samples)
    print("validated output artifacts: xlsx, md, html, hwpx, pdf")


if __name__ == "__main__":
    main()

