import pytest

from middleware import permission_guard as pg
from middleware import data_safety_guard as dsg
from middleware import leakage_guard as lg
from middleware import output_completeness_guard as oc


def test_detect_drop_command():
    matches = pg.detect_risky_commands("DROP TABLE customers")
    assert any("DROP" in m["match"].upper() for m in matches)


def test_detect_rm_rf():
    matches = pg.detect_risky_commands("rm -rf /tmp/test")
    assert any("rm -rf" in m["match"] for m in matches)


def test_detect_git_push():
    matches = pg.detect_risky_commands("git push origin main")
    assert any("git push" in m["match"] for m in matches)


def test_assert_raises_on_production_keyword():
    with pytest.raises(PermissionError):
        pg.assert_no_risky_commands("apply to production")


def test_safe_text_passes():
    pg.assert_no_risky_commands("calculate KS for sample data")


def test_pii_detect_email_phone_rrn():
    txt = "user@example.com 010-1234-5678 901231-1234567"
    out = dsg.detect_pii_in_text(txt)
    types = {x["type"] for x in out}
    assert {"email", "phone_kr", "rrn"}.issubset(types)


def test_pii_mask_text():
    masked = dsg.mask_text("contact me at user@example.com")
    assert "[REDACTED]" in masked
    assert "user@example.com" not in masked


def test_leakage_guard_detects_outcome_columns():
    feats = ["x1", "x2", "realized_lgd", "default_flag"]
    cands = lg.detect_leakage_candidates(feats)
    cols = {c["column"] for c in cands}
    assert "realized_lgd" in cols
    assert "default_flag" in cols


def test_output_completeness_missing_sections():
    res = oc.check_report_sections("only 검증 요약 here")
    assert res["pass"] is False
    assert "한계" in res["missing"]


def test_output_completeness_pass():
    txt = "\n".join(
        [
            "검증 요약",
            "입력 데이터 점검",
            "주요 지표",
            "세부 분석",
            "이상 징후",
            "한계",
            "검증 의견 초안",
            "추가 확인사항",
            "감사추적",
        ]
    )
    res = oc.check_report_sections(txt)
    assert res["pass"] is True
