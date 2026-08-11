"""data_safety_guard 가 raw PII 를 절대 반환하지 않는지 검증한다."""

from __future__ import annotations

import pandas as pd

from middleware import data_safety_guard as dsg


# 알려진 형식의 가짜 PII (실제 인물 정보 아님).
RRN = "900101-1234567"
EMAIL = "test.user@example.com"
PHONE = "010-1234-5678"


def _findings_contain_raw(findings, *raw_values) -> bool:
    """findings 의 어떤 dict 표현에도 raw PII 가 포함되어 있는지 검사."""
    blob = repr(findings)
    return any(v in blob for v in raw_values)


def _partial_in_findings(findings, *raw_values, n: int = 6) -> bool:
    """findings 에 raw PII 의 앞 n 글자(부분 마스킹) 가 포함되어 있는지."""
    blob = repr(findings)
    return any(v[:n] in blob for v in raw_values)


def test_scan_text_returns_no_raw_pii():
    text = f"고객 {EMAIL} 의 RRN 은 {RRN} 입니다."
    findings = dsg.scan_text(text)
    assert findings, "expected PII findings"
    assert not _findings_contain_raw(findings, EMAIL, RRN)
    # 부분 마스킹(앞 6자리) 도 노출되어선 안 된다 — RRN 의 YYMMDD 는 PII.
    assert not _partial_in_findings(findings, RRN)


def test_scan_text_shape():
    findings = dsg.scan_text(f"call me at {PHONE}")
    assert findings, "expected phone PII"
    f = findings[0]
    assert set(f.keys()) == {"category", "span", "length"}
    assert f["category"] == "phone_kr"
    assert isinstance(f["span"], list) and len(f["span"]) == 2
    assert f["length"] == f["span"][1] - f["span"][0]
    assert "matched" not in f


def test_scan_dataframe_returns_no_raw_pii():
    df = pd.DataFrame(
        {
            "memo": [
                f"RRN={RRN}",
                f"mail={EMAIL}",
                "no pii here",
            ]
        }
    )
    out = dsg.scan_dataframe(df)
    assert out["clean"] is False
    assert out["findings"], "expected findings"
    assert not _findings_contain_raw(out["findings"], RRN, EMAIL)
    # 부분 마스킹된 RRN 의 YYMMDD 도 절대 노출 금지.
    assert not _partial_in_findings(out["findings"], RRN, EMAIL)


def test_scan_dataframe_finding_shape_and_hash():
    df = pd.DataFrame({"memo": [f"RRN={RRN}"]})
    out = dsg.scan_dataframe(df, salt=b"fixed-salt-for-test")
    assert out["findings"]
    f = out["findings"][0]
    assert set(f.keys()) == {"row", "column", "category", "length", "hash"}
    assert f["category"] == "rrn_kr"
    assert f["length"] == len(RRN)
    # SHA-256 hex digest 는 64 hex chars.
    assert isinstance(f["hash"], str) and len(f["hash"]) == 64
    assert all(c in "0123456789abcdef" for c in f["hash"])
    # 동일 salt 로 다시 호출하면 결정적.
    out2 = dsg.scan_dataframe(df, salt=b"fixed-salt-for-test")
    assert out["findings"][0]["hash"] == out2["findings"][0]["hash"]


def test_clean_input_is_clean():
    df = pd.DataFrame({"x": ["alpha", "beta", "gamma"]})
    out = dsg.scan_dataframe(df)
    assert out["clean"] is True
    assert out["findings"] == []
