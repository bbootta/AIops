"""Scalar↔vector parity tests — guard against drift between the documented
single-exposure reference implementations and the production vectorised paths.
"""

from __future__ import annotations

import itertools

import numpy as np
import pandas as pd
import pytest

from risk_lib.capital.crm import (
    apply_crm, ccf_ead, crm_adjusted_ead, CCF_BUCKETS, _SUPERVISORY_HAIRCUTS,
)
from risk_lib.capital.rwa_irb import irb_capital_requirement, irb_k_vector
from risk_lib.capital.rwa_sa import (
    mortgage_rw, mortgage_rw_vector, sa_risk_weight, sa_risk_weight_vector,
    SA_RISK_WEIGHTS, standardised_rwa_total,
)
from risk_lib.performance.rapm import raroc, rapm_report
from risk_lib.provisioning.ecl import (
    Stage, classify_stage, classify_stage_vector,
    twelve_month_ecl, lifetime_ecl, compute_ecl,
)
from risk_lib.provisioning.macro import (
    DEFAULT_MACRO_SCENARIOS, DEFAULT_RHO, _shift_coef, _scenario_ecl, macro_ecl,
)


# ---- SA risk weights — full grid ----------------------------------------

_RATING_BUCKETS = list(SA_RISK_WEIGHTS["corporate"].keys())  # 7 buckets
_LTV_PROBES = [0.10, 0.50, 0.55, 0.60, 0.70, 0.80, 0.85, 0.90, 0.95, 1.00, 1.20]


def test_mortgage_rw_vector_matches_scalar():
    ltv = np.array(_LTV_PROBES, dtype=float)
    expected = np.array([mortgage_rw(v) for v in ltv])
    np.testing.assert_array_equal(mortgage_rw_vector(ltv), expected)


@pytest.mark.parametrize("past_due", [False, True])
def test_sa_risk_weight_vector_full_grid(past_due):
    rows = []
    for cls in ("sovereign", "bank", "corporate"):
        for rating in _RATING_BUCKETS:
            rows.append((cls, rating, None))
    for r in _RATING_BUCKETS:                       # rating ignored for retail
        rows.append(("retail_other", r, None))
        rows.append(("retail_regulatory", r, None))
    for ltv in _LTV_PROBES:
        rows.append(("residential_mortgage", "UNRATED", ltv))

    asset_class = np.array([r[0] for r in rows])
    rating = np.array([r[1] for r in rows])
    ltv = np.array([r[2] if r[2] is not None else np.nan for r in rows])
    past = np.full(len(rows), past_due, dtype=bool)

    expected = np.array([
        sa_risk_weight(cls, rt, ltv=lv if not np.isnan(lv) else None,
                       past_due=past_due)
        for (cls, rt, _), lv in zip(rows, ltv)
    ])
    actual = sa_risk_weight_vector(asset_class, rating, ltv=ltv, past_due=past)
    np.testing.assert_array_equal(actual, expected)


def test_standardised_rwa_total_matches_explicit_sum():
    portfolio = pd.DataFrame({
        "asset_class": ["corporate", "sovereign", "bank",
                        "retail_regulatory", "retail_other",
                        "residential_mortgage", "residential_mortgage"],
        "ead": [1e9, 2e9, 0.5e9, 3e8, 2e8, 4e8, 5e8],
        "rating": ["A", "AAA-AA", "BBB", None, None, None, None],
        "grade": ["AAA", None, None, None, None, None, None],
        "ltv": [np.nan, np.nan, np.nan, np.nan, np.nan, 0.55, 0.95],
    })
    bucket_map = {"AAA": "AAA-AA"}
    out = standardised_rwa_total(portfolio, bucket_map)
    # Hand-computed using the same SA tables:
    expected = (
        1e9 * 0.20    # corporate AAA → AAA-AA bucket → 20%
        + 2e9 * 0.00  # sovereign AAA-AA → 0%
        + 0.5e9 * 0.50  # bank BBB → 50%
        + 3e8 * 0.75  # retail_regulatory flat 75%
        + 2e8 * 1.00  # retail_other flat 100%
        + 4e8 * 0.25  # mortgage LTV 0.55 → 25%
        + 5e8 * 0.50  # mortgage LTV 0.95 → 50%
    )
    assert out == pytest.approx(expected, rel=1e-12)


