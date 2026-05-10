"""실행 감사 (audit) 보고.

orchestration_matrix의 step 정의와 ``logs/run.jsonl`` 의 step 이벤트를 비교하여
어느 step이 실행/스킵/누락되었는지 표 형태로 출력한다. 인간 검증자가 사후 검토에
사용한다.

사용:
    python -m tools.run_audit --log logs/run.jsonl
    python -m tools.run_audit --demo  # 신용 runner 데모를 실행한 뒤 즉시 감사

본 도구는 자동 의견을 만들지 않는다. 단순 비교만 수행한다.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from middleware.run_logger import collect_step_ids, collect_step_records

ROOT = Path(__file__).resolve().parent.parent
MATRIX_PATH = ROOT / "harness" / "orchestration_matrix.json"


def load_matrix(path: Path | None = None) -> list[dict]:
    p = path or MATRIX_PATH
    return json.loads(p.read_text(encoding="utf-8"))["steps"]


def audit(log_path: Path, *, matrix_path: Path | None = None) -> list[dict]:
    """매트릭스 step별로 실행 여부를 판정한다.

    반환 list[dict] 키: id, name, status, component, expected_outputs.
    status 값:
      - executed: 로그에 status='executed'로 기록됨
      - skipped:  로그에 status='skipped'로 명시 기록됨, 또는 게이트가 닫힘
      - missing:  always 인데 로그에 없음
    """
    steps = load_matrix(matrix_path)
    executed = set(collect_step_ids(log_path))
    skipped_ids = {
        rec["step_id"]
        for rec in collect_step_records(log_path)
        if rec.get("status") == "skipped" and rec.get("step_id")
    }
    rows: list[dict] = []
    for step in steps:
        sid = step["id"]
        if sid in executed:
            status = "executed"
        elif sid in skipped_ids:
            status = "skipped"
        elif step.get("always") is True:
            status = "missing"
        else:
            status = "skipped"  # 게이트가 닫혀서 의도적으로 미실행
        rows.append(
            {
                "id": sid,
                "name": step["name"],
                "status": status,
                "component": step["component"],
                "expected_outputs": step.get("expected_outputs", []),
            }
        )
    return rows


def render_table(rows: Iterable[dict]) -> str:
    """audit 결과를 마크다운 표로 변환한다."""
    rows = list(rows)
    out = [
        "| Step | Status | Component | Expected Outputs |",
        "|---|---|---|---|",
    ]
    for r in rows:
        outputs = ", ".join(f"`{o}`" for o in r["expected_outputs"]) or "—"
        out.append(
            f"| {r['id']} {r['name']} | {r['status']} | `{r['component']}` | {outputs} |"
        )
    return "\n".join(out)


def render_summary(rows: Iterable[dict]) -> str:
    rows = list(rows)
    counts = {"executed": 0, "skipped": 0, "missing": 0}
    for r in rows:
        counts[r["status"]] = counts.get(r["status"], 0) + 1
    return (
        f"executed = {counts['executed']}, "
        f"skipped = {counts['skipped']}, "
        f"missing = {counts['missing']}"
    )


def _cmd_log(args: argparse.Namespace) -> int:
    rows = audit(Path(args.log), matrix_path=args.matrix)
    if args.json:
        json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_summary(rows) + "\n\n")
        sys.stdout.write(render_table(rows) + "\n")
    return 0 if all(r["status"] != "missing" for r in rows) else 1


def _cmd_demo(args: argparse.Namespace) -> int:
    import tempfile

    from tools.run_validation import _build_demo_request, run

    tmp = Path(tempfile.mkdtemp(prefix="run_audit_demo_"))
    req = _build_demo_request()
    run(req, log_dir=tmp)
    rows = audit(tmp / "run.jsonl")
    sys.stdout.write(render_summary(rows) + "\n\n")
    sys.stdout.write(render_table(rows) + "\n")
    return 0 if all(r["status"] != "missing" for r in rows) else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="orchestration_matrix vs actual run audit")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_log = sub.add_parser("log", help="audit existing log file")
    p_log.add_argument("--log", required=True, type=str)
    p_log.add_argument("--matrix", type=Path, default=None)
    p_log.add_argument("--json", action="store_true")
    p_log.set_defaults(func=_cmd_log)

    p_demo = sub.add_parser("demo", help="run credit demo and audit immediately")
    p_demo.set_defaults(func=_cmd_demo)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
