"""규제 규칙 카탈로그 — 근거 수준·원문 주기·유효일자를 분리해 관리한다.

리스크 적합성검증 요건 개요서(2026-08-02)의 규칙 카탈로그 최소 필드를 구현한다.
핵심은 세 가지 분리다.

  - **원문 주기 ≠ 내부 주기** (OVR-000): 규정이 '정기적' 이라고만 적으면 내부정책상
    연 1회를 택할 수 있으나, 이를 법정 연 1회 의무로 표기하는 순간 오표기다.
    frequency_basis 가 LEGAL 이려면 원문에 구체 주기가 있어야 한다.
  - **국내 구속 ≠ Basel 기준 ≠ 내부 권고** (OVR-003): Basel IMA 의 PLA·RFET 를
    국내 공통 의무로 표기하면 안 된다. authority_level 로 강제한다.
  - **경과조치는 유효일자 규칙** (OVR-001): 출력하한 65%(2026) → 70%(2027) →
    72.5%(2028~) 를 날짜로 선택한다. 상수 하나로 박으면 연도가 바뀔 때 조용히
    틀린다 — 15회 교환에서 2선·3선 모두 72.5% 상수를 썼고, 이 카탈로그가 그
    사실을 처음 드러냈다 (이월 CO-010).

폐기된 구교재 수치는 RETIRED 로 등재해 재사용을 차단한다 (OVR-009).

사용:
    python -m tools.reg_rules list
    python -m tools.reg_rules effective --date 2026-06-30
    python -m tools.reg_rules calendar --asof 2026-06-30
    python -m tools.reg_rules verify
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT / "harness" / "regulatory_rule_catalog.json"

AUTHORITY_LEVELS = ("DOMESTIC_BINDING", "BASEL_STANDARD",
                    "BASEL_GUIDELINE", "INTERNAL_POLICY")
STATUSES = ("ACTIVE", "RETIRED")
FREQ_BASES = ("LEGAL", "INTERNAL_POLICY")
#: 원문이 주기를 특정하지 않았음을 뜻하는 표현 — 이 경우 법정 주기를 만들 수 없다.
UNSPECIFIED_MARKERS = ("정기적", "미명시", "폐기")
OPINION_CODES = ("SATISFACTORY", "SATISFACTORY_WITH_CONDITIONS",
                 "NEEDS_IMPROVEMENT", "UNSATISFACTORY", "NO_OPINION")


def load(path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path) if path else CATALOG_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def _d(s: str | None) -> date | None:
    return date.fromisoformat(s) if s else None


def _raw_is_unspecified(raw: str) -> bool:
    return any(m in raw for m in UNSPECIFIED_MARKERS)


# ------------------------------------------------------------------ 검증

def verify(data: dict[str, Any] | None = None) -> list[str]:
    """카탈로그 무결성 — 위반 목록을 돌려준다 (빈 목록 = 정상).

    각 규칙은 실패할 수 있다 — tests/test_reg_rules.py 가 규칙마다 위반
    fixture 로 반증한다.
    """
    data = data if data is not None else load()
    problems: list[str] = []
    rules = data.get("rules", [])
    if not rules:
        return ["rules 가 비어 있다"]

    seen: set[str] = set()
    groups: dict[str, list[dict[str, Any]]] = {}
    for r in rules:
        rid = r.get("rule_id", "?")
        if rid in seen:
            problems.append(f"{rid}: rule_id 중복")
        seen.add(rid)

        if r.get("authority_level") not in AUTHORITY_LEVELS:
            problems.append(f"{rid}: 알 수 없는 authority_level "
                            f"{r.get('authority_level')!r}")
        if not str(r.get("source_locator", "")).strip():
            problems.append(f"{rid}: source_locator 가 없다 — 근거 없는 규칙 금지")
        if r.get("status") not in STATUSES:
            problems.append(f"{rid}: 알 수 없는 status {r.get('status')!r}")
        if not r.get("required_evidence"):
            problems.append(f"{rid}: required_evidence 가 없다 — 충족을 입증할 "
                            f"증빙을 정의해야 한다")

        raw = str(r.get("frequency_raw", ""))
        basis = r.get("frequency_basis")
        if basis not in FREQ_BASES:
            problems.append(f"{rid}: 알 수 없는 frequency_basis {basis!r}")
        elif basis == "LEGAL" and _raw_is_unspecified(raw):
            problems.append(f"{rid}: 원문 주기가 {raw!r} 인데 basis=LEGAL — "
                            f"법정 주기로 오표기 금지 (OVR-000)")

        if r.get("status") == "RETIRED":
            if not r.get("effective_to"):
                problems.append(f"{rid}: RETIRED 인데 effective_to 가 없다 — "
                                f"언제까지 유효했는지 남긴다")
            if not r.get("replaced_by"):
                problems.append(f"{rid}: RETIRED 인데 replaced_by 가 없다 — "
                                f"대체 규칙 없이 폐기하면 공백이 생긴다 (OVR-009)")
            elif r["replaced_by"] not in {x.get("rule_id") for x in rules}:
                problems.append(f"{rid}: replaced_by {r['replaced_by']} 가 "
                                f"카탈로그에 없다")

        try:
            f, t = _d(r.get("effective_from")), _d(r.get("effective_to"))
            if f and t and f > t:
                problems.append(f"{rid}: effective_from > effective_to")
        except ValueError:
            problems.append(f"{rid}: 유효일자 형식 오류")

        gid = r.get("group_id")
        if gid and r.get("status") == "ACTIVE":
            groups.setdefault(gid, []).append(r)

    # 그룹 유효기간 — 겹치면 어느 규칙이 적용되는지 모호하고, 빈틈이 있으면
    # 그 날짜에 규칙이 없다 (경과조치의 요건 — OVR-001).
    for gid, members in groups.items():
        spans = sorted(
            ((_d(m["effective_from"]), _d(m.get("effective_to")), m["rule_id"])
             for m in members),
            key=lambda x: x[0] or date.min)
        for (f1, t1, id1), (f2, _t2, id2) in zip(spans, spans[1:]):
            if t1 is None:
                problems.append(f"{gid}: {id1} 이 무기한인데 뒤에 {id2} 가 있다 — "
                                f"유효기간이 겹친다")
            elif f2 is None or f2 <= t1:
                problems.append(f"{gid}: {id1}({t1}까지) 와 {id2}({f2}부터) 의 "
                                f"유효기간이 겹친다")
            elif (f2 - t1).days > 1:
                problems.append(f"{gid}: {id1}({t1}) 와 {id2}({f2}) 사이에 "
                                f"규칙 없는 날짜가 있다 — 경과조치 빈틈")

    # 의견 코드 매핑 — 5종 전부, 교환 판정 대응 필수, 내부정책 단서 필수
    om = data.get("opinion_map", {})
    codes = om.get("codes", {})
    for c in OPINION_CODES:
        if c not in codes:
            problems.append(f"opinion_map: {c} 누락")
        elif not codes[c].get("exchange_verdict"):
            problems.append(f"opinion_map: {c} 의 exchange_verdict 누락")
    for c in codes:
        if c not in OPINION_CODES:
            problems.append(f"opinion_map: 알 수 없는 코드 {c}")
    if "내부정책" not in str(om.get("note", "")):
        problems.append("opinion_map: 의견 명칭이 내부정책 정의라는 단서가 없다 "
                        "(OVR-011 — 금감원 통일의견으로 오인 금지)")
    return problems


# ------------------------------------------------------------------ 조회

def effective_rules(as_of: date, data: dict[str, Any] | None = None
                    ) -> list[dict[str, Any]]:
    """해당 일자에 유효한 ACTIVE 규칙 — 경과조치는 여기서 갈린다."""
    data = data if data is not None else load()
    out = []
    for r in data.get("rules", []):
        if r.get("status") != "ACTIVE":
            continue
        f, t = _d(r.get("effective_from")), _d(r.get("effective_to"))
        if f and as_of < f:
            continue
        if t and as_of > t:
            continue
        out.append(r)
    return out


def output_floor_factor(as_of: date, data: dict[str, Any] | None = None
                        ) -> float | None:
    """해당 일자의 출력하한 계수 — 유효일자 규칙에서 파생한다 (상수 금지)."""
    for r in effective_rules(as_of, data):
        if r.get("group_id") == "OUTPUT_FLOOR":
            return float(r["params"]["floor_factor"])
    return None


def calendar(as_of: date, data: dict[str, Any] | None = None
             ) -> list[dict[str, Any]]:
    """검증 캘린더 — 법정 주기와 내부정책 주기를 **이중 표시**한다 (OVR-004).

    수용기준: 법정기한 누락 0건 · 근거 없는 법정주기 생성 0건. basis 가
    INTERNAL_POLICY 인 항목은 '법정 미명시/내부정책' 으로만 표기된다.
    """
    rows = []
    for r in effective_rules(as_of, data):
        freq = r.get("internal_frequency", "")
        if freq in ("NONE", "CONTINUOUS", ""):
            continue
        legal = r.get("frequency_basis") == "LEGAL"
        rows.append({
            "rule_id": r["rule_id"],
            "title": r["title"],
            "frequency": freq,
            "basis": "LEGAL" if legal else "INTERNAL_POLICY",
            "label": (f"법정 {r['frequency_raw']}" if legal
                      else f"법정 미명시({r['frequency_raw']})/내부정책 {freq}"),
            "authority_level": r["authority_level"],
        })
    return rows


# ------------------------------------------------------------------ 렌더/CLI

def render_rules(rules: list[dict[str, Any]]) -> str:
    lines = [f"규제 규칙 카탈로그 — {len(rules)}건"]
    for r in rules:
        span = f"{r.get('effective_from', '-')}~{r.get('effective_to') or ''}"
        lines.append(f"  {r['rule_id']:15s} [{r['authority_level']:16s}] "
                     f"{r['status']:7s} {span:24s} {r['title']}")
        lines.append(f"      원문 주기: {r['frequency_raw']} · 내부: "
                     f"{r['internal_frequency']} ({r['frequency_basis']}) · "
                     f"근거: {r['source_locator']}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="규제 규칙 카탈로그 — 근거 수준·원문 주기·유효일자 분리 관리")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="전체 규칙")
    p_e = sub.add_parser("effective", help="해당 일자 유효 규칙 (경과조치 선택)")
    p_e.add_argument("--date", required=True)
    p_c = sub.add_parser("calendar", help="검증 캘린더 — 법정/내부 이중 표시")
    p_c.add_argument("--asof", required=True)
    sub.add_parser("verify", help="카탈로그 무결성 (위반 시 exit 1)")
    args = parser.parse_args(argv)

    if args.cmd == "list":
        sys.stdout.write(render_rules(load().get("rules", [])) + "\n")
        return 0
    if args.cmd == "effective":
        d = date.fromisoformat(args.date)
        rules = effective_rules(d)
        sys.stdout.write(render_rules(rules) + "\n")
        floor = output_floor_factor(d)
        if floor is not None:
            sys.stdout.write(f"\n출력하한 계수 @ {d}: {floor:.3f} "
                             f"(유효일자 규칙에서 파생 — 상수 아님)\n")
        return 0
    if args.cmd == "calendar":
        d = date.fromisoformat(args.asof)
        rows = calendar(d)
        sys.stdout.write(f"검증 캘린더 @ {d} — {len(rows)}건 "
                         f"(법정 {sum(1 for r in rows if r['basis'] == 'LEGAL')} · "
                         f"내부정책 {sum(1 for r in rows if r['basis'] != 'LEGAL')})\n")
        for r in rows:
            sys.stdout.write(f"  {r['rule_id']:15s} {r['frequency']:12s} {r['label']}\n")
        return 0
    problems = verify()
    if problems:
        sys.stderr.write("규칙 카탈로그 무결성 위반:\n")
        for p in problems:
            sys.stderr.write(f"  - {p}\n")
        return 1
    data = load()
    n_active = sum(1 for r in data["rules"] if r["status"] == "ACTIVE")
    n_ret = sum(1 for r in data["rules"] if r["status"] == "RETIRED")
    sys.stdout.write(f"규칙 카탈로그 정상 — ACTIVE {n_active} · RETIRED {n_ret} · "
                     f"의견 코드 {len(OPINION_CODES)}종 매핑 완비\n")
    return 0


__all__ = ["load", "verify", "effective_rules", "output_floor_factor",
           "calendar", "render_rules", "CATALOG_PATH", "AUTHORITY_LEVELS",
           "OPINION_CODES"]


if __name__ == "__main__":
    raise SystemExit(main())
