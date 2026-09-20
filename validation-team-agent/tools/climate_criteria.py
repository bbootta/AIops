"""기후리스크 업무요건 → 적합성검증 기준 항목 원장 조회·집계·검증.

`harness/climate_requirement_criteria.json` 을 읽는다. 원장은 생성물이며
손으로 고치지 않는다 (tools.gen_climate_criteria 가 원문에서 다시 만든다).

verify 가 강제하는 것
- 근거 원문 2종의 지문 일치 (원문이 바뀌면 원장이 낡았다는 사실이 드러난다)
- 요건 72건이 원문의 요건과 정확히 같고 제목이 원문과 같을 것
- automated 항목의 근거 파일 실재, manual·out_of_scope 항목의 사유 필수
- 인수시험이 요건마다 있고 결정 20건·근거 자료가 원문과 같을 것

사용:
    python -m tools.climate_criteria list [--automation manual] [--chapter 14]
    python -m tools.climate_criteria report
    python -m tools.climate_criteria decisions
    python -m tools.climate_criteria verify
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from tools import domain_criteria as _domain
from tools.gen_climate_criteria import (SOURCES, parse_acceptance_tests, parse_decisions,
                                        parse_norms, parse_requirements)

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "harness" / "climate_requirement_criteria.json"


def load(path: Path | str = CATALOG) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def violations(data: dict, root: Path = ROOT) -> list[str]:
    out = _domain.violations(data, root)

    raw = {}
    for key, meta in SOURCES.items():
        p = root / meta["path"]
        if not p.exists():
            out.append(f"근거 원문 없음: {meta['path']}")
            continue
        digest = hashlib.sha256(p.read_bytes()).hexdigest()
        recorded = data.get("sources", {}).get(key, {}).get("sha256")
        if digest != recorded:
            out.append(f"{key}: 원문 지문 불일치 (원장 {str(recorded)[:16]}… / 실제 {digest[:16]}…)")
        raw[key] = p.read_text(encoding="utf-8")
    if "detail" not in raw or "overview" not in raw:
        return out

    src = {r["req_id"]: r for r in parse_requirements(raw["detail"])}
    cat = {c["req_id"]: c for c in data.get("criteria", ())}
    for rid in sorted(set(src) - set(cat)):
        out.append(f"{rid}: 원문 요건이 원장에 없다")
    for rid in sorted(set(cat) - set(src)):
        out.append(f"{rid}: 원장 요건이 원문에 없다")
    for rid in sorted(set(src) & set(cat)):
        if cat[rid].get("title") != src[rid]["title"]:
            out.append(f"{rid}: 제목이 원문과 다르다 ({cat[rid].get('title')!r} / {src[rid]['title']!r})")
        if cat[rid].get("acceptance_test") != src[rid]["acceptance_test"]:
            out.append(f"{rid}: 인수시험 ID 가 원문과 다르다")

    ats = {a["req_id"] for a in parse_acceptance_tests(raw["detail"])}
    for rid in sorted(set(src) - ats):
        out.append(f"{rid}: 원문 인수시험 추적표에 없다")
    if len(data.get("acceptance_tests", ())) != len(ats):
        out.append(f"인수시험 건수 불일치: 원장 {len(data.get('acceptance_tests', ()))} / 원문 {len(ats)}")

    dec_src = [d["dec_id"] for d in parse_decisions(raw["overview"])]
    dec_cat = [d["dec_id"] for d in data.get("decisions", ())]
    if dec_src != dec_cat:
        out.append(f"결정 원장 불일치: 원장 {len(dec_cat)} / 원문 {len(dec_src)}")

    norm_ids = {n["source_id"] for n in data.get("norms", ())}
    if norm_ids != {n["source_id"] for n in parse_norms(raw["detail"])}:
        out.append("근거 자료(S01~) 목록이 원문과 다르다")
    for c in data.get("criteria", ()):
        for s in c.get("sources", ()):
            if s not in norm_ids:
                out.append(f"{c['req_id']}: 근거 자료 {s} 가 norms 에 없다")
    return out


def _cmd_list(args) -> int:
    data = load(args.catalog)
    rows = data["criteria"]
    if args.automation:
        rows = [r for r in rows if r["automation"] == args.automation]
    if args.chapter:
        rows = [r for r in rows if r["chapter"] == args.chapter]
    for r in rows:
        sys.stdout.write(f"{r['req_id']} [{r['automation']:<12}] {r['title']}\n    {r['criterion']}\n")
        if r["note"]:
            sys.stdout.write(f"    비고: {r['note']}\n")
    sys.stdout.write(f"{len(rows)}건\n")
    return 0


def _cmd_report(args) -> int:
    data = load(args.catalog)
    rows = data["criteria"]
    auto = Counter(r["automation"] for r in rows)
    sys.stdout.write(f"기후리스크 요건 {len(rows)}건 · 자동 {auto['automated']} · 수동 {auto['manual']} "
                     f"· 범위밖 {auto['out_of_scope']}\n")
    sys.stdout.write(f"원문: {data['sources']['detail']['title']} (설계 {data['sources']['detail']['design_version']} "
                     f"· {data['sources']['detail']['date']})\n\n")
    for no, ch in sorted(data["chapters"].items()):
        sub = [r for r in rows if r["chapter"] == no]
        c = Counter(r["automation"] for r in sub)
        sys.stdout.write(f"{no} {ch['title']:<22} {len(sub)}건 (자동 {c['automated']} · 수동 {c['manual']}"
                         f" · 범위밖 {c['out_of_scope']})  → 부문 {', '.join(ch['related_sections'])}\n")
    ev = {p for r in rows for p in r["evidence"]}
    sys.stdout.write(f"\n자동 {auto['automated']}건의 근거 파일 {len(ev)}종 · 인수시험 {len(data['acceptance_tests'])}"
                     f" · 운영 전 결정 {len(data['decisions'])} · 근거 자료 {len(data['norms'])}"
                     f" (구속 {sum(1 for n in data['norms'] if n['binding'])})\n")
    return 0


def _cmd_decisions(args) -> int:
    data = load(args.catalog)
    sys.stdout.write("운영 전 확정할 결정 (DEC). 미승인이면 해당 산출은 차단 대상이다.\n")
    for d in data["decisions"]:
        sys.stdout.write(f"{d['dec_id']} {d['title']}\n    확정 대상: {d['bank_must_fix']}\n    게이트: {d['gate']}\n")
    return 0


def _cmd_verify(args) -> int:
    data = load(args.catalog)
    bad = violations(data)
    if bad:
        for b in bad:
            sys.stdout.write(f"위반: {b}\n")
        return 1
    auto = Counter(r["automation"] for r in data["criteria"])
    ev = {p for r in data["criteria"] for p in r["evidence"]}
    sys.stdout.write(f"기후리스크 기준 항목 정상: {len(data['criteria'])}건 · 자동 {auto['automated']}건의 근거 "
                     f"{len(ev)}개 파일 전부 실재 · 원문 2종 지문 일치 · 인수시험 {len(data['acceptance_tests'])}"
                     f" · 결정 {len(data['decisions'])}\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="기후리스크 업무요건 → 적합성검증 기준 항목 원장 (원문 파싱·근거 실재성 강제)")
    parser.add_argument("--catalog", default=str(CATALOG))
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list"); p.add_argument("--automation"); p.add_argument("--chapter"); p.set_defaults(func=_cmd_list)
    sub.add_parser("report").set_defaults(func=_cmd_report)
    sub.add_parser("decisions").set_defaults(func=_cmd_decisions)
    sub.add_parser("verify").set_defaults(func=_cmd_verify)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
