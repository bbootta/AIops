"""감독시행세칙(국내 적용) 조정 검증.

- liquidity: 외화LCR 추가
- operational: domestic_default_ilm=1.0 정책
- taxonomy: capital_adequacy 부문 추가
"""

import json
from pathlib import Path

import pytest

from tools.risk_checks import liquidity as lq
from tools.risk_checks import operational as op


ROOT = Path(__file__).resolve().parent.parent


def test_foreign_currency_lcr_ok():
    out = lq.check_foreign_currency_lcr(100.0, 100.0)
    assert out["ratio"] == pytest.approx(1.0)
    assert out["status"] == "ok"


def test_foreign_currency_lcr_below_min_at_70pct():
    out = lq.check_foreign_currency_lcr(70.0, 100.0)
    assert out["status"] == "below_min"


def test_foreign_currency_lcr_warning_at_85pct():
    out = lq.check_foreign_currency_lcr(85.0, 100.0)
    assert out["status"] == "warning"


def test_foreign_currency_lcr_rejects_invalid_outflow():
    with pytest.raises(ValueError):
        lq.check_foreign_currency_lcr(100.0, 0.0)


def test_operational_orc_domestic_ilm_one():
    out = op.compute_orc_domestic(bic=2.0)
    assert out["ilm"] == pytest.approx(1.0)
    assert out["orc"] == pytest.approx(2.0)
    assert out["domestic_default"] is True


def test_taxonomy_includes_capital_adequacy():
    data = json.loads(
        (ROOT / "harness" / "basel_risk_taxonomy.json").read_text(encoding="utf-8")
    )
    ids = {b["id"] for b in data["risk_buckets"]}
    assert "capital_adequacy" in ids


def test_taxonomy_validates_after_capital_added():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(
        (ROOT / "harness" / "basel_risk_taxonomy.schema.json").read_text(encoding="utf-8")
    )
    data = json.loads(
        (ROOT / "harness" / "basel_risk_taxonomy.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(data, schema)


def test_liquidity_thresholds_have_foreign_currency_field():
    th = lq.load_thresholds()
    assert "foreign_currency_lcr_min" in th
    assert th["foreign_currency_lcr_min"] == pytest.approx(0.80)


def test_operational_thresholds_have_domestic_default():
    th = op.load_thresholds()
    assert th.get("domestic_default_ilm") == pytest.approx(1.0)
