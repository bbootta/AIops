import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MATRIX_PATH = ROOT / "harness" / "orchestration_matrix.json"


def test_matrix_file_loads_and_has_required_steps():
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    assert matrix["matrix_version"]
    step_ids = [s["id"] for s in matrix["steps"]]
    for required in ("1.req", "4.report", "5.complete", "5.cite", "5.watermark", "6.audit"):
        assert required in step_ids


def test_every_step_has_unique_id_and_required_fields():
    matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
    ids = [s["id"] for s in matrix["steps"]]
    assert len(set(ids)) == len(ids)
    for s in matrix["steps"]:
        for k in ("id", "name", "component", "rationale"):
            assert k in s and s[k]
        # gate fields must be exclusive
        gates = [k for k in ("always", "requires_all", "requires_any") if k in s]
        assert len(gates) >= 1