def test_standardised_rwa_total_retail_buckets_not_swapped():
    """Regression for retail_regulatory(75%) vs retail_other(100%) swap bug."""
    portfolio = pd.DataFrame({
        "asset_class": ["retail_regulatory", "retail_other"],
        "ead": [1e9, 1e9],
        "rating": [None, None],
        "grade": [None, None],
        "ltv": [np.nan, np.nan],
    })
    out = standardised_rwa_total(portfolio)
    # 1e9 * 0.75 + 1e9 * 1.00 = 1.75e9
    assert out == pytest.approx(1.75e9, rel=1e-12)


# ---- CRM / CCF parity ---------------------------------------------------

def _crm_book(seed=7, n=100):
    rng = np.random.default_rng(seed)
    ccf_types = list(CCF_BUCKETS.keys())
    coll_types = list(_SUPERVISORY_HAIRCUTS.keys())
    return pd.DataFrame({
        "drawn": rng.uniform(0, 1e7, n),
        "undrawn": rng.uniform(0, 5e6, n),
        "ccf_type": rng.choice(ccf_types, n),
        "collateral_value": rng.uniform(0, 4e6, n) * (rng.random(n) > 0.3),
        "collateral_type": rng.choice(coll_types, n),
        "fx_mismatch": rng.random(n) > 0.7,
        "exposure_haircut": rng.uniform(0, 0.1, n),
    })


def test_apply_crm_matches_scalar_row_loop():
    book = _crm_book()
    out = apply_crm(book)

    ead_gross_ref = np.array([
        ccf_ead(r.drawn, r.undrawn, r.ccf_type) for r in book.itertuples()
    ])
    ead_ref = np.array([
        crm_adjusted_ead(
            eg,
            r.collateral_value,
            r.collateral_type,
            fx_mismatch=r.fx_mismatch,
            exposure_haircut=r.exposure_haircut,
        )
        for eg, r in zip(ead_gross_ref, book.itertuples())
    ])
    np.testing.assert_allclose(out["ead_gross"].to_numpy(), ead_gross_ref, rtol=1e-12)
    np.testing.assert_allclose(out["ead"].to_numpy(), ead_ref, rtol=1e-12)


def test_apply_crm_rejects_unknown_ccf_type():
    book = pd.DataFrame({
        "drawn": [1.0], "undrawn": [1.0], "ccf_type": ["bogus"],
    })
    with pytest.raises(ValueError, match="unknown ccf_type"):
        apply_crm(book)


def test_apply_crm_rejects_unknown_collateral_type():
    book = pd.DataFrame({
        "ead": [100.0], "collateral_value": [50.0], "collateral_type": ["moon_rock"],
    })
    with pytest.raises(ValueError, match="unknown collateral_type"):
        apply_crm(book)


# ---- IRB K parity --------------------------------------------------------

def _irb_book(seed=11, n=200):
    rng = np.random.default_rng(seed)
    classes = ["corporate", "retail_other", "residential_mortgage",
               "sovereign", "bank", "retail_revolving"]
    return pd.DataFrame({
        "exposure_id": [f"E{i:04d}" for i in range(n)],
        "asset_class": rng.choice(classes, n),
        "ead": rng.lognormal(15, 1.0, n),
        "pd": np.clip(rng.beta(2, 60, n), 1e-5, 0.5),
        "lgd": np.clip(rng.beta(3, 3, n), 0.05, 0.95),
        "maturity": rng.uniform(0.5, 6.0, n),
    })


def test_irb_k_vector_matches_scalar_loop():
    book = _irb_book()
    expected = np.array([
        irb_capital_requirement(r.pd, r.lgd, r.asset_class, r.maturity)
        for r in book.itertuples()
    ])
    actual = irb_k_vector(
        book["pd"].to_numpy(dtype=float),
        book["lgd"].to_numpy(dtype=float),
        book["asset_class"].to_numpy(),
        book["maturity"].to_numpy(dtype=float),
    )
    np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-15)


# ---- IFRS9 staging + lifetime ECL ---------------------------------------

def test_classify_stage_vector_matches_scalar():
    rng = np.random.default_rng(7)
    n = 300
    dpd = rng.integers(0, 200, n)
    pd_now = rng.uniform(0.001, 0.5, n)
    pd_orig = np.where(rng.random(n) > 0.5, rng.uniform(0.001, 0.2, n), np.nan)
    watch = rng.random(n) > 0.85

    expected = np.array([
        int(classify_stage(int(d), float(p),
                           float(o) if not np.isnan(o) else None,
                           watchlist=bool(w)))
        for d, p, o, w in zip(dpd, pd_now, pd_orig, watch)
    ])
    actual = classify_stage_vector(
        dpd.astype(float), pd_now, pd_orig, watchlist=watch,
    )
    np.testing.assert_array_equal(actual, expected)


