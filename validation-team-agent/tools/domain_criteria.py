"""도메인 업무요건 → 적합성검증 기준 항목 원장.

RYNTA BRD Level 1 요건 131건을 부문·검증관점·기준·자동화 상태로 전개한
`harness/domain_requirement_criteria.json`을 읽어 조회·집계·검증한다.

`verify`는 근거 실재성을 강제한다: `automated`로 선언했는데 근거 파일이
없으면 위반이다. 통과가 곧 구현이 아니라는 규율을 파일 단위로 고정한다.

사용:
    python -m tools.domain_criteria list [--section 08] [--scope 은행]
    python -m tools.domain_criteria report
    python -m tools.domain_criteria verify
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "harness" / "domain_requirement_criteria.json"

AUTOMATION = ("automated", "manual", "out_of_scope")


def load(path: Path | str = CATALOG) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def violations(data: dict, root: Path = ROOT) -> list[str]:
    """근거 실재성·필드 정합성 위반 목록. 비어 있으면 정상."""
    out: list[str] = []
    seen: set[str] = set()
    sections = data.get("sections", {})
    lenses = set(data.get("lenses", ()))

    for c in data.get("criteria", ()):
        rid = c.get("req_id", "?")
        if rid in seen:
            out.append(f"{rid}: req_id 중복")
        seen.add(rid)

        auto = c.get("automation")
        if auto not in AUTOMATION:
            out.append(f"{rid}: automation 값이 정의 밖 ({auto})")
            continue

        ev = c.get("evidence", [])
        if auto == "automated":
            if not ev:
                out.append(f"{rid}: automated 인데 근거가 0건")
            for p in ev:
                if not (root / p).exists():
                    out.append(f"{rid}: 근거 파일 없음: {p}")
        else:
            if ev:
                out.append(f"{rid}: {auto} 인데 근거가 선언됨: 통제가 없다는 뜻이어야 한다")
            if not c.get("note"):
                out.append(f"{rid}: {auto} 인데 사유(note)가 비어 있다")

        if c.get("section") not in sections:
            out.append(f"{rid}: 부문 코드가 정의 밖 ({c.get('section')})")
        for l in c.get("lens", ()):
            if l not in lenses:
                out.append(f"{rid}: 검증 관점이 정의 밖 ({l})")
        if not c.get("criterion"):
            out.append(f"{rid}: 검증 기준 문장이 비어 있다")

    return out


def _cmd_list(args) -> int:
    data = load(args.catalog)
    rows = data["criteria"]
    if args.section:
        rows = [c for c in rows if c["section"] == args.section]
    if args.scope:
        rows = [c for c in rows if c["scope"] == args.scope]
    if args.automation:
        rows = [c for c in rows if c["automation"] == args.automation]
    for c in rows:
        mark = {"automated": "[자동]", "manual": "[수동]",
                "out_of_scope": "[범위밖]"}[c["automation"]]
        print(f'{mark} {c["req_id"]:14s} {c["section"]} {c["title"]}')
        print(f'        {c["criterion"]}')
        if c["evidence"]:
            print(f'        근거: {" · ".join(c["evidence"])}')
        elif c["note"]:
            print(f'        사유: {c["note"]}')
    print(f"\n{len(rows)}건")
    return 0


def _cmd_report(args) -> int:
    data = load(args.catalog)
    rows = data["criteria"]
    auto = Counter(c["automation"] for c in rows)
    print(f'도메인 업무요건 → 적합성검증 기준 항목: {data["source"]}')
    print(f'원문 지문 {data["source_sha256"][:16]}… · 레지스터 {data["source_register"]}')
    print(f'\n총 {len(rows)}건 · 자동 {auto["automated"]} · 수동 {auto["manual"]} '
          f'· 범위밖 {auto["out_of_scope"]}')

    print("\n[부문별]")
    for code, name in data["sections"].items():
        sec = [c for c in rows if c["section"] == code]
        if not sec:
            continue
        a = sum(1 for c in sec if c["automation"] == "automated")
        m = sum(1 for c in sec if c["automation"] == "manual")
        o = len(sec) - a - m
        print(f'  {code} {name:28s} {len(sec):3d}건 · 자동 {a:3d} · 수동 {m:2d} · 범위밖 {o:3d}')

    print("\n[검증 관점별] (중복 계상: 한 요건이 여러 관점을 가진다)")
    lens = Counter(l for c in rows for l in c["lens"])
    for l in data["lenses"]:
        print(f'  {l:6s} {lens.get(l, 0):3d}건')

    print("\n[업권별]")
    for s, n in sorted(Counter(c["scope"] for c in rows).items()):
        a = sum(1 for c in rows if c["scope"] == s and c["automation"] == "automated")
        print(f'  {s:4s} {n:3d}건 · 자동 {a}')

    manual = [c for c in rows if c["automation"] == "manual"]
    if manual:
        print(f"\n[사람 검토로 남은 항목 {len(manual)}건: 통제 공백]")
        for c in manual:
            print(f'  {c["req_id"]:14s} {c["title"]}: {c["note"]}')
    print("\n> 자동 통제가 있다는 것이 요건을 다 덮는다는 뜻은 아니다. 범위밖은 "
          "은행 8부문 검증 범위 밖이라는 선언이며 요건이 불필요하다는 뜻이 아니다.")
    return 0


def _cmd_verify(args) -> int:
    data = load(args.catalog)
    bad = violations(data)
    if bad:
        print(f"위반 {len(bad)}건")
        for b in bad:
            print("  -", b)
        return 1
    rows = data["criteria"]
    auto = sum(1 for c in rows if c["automation"] == "automated")
    ev = sum(len(c["evidence"]) for c in rows)
    print(f"기준 항목 정상: {len(rows)}건 · 자동 {auto}건의 근거 {ev}개 파일 전부 실재")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalog", default=str(CATALOG))
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="기준 항목 조회")
    p.add_argument("--section", help="부문 코드 (01~08, --)")
    p.add_argument("--scope", help="업권 (공통·은행·증권)")
    p.add_argument("--automation", choices=AUTOMATION)
    p.set_defaults(func=_cmd_list)

    p = sub.add_parser("report", help="부문·관점·업권별 집계")
    p.set_defaults(func=_cmd_report)

    p = sub.add_parser("verify", help="근거 실재성 검사 (위반 시 exit 1)")
    p.set_defaults(func=_cmd_verify)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
