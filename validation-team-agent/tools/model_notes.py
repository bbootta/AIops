"""model_specific_notes JSON ↔ 마크다운 sync.

memory/model_specific_notes.json 이 SSoT. 마크다운은 본 도구로 생성된다.
recurring_findings 와 동일한 패턴.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JSON_PATH = ROOT / "memory" / "model_specific_notes.json"
MD_PATH = ROOT / "memory" / "model_specific_notes.md"


def load(path: Path | None = None) -> dict:
    return json.loads((path or JSON_PATH).read_text(encoding="utf-8"))


def render_markdown(data: dict | None = None) -> str:
    d = data if data is not None else load()
    lines = [
        "# Model-Specific Notes",
        "",
        "모형군별 검증 시 유의사항. 본 문서는 `memory/model_specific_notes.json`에서",
        "자동 생성된다. 직접 편집하지 말고 `python -m tools.model_notes sync` 명령을",
        "사용하라. 모든 노트는 **참고 정보**이며, 정책 확정은 인간 검증자의 검토를",
        "거쳐야 한다.",
        "",
    ]
    for group in d["groups"]:
        lines.append(f"## {group['title']}")
        for note in group["notes"]:
            lines.append(f"- {note}")
        lines.append("")
    return "\n".join(lines)


def sync(json_path: Path | None = None, md_path: Path | None = None) -> Path:
    data = load(json_path)
    out_path = md_path or MD_PATH
    out_path.write_text(render_markdown(data), encoding="utf-8")
    return out_path


def _cmd_sync(args: argparse.Namespace) -> int:
    sync()
    print("model_specific_notes.md synced from JSON")
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    for group in load()["groups"]:
        print(f"{group['model_group']:<20} {len(group['notes'])} notes  {group['title']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="model_specific_notes JSON sync")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("sync").set_defaults(func=_cmd_sync)
    sub.add_parser("list").set_defaults(func=_cmd_list)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