def test_compute_ecl_matches_scalar_oracle():
    rng = np.random.default_rng(13)
    n = 100
    book = pd.DataFrame({
        "exposure_id": [f"E{i:03d}" for i in range(n)],
        "ead": rng.uniform(1e6, 1e9, n),
        "pd": np.clip(rng.beta(2, 50, n), 1e-4, 0.5),
        "lgd": np.clip(rng.beta(3, 3, n), 0.05, 0.95),
        "dpd": rng.integers(0, 200, n),
        "maturity": rng.uniform(0.5, 8.0, n),
    })
    out = compute_ecl(book, eir=0.05)
    for i, r in enumerate(book.itertuples()):
        stage = classify_stage(int(r.dpd), float(r.pd))
        if stage == Stage.STAGE_1:
            expected = twelve_month_ecl(r.pd, r.lgd, r.ead)
        elif stage == Stage.STAGE_2:
            expected = lifetime_ecl(r.pd, r.lgd, r.ead, r.maturity, eir=0.05)
        else:
            expected = max(r.lgd, 0.0) * max(r.ead, 0.0)
        assert out["stage"].iloc[i] == int(stage)
        assert out["ecl"].iloc[i] == pytest.approx(expected, rel=1e-12, abs=1e-9)


# ---- Macro PIT scenario ECL parity --------------------------------------

def test_macro_ecl_matches_scenario_ecl_oracle():
    rng = np.random.default_rng(31)
    n = 60
    book = pd.DataFrame({
        "exposure_id": [f"M{i:03d}" for i in range(n)],
        "ead": rng.uniform(1e6, 1e9, n),
        "pd": np.clip(rng.beta(2, 40, n), 1e-4, 0.4),
        "lgd": np.clip(rng.beta(3, 3, n), 0.05, 0.95),
        "dpd": rng.integers(0, 200, n),
        "maturity": rng.uniform(0.5, 6.0, n),
    })
    res = macro_ecl(book)

    # Compute the same expected ECL via the scalar oracle and check each
    # scenario column matches to ≤1e-9 relative.
    max_n = int(np.ceil(book["maturity"].max()))
    stages_actual = res.per_exposure["stage"].to_numpy()
    for s in DEFAULT_MACRO_SCENARIOS:
        z = s.z_path(max_n)
        expected = np.array([
            _scenario_ecl(
                float(r.pd), float(r.lgd), float(r.ead),
                float(r.maturity), Stage(int(st)), z,
                rho=DEFAULT_RHO, eir=0.05,
            )
            for r, st in zip(book.itertuples(), stages_actual)
        ])
        np.testing.assert_allclose(
            res.per_exposure[f"ecl_{s.name}"].to_numpy(),
            expected, rtol=1e-9, atol=1e-6,
        )


# ---- RAPM parity ---------------------------------------------------------

def test_rapm_report_matches_scalar_raroc():
    rng = np.random.default_rng(101)
    n = 150
    book = pd.DataFrame({
        "exposure_id": [f"R{i:03d}" for i in range(n)],
        "asset_class": rng.choice(
            ["corporate", "retail_other", "residential_mortgage"], n),
        "ead": rng.uniform(1e6, 5e8, n),
        "pd": np.clip(rng.beta(2, 40, n), 1e-4, 0.4),
        "lgd": np.clip(rng.beta(3, 3, n), 0.05, 0.95),
        "maturity": rng.uniform(1.0, 5.0, n),
        "revenue": rng.uniform(1e5, 1e7, n),
        "operating_cost": rng.uniform(1e4, 1e6, n),
    })
    out = rapm_report(book)

    for r in book.itertuples():
        expected = raroc(
            r.revenue, r.operating_cost, r.pd, r.lgd, r.ead,
            asset_class=r.asset_class, maturity=r.maturity,
        )
        row = out[out["exposure_id"] == r.exposure_id].iloc[0]
        assert row["raroc"] == pytest.approx(expected["raroc"], rel=1e-12)
        assert row["economic_capital"] == pytest.approx(
            expected["economic_capital"], rel=1e-12)
