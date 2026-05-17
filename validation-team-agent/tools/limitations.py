"""known_limitations JSON ↔ 마크다운 sync.

memory/known_limitations.json 이 SSoT. recurring_findings / model_notes 와
동일한 패턴.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = ROOT / "memory" / "known_limitations.json"
MD_PATH = ROOT / "memory" / "known_limitations.md"


def load(path: Path | None = None) -> dict:
    return json.loads((path or JSON_PATH).read_text(encoding="utf-8"))


def render_markdown(data: dict | None = None) -> str:
    d = data if data is not None else load()
    lines = [
        "# Known Limitations",
        "",
        "본 하니스의 알려진 한계. 본 문서는 `memory/known_limitations.json`에서",
        "자동 생성된다. 직접 편집하지 말고 `python -m tools.limitations sync`",
        "명령을 사용하라. 인간 검증자가 운영 시 반드시 인지해야 한다.",
        "",
    ]
    for i, cat in enumerate(d["categories"], start=1):
        lines.append(f"## {i}. {cat['title']}")
        for item in cat["items"]:
            lines.append(f"- {item}")
        lines.append("")
    return "\n".join(lines)


def sync(json_path: Path | None = None, md_path: Path | None = None) -> Path:
    data = load(json_path)
    out_path = md_path or MD_PATH
    out_path.write_text(render_markdown(data), encoding="utf-8")
    return out_path


def _cmd_sync(args: argparse.Namespace) -> int:
    sync()
    print("known_limitations.md synced from JSON")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    for cat in load()["categories"]:
        print(f"{cat['category']:<20} {len(cat['items'])} items  {cat['title']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="known_limitations JSON sync")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sync").set_defaults(func=_cmd_sync)
    sub.add_parser("list").set_defaults(func=_cmd_list)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
