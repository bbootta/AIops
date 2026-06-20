"""vta 단일 CLI entry point (Phase 4).

`python -m vta <subcommand> [args]` 형태로 v1 의 CLI 전체에 dispatch.

v1 의 모든 명령은 본 entry 가 없어도 그대로 동작한다 (`python -m tools.*`).
본 모듈은 단일 진입 편의를 위한 wrapper 일 뿐, v1 의 sys.exit / argparse
동작을 그대로 보존한다.

usage:
    python -m vta --help                 # subcommand 카탈로그
    python -m vta workflow demo          # = python -m tools.run_workflow_demo
    python -m vta workflow audit         # = python -m tools.run_audit
    python -m vta manifest <cmd>         # = python -m tools.manifest <cmd>
    python -m vta sample credit ...      # = python -m tools.sample_generators (helper)
    python -m vta policy lint            # = python -m tools.policy_lint
    python -m vta policy list            # 신규: 정책 파일 인덱스
    python -m vta classify <cmd>         # = python -m tools.classify_error <cmd>
"""

from __future__ import annotations

import runpy
import sys

# subcommand → v1 module 매핑
_DISPATCH = {
    ("workflow", "demo"): "tools.run_workflow_demo",
    ("workflow", "audit"): "tools.run_audit",
    ("workflow", "diff"): "tools.dry_run_diff",
    ("workflow", "dryrun"): "tools.dry_run",
    ("workflow", "viz"): "tools.workflow_viz",
    ("benchmark",): "tools.benchmark",
    ("kpi",): "tools.governance_kpi",
    ("report", "pdf"): "tools.report_pdf",
    ("report", "pack"): "tools.report_pack",
    ("report", "export"): "tools.report_export",
    ("findings", "map"): "tools.findings_mapping",
    ("pack", "diff"): "tools.pack_diff",
    ("dashboard",): "tools.dashboard",
    ("manifest",): "tools.manifest",
    ("findings",): "tools.findings",
    ("model-notes",): "tools.model_notes",
    ("limitations",): "tools.limitations",
    ("policy", "lint"): "tools.policy_lint",
    ("classify",): "tools.classify_error",
    ("feedback",): "tools.feedback_retention",
    ("audit-retention",): "tools.audit_retention",
    ("runner-result",): "tools.runner_result",
    ("cli-index",): "tools.cli_index",
    ("credit",): "tools.run_validation",
    ("macro",): "tools.run_macro_validation",
    ("ifrs9",): "tools.run_ifrs9_validation",
}

# v2-native subcommands (no v1 dispatch — 본 모듈 내 함수 호출)
_NATIVE = {
    ("policy", "list"),
    ("policy", "show"),
}


def _print_help() -> int:
    sys.stdout.write(__doc__ + "\n")
    sys.stdout.write("Available subcommands:\n\n")
    seen: set[str] = set()
    for key in sorted(_DISPATCH.keys()):
        head = key[0]
        if head not in seen:
            seen.add(head)
            sys.stdout.write(f"  {head}\n")
    sys.stdout.write("\nRun any subcommand with --help for details.\n")
    return 0


def _native_policy_list() -> int:
    from vta.policies import list_policies

    for name, path in list_policies():
        sys.stdout.write(f"{name}\t{path}\n")
    return 0


def _native_policy_show(name: str) -> int:
    import json as _json

    from vta.policies import load

    sys.stdout.write(_json.dumps(load(name), ensure_ascii=False, indent=2) + "\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])
    if not args or args[0] in {"-h", "--help"}:
        return _print_help()

    # 가장 긴 매칭 우선
    for length in (2, 1):
        if len(args) < length:
            continue
        key = tuple(args[:length])
        if key in _NATIVE:
            sub_args = args[length:]
            if key == ("policy", "list"):
                return _native_policy_list()
            if key == ("policy", "show"):
                if not sub_args:
                    sys.stderr.write("usage: vta policy show <name>\n")
                    return 2
                return _native_policy_show(sub_args[0])
        if key in _DISPATCH:
            module = _DISPATCH[key]
            # v1 모듈로 args 전달. argparse.exit 가 SystemExit 던지므로 trap.
            sys.argv = [f"python -m {module}", *args[length:]]
            try:
                runpy.run_module(module, run_name="__main__")
            except SystemExit as exc:
                return int(exc.code or 0)
            return 0

    sys.stderr.write(f"unknown subcommand: {' '.join(args)}\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
