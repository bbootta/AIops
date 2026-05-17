"""정책 일관성 lint.

``harness/metric_policy.md``와 ``harness/policies/*.md`` 사이에 동일 지표가
서로 다른 임계값으로 기재되어 있는지 점검한다. 동일 모형군의 정책 파일
내부에서 동일 지표가 중복 정의되며 값이 다른 경우도 위반으로 본다.

본 모듈은 정책을 자동 수정하지 않는다. 위반 사항만 보고한다.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Iterable, List, Mapping

ROOT = Path(__file__).resolve().parent.parent
METRIC_POLICY = ROOT / "harness" / "metric_policy.md"
POLICIES_DIR = ROOT / "harness" / "policies"

_METRICS = ("KS", "AUROC", "AUC", "Gini", "AR", "PSI", "VIF")

_OP_PATTERN = re.compile(
    r"\b(KS|AUROC|AUC|Gini|AR|PSI|VIF)\b\s*"
    r"(≥|>=|≤|<=|>|<|=)\s*"
    r"(\d+(?:\.\d+)?)",
    flags=re.IGNORECASE,
)

# HTML 주석 마커: <!-- threshold: KS>=0.30 --> 또는 <!-- threshold: KS >= 0.30 -->
_MARKER_PATTERN = re.compile(
    r"<!--\s*threshold\s*:\s*"
    r"(KS|AUROC|AUC|Gini|AR|PSI|VIF)\s*"
    r"(≥|>=|≤|<=|>|<|=)\s*"
    r"(\d+(?:\.\d+)?)"
    r"\s*-->",
    flags=re.IGNORECASE,
)


def _normalize_op(op: str) -> str:
    return {">=": "≥", "<=": "≤"}.get(op, op)


def _extract(text: str) -> List[tuple[str, str, float]]:
    """(metric, op, value) triples 추출. metric은 대문자 정규화.

    인식 대상:
        1) `<!-- threshold: KS>=0.30 -->` 형태의 명시 마커
        2) 본문 산문 / 표의 `KS ≥ 0.30` 형태 자유 표기
    """
    out: List[tuple[str, str, float]] = []
    for m in _MARKER_PATTERN.finditer(text):
        metric = m.group(1).upper().replace("AUC", "AUROC")
        out.append((metric, _normalize_op(m.group(2)), float(m.group(3))))
    for m in _OP_PATTERN.finditer(text):
        metric = m.group(1).upper().replace("AUC", "AUROC")
        out.append((metric, _normalize_op(m.group(2)), float(m.group(3))))
    return out


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _label(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def collect_thresholds(
    metric_policy_path: Path | None = None,
    policies_dir: Path | None = None,
) -> dict:
    """파일별 추출된 임계값 dict를 반환한다.

    반환 dict 형태:
        {file_relpath: [(metric, op, value), ...]}
    """
    metric_path = metric_policy_path or METRIC_POLICY
    pol_dir = policies_dir or POLICIES_DIR
    out: dict[str, List[tuple[str, str, float]]] = {}
    if metric_path.exists():
        out[_label(metric_path)] = _extract(_read(metric_path))
    if pol_dir.exists():
        for p in sorted(pol_dir.glob("*.md")):
            out[_label(p)] = _extract(_read(p))
    return out


def lint_policies(
    metric_policy_path: Path | None = None,
    policies_dir: Path | None = None,
) -> dict:
    """파일 간 / 파일 내부 임계값 충돌을 보고한다.

    반환 dict 키: passed, conflicts(list of dict), thresholds(dict)
    """
    thresholds = collect_thresholds(metric_policy_path, policies_dir)

    bucket: dict[tuple[str, str], list[tuple[str, float]]] = {}
    for fname, items in thresholds.items():
        for metric, op, val in items:
            bucket.setdefault((metric, op), []).append((fname, val))

    conflicts: List[dict] = []
    for (metric, op), entries in bucket.items():
        values = {v for _, v in entries}
        if len(values) <= 1:
            continue
        conflicts.append(
            {
                "metric": metric,
                "op": op,
                "values_by_source": entries,
            }
        )
    return {
        "passed": len(conflicts) == 0,
        "conflicts": conflicts,
        "thresholds": thresholds,
    }


def format_report(result: Mapping) -> str:
    """lint 결과를 사람이 읽기 좋은 텍스트로 반환."""
    if result["passed"]:
        return "policy_lint: OK (no conflicts)"
    lines = ["policy_lint: CONFLICTS"]
    for c in result["conflicts"]:
        lines.append(f"- {c['metric']} {c['op']} ?")
        for src, val in c["values_by_source"]:
            lines.append(f"    {src}: {val}")
    return "\n".join(lines)


_SAMPLE_PATTERNS = [
    ("min_total",    re.compile(r"min[_\s]?total\s*[:=≥>=]+\s*(\d+)", re.IGNORECASE)),
    ("min_defaults", re.compile(r"min[_\s]?defaults?\s*[:=≥>=]+\s*(\d+)", re.IGNORECASE)),
    ("min_per_grade", re.compile(r"min[_\s]?per[_\s]?grade\s*[:=≥>=]+\s*(\d+)", re.IGNORECASE)),
]


def check_sample_size_alignment(
    code_defaults: dict[str, int] | None = None,
    policies_dir: Path | None = None,
) -> dict:
    """sample_size_guard 의 코드 default 와 policies/*.md 의 문서 임계가 일치하는지.

    code_defaults 가 None 이면 middleware 에서 직접 import 한다. 정책 파일에서
    추출 가능한 키워드만 비교. 위반 없음 / 충돌 발견 형태로 결과 반환.
    """
    if code_defaults is None:
        try:
            from middleware.sample_size_guard import DEFAULTS as _DEFAULTS
            code_defaults = dict(_DEFAULTS)
        except Exception:
            code_defaults = {}

    pol_dir = policies_dir or POLICIES_DIR
    pol_findings: dict[str, dict[str, int]] = {}
    if pol_dir.exists():
        for p in sorted(pol_dir.glob("*.md")):
            text = _read(p)
            hits = {}
            for key, pat in _SAMPLE_PATTERNS:
                m = pat.search(text)
                if m:
                    hits[key] = int(m.group(1))
            if hits:
                pol_findings[_label(p)] = hits

    conflicts: list[dict] = []
    for fname, hits in pol_findings.items():
        for key, val in hits.items():
            code_val = code_defaults.get(key)
            if code_val is not None and code_val != val:
                conflicts.append({"file": fname, "key": key, "code": code_val, "policy": val})

    return {
        "passed": len(conflicts) == 0,
        "conflicts": conflicts,
        "code_defaults": code_defaults,
        "policy_findings": pol_findings,
    }


def main(argv: Iterable[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="validation-team-agent policy lint")
    parser.add_argument("--metric-policy", type=Path, default=None)
    parser.add_argument("--policies-dir", type=Path, default=None)
    parser.add_argument(
        "--include-sample-size",
        action="store_true",
        help="sample_size_guard DEFAULTS 와 정책 문서 임계 일치도 점검",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    result = lint_policies(args.metric_policy, args.policies_dir)
    rc = 0 if result["passed"] else 1
    print(format_report(result))

    if args.include_sample_size:
        sub = check_sample_size_alignment(policies_dir=args.policies_dir)
        if sub["passed"]:
            print("sample_size_alignment: OK")
        else:
            print("sample_size_alignment: CONFLICTS")
            for c in sub["conflicts"]:
                print(f"- {c['file']} / {c['key']}: code={c['code']} policy={c['policy']}")
            rc = 1
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
