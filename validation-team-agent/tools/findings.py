"""recurring_findings.json sync 도구.

JSON이 SSoT. 마크다운은 본 도구로 생성된다. 신규 finding 추가 시:
    python -m tools.findings add --domain calibration \\
        --frequency moderate --description "..." --tool path

sync 명령은 JSON에서 마크다운을 다시 만든다. 빈도 카운터 증가는
``bump_frequency`` 함수로 가능 (rare → moderate → frequent).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = ROOT / "memory" / "recurring_findings.json"
MD_PATH = ROOT / "memory" / "recurring_findings.md"

_FREQUENCY_ORDER = ("rare", "moderate", "frequent")
_FREQUENCY_LABEL = {"rare": "드묾", "moderate": "보통", "frequent": "빈번"}


def load(path: Path | None = None) -> dict:
    return json.loads((path or JSON_PATH).read_text(encoding="utf-8"))


def save(data: dict, path: Path | None = None) -> Path:
    p = path or JSON_PATH
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def _next_id(data: dict) -> str:
    nums = []
    for f in data["findings"]:
        try:
            nums.append(int(f["id"].split("-", 1)[1]))
        except (IndexError, ValueError):
            continue
    return f"RF-{(max(nums) + 1) if nums else 1:03d}"


def add_finding(
    *,
    domain: str,
    frequency: str,
    description: str,
    primary_tool: str,
    json_path: Path | None = None,
) -> dict:
    if frequency not in _FREQUENCY_ORDER:
        raise ValueError(f"frequency must be one of {_FREQUENCY_ORDER}")
    data = load(json_path)
    entry = {
        "id": _next_id(data),
        "frequency": frequency,
        "domain": domain,
        "description": description,
        "primary_tool": primary_tool,
    }
    data["findings"].append(entry)
    save(data, json_path)
    return entry


def bump_frequency(finding_id: str, json_path: Path | None = None) -> dict:
    """rare → moderate → frequent 한 단계 상승. frequent는 더 이상 변경 없음."""
    data = load(json_path)
    for f in data["findings"]:
        if f["id"] == finding_id:
            cur = f["frequency"]
            if cur not in _FREQUENCY_ORDER:
                raise ValueError(f"unknown current frequency {cur}")
            idx = _FREQUENCY_ORDER.index(cur)
            f["frequency"] = _FREQUENCY_ORDER[min(idx + 1, len(_FREQUENCY_ORDER) - 1)]
            save(data, json_path)
            return f
    raise KeyError(f"finding not found: {finding_id}")


def render_markdown(data: dict | None = None) -> str:
    d = data if data is not None else load()
    lines = [
        "# Recurring Findings",
        "",
        "검증 과정에서 반복적으로 발견되는 패턴. 본 문서는 `memory/recurring_findings.json`에서",
        "자동 생성된다. 직접 편집하지 말고 `python -m tools.findings sync` 또는 `add` 명령을",
        "사용하라.",
        "",
        "| ID | 발생 빈도 | 영역 | 설명 | 우선 점검 도구/스킬 |",
        "|---|---|---|---|---|",
    ]
    for f in d["findings"]:
        lines.append(
            f"| {f['id']} | {_FREQUENCY_LABEL.get(f['frequency'], f['frequency'])} "
            f"| {f['domain']} | {f['description']} | `{f['primary_tool']}` |"
        )
    return "\n".join(lines) + "\n"


def sync(json_path: Path | None = None, md_path: Path | None = None) -> Path:
    data = load(json_path)
    out_path = md_path or MD_PATH
    out_path.write_text(render_markdown(data), encoding="utf-8")
    return out_path


def _cmd_sync(args: argparse.Namespace) -> int:
    sync()
    print("recurring_findings.md synced from JSON")
    return 0


def _cmd_add(args: argparse.Namespace) -> int:
    entry = add_finding(
        domain=args.domain,
        frequency=args.frequency,
        description=args.description,
        primary_tool=args.tool,
    )
    sync()
    print(f"added {entry['id']} ({entry['domain']}) and synced markdown")
    return 0


def _cmd_bump(args: argparse.Namespace) -> int:
    try:
        entry = bump_frequency(args.finding_id)
    except (KeyError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    sync()
    print(f"{entry['id']} -> {entry['frequency']}")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    data = load()
    for f in data["findings"]:
        print(f"{f['id']:<7} {f['frequency']:<10} {f['domain']:<14} {f['description']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="recurring_findings JSON sync/edit")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list").set_defaults(func=_cmd_list)
    sub.add_parser("sync").set_defaults(func=_cmd_sync)

    p_add = sub.add_parser("add")
    p_add.add_argument("--domain", required=True)
    p_add.add_argument("--frequency", required=True, choices=list(_FREQUENCY_ORDER))
    p_add.add_argument("--description", required=True)
    p_add.add_argument("--tool", required=True)
    p_add.set_defaults(func=_cmd_add)

    p_bump = sub.add_parser("bump")
    p_bump.add_argument("finding_id")
    p_bump.set_defaults(func=_cmd_bump)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
