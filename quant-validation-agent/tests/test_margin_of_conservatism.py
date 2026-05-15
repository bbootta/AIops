import pytest

from tools import margin_of_conservatism as moc


def _components():
    return [
        {"category": "A", "label": "short_history", "value": 0.002,
         "rationale": "only 3 years of obs"},
        {"category": "B", "label": "estimation_error", "value": 0.001,
         "rationale": "bootstrap CI half-width"},
        {"category": "C", "label": "cycle_uncertainty", "value": 0.0005},
    ]


def test_build_moc_table_sorts_and_validates():
    df = moc.build_moc_table(_components())
    assert df.shape == (3, 4)
    assert list(df["category"]) == ["A", "B", "C"]


def test_aggregate_moc_totals():
    out = moc.aggregate_moc(_components())
    assert out["n_components"] == 3
    assert out["by_category"]["A"] == pytest.approx(0.002)
    assert out["by_category"]["B"] == pytest.approx(0.001)
    assert out["by_category"]["C"] == pytest.approx(0.0005)
    assert out["total_moc"] == pytest.approx(0.0035)


def test_aggregate_moc_empty():
    out = moc.aggregate_moc([])
    assert out["total_moc"] == 0.0
    assert out["n_components"] == 0
    assert out["by_category"] == {"A": 0.0, "B": 0.0, "C": 0.0}


def test_apply_moc_adds_addon():
    assert moc.apply_moc(0.02, 0.0035) == pytest.approx(0.0235)


def test_apply_moc_rejects_negative():
    with pytest.raises(ValueError):
        moc.apply_moc(-0.01, 0.001)
    with pytest.raises(ValueError):
        moc.apply_moc(0.01, -0.001)


def test_build_rejects_unknown_category():
    with pytest.raises(ValueError):
        moc.build_moc_table([{"category": "Z", "value": 0.1}])


def test_build_rejects_negative_value():
    with pytest.raises(ValueError):
        moc.build_moc_table([{"category": "A", "value": -0.001}])


def test_build_rejects_missing_fields():
    with pytest.raises(ValueError):
        moc.build_moc_table([{"category": "A"}])
    with pytest.raises(ValueError):
        moc.build_moc_table([{"value": 0.1}])
