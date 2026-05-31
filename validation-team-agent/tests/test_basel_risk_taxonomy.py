import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "harness" / "basel_risk_taxonomy.schema.json"
DATA = ROOT / "harness" / "basel_risk_taxonomy.json"


def test_taxonomy_validates_against_schema():
    jsonschema = pytest.importorskip("jsonschema")
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    data = json.loads(DATA.read_text(encoding="utf-8"))
    jsonschema.validate(data, schema)


def test_taxonomy_covers_all_basel_buckets():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    ids = {b["id"] for b in data["risk_buckets"]}
    for required in ("credit", "ifrs9", "market", "operational",
                     "liquidity", "irrbb", "cva", "ccr"):
        assert required in ids


def test_policy_files_exist_for_each_bucket():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    for bucket in data["risk_buckets"]:
        policy = ROOT / bucket["policy"]
        assert policy.exists(), f"missing {bucket['policy']}"


def test_thresholds_files_exist_when_declared():
    data = json.loads(DATA.read_text(encoding="utf-8"))
    for bucket in data["risk_buckets"]:
        if "thresholds" in bucket and bucket["thresholds"]:
            path = ROOT / bucket["thresholds"]
            assert path.exists(), f"missing {bucket['thresholds']}"
            # JSON 으로 로드 가능해야 한다.
            json.loads(path.read_text(encoding="utf-8"))
