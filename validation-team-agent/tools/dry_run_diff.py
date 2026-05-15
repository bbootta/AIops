"""Plan diff between two orchestration matrix files.

매트릭스 정책이 변경되었을 때 dry_run plan이 어떻게 달라졌는지 비교한다. 의도된
step 추가/제거와 회귀 (의도되지 않은 변경)를 구분하는 목적.

사용:
    python -m tools.dry_run_diff --before old_matrix.json --after new_matrix.json
    python -m tools.dry_run_diff --before old.json --after new.json --request request.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Mapping

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.dry_run import simulate, _demo_request


def diff_plans(
    before_matrix_path: Path,
    after_matrix_path: Path,
    request: Mapping | None = None,
) -> dict:
    """두 매트릭스에 대한 plan을 시뮬레이트하고 step id 차이를 반환한다.

    반환 dict 키: added, removed, reordered, field_changes, before, after.
        field_changes: 같은 step id 의 component / inputs / expected_outputs /
        rationale 변경을 리스트로 보고.
    """
    req = dict(request) if request else _demo_request()
    before_plan = simulate(req, matrix_path=Path(before_matrix_path))
    after_plan = simulate(req, matrix_path=Path(after_matrix_path))
    before_ids = [s["id"] for s in before_plan]
    after_ids = [s["id"] for s in after_plan]

    before_set = set(before_ids)
    after_set = set(after_ids)
    added = [s for s in after_ids if s not in before_set]
    removed = [s for s in before_ids if s not in after_set]

    reordered: list[tuple[str, int, int]] = []
    common = before_set & after_set
    for sid in common:
        oi = before_ids.index(sid)
        ni = after_ids.index(sid)
        if oi != ni:
            reordered.append((sid, oi, ni))
    reordered.sort(key=lambda x: x[2])

    before_by_id = {s["id"]: s for s in before_plan}
    after_by_id = {s["id"]: s for s in after_plan}
    field_changes: list[dict] = []
    for sid in sorted(common):
        for field in ("component", "rationale", "expected_outputs", "inputs"):
            old = before_by_id[sid].get(field)
            new = after_by_id[sid].get(field)
            if old != new:
                field_changes.append(
                    {"id": sid, "field": field, "before": old, "after": new}
                )

    return {
        "added": added,
        "removed": removed,
        "reordered": reordered,
        "field_changes": field_changes,
        "before": before_ids,
        "after": after_ids,
    }


def render_markdown(diff: Mapping) -> str:
    lines = ["# Orchestration Plan Diff", ""]
    lines.append(f"- before: {len(diff['before'])} steps")
    lines.append(f"- after:  {len(diff['after'])} steps")
    lines.append("")

    if diff["added"]:
        lines.append("## Added")
        for sid in diff["added"]:
            lines.append(f"- `{sid}`")
        lines.append("")
    if diff["removed"]:
        lines.append("## Removed")
        for sid in diff["removed"]:
            lines.append(f"- `{sid}`")
        lines.append("")
    if diff["reordered"]:
        lines.append("## Reordered")
        for sid, oi, ni in diff["reordered"]:
            lines.append(f"- `{sid}`: index {oi} → {ni}")
        lines.append("")
    if diff.get("field_changes"):
        lines.append("## Field Changes")
        for ch in diff["field_changes"]:
            lines.append(
                f"- `{ch['id']}` / `{ch['field']}`: {ch['before']!r} → {ch['after']!r}"
            )
        lines.append("")
    if not (
        diff["added"]
        or diff["removed"]
        or diff["reordered"]
        or diff.get("field_changes")
    ):
        lines.append("(no plan-level differences)")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="orchestration plan diff")
    parser.add_argument("--before", required=True, type=Path)
    parser.add_argument("--after", required=True, type=Path)
    parser.add_argument("--request", type=Path, default=None,
                        help="JSON file with request dict (default: dry_run demo request)")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    request = None
    if args.request:
        request = json.loads(args.request.read_text(encoding="utf-8"))
    diff = diff_plans(args.before, args.after, request=request)
    if args.json:
        json.dump(diff, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_markdown(diff))
    return (
        0
        if not (
            diff["added"]
            or diff["removed"]
            or diff["reordered"]
            or diff.get("field_changes")
        )
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
