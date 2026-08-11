"""외부 업무요건(PRD-VAL) 대비 하니스 구현 커버리지 — 검증 가능한 매트릭스.

커버리지 문서는 방치되면 거짓말이 된다. 본 모듈은 그것을 구조적으로 막는다.

``verify`` 가 강제하는 규칙:

1. ``implemented`` / ``partial`` 은 **evidence 파일이 실재해야** 주장할 수 있다.
   파일을 지우거나 이름을 바꾸면 검증이 실패한다.
2. ``missing`` 은 evidence 를 가질 수 없다 (주장과 근거의 방향이 어긋나므로).
3. ``partial`` / ``missing`` 은 gap 을 반드시 서술해야 한다.
4. 요건 ID 는 중복 없이 연속이어야 한다 (누락된 요건을 조용히 빠뜨릴 수 없다).

CLAUDE.md §5: 검증 기준을 임의로 완화하지 않는다. 커버리지 상향은 근거 파일과
테스트가 먼저 존재할 때만 가능하다.

사용:
    python -m tools.val_coverage report
    python -m tools.val_coverage verify      # 드리프트 시 exit 1
    python -m tools.val_coverage report --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
COVERAGE_PATH = ROOT / "harness" / "val_requirement_coverage.json"

VALID_STATUS = ("implemented", "partial", "missing")
#: 커버리지 점수 가중치 — partial 을 0.5 로 세어 진행률을 과대·과소 표기하지 않는다.
_WEIGHT = {"implemented": 1.0, "partial": 0.5, "missing": 0.0}


def load(path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path) if path else COVERAGE_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def verify(data: dict[str, Any] | None = None, *,
           root: Path | None = None) -> list[str]:
    """규칙 위반 목록을 반환한다 (빈 리스트면 통과)."""
    data = data if data is not None else load()
    base = root or ROOT
    problems: list[str] = []
    reqs = data.get("requirements", [])
    if not reqs:
        return ["requirements 가 비어 있다"]

    seen: set[str] = set()
    for r in reqs:
        rid = r.get("id", "?")
        if rid in seen:
            problems.append(f"{rid}: 중복 ID")
        seen.add(rid)

        status = r.get("status")
        if status not in VALID_STATUS:
            problems.append(f"{rid}: 잘못된 status={status!r}")
            continue

        evidence = r.get("evidence", [])
        gap = (r.get("gap") or "").strip()

        if status == "missing":
            if evidence:
                problems.append(
                    f"{rid}: status=missing 인데 evidence 가 있다 {evidence}")
            if not gap:
                problems.append(f"{rid}: missing 인데 gap 서술이 없다")
        else:
            if not evidence:
                problems.append(
                    f"{rid}: status={status} 인데 evidence 가 없다 "
                    "(근거 없는 구현 주장 금지)")
            for path in evidence:
                if not (base / path).exists():
                    problems.append(f"{rid}: evidence 파일 부재 — {path}")
            if status == "partial" and not gap:
                problems.append(f"{rid}: partial 인데 gap 서술이 없다")

    # ID 연속성 — VAL-001 … VAL-0NN 이 빠짐없이 존재해야 한다
    nums = sorted(int(x.split("-")[1]) for x in seen if "-" in x)
    if nums and nums != list(range(1, len(nums) + 1)):
        missing = sorted(set(range(1, max(nums) + 1)) - set(nums))
        problems.append(f"요건 ID 불연속 — 누락: {missing}")
    return problems


def summarize(data: dict[str, Any] | None = None) -> dict[str, Any]:
    data = data if data is not None else load()
    reqs = data["requirements"]
    counts = {s: sum(1 for r in reqs if r["status"] == s) for s in VALID_STATUS}
    score = sum(_WEIGHT[r["status"]] for r in reqs)
    by_phase: dict[str, dict[str, int]] = {}
    for r in reqs:
        slot = by_phase.setdefault(r.get("phase", "-"), dict.fromkeys(VALID_STATUS, 0))
        slot[r["status"]] += 1
    return {
        "total": len(reqs),
        "counts": counts,
        "coverage_score": round(score, 1),
        "coverage_pct": round(100.0 * score / len(reqs), 1),
        "by_phase": by_phase,
    }


_MARK = {"implemented": "구현", "partial": "부분", "missing": "미구현"}


def render_report(data: dict[str, Any] | None = None) -> str:
    data = data if data is not None else load()
    s = summarize(data)
    lines = [
        f"PRD-VAL 요건 커버리지 — {data['source']}",
        "",
        f"총 {s['total']}건 · 구현 {s['counts']['implemented']} · "
        f"부분 {s['counts']['partial']} · 미구현 {s['counts']['missing']} "
        f"· 커버리지 {s['coverage_pct']}% "
        f"(부분={_WEIGHT['partial']} 가중)",
        "",
    ]
    phase = None
    for r in data["requirements"]:
        if r["phase"] != phase:
            phase = r["phase"]
            lines.append(f"[{phase}]")
        lines.append(f"  {r['id']} {r['title']} — {_MARK[r['status']]}")
        for e in r.get("evidence", []):
            lines.append(f"      근거: {e}")
        if r.get("gap"):
            lines.append(f"      공백: {r['gap']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PRD-VAL 업무요건 대비 하니스 구현 커버리지")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_rep = sub.add_parser("report", help="커버리지 현황 출력")
    p_rep.add_argument("--json", action="store_true")
    p_rep.add_argument("--path", default=None,
                       help="다른 매트릭스 파일 (기본: PRD-VAL)")

    p_ver = sub.add_parser("verify",
                           help="근거 실재성·규칙 위반 검사 (위반 시 exit 1)")
    p_ver.add_argument("--path", default=None,
                       help="다른 매트릭스 파일 (예: harness/valdoc_coverage.json)")

    args = parser.parse_args(argv)
    data = load(args.path)

    if args.cmd == "verify":
        problems = verify(data)
        if problems:
            for p in problems:
                sys.stderr.write(f"위반: {p}\n")
            sys.stderr.write(f"\n커버리지 매트릭스 검증 실패 ({len(problems)}건)\n")
            return 1
        s = summarize(data)
        sys.stdout.write(
            f"커버리지 매트릭스 정상 — {s['total']}건, "
            f"근거 파일 전부 실재, 커버리지 {s['coverage_pct']}%\n")
        return 0

    if args.json:
        sys.stdout.write(json.dumps(
            {"summary": summarize(data), "requirements": data["requirements"]},
            ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(render_report(data) + "\n")
    return 0


__all__ = ["load", "verify", "summarize", "render_report", "COVERAGE_PATH"]


if __name__ == "__main__":
    raise SystemExit(main())
