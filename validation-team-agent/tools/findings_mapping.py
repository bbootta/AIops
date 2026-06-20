"""Recurring findings 자동 매핑 (R64 audit log → memory/recurring_findings 후보).

R64 의 ``analyse_log`` 가 산출하는 step 별 fail rate 와 dynamic activations 를
``memory/recurring_findings.json`` 의 기존 finding 들과 매핑하고, 매핑되지
않은 신규 패턴은 **proposed** 상태로 후보 dict 를 반환한다.

본 모듈은 자동 promote 를 하지 않는다 (CLAUDE.md §5: 검증 기준의 임의 완화
금지). 단순히 (a) 어떤 step 이 RF 후보인지 (b) 기존 RF 가 자동 점검과 어떻게
연결되는지 제시한다.

매핑 규칙:
- step_id → finding domain : 정적 매핑 (handler 의도 기반).
- fail_rate ≥ 0.30 → frequent 후보
- fail_rate ≥ 0.10 → moderate 후보
- fail_rate < 0.10 (그러나 > 0)  → rare 후보
- description 은 step_id + 직전 detail 의 짧은 요약
"""

from __future__ import annotations

import json
from pathlib import Path

# step_id → recurring_findings domain
_STEP_TO_DOMAIN = {
    "3.disc": "discrimination",
    "3.psi": "data",
    "3.cal": "calibration",
    "3.macro": "methodology",
    "3.weights": "scenario",
    "3.capital": "capital",
    "3.icaap": "capital",
    "3.market": "market",
    "3.operational": "operational",
    "3.liquidity": "liquidity",
    "3.alm": "liquidity",
    "3.irrbb": "irrbb",
    "3.cva": "cva",
    "3.ccr": "ccr",
    "3.conc": "concentration",
    "2.schema": "data",
    "2.safety": "data",
    "2.leakage": "leakage",
    "2.date": "data",
    "2.dup": "data",
    "2.sample": "data",
    "9.escalate": "governance",
}

# 자주 fail 하는 step 에 대한 기본 권고 (정책 SSoT 매핑, 임의 완화 금지)
_STEP_TO_REMEDY = {
    "3.disc": "재훈련 또는 챌린저 모형 검토 (skills/challenger_model_review.md).",
    "3.psi": "PSI bin 재정의 + 변수 재선정 + 재캘리브레이션 트리거.",
    "3.cal": "등급별 binomial reject → 재캘리브레이션 또는 등급 통합.",
    "3.macro": "거시 변수 정상성 재검토 + 시차 구조 재선정.",
    "3.weights": "IFRS 9 시나리오 가중치 floor — MRMC 승인 후 조정.",
    "3.capital": "자본확충 / RWA 축소 / 자본보전 buffer 활용 — MRMC 상정.",
    "3.icaap": "내부자본 시나리오 재산정 + 자본계획 보완 (SREP).",
    "3.market": "VaR 모형 재검증 / SVaR 추가 / 한도 일시 축소.",
    "3.operational": "BI 구성 재검증 + ILDC 도입 검토.",
    "3.liquidity": "HQLA 확충 + 만기 부채 차환 + 외화 LCR 80% 점검.",
    "3.alm": "만기 mismatch 축소 + 조달처 다변화 + 예대율 100% 한도.",
    "3.irrbb": "금리 시나리오별 헤지 + 모형 가정 (NMD/prepayment) 재검증.",
    "3.cva": "Hedging 효과 점검 + SA-CVA 모형 승인 절차.",
    "3.ccr": "SA-CCR α 검토 + wrong-way risk 식별 + 담보 관리.",
    "3.conc": "거액익스포저 부분 상환 + 한도 재배분.",
}


def _frequency_bucket(rate: float) -> str:
    if rate >= 0.30:
        return "frequent"
    if rate >= 0.10:
        return "moderate"
    if rate > 0:
        return "rare"
    return "none"


def load_findings(path: Path | None = None) -> list[dict]:
    p = path or (Path(__file__).resolve().parent.parent
                 / "memory" / "recurring_findings.json")
    if not p.exists():
        return []
    return json.loads(p.read_text(encoding="utf-8")).get("findings", [])


