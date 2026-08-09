"""국내 감독규정 검증 항목 원장 — 조회·집계·검증.

`harness/domestic_rule_criteria.json`을 읽는다. `verify`는 세 가지를 강제한다.

1. 근거 원문의 지문(SHA-256)이 카탈로그 기록과 일치하는가 — 원문이 바뀌면 드러난다
2. 각 항목의 인용이 **원문에서 실제로 해석되는가**, 그리고 기록된 라인이 맞는가
3. `automated`로 선언한 항목의 하니스 근거 파일이 실재하는가

사용:
    python -m tools.domestic_criteria list [--section 05]
    python -m tools.domestic_criteria report
    python -m tools.domestic_criteria cite-check "별표 3의6"
    python -m tools.domestic_criteria verify
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from tools.gen_domestic_criteria import SOURCE, heading_of, resolve

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "harness" / "domestic_rule_criteria.json"

AUTOMATION = ("automated", "manual")


def load(path: Path | str = CATALOG) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def violations(data: dict, root: Path = ROOT) -> list[str]:
    out: list[str] = []
    src = root / data["source"]["path"]
    if not src.exists():
        return [f"근거 원문이 없다 — {data['source']['path']}"]

    digest = hashlib.sha256(src.read_bytes()).hexdigest()
    if digest != data["source"]["sha256"]:
        out.append(f"원문 지문 불일치 — 기록 {data['source']['sha256'][:16]}… "
                   f"실제 {digest[:16]}… (재생성 필요)")
        return out

    lines = src.read_text(encoding="utf-8").splitlines()
    seen: set[str] = set()
    for c in data["criteria"]:
        rid = c["rule_id"]
        if rid in seen:
            out.append(f"{rid}: rule_id 중복")
        seen.add(rid)

        ln = resolve(c["citation"], lines)
        if ln is None:
            out.append(f'{rid}: 인용이 원문에서 해석되지 않음 — {c["citation"]}')
        elif ln != c["source_line"]:
            out.append(f'{rid}: 기록 라인이 원문과 다름 — {c["citation"]} '
                       f'기록 {c["source_line"]} 실제 {ln}')
        elif heading_of(ln, lines) != c["source_heading"]:
            out.append(f'{rid}: 기록 표제가 원문과 다름 — {c["citation"]}')

        if c["automation"] not in AUTOMATION:
            out.append(f'{rid}: automation 값이 정의 밖 ({c["automation"]})')
        elif c["automation"] == "automated":
            if not c["evidence"]:
                out.append(f"{rid}: automated 인데 근거가 0건")
            for p in c["evidence"]:
                if not (root / p).exists():
                    out.append(f"{rid}: 근거 파일 없음 — {p}")
        else:
            if c["evidence"]:
                out.append(f"{rid}: manual 인데 근거가 선언됨")
            if not c["note"]:
                out.append(f"{rid}: manual 인데 사유(note)가 비어 있다")

        if c["section"] not in data["sections"]:
            out.append(f'{rid}: 부문 코드가 정의 밖 ({c["section"]})')
        for l in c["lens"]:
            if l not in data["lenses"]:
                out.append(f'{rid}: 검증 관점이 정의 밖 ({l})')
    return out


def _cmd_list(args) -> int:
    data = load(args.catalog)
    rows = data["criteria"]
    if args.section:
        rows = [c for c in rows if c["section"] == args.section]
    if args.automation:
        rows = [c for c in rows if c["automation"] == args.automation]
    for c in rows:
        mark = "[자동]" if c["automation"] == "automated" else "[수동]"
        print(f'{mark} {c["rule_id"]}  {c["section"]}  {c["citation"]} '
              f'(원문 L{c["source_line"]})')
        print(f'        {c["criterion"]}')
        if c["evidence"]:
            print(f'        근거: {" · ".join(c["evidence"])}')
        elif c["note"]:
            print(f'        공백: {c["note"]}')
    print(f"\n{len(rows)}건")
    return 0


def _cmd_report(args) -> int:
    data = load(args.catalog)
    rows = data["criteria"]
    s = data["source"]
    print(f'국내 감독규정 검증 항목 — {s["title"]} [시행 {s["effective"]}]')
    print(f'근거수준 국내구속 · 원문 지문 {s["sha256"][:16]}…')
    print(f'원문 수록: 별표 {s["n_schedules"]}건 · 조문 heading {s["n_article_headings"]}건')
    auto = Counter(c["automation"] for c in rows)
    print(f'\n총 {len(rows)}건 · 자동 {auto["automated"]} · 수동 {auto["manual"]}')

    print("\n[부문별]")
    for code, name in data["sections"].items():
        sec = [c for c in rows if c["section"] == code]
        if not sec:
            continue
        a = sum(1 for c in sec if c["automation"] == "automated")
        print(f'  {code} {name:22s} {len(sec):3d}건 · 자동 {a:2d} · 수동 {len(sec)-a:2d}')

    print("\n[검증 관점별] (중복 계상)")
    lens = Counter(l for c in rows for l in c["lens"])
    for l in data["lenses"]:
        print(f'  {l:6s} {lens.get(l, 0):3d}건')

    gap = [c for c in rows if c["automation"] == "manual"]
    print(f"\n[국내 기준을 덮지 못하는 항목 {len(gap)}건 — 통제 공백]")
    for c in gap:
        print(f'  {c["rule_id"]} {c["citation"]:12s} {c["note"]}')
    print("\n> 인용이 원문에서 해석된다는 것은 조문·별표가 존재한다는 뜻이며, "
          "그 내용을 다 덮는다는 뜻이 아니다.")
    return 0


def _cmd_cite_check(args) -> int:
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    ln = resolve(args.citation, lines)
    if ln is None:
        print(f'해석 실패 — "{args.citation}" 는 원문에서 찾을 수 없다')
        return 1
    print(f'해석됨 — L{ln}: {heading_of(ln, lines)}')
    for l in lines[ln:ln + args.context]:
        if l.strip():
            print(f'  {l[:160]}')
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
    print(f'국내 검증 항목 정상 — {len(rows)}건 · 인용 전부 원문에서 해석 · '
          f'자동 {auto}건의 근거 {ev}개 파일 실재 · 원문 지문 일치')
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalog", default=str(CATALOG))
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="검증 항목 조회")
    p.add_argument("--section", help="부문 코드 (01~08)")
    p.add_argument("--automation", choices=AUTOMATION)
    p.set_defaults(func=_cmd_list)

    p = sub.add_parser("report", help="부문·관점별 집계")
    p.set_defaults(func=_cmd_report)

    p = sub.add_parser("cite-check", help="인용이 원문에서 해석되는지 확인")
    p.add_argument("citation", help='예: "별표 3의6" · "제29조의3"')
    p.add_argument("--context", type=int, default=6, help="함께 출력할 원문 줄 수")
    p.set_defaults(func=_cmd_cite_check)

    p = sub.add_parser("verify", help="원문 지문·인용 해석·근거 실재성 (위반 시 exit 1)")
    p.set_defaults(func=_cmd_verify)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
