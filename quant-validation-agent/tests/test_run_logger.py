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


def _worker(log_dir, n):
    """Module-level worker: spawn-safe (no closures)."""
    from middleware import run_logger as _rl
    paths = []
    for i in range(n):
        paths.append(_rl.write_run_log(
            request_summary=f"w{i}",
            inputs=[], functions_used=[], main_results={},
            log_dir=log_dir,
        ))
    return paths


def test_write_run_log_filenames_unique_across_processes(tmp_path):
    """Concurrent processes should not collide thanks to the PID segment."""
    import concurrent.futures as cf

    n_proc = 3
    per_proc = 20
    futures = []
    with cf.ProcessPoolExecutor(max_workers=n_proc) as pool:
        for _ in range(n_proc):
            futures.append(pool.submit(_worker, str(tmp_path), per_proc))
        all_paths = []
        for f in futures:
            all_paths.extend(f.result())
    assert len(set(all_paths)) == n_proc * per_proc


def test_write_run_log_filename_includes_pid_and_counter(tmp_path):
    p = run_logger.write_run_log(
        request_summary="t", inputs=[], functions_used=[],
        main_results={}, log_dir=str(tmp_path),
    )
    name = os.path.basename(p)
    assert "_pid" in name
    # Counter is six zero-padded digits.
    assert name.endswith(".json")
