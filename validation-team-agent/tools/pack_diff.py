"""보고서 팩 결과 변화 감지 (diff).

두 보고서 팩 (예: 전 분기 vs 당 분기) 의 ``export.json`` 또는
``pack_manifest.json`` 을 비교해 변화를 산출한다. 분기별 보고서 누적 시
"어떤 부문이 새로 fail 했고", "어떤 KPI 값이 어떻게 변했는지" 를 한 화면에서
확인하기 위함.

본 모듈은 read-only — 입력 팩을 수정하지 않는다.

매핑 단위:
- KPI: label 기준 매칭, value/status 변화 + 새로 추가/제거된 카드
- Heatmap: domain 기준 매칭, status 전이 + 추가/제거
- QoQ metric: metric 기준 매칭, current_value 차이
- pages (pack_manifest): file 기준 매칭, SHA-256 변화·추가·제거
"""

from __future__ import annotations

import json
from pathlib import Path


_STATUS_ORDER = {
    "ok": 0,
    "warning": 1,
    "fail": 2,
    "skipped": 3,
    "simulated": 4,
    "?": 5,
}


def _load(path: Path) -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    return json.loads(p.read_text(encoding="utf-8"))


def _index_by(rows: list[dict], key: str) -> dict[str, dict]:
    return {str(r.get(key, "?")): r for r in rows}


def _status_transition_severity(prev: str, curr: str) -> str:
    """status 전이의 심각도 — improved / degraded / unchanged / status-new."""
    if prev == curr:
        return "unchanged"
    p = _STATUS_ORDER.get(prev, 99)
    c = _STATUS_ORDER.get(curr, 99)
    if c > p:
        return "degraded"
    return "improved"


def diff_kpi(prev: list[dict], curr: list[dict]) -> dict:
    p_by = _index_by(prev, "label")
    c_by = _index_by(curr, "label")
    added = sorted(set(c_by) - set(p_by))
    removed = sorted(set(p_by) - set(c_by))
    changed = []
    unchanged = 0
    for label in sorted(set(p_by) & set(c_by)):
        a = p_by[label]
        b = c_by[label]
        if a.get("value") != b.get("value") or a.get("status") != b.get("status"):
            changed.append({
                "label": label,
                "prev_value": a.get("value"),
                "curr_value": b.get("value"),
                "prev_status": a.get("status"),
                "curr_status": b.get("status"),
                "transition": _status_transition_severity(
                    a.get("status", "?"), b.get("status", "?")),
            })
        else:
            unchanged += 1
    return {
        "added": [c_by[lab] for lab in added],
        "removed": [p_by[lab] for lab in removed],
        "changed": changed,
        "unchanged_count": unchanged,
    }


def diff_heatmap(prev: list[dict], curr: list[dict]) -> dict:
    p_by = _index_by(prev, "domain")
    c_by = _index_by(curr, "domain")
    transitions = []
    for dom in sorted(set(p_by) & set(c_by)):
        a = p_by[dom]
        b = c_by[dom]
        if a.get("status") != b.get("status"):
            transitions.append({
                "domain": dom,
                "prev_status": a.get("status"),
                "curr_status": b.get("status"),
                "prev_detail": a.get("detail", ""),
                "curr_detail": b.get("detail", ""),
                "severity": _status_transition_severity(
                    a.get("status", "?"), b.get("status", "?")),
            })
    return {
        "added": [c_by[d] for d in sorted(set(c_by) - set(p_by))],
        "removed": [p_by[d] for d in sorted(set(p_by) - set(c_by))],
        "transitions": transitions,
    }


def diff_qoq(prev: list[dict], curr: list[dict]) -> list[dict]:
    p_by = _index_by(prev, "metric")
    c_by = _index_by(curr, "metric")
    out = []
    for m in sorted(set(p_by) & set(c_by)):
        try:
            p_v = float(p_by[m].get("current_value", 0))
            c_v = float(c_by[m].get("current_value", 0))
        except (TypeError, ValueError):
            continue
        out.append({
            "metric": m,
            "prev_current_value": p_v,
            "curr_current_value": c_v,
            "abs_change": c_v - p_v,
            "rel_change": (c_v - p_v) / p_v if p_v != 0 else None,
        })
    return out


def diff_pages(prev_pages: list[dict], curr_pages: list[dict]) -> dict:
    p_by = {p["file"]: p for p in prev_pages}
    c_by = {p["file"]: p for p in curr_pages}
    added = sorted(set(c_by) - set(p_by))
    removed = sorted(set(p_by) - set(c_by))
    changed_sha = []
    for f in sorted(set(p_by) & set(c_by)):
        if p_by[f].get("sha256") != c_by[f].get("sha256"):
            changed_sha.append({
                "file": f,
                "prev_sha": p_by[f].get("sha256", "")[:16],
                "curr_sha": c_by[f].get("sha256", "")[:16],
                "prev_size": p_by[f].get("size_bytes"),
                "curr_size": c_by[f].get("size_bytes"),
            })
    return {
        "added_pages": added,
        "removed_pages": removed,
        "changed_pages": changed_sha,
        "unchanged_count": (
            len(set(p_by) & set(c_by)) - len(changed_sha)),
    }


