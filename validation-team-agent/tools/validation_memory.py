"""검증 기억 원장 — 회차·패턴·자기결함·이월사항을 기계 검증 가능하게 유지한다.

15회 교환 동안 이 넷은 전부 의견서 산문에 손으로 적혀 있었다. 그 결과
3선 자신이 2선에 지적해 온 결함을 그대로 만들었다 — 반복 횟수를 손으로 세다
두 번 틀렸고(미등록 125→143종 · 오인용 9→8건), 회차 번호를 손으로 세다
한 번 틀렸다(F-502 는 2선 지적이지만 유형이 같다).

원칙은 2선에 요구해 온 것과 동일하다.

  - 셀 수 있는 값은 세서 쓴다 — 반복 횟수는 len(members) 로 파생 (F-501)
  - 회차는 손으로 부여하지 않는다 — 요청 이력 등장 순서에서 파생 (F-502)
  - 참조는 실재해야 한다 — 패턴 멤버·자기결함 근거는 회차 원장에 있어야 하고,
    프로토콜 origin 이 가리키는 finding 도 회차 원장에 있어야 한다 (F-D01)
  - 검사는 실패할 수 있어야 한다 — verify 규칙마다 반증 테스트가 있다 (F-602·F-E01)

원장 4종 (memory/):
  validation_rounds.jsonl   회차 기록 — git 응답 이력에서 백필, append-only
  finding_patterns.json     결함 계보 — 회차를 관통하는 반복 유형
  self_defects.jsonl        3선 자기결함 — 프로토콜 진화의 근거
  carryover_register.jsonl  이월·미확인 — "N~M차 연속 미해소" 를 생성한다

사용:
    python -m tools.validation_memory rounds [--md]
    python -m tools.validation_memory patterns
    python -m tools.validation_memory self-defects
    python -m tools.validation_memory carryover
    python -m tools.validation_memory verify
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

ROOT = Path(__file__).resolve().parent.parent
ROUNDS_PATH = ROOT / "memory" / "validation_rounds.jsonl"
PATTERNS_PATH = ROOT / "memory" / "finding_patterns.json"
SELF_DEFECTS_PATH = ROOT / "memory" / "self_defects.jsonl"
CARRYOVER_PATH = ROOT / "memory" / "carryover_register.jsonl"
PROTOCOL_PATH = ROOT / "harness" / "adversarial_protocol.json"

SEVERITIES = ("중부적합", "경부적합", "적합")
_FINDING_REF = re.compile(r"F-[0-9A-E]\d{2}")


class MemoryError_(RuntimeError):
    """검증 기억 원장 무결성 위반."""


# ------------------------------------------------------------------ 로딩

def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def load_rounds(path: Path | None = None) -> list[dict[str, Any]]:
    return _jsonl(path or ROUNDS_PATH)


def load_patterns(path: Path | None = None) -> dict[str, Any]:
    p = path or PATTERNS_PATH
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"patterns": []}


def load_self_defects(path: Path | None = None) -> list[dict[str, Any]]:
    return _jsonl(path or SELF_DEFECTS_PATH)


def load_carryover(path: Path | None = None) -> list[dict[str, Any]]:
    return _jsonl(path or CARRYOVER_PATH)


# ------------------------------------------------------------------ 검증

def verify(*, rounds: list[dict] | None = None,
           patterns: dict | None = None,
           self_defects: list[dict] | None = None,
           carryover: list[dict] | None = None,
           protocol: dict | None = None) -> list[str]:
    """원장 4종 + 프로토콜의 상호 정합을 검사한다. 문제 목록을 돌려준다 (빈 목록 = 정상).

    각 규칙은 실제로 실패할 수 있다 — tests/test_validation_memory.py 가 규칙마다
    위반 fixture 로 반증한다 (F-602·F-E01 교훈: 실패할 수 없는 검사는 통제가 아니다).
    """
    rounds = load_rounds() if rounds is None else rounds
    patterns = load_patterns() if patterns is None else patterns
    self_defects = load_self_defects() if self_defects is None else self_defects
    carryover = load_carryover() if carryover is None else carryover
    if protocol is None:
        protocol = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))

    problems: list[str] = []

    # ---- 회차 원장
    seqs = [r["seq"] for r in rounds]
    if seqs != list(range(1, len(rounds) + 1)):
        problems.append(f"회차 번호가 1..N 연속이 아니다: {seqs} — 회차는 손으로 "
                        f"부여하지 않는다 (F-502)")
    rids = [r["request_id"] for r in rounds]
    if len(set(rids)) != len(rids):
        problems.append("request_id 중복 — 같은 요청이 두 회차로 기록됐다")

    all_findings: dict[str, int] = {}
    for r in rounds:
        for f in r["findings"]:
            fid = f["finding_id"]
            if fid in all_findings:
                problems.append(f"{fid}: finding_id 가 {all_findings[fid]}차와 "
                                f"{r['seq']}차에 중복")
            all_findings[fid] = r["seq"]
            if f["severity"] not in SEVERITIES:
                problems.append(f"{fid}: 알 수 없는 심각도 {f['severity']!r}")

        counted = {s: sum(1 for f in r["findings"] if f["severity"] == s)
                   for s in SEVERITIES}
        if counted != r["severity_counts"]:
            problems.append(f"{r['seq']}차: severity_counts {r['severity_counts']} 가 "
                            f"findings 실계 {counted} 와 불일치 — 집계는 파생값이다")

        worst = ("중부적합" if counted["중부적합"] else
                 "경부적합" if counted["경부적합"] else "적합")
        if r["verdict"] != worst:
            problems.append(f"{r['seq']}차: verdict {r['verdict']} 가 최고 심각도 "
                            f"{worst} 와 불일치")

        derived_gate = ("부적합" if counted["중부적합"] else
                        "조건부" if counted["경부적합"] else "적합")
        if r["gate"] != derived_gate and not r.get("gate_note"):
            problems.append(f"{r['seq']}차: gate {r['gate']} 가 파생값 {derived_gate} 와 "
                            f"다른데 gate_note 가 없다 — 역사적 예외는 사유를 남긴다")

    n_rounds = len(rounds)

    # ---- 패턴 계보
    for p in patterns.get("patterns", []):
        pid = p["pattern_id"]
        for m in p["members"]:
            if m not in all_findings:
                problems.append(f"{pid}: 멤버 {m} 가 회차 원장에 없다 — 참조는 "
                                f"실재해야 한다 (F-D01)")
        member_rounds = [all_findings[m] for m in p["members"] if m in all_findings]
        if member_rounds != sorted(member_rounds):
            problems.append(f"{pid}: 멤버가 회차 순이 아니다 — 계보는 시간순으로 남긴다")
        if p["status"] == "live":
            om = p.get("open_member")
            if not om:
                problems.append(f"{pid}: live 인데 open_member 가 없다 — 무엇이 "
                                f"열려 있는지 지목해야 한다")
            elif not p.get("open_member_external") and om not in all_findings:
                problems.append(f"{pid}: open_member {om} 가 회차 원장에 없다")
        elif p["status"] == "closed":
            if not p.get("closed_note"):
                problems.append(f"{pid}: closed 인데 closed_note 가 없다 — 무엇으로 "
                                f"닫혔는지 남긴다")
        else:
            problems.append(f"{pid}: 알 수 없는 status {p['status']!r}")

    # ---- 자기결함
    challenge_ids = {c["challenge_id"] for c in protocol["challenges"]}
    for d in self_defects:
        did = d["defect_id"]
        if not 1 <= d["round"] <= n_rounds:
            problems.append(f"{did}: round {d['round']} 가 회차 범위 밖")
        if d.get("recorded_in") and d["recorded_in"] not in all_findings:
            problems.append(f"{did}: 근거 finding {d['recorded_in']} 이 회차 원장에 없다")
        fc = d.get("fix_challenge")
        if fc and fc not in challenge_ids:
            problems.append(f"{did}: fix_challenge {fc} 가 프로토콜에 없다")
        if not fc and not d.get("fix_note"):
            problems.append(f"{did}: 시정이 challenge 도 fix_note 도 아니다 — "
                            f"자기결함은 시정 없이 닫히지 않는다")

    # ---- 프로토콜 origin 역참조: origin 이 가리키는 finding 은 회차 원장에 있어야 한다
    for c in protocol["challenges"]:
        origin = c.get("origin") or ""
        for fid in _FINDING_REF.findall(origin):
            if fid not in all_findings:
                problems.append(f"{c['challenge_id']}: origin 이 가리키는 {fid} 가 "
                                f"회차 원장에 없다 — 프로토콜의 출처가 끊겼다")

    # ---- 이월 원장
    seen_ids = set()
    for co in carryover:
        cid = co["item_id"]
        if cid in seen_ids:
            problems.append(f"{cid}: item_id 중복")
        seen_ids.add(cid)
        if not 1 <= co["first_seen_round"] <= co["last_seen_round"] <= n_rounds:
            problems.append(f"{cid}: 회차 범위 오류 "
                            f"({co['first_seen_round']}~{co['last_seen_round']}, "
                            f"전체 {n_rounds})")
        if co["status"] == "closed" and not co.get("resolution"):
            problems.append(f"{cid}: closed 인데 resolution 이 없다 — 미확인은 "
                            f"조용히 닫히지 않는다")
        if co["status"] not in ("open", "closed"):
            problems.append(f"{cid}: 알 수 없는 status {co['status']!r}")

    return problems


# ------------------------------------------------------------------ 렌더

def render_rounds(rounds: list[dict], *, md: bool = False) -> str:
    if md:
        lines = ["| 회차 | request_id | 판정 | 게이트 | 중 | 경 | 적 | 축 |",
                 "|---:|---|---|---|---:|---:|---:|---|"]
        for r in rounds:
            s = r["severity_counts"]
            gate = r["gate"] + (" → 결재" if r.get("approved") else "")
            lines.append(f"| {r['seq']} | `{r['request_id']}` | {r['verdict']} | "
                         f"{gate} | {s['중부적합']} | {s['경부적합']} | {s['적합']} | "
                         f"{r['theme']} |")
        return "\n".join(lines)
    lines = [f"독립검증 회차 원장 — {len(rounds)}회"]
    for r in rounds:
        s = r["severity_counts"]
        gate = r["gate"] + (" → 결재" if r.get("approved") else "")
        lines.append(f"  {r['seq']:2d}  {r['request_id']}  {r['verdict']:5s} "
                     f"{gate:9s} 중{s['중부적합']} 경{s['경부적합']} 적{s['적합']}  "
                     f"{r['theme']}")
    total = {s: sum(r["severity_counts"][s] for r in rounds) for s in SEVERITIES}
    lines.append(f"  합계 — 지적 {sum(total.values())}건 "
                 f"(중 {total['중부적합']} · 경 {total['경부적합']} · 적 {total['적합']})")
    return "\n".join(lines)


def render_patterns(patterns: dict, rounds: list[dict]) -> str:
    idx = {f["finding_id"]: r["seq"] for r in rounds for f in r["findings"]}
    lines = ["결함 계보 — 반복 횟수는 멤버 수에서 파생한다 (손으로 세지 않는다)"]
    for p in patterns.get("patterns", []):
        n = len(p["members"])
        spans = [idx[m] for m in p["members"] if m in idx]
        span = f"{min(spans)}~{max(spans)}차" if spans else "-"
        state = ("진행 중" if p["status"] == "live" else "종결")
        lines.append(f"  {p['pattern_id']:9s} {p['name']}")
        lines.append(f"            {n}회 반복 · {span} · {state}"
                     + (f" (열림: {p.get('open_member')})" if p["status"] == "live" else ""))
        lines.append(f"            {' → '.join(p['members'])}")
    return "\n".join(lines)


def render_self_defects(defects: list[dict]) -> str:
    lines = [f"3선 자기결함 원장 — {len(defects)}건. 검증자도 검증 대상이다."]
    for d in defects:
        fix = d.get("fix_challenge") or d.get("fix_note", "")
        lines.append(f"  {d['defect_id']}  {d['round']:2d}차 [{d['kind']}] {d['summary']}")
        lines.append(f"        기록: {d.get('recorded_in', '-')} · 시정: {fix}")
        lines.append(f"        교훈: {d['lesson']}")
    return "\n".join(lines)


def render_carryover(items: list[dict], *, n_rounds: int) -> str:
    open_items = [c for c in items if c["status"] == "open"]
    lines = [f"이월·미확인 원장 — 열림 {len(open_items)}건 / 전체 {len(items)}건. "
             f"미확인은 통과가 아니다."]
    for c in sorted(open_items, key=lambda x: x["first_seen_round"]):
        age = n_rounds - c["first_seen_round"] + 1
        lines.append(f"  {c['item_id']}  {c['first_seen_round']}~{c['last_seen_round']}차 "
                     f"연속 미해소 ({age}회차 경과) — {c['title']}")
        lines.append(f"        차단 사유: {c['blocker']}")
    return "\n".join(lines)


# ------------------------------------------------------------------ CLI

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="검증 기억 원장 — 회차·패턴·자기결함·이월 (생성·대조, 손으로 세지 않는다)")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_r = sub.add_parser("rounds", help="회차 원장")
    p_r.add_argument("--md", action="store_true", help="의견서용 마크다운 표")
    sub.add_parser("patterns", help="결함 계보 (반복 횟수는 파생값)")
    sub.add_parser("self-defects", help="3선 자기결함 원장")
    sub.add_parser("carryover", help="이월·미확인 원장 (연속 미해소 구간 생성)")
    sub.add_parser("verify", help="원장 4종 + 프로토콜 상호 정합 (위반 시 exit 1)")
    args = parser.parse_args(argv)

    rounds = load_rounds()
    if args.cmd == "rounds":
        sys.stdout.write(render_rounds(rounds, md=args.md) + "\n")
        return 0
    if args.cmd == "patterns":
        sys.stdout.write(render_patterns(load_patterns(), rounds) + "\n")
        return 0
    if args.cmd == "self-defects":
        sys.stdout.write(render_self_defects(load_self_defects()) + "\n")
        return 0
    if args.cmd == "carryover":
        sys.stdout.write(render_carryover(load_carryover(), n_rounds=len(rounds)) + "\n")
        return 0
    problems = verify()
    if problems:
        sys.stderr.write("검증 기억 원장 무결성 위반:\n")
        for p in problems:
            sys.stderr.write(f"  - {p}\n")
        return 1
    sys.stdout.write(
        f"검증 기억 원장 정상 — 회차 {len(rounds)} · "
        f"패턴 {len(load_patterns().get('patterns', []))} · "
        f"자기결함 {len(load_self_defects())} · "
        f"이월 {len(load_carryover())} · 프로토콜 origin 역참조 전부 실재\n")
    return 0


__all__ = ["MemoryError_", "load_rounds", "load_patterns", "load_self_defects",
           "load_carryover", "verify", "render_rounds", "render_patterns",
           "render_self_defects", "render_carryover"]


if __name__ == "__main__":
    raise SystemExit(main())
