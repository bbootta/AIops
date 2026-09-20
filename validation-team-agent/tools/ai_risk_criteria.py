"""AI 리스크 업무요건 → 적합성검증 기준 항목 원장 조회·집계·검증.

`harness/ai_risk_requirement_criteria.json` 을 읽는다. 원장은 생성물이며 손으로
고치지 않는다 (tools.gen_ai_risk_criteria 가 원문에서 다시 만든다).

verify 가 강제하는 것: 근거 원문 4종의 지문 일치(문서 세트 manifest 와도 대조),
요건 76건이 구조화 원장과 같고 규칙 문장이 원문과 같을 것, automated 근거 실재,
manual·out_of_scope 사유 필수, 구속 근거(인공지능기본법·시행령·개인정보보호법·
신용정보법)가 근거원장에 실재할 것.

사용:
    python -m tools.ai_risk_criteria list [--automation manual] [--chapter 09]
    python -m tools.ai_risk_criteria report
    python -m tools.ai_risk_criteria norms
    python -m tools.ai_risk_criteria verify
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

from tools import domain_criteria as _domain
from tools.gen_ai_risk_criteria import BINDING_NORMS, SOURCES, parse_norms, parse_register

ROOT = Path(__file__).resolve().parent.parent
CATALOG = ROOT / "harness" / "ai_risk_requirement_criteria.json"


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
    if "register" not in raw or "manual" not in raw:
        return out

    src = {r["req_id"]: r for r in parse_register(raw["register"])}
    cat = {c["req_id"]: c for c in data.get("criteria", ())}
    for rid in sorted(set(src) - set(cat)):
        out.append(f"{rid}: 원문 요건이 원장에 없다")
    for rid in sorted(set(cat) - set(src)):
        out.append(f"{rid}: 원장 요건이 원문에 없다")
    for rid in sorted(set(src) & set(cat)):
        for k in ("rule", "test_id", "priority"):
            if cat[rid].get(k) != src[rid][k]:
                out.append(f"{rid}: {k} 가 원문과 다르다")

    norm_ids = {n["source_id"] for n in parse_norms(raw["manual"])}
    if norm_ids != {n["source_id"] for n in data.get("norms", ())}:
        out.append("근거원장(G·K·CASE) 목록이 해설서와 다르다")
    for sid in BINDING_NORMS:
        if sid not in norm_ids:
            out.append(f"구속 근거 {sid} 가 근거원장에 없다")
    return out


def _cmd_list(args) -> int:
    rows = load(args.catalog)["criteria"]
    if args.automation:
        rows = [r for r in rows if r["automation"] == args.automation]
    if args.chapter:
        rows = [r for r in rows if r["chapter"] == args.chapter]
    for r in rows:
        sys.stdout.write(f"{r['req_id']} [{r['automation']:<12}] {r['chapter']} · {r['priority']}\n    {r['criterion']}\n")
        if r["note"]:
            sys.stdout.write(f"    비고: {r['note']}\n")
    sys.stdout.write(f"{len(rows)}건\n")
    return 0


def _cmd_report(args) -> int:
    data = load(args.catalog)
    rows = data["criteria"]
    auto = Counter(r["automation"] for r in rows)
    sys.stdout.write(f"AI 리스크 요건 {len(rows)}건 · 자동 {auto['automated']} · 수동 {auto['manual']} · 범위밖 {auto['out_of_scope']}\n")
    sys.stdout.write(f"원문: {data['sources']['manual']['title']} ({data['sources']['manual']['date']})\n\n")
    for no, ch in sorted(data["chapters"].items()):
        sub = [r for r in rows if r["chapter"] == no]
        if not sub:
            continue
        c = Counter(r["automation"] for r in sub)
        sys.stdout.write(f"{no} {ch['title'][4:]:<26} {len(sub)}건 (자동 {c['automated']} · 수동 {c['manual']} · 범위밖 {c['out_of_scope']})  → 부문 {', '.join(ch['related_sections'])}\n")
    ev = {p for r in rows for p in r["evidence"]}
    sys.stdout.write(f"\n자동 {auto['automated']}건의 근거 파일 {len(ev)}종 · 근거원장 {len(data['norms'])} (구속 {sum(1 for n in data['norms'] if n['binding'])})\n")
    nr = data.get("document_verification", {})
    not_run = [k for k, v in nr.items() if str(v).startswith("NOT_RUN")]
    sys.stdout.write(f"문서 세트가 밝힌 미수행 검증: {', '.join(not_run) or '없음'}\n")
    return 0


def _cmd_norms(args) -> int:
    for n in load(args.catalog)["norms"]:
        sys.stdout.write(f"{n['source_id']:<14} {'구속' if n['binding'] else '참고'}  {n['title']}\n")
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
    sys.stdout.write(f"AI 리스크 기준 항목 정상: {len(data['criteria'])}건 · 자동 {auto['automated']}건의 근거 {len(ev)}개 파일 전부 실재 · 원문 4종 지문 일치 (문서 manifest 대조)\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI 리스크 업무요건 → 적합성검증 기준 항목 원장 (원문 파싱·근거 실재성 강제)")
    parser.add_argument("--catalog", default=str(CATALOG))
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list"); p.add_argument("--automation"); p.add_argument("--chapter"); p.set_defaults(func=_cmd_list)
    sub.add_parser("report").set_defaults(func=_cmd_report)
    sub.add_parser("norms").set_defaults(func=_cmd_norms)
    sub.add_parser("verify").set_defaults(func=_cmd_verify)
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