def diff_against_curr_data(
    prev_dir: str | Path,
    curr_export: dict,
    curr_pages: list[dict] | None = None,
    *,
    curr_label: str = "(in-memory)",
) -> dict:
    """prev 팩(export.json + pack_manifest.json) vs curr (이미 산출된 dict).

    build_pack 시점에 curr 의 export.json 이 아직 없을 때 사용한다.
    """
    prev = Path(prev_dir)
    prev_export = _load(prev / "export.json")
    prev_manifest = _load(prev / "pack_manifest.json")
    return {
        "prev_pack": str(prev),
        "curr_pack": curr_label,
        "prev_generated_at": prev_export.get("generated_at_utc"),
        "curr_generated_at": curr_export.get("generated_at_utc"),
        "kpi": diff_kpi(prev_export.get("kpi", []),
                        curr_export.get("kpi", [])),
        "heatmap": diff_heatmap(prev_export.get("heatmap", []),
                                curr_export.get("heatmap", [])),
        "qoq": diff_qoq(prev_export.get("qoq", []),
                        curr_export.get("qoq", [])),
        "pages": diff_pages(prev_manifest.get("pages", []),
                            curr_pages or []),
    }


def diff_export_files(prev_dir: str | Path, curr_dir: str | Path) -> dict:
    """전체 diff — export.json + pack_manifest.json 통합."""
    prev = Path(prev_dir)
    curr = Path(curr_dir)
    prev_export = _load(prev / "export.json")
    curr_export = _load(curr / "export.json")
    prev_manifest = _load(prev / "pack_manifest.json")
    curr_manifest = _load(curr / "pack_manifest.json")

    return {
        "prev_pack": str(prev),
        "curr_pack": str(curr),
        "prev_generated_at": prev_export.get("generated_at_utc"),
        "curr_generated_at": curr_export.get("generated_at_utc"),
        "kpi": diff_kpi(prev_export.get("kpi", []),
                        curr_export.get("kpi", [])),
        "heatmap": diff_heatmap(prev_export.get("heatmap", []),
                                curr_export.get("heatmap", [])),
        "qoq": diff_qoq(prev_export.get("qoq", []),
                        curr_export.get("qoq", [])),
        "pages": diff_pages(prev_manifest.get("pages", []),
                            curr_manifest.get("pages", [])),
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="두 보고서 팩 간 변화 detection")
    parser.add_argument("--prev", type=Path, required=True,
                        help="이전 팩 디렉터리 (export.json 포함)")
    parser.add_argument("--curr", type=Path, required=True,
                        help="현재 팩 디렉터리")
    parser.add_argument("--json", action="store_true",
                        help="결과 JSON 출력")
    args = parser.parse_args(argv)

    diff = diff_export_files(args.prev, args.curr)
    if args.json:
        sys.stdout.write(json.dumps(diff, ensure_ascii=False, indent=2))
        sys.stdout.write("\n")
        return 0

    sys.stdout.write(
        f"# Pack diff\n\n"
        f"- prev: {diff['prev_pack']} ({diff['prev_generated_at']})\n"
        f"- curr: {diff['curr_pack']} ({diff['curr_generated_at']})\n\n"
        f"## KPI\n"
        f"- added: {len(diff['kpi']['added'])}\n"
        f"- removed: {len(diff['kpi']['removed'])}\n"
        f"- changed: {len(diff['kpi']['changed'])}\n"
        f"- unchanged: {diff['kpi']['unchanged_count']}\n\n"
        f"## Heatmap transitions\n"
        f"- transitions: {len(diff['heatmap']['transitions'])}\n"
        f"  - degraded: {sum(1 for t in diff['heatmap']['transitions'] if t['severity'] == 'degraded')}\n"
        f"  - improved: {sum(1 for t in diff['heatmap']['transitions'] if t['severity'] == 'improved')}\n\n"
        f"## Pages\n"
        f"- added: {len(diff['pages']['added_pages'])}\n"
        f"- removed: {len(diff['pages']['removed_pages'])}\n"
        f"- changed (sha256): {len(diff['pages']['changed_pages'])}\n"
        f"- unchanged: {diff['pages']['unchanged_count']}\n")
    return 0


__all__ = [
    "diff_kpi", "diff_heatmap", "diff_qoq", "diff_pages",
    "diff_export_files", "diff_against_curr_data",
]


if __name__ == "__main__":
    raise SystemExit(main())
