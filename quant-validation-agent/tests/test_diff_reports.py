from tools import diff_reports as dr


def test_diff_metric_blocks_basic():
    base = {"metrics": {"ks": {"value": 0.42, "rag": "Green"},
                        "auroc": {"value": 0.80, "rag": "Green"}}}
    cur = {"metrics": {"ks": {"value": 0.35, "rag": "Yellow"},
                       "psi": {"value": 0.12, "rag": "Yellow"}}}
    rows = dr.diff_metric_blocks(base, cur)
    by = {r["metric"]: r for r in rows}
    assert by["ks"]["delta"] < 0
    assert by["ks"]["transition"] == "Green -> Yellow"
    assert by["auroc"]["current_value"] is None
    assert by["psi"]["base_value"] is None


def test_diff_overall_rag_detects_regression():
    base = {"overall_rag": "Green"}
    cur = {"overall_rag": "Red"}
    out = dr.diff_overall_rag(base, cur)
    assert out["base"] == "Green"
    assert out["current"] == "Red"
    assert out["regressed"] is True


def test_diff_overall_rag_improvement():
    out = dr.diff_overall_rag({"overall_rag": "Yellow"}, {"overall_rag": "Green"})
    assert out["regressed"] is False
