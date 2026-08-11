import pytest

from tools import sample_generators as sg


def test_credit_sample_shape_and_columns():
    df = sg.credit_scoring_sample(n=1000, seed=1)
    assert len(df) == 1000
    for col in ("customer_id", "obs_date", "score", "target", "grade", "pd", "set"):
        assert col in df.columns


def test_credit_sample_target_is_binary():
    df = sg.credit_scoring_sample(n=500, seed=2)
    unique = set(df["target"].unique().tolist())
    assert unique == {0, 1}


def test_credit_sample_dev_oot_split():
    df = sg.credit_scoring_sample(n=1600, seed=3, dev_ratio=0.625)
    assert (df["set"] == "dev").sum() == 1000
    assert (df["set"] == "oot").sum() == 600


def test_credit_sample_grades_within_known_set():
    df = sg.credit_scoring_sample(n=2000, seed=4)
    assert set(df["grade"].unique().tolist()).issubset(set("ABCDE"))


def test_credit_sample_deterministic():
    a = sg.credit_scoring_sample(n=500, seed=42)
    b = sg.credit_scoring_sample(n=500, seed=42)
    assert a.equals(b)


def test_credit_sample_rejects_too_small():
    with pytest.raises(ValueError):
        sg.credit_scoring_sample(n=10)


def test_psi_shift_changes_oot_distribution():
    base = sg.credit_scoring_sample(n=2000, seed=5, psi_shift=0.0)
    shifted = sg.credit_scoring_sample(n=2000, seed=5, psi_shift=0.5)
    base_oot = base.loc[base["set"] == "oot", "score"].mean()
    shifted_oot = shifted.loc[shifted["set"] == "oot", "score"].mean()
    assert shifted_oot > base_oot + 0.2


def test_capital_samples_have_expected_keys():
    ok = sg.capital_ratio_sample()
    bad = sg.capital_stress_sample()
    for k in ("capital_cet1", "capital_tier1", "capital_total", "capital_leverage"):
        assert k in ok and k in bad
    # stress 는 CET1 미달
    assert bad["capital_cet1"] < 0.045
