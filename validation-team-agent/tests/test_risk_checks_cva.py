import math

import pytest

from tools.risk_checks import cva


def test_ba_cva_formula_single_counterparty():
    """단일 counterparty 에서 BA-CVA = α × SCVA (ρ 항이 모두 같으면 SCVA = sqrt(ρ²S² + (1-ρ²)S²) = S)."""
    out = cva.compute_ba_cva([{"name": "A", "scva": 100.0}])
    # math: sqrt((0.5×100)² + 0.75×100²) = sqrt(2500 + 7500) = sqrt(10000) = 100
    # ×α (1.4) = 140
    assert out["ba_cva"] == pytest.approx(140.0)
    assert out["alpha"] == 1.4
    assert out["rho"] == 0.5


def test_ba_cva_two_counterparties_diversifies():
    """단일과 두 개 비교: 두 개로 분산 시 BA-CVA 감소."""
    single = cva.compute_ba_cva([{"name": "A", "scva": 200.0}])["ba_cva"]
    pair = cva.compute_ba_cva([
        {"name": "A", "scva": 100.0},
        {"name": "B", "scva": 100.0},
    ])["ba_cva"]
    assert pair < single  # diversification benefit


def test_ba_cva_rejects_missing_scva():
    with pytest.raises(KeyError):
        cva.compute_ba_cva([{"name": "A"}])


def test_ba_cva_rejects_negative_scva():
    with pytest.raises(ValueError):
        cva.compute_ba_cva([{"name": "A", "scva": -1.0}])


def test_sa_cva_required_above_threshold():
    out = cva.check_sa_cva_required(120.0)
    assert out["sa_cva_required"] is True


def test_sa_cva_not_required_below_threshold():
    out = cva.check_sa_cva_required(50.0)
    assert out["sa_cva_required"] is False
