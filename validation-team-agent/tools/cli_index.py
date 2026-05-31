"""validation-team-agent CLI index.

``python -m tools.<name> --help`` 으로 노출된 모든 CLI 의 1-line 설명을 한 곳에
모은다. 내부 검증자가 어떤 도구를 호출해야 하는지 빠르게 확인하기 위한 인덱스.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (module, headline) — module 은 `python -m <module>` 형태로 호출 가능해야 한다.
CLI_MODULES: list[tuple[str, str]] = [
    ("tools.run_validation", "신용 / PD 모형 thin runner"),
    ("tools.run_macro_validation", "거시 / forward-looking 모형 runner"),
    ("tools.run_ifrs9_validation", "IFRS 9 ECL 통합 runner"),
    ("tools.run_audit", "매트릭스 plan vs 실제 실행 감사"),
    ("tools.dry_run", "오케스트레이터 호출 시뮬레이션"),
    ("tools.dry_run_diff", "두 매트릭스 plan 비교"),
    ("tools.manifest", "change_manifest 편집/검증/promote"),
    ("tools.findings", "recurring_findings JSON ↔ md sync"),
    ("tools.model_notes", "model_specific_notes JSON ↔ md sync"),
    ("tools.policy_lint", "정책 임계값 일관성 lint"),
    ("tools.classify_error", "harness_debugger 6-카테고리 분류기"),
    ("tools.feedback_retention", "classify_feedback retention/anonymize"),
    ("tools.audit_retention", "audit.jsonl retention"),
    ("tools.runner_result", "runner 결과 dict schema 검증"),
]


def _help_first_line(module: str, timeout: float = 10.0) -> str:
    cmd = [sys.executable, "-m", module, "--help"]
    try:
        res = subprocess.run(
            cmd, cwd=str(ROOT), capture_output=True, text=True, timeout=timeout
        )
    except (OSError, subprocess.TimeoutExpired):
        return "(help unavailable)"
    text = (res.stdout or "") + (res.stderr or "")
    for line in text.splitlines():
        if line.strip().startswith("description:") or "description:" in line:
            return line.split("description:", 1)[1].strip()
    # argparse default: 첫 줄은 보통 usage. 두 번째 빈 줄 이후가 설명.
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    if len(blocks) >= 2 and not blocks[1].startswith("positional"):
        return blocks[1].splitlines()[0].strip()
    return text.splitlines()[0].strip() if text else "(no help)"


def build_index() -> list[dict]:
    rows = []
    for module, headline in CLI_MODULES:
        rows.append(
            {
                "module": module,
                "invocation": f"python -m {module}",
                "headline": headline,
            }
        )
    return rows


def render_markdown(rows: list[dict]) -> str:
    lines = [
        "# CLI Index",
        "",
        "모든 CLI 의 1-line 인덱스. `python -m <module> --help` 로 상세 옵션 확인.",
        "",
        "| Module | Invocation | Headline |",
        "|---|---|---|",
    ]
    for row in rows:
        lines.append(f"| `{row['module']}` | `{row['invocation']}` | {row['headline']} |")
    return "\n".join(lines) + "\n"


def _cmd_show(args: argparse.Namespace) -> int:
    rows = build_index()
    if args.json:
        json.dump(rows, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_markdown(rows))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="validation-team-agent CLI index")
    parser.add_argument("--json", action="store_true")
    parser.set_defaults(func=_cmd_show)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