def map_audit_to_findings(
    audit: dict,
    *,
    findings_path: Path | None = None,
) -> dict:
    """audit (analyse_log 결과) → 기존 RF 매핑 + 신규 후보.

    반환:
        {
            "covered": [{step_id, fail_rate, mapped_finding_id, frequency}],
            "candidates": [{step_id, fail_rate, suggested_frequency,
                            suggested_domain, suggested_remedy, description}],
            "n_runs": ...,
        }
    """
    findings = load_findings(findings_path)
    existing_by_domain: dict[str, list[dict]] = {}
    for f in findings:
        existing_by_domain.setdefault(f.get("domain", "?"), []).append(f)

    covered = []
    candidates = []
    seen_domains: set[str] = set()

    for r in audit.get("step_fail_rates", []):
        rate = float(r["fail_rate"])
        if rate <= 0:
            continue
        sid = r["step_id"]
        bucket = _frequency_bucket(rate)
        domain = _STEP_TO_DOMAIN.get(sid, "other")

        if domain in existing_by_domain:
            # 같은 domain 에 기존 RF 가 있으면 covered 로 분류 (1:N 매핑)
            for f in existing_by_domain[domain]:
                covered.append({
                    "step_id": sid,
                    "fail_rate": rate,
                    "mapped_finding_id": f["id"],
                    "mapped_frequency": f["frequency"],
                    "observed_frequency": bucket,
                    "description": f["description"],
                    "frequency_upgrade_needed": _needs_upgrade(
                        f["frequency"], bucket),
                })
            seen_domains.add(domain)
        else:
            candidates.append({
                "step_id": sid,
                "fail_rate": rate,
                "n_fails": r.get("n_fails", 0),
                "n_runs_with_step": r.get("runs_with_step", 0),
                "suggested_frequency": bucket,
                "suggested_domain": domain,
                "suggested_remedy": _STEP_TO_REMEDY.get(
                    sid, "MRMC 검토 필요 — 표준 권고 미정."),
                "description": (
                    f"{sid} step 이 {r.get('n_fails', 0)} / "
                    f"{r.get('runs_with_step', 0)} runs 에서 fail "
                    f"({rate:.1%}). domain={domain}."),
            })

    # dynamic activations 기반 governance finding 후보
    dyn = audit.get("dynamic_activations", [])
    if dyn and "governance" not in existing_by_domain:
        candidates.append({
            "step_id": "9.escalate",
            "fail_rate": None,
            "n_fails": None,
            "n_runs_with_step": len(dyn),
            "suggested_frequency": ("frequent" if len(dyn) >= 5
                                    else "moderate" if len(dyn) >= 2
                                    else "rare"),
            "suggested_domain": "governance",
            "suggested_remedy": (
                "Escalation 반복 — MRMC 보고 절차 점검 + 매니페스트 CHG 자동화 검토."),
            "description": (
                f"9.escalate 동적 활성 {len(dyn)} 건 — 반복적 인간 검증자 "
                f"보고 필요."),
        })

    return {
        "n_runs": audit.get("n_runs", 0),
        "covered": covered,
        "candidates": candidates,
        "covered_domains": sorted(seen_domains),
    }


def _needs_upgrade(current: str, observed: str) -> bool:
    order = {"rare": 0, "moderate": 1, "frequent": 2}
    return order.get(observed, -1) > order.get(current, -1)


def _shell_escape(s: str) -> str:
    return "'" + s.replace("'", "'\\''") + "'"


def emit_add_commands(mapping: dict) -> list[str]:
    """신규 후보를 tools.findings add CLI 명령어로 변환 (자동 실행은 X)."""
    lines = []
    for c in mapping.get("candidates", []):
        cmd = (
            "python -m tools.findings add "
            f"--domain {_shell_escape(c['suggested_domain'])} "
            f"--frequency {c['suggested_frequency']} "
            f"--description {_shell_escape(c['description'])} "
            f"--tool {_shell_escape(c['step_id'])}"
        )
        lines.append(cmd)
    return lines


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="audit log → recurring_findings 매핑/후보 추출")
    parser.add_argument("--log", type=Path, default=Path("logs/run.jsonl"),
                        help="run.jsonl 경로")
    parser.add_argument("--json", action="store_true",
                        help="매핑 결과를 JSON 으로 출력")
    parser.add_argument("--emit-add", action="store_true",
                        help="신규 후보를 tools.findings add 명령어로 출력")
    args = parser.parse_args(argv)

    from tools.audit_timeseries import analyse_log

    audit = analyse_log(args.log)
    mapping = map_audit_to_findings(audit)
    if args.emit_add:
        for cmd in emit_add_commands(mapping):
            sys.stdout.write(cmd + "\n")
        return 0
    if args.json:
        sys.stdout.write(json.dumps(mapping, ensure_ascii=False, indent=2))
        sys.stdout.write("\n")
        return 0
    # 기본: 요약 markdown
    sys.stdout.write(
        f"# Recurring Findings Mapping\n\n"
        f"- runs: {mapping['n_runs']}\n"
        f"- covered: {len(mapping['covered'])}\n"
        f"- candidates: {len(mapping['candidates'])}\n"
        f"- upgrade-needed: "
        f"{sum(1 for c in mapping['covered'] if c['frequency_upgrade_needed'])}\n")
    return 0


__all__ = [
    "load_findings",
    "map_audit_to_findings",
    "emit_add_commands",
]


if __name__ == "__main__":
    raise SystemExit(main())
