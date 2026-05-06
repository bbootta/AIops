import json
from pathlib import Path

import pytest

from tools import scenario_order_check as soc

FLOORS_FILE = Path(__file__).resolve().parent.parent / "harness" / "scenario_floors.json"


def test_floors_file_loads_with_required_keys():
    floors = soc.load_floors()
    for k in ("base", "adverse", "severe"):
        assert k in floors
        assert isinstance(floors[k], (int, float))


def test_floors_file_on_disk_is_consistent():
    cfg = json.loads(FLOORS_FILE.read_text(encoding="utf-8"))
    assert "floors" in cfg
    assert cfg["floors"]["base"] <= cfg["floors"]["adverse"] <= cfg["floors"]["severe"]


def test_floors_argument_overrides_policy_file():
    custom = {"base": 1.0, "adverse": 1.4, "severe": 2.0}
    out = soc.check_pd_multiplier_floor([1.5, 1.45], "adverse", floors=custom)
    assert out["floor"] == 1.4
    assert out["floors_source"] == "argument"
    assert out["n_violation"] == 0


def test_default_floors_used_when_no_arg():
    out = soc.check_pd_multiplier_floor([1.6, 1.7], "severe")
    assert out["floors_source"] == "policy_file"


def test_unknown_scenario_with_custom_floors():
    with pytest.raises(ValueError):
        soc.check_pd_multiplier_floor([1.0], "extreme", floors={"base": 1.0})
