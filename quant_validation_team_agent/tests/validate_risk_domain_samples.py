#!/usr/bin/env python3
"""Validate risk-output-domain UAT sample data.

This test intentionally performs no risk metric calculation. It checks that the
sample pack is complete, deterministic, and aligned with the operational
package's allowed labels and risk-output-domain taxonomy.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PATH = ROOT / "samples" / "risk_domain_samples.json"

ALLOWED_DOMAINS = {
    "credit_risk",
    "market_risk",
    "operational_risk",
    "interest_rate_risk",
    "liquidity_risk",
    "strategic_risk",
    "reputational_risk",
    "capital_adequacy_aggregation",
    "multi_risk_or_unclear",
}

ALLOWED_VALIDATION_OBJECT_TYPES = {
    "credit_rating_model",
    "credit_risk_parameter",
    "risk_factor_validation",
    "aggregation_reporting",
    "hybrid_risk_output",
}

ALLOWED_JUDGEMENTS = {"Green", "Yellow", "Red", "Gray"}
GRAY_REASON_CODES = {
    "POLICY_UNDEFINED",
    "DATA_INSUFFICIENT",
    "SAMPLE_INSUFFICIENT",
    "ACCESS_LIMITED",
    "LINEAGE_UNCLEAR",
    "EVIDENCE_INSUFFICIENT",
}

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


def main() -> None:
    data = json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))
    samples = data["samples"]

    domains = {sample["risk_output_domain"] for sample in samples}
    missing_domains = ALLOWED_DOMAINS - domains
    extra_domains = domains - ALLOWED_DOMAINS
    assert not missing_domains, f"Missing sample domains: {sorted(missing_domains)}"
    assert not extra_domains, f"Unexpected sample domains: {sorted(extra_domains)}"

    object_types = {sample["validation_object_type"] for sample in samples}
    missing_object_types = ALLOWED_VALIDATION_OBJECT_TYPES - object_types
    assert not missing_object_types, f"Missing validation object type samples: {sorted(missing_object_types)}"

    case_ids = [sample["case_id"] for sample in samples]
    request_ids = [sample["request_id"] for sample in samples]
    assert len(case_ids) == len(set(case_ids)), "case_id values must be unique"
    assert len(request_ids) == len(set(request_ids)), "request_id values must be unique"

    text_alias_sample = {
        "request_type": "validation",
        "validation_object_type": "hybrid_risk_output",
        "risk_output_domain": "금리리스크",
        "primary_risk_output_domain": "Interest Rate Risk",
        "secondary_risk_output_domains": ["시장리스크", "credit risk", "시장리스크"],
        "scope_statement": "IRRBB text alias normalization",
        "policy_reference": "POL-IRRBB-2026",
        "regulatory_source_reference": "KR-STRESS-ANNEX19",
        "calculation_engine_result_reference": "ENGINE-IRRBB-001",
    }
    code_sample = {
        **text_alias_sample,
        "risk_output_domain": "interest_rate_risk",
        "primary_risk_output_domain": "interest_rate_risk",
        "secondary_risk_output_domains": ["credit_risk", "market_risk"],
    }
    assert fingerprint(text_alias_sample) == fingerprint(code_sample), "text aliases must normalize before fingerprinting to avoid false Gray"

    fingerprints: dict[str, str] = {}
    for sample in samples:
        domain = sample["risk_output_domain"]
        judgement = sample["expected_provisional_judgement"]
        action_required = sample["expected_action_notice_required"]
        gray_reason = sample["expected_gray_reason_code"]

        assert sample["validation_object_type"] in ALLOWED_VALIDATION_OBJECT_TYPES
        assert domain in ALLOWED_DOMAINS
        assert sample["primary_risk_output_domain"] in ALLOWED_DOMAINS
        assert all(item in ALLOWED_DOMAINS for item in sample["secondary_risk_output_domains"])
        assert judgement in ALLOWED_JUDGEMENTS
        assert isinstance(sample["human_reviewer_required"], bool) and sample["human_reviewer_required"]
        assert sample["input_documents"], f"{sample['case_id']} must include input documents"
        assert sample["audit_trail_items"], f"{sample['case_id']} must include audit trail items"

        if judgement == "Green":
            assert action_required is False, f"Green sample {sample['case_id']} must not require Action Notice"
            assert gray_reason is None, f"Green sample {sample['case_id']} must not have Gray reason"
            assert not sample["evidence_gaps"], f"Green sample {sample['case_id']} must not have evidence gaps"
            assert sample["calculation_engine_result_reference"], f"Green sample {sample['case_id']} needs engine result"
        else:
            assert action_required is True, f"Non-Green sample {sample['case_id']} must require Action Notice"

        if judgement == "Gray":
            assert gray_reason in GRAY_REASON_CODES, f"Gray sample {sample['case_id']} needs valid reason code"
            assert sample["evidence_gaps"], f"Gray sample {sample['case_id']} must list evidence gaps"

        if domain == "multi_risk_or_unclear":
            assert judgement == "Gray", "multi_risk_or_unclear must remain Gray until ownership/policy is clarified"
            assert sample["secondary_risk_output_domains"], "multi-risk sample must list secondary domains"

        first = fingerprint(sample)
        second = fingerprint(dict(reversed(list(sample.items()))))
        assert first == second, f"Fingerprint must be stable for {sample['case_id']}"
        assert len(first) == 64 and all(char in "0123456789abcdef" for char in first)
        fingerprints[sample["case_id"]] = first

    assert len(set(fingerprints.values())) == len(fingerprints), "fingerprints must be unique across samples"
    print(f"validated {len(samples)} samples across {len(domains)} risk output domains")


if __name__ == "__main__":
    main()

