"""change_manifest 상태 전환 CLI.

상태 전환 규칙:
    proposed   -> applied   (사용자 승인 후 적용 단계)
    applied    -> validated (검증 완료)
    *          -> rolled_back (강제 롤백)
    validated  -> 다른 상태로 전환 불가 (immutable)

CLI:
    python -m tools.manifest list
    python -m tools.manifest add --component path --type create --evidence ... --root-cause ...
    python -m tools.manifest promote CHG-0002 --to applied
    python -m tools.manifest validate
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Sequence

ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "harness" / "change_manifest.schema.json"
MANIFEST_PATH = ROOT / "harness" / "change_manifest.json"

_TRANSITIONS = {
    "proposed": {"applied", "rolled_back"},
    "applied": {"validated", "rolled_back"},
    "validated": set(),
    "rolled_back": set(),
}


class ManifestError(RuntimeError):
    pass


def load(manifest_path: Path | None = None) -> dict:
    p = manifest_path or MANIFEST_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def save(manifest: dict, manifest_path: Path | None = None) -> Path:
    p = manifest_path or MANIFEST_PATH
    p.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def validate(
    manifest: dict | None = None,
    schema_path: Path | None = None,
) -> None:
    """jsonschema 검증 + change_id 유일성 + status 값 검증."""
    import jsonschema

    m = manifest or load()
    schema = json.loads((schema_path or SCHEMA_PATH).read_text(encoding="utf-8"))
    jsonschema.validate(m, schema)
    ids = [c["change_id"] for c in m["changes"]]
    if len(set(ids)) != len(ids):
        raise ManifestError(f"duplicate change_id detected: {ids}")


def _next_change_id(manifest: dict) -> str:
    nums = []
    for c in manifest["changes"]:
        try:
            nums.append(int(c["change_id"].split("-", 1)[1]))
        except (IndexError, ValueError):
            continue
    return f"CHG-{(max(nums) + 1) if nums else 1:04d}"


def add_change(
    component: str,
    change_type: str,
    evidence: str,
    root_cause: str,
    targeted_fix: str,
    expected_benefit: str,
    expected_regression_risk: str,
    validation_method: str,
    rollback_rule: str,
    human_approval_required: bool = True,
    manifest_path: Path | None = None,
) -> dict:
    """새 항목을 status='proposed'로 추가하고 저장한다. 반환은 추가된 항목."""
    m = load(manifest_path)
    entry = {
        "change_id": _next_change_id(m),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "component": component,
        "change_type": change_type,
        "evidence": evidence,
        "root_cause": root_cause,
        "targeted_fix": targeted_fix,
        "expected_benefit": expected_benefit,
        "expected_regression_risk": expected_regression_risk,
        "validation_method": validation_method,
        "rollback_rule": rollback_rule,
        "human_approval_required": bool(human_approval_required),
        "status": "proposed",
    }
    m["changes"].append(entry)
    validate(m)
    save(m, manifest_path)
    return entry


def promote(change_id: str, to: str, manifest_path: Path | None = None) -> dict:
    """상태 전환을 수행한다. 위반 시 ManifestError."""
    if to not in {"applied", "validated", "rolled_back"}:
        raise ManifestError(f"invalid target status: {to}")
    m = load(manifest_path)
    target = None
    for c in m["changes"]:
        if c["change_id"] == change_id:
            target = c
            break
    if target is None:
        raise ManifestError(f"change_id not found: {change_id}")
    current = target["status"]
    allowed = _TRANSITIONS[current]
    if to not in allowed:
        raise ManifestError(
            f"invalid transition {current!r} -> {to!r}; allowed = {sorted(allowed)}"
        )
    target["status"] = to
    target["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    validate(m)
    save(m, manifest_path)
    return target


def list_changes(manifest_path: Path | None = None) -> list[dict]:
    m = load(manifest_path)
    return [
        {"change_id": c["change_id"], "status": c["status"], "component": c["component"]}
        for c in m["changes"]
    ]


def _cmd_list(args: argparse.Namespace) -> int:
    rows = list_changes(args.manifest)
    width = max((len(r["change_id"]) for r in rows), default=8)
    for r in rows:
        print(f"{r['change_id']:<{width}}  {r['status']:<11}  {r['component']}")
    return 0


def _cmd_add(args: argparse.Namespace) -> int:
    entry = add_change(
        component=args.component,
        change_type=args.type,
        evidence=args.evidence,
        root_cause=args.root_cause,
        targeted_fix=args.targeted_fix,
        expected_benefit=args.expected_benefit,
        expected_regression_risk=args.expected_regression_risk,
        validation_method=args.validation_method,
        rollback_rule=args.rollback_rule,
        human_approval_required=not args.no_human_approval,
        manifest_path=args.manifest,
    )
    print(f"added {entry['change_id']} (status=proposed)")
    return 0


def _cmd_promote(args: argparse.Namespace) -> int:
    try:
        entry = promote(args.change_id, args.to, manifest_path=args.manifest)
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(f"{entry['change_id']} -> {entry['status']}")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    try:
        validate(manifest=None if args.manifest is None else load(args.manifest))
    except Exception as exc:  # pragma: no cover - delegated to jsonschema/ManifestError
        print(f"invalid: {exc}", file=sys.stderr)
        return 2
    print("manifest valid")
    return 0


def promote_if_passing(
    change_ids: Sequence[str],
    to: str,
    *,
    confirmed_by_human: bool,
    pytest_runner=None,
    manifest_path: Path | None = None,
) -> dict:
    """pytest 통과 + 사용자 명시 승인이 모두 있을 때만 다수 항목을 promote.

    confirmed_by_human이 False이면 ManifestError. pytest_runner는 인자 없이 호출
    가능하고 (returncode_int, stdout_str) 튜플을 반환하는 callable. 기본은 실제
    ``python -m pytest`` 실행.
    """
    if to not in {"applied", "validated"}:
        raise ManifestError(f"promote_if_passing only supports applied/validated, got {to!r}")
    if not confirmed_by_human:
        raise ManifestError("human confirmation required (pass confirmed_by_human=True)")

    if pytest_runner is None:
        pytest_runner = _default_pytest_runner

    rc, stdout = pytest_runner()
    if rc != 0:
        raise ManifestError(f"pytest failed (rc={rc}); promotion blocked")

    promoted: list[dict] = []
    for cid in change_ids:
        promoted.append(promote(cid, to, manifest_path=manifest_path))
    return {"pytest_returncode": rc, "pytest_stdout_tail": stdout[-400:], "promoted": promoted}


def _default_pytest_runner():
    import subprocess

    proj_root = Path(__file__).resolve().parent.parent
    res = subprocess.run(
        [sys.executable, "-m", "pytest", "-q"],
        cwd=str(proj_root),
        capture_output=True,
        text=True,
        check=False,
    )
    return res.returncode, (res.stdout or "") + (res.stderr or "")


def _cmd_promote_if_passing(args: argparse.Namespace) -> int:
    try:
        out = promote_if_passing(
            args.change_ids,
            args.to,
            confirmed_by_human=args.i_am_human,
            manifest_path=args.manifest,
        )
    except ManifestError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    for entry in out["promoted"]:
        print(f"{entry['change_id']} -> {entry['status']} (pytest rc=0)")
    return 0


def _cmd_from_classification(args: argparse.Namespace) -> int:
    """classify_error.suggest_manifest_fields 결과를 manifest add 인자로 사용해 신규 항목 추가.

    인간 검증자가 evidence / expected_benefit / expected_regression_risk /
    validation_method / rollback_rule 만 직접 채우면 root_cause / targeted_fix는
    자동 분류 결과로 채워진다. confidence=low 인 경우 경고 출력 후 추가는 진행.
    """
    if __package__:
        from . import classify_error as ce  # type: ignore
    else:  # pragma: no cover - direct module execution
        from tools import classify_error as ce  # type: ignore

    if args.error_file:
        text = Path(args.error_file).read_text(encoding="utf-8")
    elif args.error_text is not None:
        text = args.error_text
    else:
        text = sys.stdin.read()
    suggestion = ce.suggest_manifest_fields(text)
    if suggestion["confidence"] == "low":
        print(
            f"warning: low-confidence classification (category={suggestion['category']}). "
            "Review root_cause/targeted_fix carefully.",
            file=sys.stderr,
        )

    entry = add_change(
        component=args.component,
        change_type=args.type,
        evidence=args.evidence,
        root_cause=suggestion["root_cause"],
        targeted_fix=suggestion["targeted_fix"],
        expected_benefit=args.expected_benefit,
        expected_regression_risk=args.expected_regression_risk,
        validation_method=args.validation_method,
        rollback_rule=args.rollback_rule,
        human_approval_required=not args.no_human_approval,
        manifest_path=args.manifest,
    )
    print(
        f"added {entry['change_id']} (status=proposed, "
        f"category={suggestion['category']}, confidence={suggestion['confidence']})"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="change_manifest CLI")
    parser.add_argument("--manifest", type=Path, default=None)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list").set_defaults(func=_cmd_list)

    p_add = sub.add_parser("add")
    p_add.add_argument("--component", required=True)
    p_add.add_argument("--type", required=True, choices=["create", "modify", "delete", "rollback"])
    p_add.add_argument("--evidence", required=True)
    p_add.add_argument("--root-cause", required=True)
    p_add.add_argument("--targeted-fix", required=True)
    p_add.add_argument("--expected-benefit", required=True)
    p_add.add_argument("--expected-regression-risk", required=True)
    p_add.add_argument("--validation-method", required=True)
    p_add.add_argument("--rollback-rule", required=True)
    p_add.add_argument("--no-human-approval", action="store_true")
    p_add.set_defaults(func=_cmd_add)

    p_promote = sub.add_parser("promote")
    p_promote.add_argument("change_id")
    p_promote.add_argument("--to", required=True, choices=["applied", "validated", "rolled_back"])
    p_promote.set_defaults(func=_cmd_promote)

    sub.add_parser("validate").set_defaults(func=_cmd_validate)

    p_pip = sub.add_parser("promote-if-passing")
    p_pip.add_argument("change_ids", nargs="+")
    p_pip.add_argument("--to", required=True, choices=["applied", "validated"])
    p_pip.add_argument(
        "--i-am-human",
        action="store_true",
        help="명시적 인간 승인. 본 플래그가 없으면 차단된다.",
    )
    p_pip.set_defaults(func=_cmd_promote_if_passing)

    p_fc = sub.add_parser("from-classification",
                          help="error text → classify_error suggestion으로 root_cause/targeted_fix 자동 채움")
    p_fc.add_argument("--component", required=True)
    p_fc.add_argument("--type", required=True, choices=["create", "modify", "delete", "rollback"])
    p_fc.add_argument("--evidence", required=True)
    p_fc.add_argument("--expected-benefit", required=True)
    p_fc.add_argument("--expected-regression-risk", required=True)
    p_fc.add_argument("--validation-method", required=True)
    p_fc.add_argument("--rollback-rule", required=True)
    p_fc.add_argument("--no-human-approval", action="store_true")
    p_fc.add_argument("--error-file", type=str, default=None,
                      help="path to error log/trace file")
    p_fc.add_argument("--error-text", type=str, default=None,
                      help="error text inline (or piped via stdin)")
    p_fc.set_defaults(func=_cmd_from_classification)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
