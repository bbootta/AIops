import json
from pathlib import Path

from tools.run_validation import _build_demo_request, run


def test_demo_run_produces_full_report(tmp_path):
    req = _build_demo_request()
    out = run(req, log_dir=tmp_path)
    md = out["report_md"]
    assert "## 1. 요약" in md
    assert "## 10. 감사추적 및 변경 이력" in md
    assert out["completeness"]["passed"] is True
    assert out["citations"]["passed"] is True


def test_demo_run_writes_jsonl_log(tmp_path):
    req = _build_demo_request()
    run(req, log_dir=tmp_path)
    log_path = Path(tmp_path) / "run.jsonl"
    assert log_path.exists()
    lines = [json.loads(l) for l in log_path.read_text(encoding="utf-8").splitlines() if l.strip()]
    events = {l["event"] for l in lines}
    assert "start" in events
    assert "end" in events
    assert any(l["function"] == "run_validation.run" for l in lines)


def test_demo_run_records_sample_size_decision(tmp_path):
    req = _build_demo_request()
    out = run(req, log_dir=tmp_path)
    assert "sample_size" in out["quant"]
    assert isinstance(out["quant"]["sample_size"]["passed"], bool)
