"""규제 기준 검증 항목 원장: 조회·집계·검증 (국내 + 국제).

기준 스택은 세 층이다.

    규정(국내구속) → 세칙(국내구속) → 바젤(국제권고)

**국내 기준이 우선한다.** 국내가 그 주제를 정하지 않으면 바젤이 지배하고,
국내 기준이 있으나 해석이 모호하면 바젤로 보충한다. 국내가 바젤보다 느슨해도
국내가 적용되나 그 차이는 산출물에 표기해야 한다: 국내 준수가 국제 기준
충족을 뜻하지 않는다.

`verify`가 강제하는 것:

1. 각 근거 원문의 지문(SHA-256)이 카탈로그 기록과 일치하는가: 원문이 바뀌면 드러난다
2. 각 항목의 인용이 해당 원문에서 실제로 해석되는가, 기록 라인·표제가 맞는가
3. 계량 임계의 원문 발췌가 실재하고, 하니스 임계가 규정을 **느슨하게 통과시키지 않는가**
4. `automated`로 선언한 항목의 하니스 근거 파일이 실재하는가
5. 지배기준(governing)이 우선순위 정책에서 파생된 값과 일치하는가: 손으로
   "이건 바젤을 따른다"고 적을 수 없다

사용:
    python -m tools.regulatory_criteria list [--section 05] [--source 규정] [--governing 바젤]
    python -m tools.regulatory_criteria report
    python -m tools.regulatory_criteria precedence
    python -m tools.regulatory_criteria thresholds
    python -m tools.regulatory_criteria cite-check "제26조" [--source 규정]
    python -m tools.regulatory_criteria verify
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

from tools.gen_regulatory_criteria import (basel_chapter, compare, dig,
                                            governing_of, heading_of, resolve)

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "harness" / "regulatory_criteria.json"

AUTOMATION = ("automated", "manual")


def load(path: Path | str = CATALOG) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _source_lines(data: dict, root: Path) -> dict[str, list[str]]:
    return {k: (root / v["path"]).read_text(encoding="utf-8").splitlines()
            for k, v in data["sources"].items()}


def violations(data: dict, root: Path = ROOT) -> list[str]:
    out: list[str] = []

    for key, meta in data["sources"].items():
        src = root / meta["path"]
        if not src.exists():
            out.append(f"[{key}] 근거 원문이 없다: {meta['path']}")
            continue
        digest = hashlib.sha256(src.read_bytes()).hexdigest()
        if digest != meta["sha256"]:
            out.append(f"[{key}] 원문 지문 불일치: 기록 {meta['sha256'][:16]}… "
                       f"실제 {digest[:16]}… (재생성 필요)")
    if out:
        return out

    lines = _source_lines(data, root)
    seen: set[str] = set()
    for c in data["criteria"]:
        rid, key = c["rule_id"], c["source_key"]
        if rid in seen:
            out.append(f"{rid}: rule_id 중복")
        seen.add(rid)
        if key not in lines:
            out.append(f'{rid}: 근거 키가 정의 밖 ({key})')
            continue

        ln = resolve(c["citation"], lines[key])
        if ln is None:
            out.append(f'{rid}: 인용이 {key} 원문에서 해석되지 않음: {c["citation"]}')
        elif ln != c["source_line"]:
            out.append(f'{rid}: 기록 라인이 원문과 다름: {c["citation"]} '
                       f'기록 {c["source_line"]} 실제 {ln}')
        elif heading_of(ln, lines[key]) != c["source_heading"]:
            out.append(f'{rid}: 기록 표제가 원문과 다름: {c["citation"]}')

        if c["automation"] not in AUTOMATION:
            out.append(f'{rid}: automation 값이 정의 밖 ({c["automation"]})')
        elif c["automation"] == "automated":
            if not c["evidence"]:
                out.append(f"{rid}: automated 인데 근거가 0건")
            for p in c["evidence"]:
                if not (root / p).exists():
                    out.append(f"{rid}: 근거 파일 없음: {p}")
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

        want = governing_of(key, c["ambiguous_domestic"])
        if c["governing"] != want:
            out.append(f'{rid}: 지배기준이 우선순위 정책과 다름: 기록 '
                       f'{c["governing"]} 정책 {want}')
        if c["governing"] not in data["precedence"]["governing_values"]:
            out.append(f'{rid}: 지배기준 값이 정의 밖 ({c["governing"]})')
        if key == "바젤":
            if c["basel_ref"] != basel_chapter(c["citation"]):
                out.append(f'{rid}: 바젤 항목의 basel_ref 가 인용 Chapter 와 다름')
            if c["basis_level"] != "국제권고":
                out.append(f'{rid}: 바젤 항목의 근거수준이 국제권고가 아님')
        elif c["basis_level"] != "국내구속":
            out.append(f'{rid}: 국내 항목의 근거수준이 국내구속이 아님')
        if c["basel_ref"] and resolve(c["basel_ref"], lines["바젤"]) is None:
            out.append(f'{rid}: 대응 바젤 Chapter 가 소스북에서 해석되지 않음: '
                       f'{c["basel_ref"]}')

    for t in data["thresholds"]:
        key = t["key"]
        if not any(t["quote"] in l for l in lines[t["source_key"]]):
            out.append(f'임계 {key}: 원문 발췌가 {t["source_key"]}에 없다: {t["quote"]}')
        actual = dig(json.loads((root / t["harness_file"]).read_text(encoding="utf-8")),
                     t["harness_path"])
        if actual != t["harness_value"]:
            out.append(f'임계 {key}: 하니스 값이 기록과 다름: 기록 {t["harness_value"]} '
                       f'실제 {actual} ({t["harness_file"]}) · 재생성 필요')
            continue
        status = compare(t["regulated_value"], actual, t["direction"])
        if status != t["status"]:
            out.append(f'임계 {key}: 기록 상태가 재계산과 다름: 기록 {t["status"]} 실제 {status}')
        if status == "looser":
            out.append(f'임계 {key}: 하니스 임계가 규정보다 느슨하다: '
                       f'규정 {t["regulated_value"]} vs 하니스 {actual} '
                       f'({t["citation"]}) · 규제 미달을 통과시킨다')
        elif status == "missing":
            out.append(f'임계 {key}: 하니스 임계 파일에 값이 없다: '
                       f'{t["harness_file"]} {" > ".join(t["harness_path"])}')
    return out


def _cmd_list(args) -> int:
    data = load(args.catalog)
    rows = data["criteria"]
    if args.section:
        rows = [c for c in rows if c["section"] == args.section]
    if args.source:
        rows = [c for c in rows if c["source_key"] == args.source]
    if args.automation:
        rows = [c for c in rows if c["automation"] == args.automation]
    if args.governing:
        rows = [c for c in rows if c["governing"] == args.governing]
    for c in rows:
        mark = "[자동]" if c["automation"] == "automated" else "[수동]"
        ref = f' → {c["basel_ref"]}' if c["basel_ref"] else ""
        print(f'{mark} {c["rule_id"]}  {c["section"]}  [{c["source_key"]}] '
              f'{c["citation"]}{ref} · 지배 {c["governing"]} (L{c["source_line"]})')
        print(f'        {c["criterion"]}')
        if c["evidence"]:
            print(f'        근거: {" · ".join(c["evidence"])}')
        elif c["note"]:
            print(f'        공백: {c["note"]}')
    print(f"\n{len(rows)}건")
    return 0


def _cmd_thresholds(args) -> int:
    data = load(args.catalog)
    print("계량 임계: 규정 값 vs 하니스 임계\n")
    mark = {"ok": "[일치]", "stricter": "[엄격]", "looser": "[느슨]", "missing": "[없음]"}
    for t in data["thresholds"]:
        arrow = "이상" if t["direction"] == "min" else "이하"
        print(f'{mark[t["status"]]} {t["korean"]:24s} 규정 {t["regulated_value"]:<7} {arrow} '
              f'| 하니스 {t["harness_value"]} '
              f'| [{t["source_key"]}] {t["citation"]}')
        print(f'        원문: "{t["quote"]}"')
        print(f'        하니스: {t["harness_file"]} > {" > ".join(t["harness_path"])}')
    c = Counter(t["status"] for t in data["thresholds"])
    print(f'\n{len(data["thresholds"])}건 · 일치 {c["ok"]} · 엄격 {c["stricter"]} '
          f'· 느슨 {c["looser"]} · 없음 {c["missing"]}')
    if c["looser"] or c["missing"]:
        print("> 느슨·없음은 규제 미달을 통과시킨다: verify 가 위반으로 판정한다.")
    return 0


def _cmd_precedence(args) -> int:
    data = load(args.catalog)
    pr = data["precedence"]
    print("기준 스택: " + " → ".join(pr["order"]) + "\n")
    for k in pr["order"]:
        s = data["sources"][k]
        print(f'  [{k}] {s["basis_level"]} · {s["title"]} [{s["effective"]}]')
        print(f'       {s["role"]}')
    print("\n적용 규칙")
    for r in pr["rules"]:
        print(f'  {r}')
    print("\n지배기준 값")
    for k, v in pr["governing_values"].items():
        n = sum(1 for c in data["criteria"] if c["governing"] == k)
        print(f'  {k:14s} {n:3d}건: {v}')
    amb = [c for c in data["criteria"] if c["ambiguous_domestic"]]
    print(f'\n[국내 해석이 모호해 바젤로 보충하는 항목 {len(amb)}건]')
    for c in amb:
        print(f'  {c["rule_id"]} [{c["source_key"]}] {c["citation"]:12s} → 바젤 {c["basel_ref"]}')
    print("\n> 국내 준수가 국제 기준 충족을 뜻하지 않는다 (규칙 ④). "
          "국내가 바젤보다 느슨한 경우의 차이 표기는 사람 판단 사항이다: "
          "바젤 소스북은 Chapter 색인이라 수치 대조를 지원하지 않는다.")
    return 0


def _cmd_report(args) -> int:
    data = load(args.catalog)
    rows = data["criteria"]
    print("규제 기준 검증 항목: 기준 스택 " +
          " → ".join(data["precedence"]["order"]) + "\n")
    for k, s in data["sources"].items():
        print(f'  [{k}] {s["basis_level"]} · {s["title"]} [{s["effective"]}] · {s["role"]}')
        if "n_current_chapters" in s:
            print(f'       지문 {s["sha256"][:16]}… · 현행 Chapter {s["n_current_chapters"]}건 '
                  f'(Chapter 단위 대조)')
        else:
            print(f'       지문 {s["sha256"][:16]}… · 별표 {s["n_schedules"]}건 '
                  f'· 조문 heading {s["n_article_headings"]}건')
    auto = Counter(c["automation"] for c in rows)
    print(f'\n총 {len(rows)}건 · 자동 {auto["automated"]} · 수동 {auto["manual"]}')

    print("\n[근거별]")
    for k in data["sources"]:
        sub = [c for c in rows if c["source_key"] == k]
        a = sum(1 for c in sub if c["automation"] == "automated")
        print(f'  {k}  {len(sub):3d}건 · 자동 {a:2d} · 수동 {len(sub)-a:2d}')

    print("\n[지배기준별]")
    from collections import Counter as _C
    g = _C(c["governing"] for c in rows)
    for k in data["precedence"]["governing_values"]:
        print(f'  {k:14s} {g.get(k, 0):3d}건')

    print("\n[부문별]")
    for code, name in data["sections"].items():
        sec = [c for c in rows if c["section"] == code]
        if not sec:
            continue
        a = sum(1 for c in sec if c["automation"] == "automated")
        print(f'  {code} {name:22s} {len(sec):3d}건 · 자동 {a:2d} · 수동 {len(sec)-a:2d}')

    tc = Counter(t["status"] for t in data["thresholds"])
    print(f'\n[계량 임계] {len(data["thresholds"])}건 · 일치 {tc["ok"]} · 엄격 {tc["stricter"]} '
          f'· 느슨 {tc["looser"]} · 없음 {tc["missing"]}')

    gap = [c for c in rows if c["automation"] == "manual"]
    print(f"\n[기준을 덮지 못하는 항목 {len(gap)}건: 통제 공백]")
    for c in gap:
        print(f'  {c["rule_id"]} [{c["source_key"]}] {c["citation"]:12s} {c["note"]}')
    print("\n> 인용이 해석되고 임계가 일치한다는 것은 그 값이 맞다는 뜻이며, "
          "규정 내용을 다 덮는다는 뜻이 아니다.")
    return 0


def _cmd_cite_check(args) -> int:
    data = load(args.catalog)
    keys = [args.source] if args.source else list(data["sources"])
    lines = _source_lines(data, ROOT)
    found = False
    for k in keys:
        ln = resolve(args.citation, lines[k])
        if ln is None:
            print(f'[{k}] 해석 실패: "{args.citation}"')
            continue
        found = True
        print(f'[{k}] 해석됨 L{ln}: {heading_of(ln, lines[k])}')
        for l in lines[k][ln:ln + args.context]:
            if l.strip():
                print(f'    {l[:160]}')
    return 0 if found else 1


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
    th = data["thresholds"]
    print(f'규제 기준 검증 항목 정상: {len(rows)}건 · 인용 전부 원문에서 해석 · '
          f'자동 {auto}건의 근거 {ev}개 파일 실재')
    print(f'계량 임계 {len(th)}건: 규정보다 느슨한 임계 0건 · 원문 발췌 전부 실재')
    from collections import Counter as _C2
    g = _C2(c["governing"] for c in rows)
    print(f'지배기준 정책 일치: 국내 {g["국내"]} · 국내+바젤보충 {g["국내+바젤보충"]} '
          f'· 바젤 {g["바젤"]}')
    print(f'근거 원문 {len(data["sources"])}종 지문 일치')
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalog", default=str(CATALOG))
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("list", help="검증 항목 조회")
    p.add_argument("--section", help="부문 코드 (01~08)")
    p.add_argument("--source", help="근거 (규정·세칙)")
    p.add_argument("--automation", choices=AUTOMATION)
    p.add_argument("--governing", help="지배기준 (국내·국내+바젤보충·바젤)")
    p.set_defaults(func=_cmd_list)

    p = sub.add_parser("report", help="근거·부문별 집계")
    p.set_defaults(func=_cmd_report)

    p = sub.add_parser("precedence", help="기준 스택과 지배기준 분포")
    p.set_defaults(func=_cmd_precedence)

    p = sub.add_parser("thresholds", help="규정 값 vs 하니스 임계 대조")
    p.set_defaults(func=_cmd_thresholds)

    p = sub.add_parser("cite-check", help="인용이 원문에서 해석되는지 확인")
    p.add_argument("citation", help='예: "제26조" · "별표 3의6"')
    p.add_argument("--source", help="근거 (규정·세칙). 생략하면 둘 다")
    p.add_argument("--context", type=int, default=6)
    p.set_defaults(func=_cmd_cite_check)

    p = sub.add_parser("verify", help="지문·인용·임계·근거 실재성 (위반 시 exit 1)")
    p.set_defaults(func=_cmd_verify)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
