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
from risk_lib.capital.rwa_sa import (
    mortgage_rw, mortgage_rw_vector, sa_risk_weight, sa_risk_weight_vector,
    SA_RISK_WEIGHTS, standardised_rwa_total,
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
        "asset_class": ["corporate", "sovereign", "bank", "retail_other",
                        "residential_mortgage", "residential_mortgage"],
        "ead": [1e9, 2e9, 0.5e9, 3e8, 4e8, 5e8],
        "rating": ["A", "AAA-AA", "BBB", None, None, None],
        "grade": ["AAA", None, None, None, None, None],
        "ltv": [np.nan, np.nan, np.nan, np.nan, 0.55, 0.95],
    })
    bucket_map = {"AAA": "AAA-AA"}
    out = standardised_rwa_total(portfolio, bucket_map)
    # Hand-computed using the same SA tables:
    expected = (
        1e9 * 0.20    # corporate AAA → AAA-AA bucket → 20%
        + 2e9 * 0.00  # sovereign AAA-AA → 0%
        + 0.5e9 * 0.50  # bank BBB → 50%
        + 3e8 * 0.75  # retail_regulatory flat 75%
        + 4e8 * 0.25  # mortgage LTV 0.55 → 25%
        + 5e8 * 0.50  # mortgage LTV 0.95 → 50%
    )
    assert out == pytest.approx(expected, rel=1e-12)


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
