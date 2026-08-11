import json
import time
from pathlib import Path

from tools import feedback_retention as fr


def _seed(path: Path, records: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def test_prune_removes_old_entries(tmp_path):
    p = tmp_path / "fb.jsonl"
    now = time.time()
    old = now - 200 * 86400.0
    new = now - 10 * 86400.0
    _seed(
        p,
        [
            {"text": "old", "recorded_at": old},
            {"text": "new", "recorded_at": new},
            {"text": "no_ts"},
        ],
    )
    res = fr.prune(p, max_age_days=90, now_epoch=now)
    assert res["removed"] == 1
    assert res["kept"] == 2
    remaining = p.read_text(encoding="utf-8").splitlines()
    assert all('"text": "old"' not in line for line in remaining)


def test_anonymize_replaces_text_and_notes(tmp_path):
    p = tmp_path / "fb.jsonl"
    _seed(
        p,
        [
            {"text": "PermissionError on host", "notes": "context", "confirmed_category": "permission"},
        ],
    )
    res = fr.anonymize(p)
    assert res["fields_anonymized"] == 2
    rec = json.loads(p.read_text(encoding="utf-8").strip())
    assert rec["text"].startswith("<")
    assert "#" in rec["text"]
    assert rec["notes"].startswith("<")


def test_record_feedback_has_recorded_at(tmp_path):
    from tools import classify_error as ce

    fp = tmp_path / "fb.jsonl"
    rec = ce.record_feedback("VIF > 10", "methodology", feedback_path=fp)
    assert "recorded_at" in rec
    assert isinstance(rec["recorded_at"], float)
