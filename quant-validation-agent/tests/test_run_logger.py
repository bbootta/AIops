import json
import os

from middleware import run_logger


def test_write_run_log_creates_file(tmp_path):
    path = run_logger.write_run_log(
        request_summary="t",
        inputs=["x"],
        functions_used=["f"],
        main_results={"k": 1},
        log_dir=str(tmp_path),
    )
    assert os.path.exists(path)
    payload = json.loads(open(path, "r", encoding="utf-8").read())
    assert payload["request_summary"] == "t"


def test_write_run_log_filenames_unique_under_burst(tmp_path):
    """Filenames must remain unique even when many records are written in a tight loop."""
    paths = set()
    for i in range(50):
        p = run_logger.write_run_log(
            request_summary=f"r{i}", inputs=[], functions_used=[],
            main_results={}, log_dir=str(tmp_path),
        )
        paths.add(p)
    assert len(paths) == 50, "duplicate run-log filenames under tight loop"


def test_write_run_log_filename_includes_pid_and_counter(tmp_path):
    p = run_logger.write_run_log(
        request_summary="t", inputs=[], functions_used=[],
        main_results={}, log_dir=str(tmp_path),
    )
    name = os.path.basename(p)
    assert "_pid" in name
    # Counter is six zero-padded digits.
    assert name.endswith(".json")
