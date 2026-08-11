"""보고서 팩 export 유틸리티 (CSV / JSON / 인덱스).

CRO 보고용 산출물의 형식 다양화:

- **CSV**: KPI / QoQ / heatmap / risk watch / change manifest summary 를
  실무진 분석용으로 추출.
- **JSON**: 동일 데이터를 외부 시스템(BI 대시보드) 연계용으로 export.
- **인덱스 (manifest.json)**: 팩 내 각 페이지의 메타데이터 (제목, 경로,
  부문, 크기, hash) — 자동 카탈로그.

본 모듈은 보고서 팩(``tools.report_pack``)이 생성된 디렉터리를 입력으로 받고,
같은 디렉터리에 export 파일을 추가한다. 운영 데이터를 다루지 않으며 모든
산출은 결정론적이다.

사용:
    python -m tools.report_export --pack reports/pack_1m_stress --out reports/pack_1m_stress
    # 결과: kpi.csv, qoq.csv, heatmap.csv, risk_watch.csv,
    #       change_manifest_summary.csv, export.json, pack_manifest.json
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------- 데이터 수집 ----------

def _kpi_cards(stress: bool, seed: int = 42) -> list[dict]:
    """동일 seed 로 demo 를 재실행해 KPI 카드 데이터 수집."""
    from tools.executive_insights import kpi_cards
    from tools.run_workflow_demo import run_demo

    log_dir = Path("logs/export_temp")
    demo = run_demo(2_000, stress, seed, log_dir)
    return [{"label": k, "value": v, "status": s}
            for k, v, s in kpi_cards(demo)]


def _heatmap_rows(stress: bool, seed: int = 42) -> list[dict]:
    from tools.executive_insights import domain_rows
    from tools.run_workflow_demo import run_demo

    log_dir = Path("logs/export_temp")
    demo = run_demo(2_000, stress, seed, log_dir)
    return [{"domain": label, "status": status, "detail": detail, "link": link}
            for label, status, detail, link in domain_rows(demo)]


def _qoq_table() -> list[dict]:
    """전 분기 대비 QoQ 변화 (quarterly_panel 마지막 2분기)."""
    from tools.sample_generators import quarterly_panel

    panel = quarterly_panel()
    if len(panel) < 2:
        return []
    prev, curr = panel[-2], panel[-1]
    out = []
    for metric in ("cet1", "leverage", "lcr", "nsfr", "icaap",
                   "delta_eve", "psi", "hhi"):
        p = float(prev[metric])
        c = float(curr[metric])
        out.append({
            "metric": metric,
            "previous_quarter": prev["period"],
            "current_quarter": curr["period"],
            "previous_value": p,
            "current_value": c,
            "delta": c - p,
            "delta_pct": (c - p) / p if p != 0 else 0.0,
        })
    return out


def _risk_watch(stress: bool, seed: int = 42) -> list[dict]:
    from tools.executive_insights import top_risks_and_actions
    from tools.run_workflow_demo import run_demo

    log_dir = Path("logs/export_temp")
    demo = run_demo(2_000, stress, seed, log_dir)
    risks, actions = top_risks_and_actions(demo, n=5)
    out = []
    for r, a in zip(risks, actions):
        out.append({
            "sid": r["sid"], "label": r["label"], "status": r["status"],
            "detail": r["detail"], "drill_link": r["link"],
            "standard_action": a["action"],
        })
    return out


def _change_manifest_summary() -> list[dict]:
    """매니페스트 CHG 요약 — status × type 매트릭스."""
    from tools.manifest import load

    m = load()
    items = m.get("changes", [])
    matrix: dict[tuple[str, str], int] = {}
    for it in items:
        key = (it.get("status", "?"), it.get("change_type", "?"))
        matrix[key] = matrix.get(key, 0) + 1
    out = [{"status": s, "type": t, "count": n}
           for (s, t), n in sorted(matrix.items())]
    return out


# ---------- 파일 export ----------

def _write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        path.write_text("(empty)\n", encoding="utf-8")
        return
    fields = list(rows[0])
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


# ---------- 팩 manifest ----------

_TITLE_RE = re.compile(r"<title>([^<]+)</title>", re.IGNORECASE)
_DOMAIN_TAGS = {
    "credit": "신용",
    "capital": "자본",
    "icaap": "ICAAP",
    "alm": "ALM",
    "irrbb": "IRRBB",
    "market": "시장",
    "operational": "운영",
    "op": "운영",
    "cva": "CVA",
    "ccr": "CCR",
    "concentration": "집중",
    "data": "데이터품질",
    "ifrs9": "IFRS9",
    "esg": "ESG",
    "cyber": "Cyber",
    "fx": "FX",
    "stress": "스트레스",
    "macro": "거시",
    "trends": "추세",
    "change": "변경감사",
    "explainability": "설명가능성",
    "executive": "경영진",
    "exec": "경영진",
    "index": "요약",
}


def _classify_page(name: str) -> str:
    stem = name.removesuffix(".html").lower()
    for tag, label in _DOMAIN_TAGS.items():
        if stem == tag or stem.startswith(tag + "_") or "_" + tag in stem:
            return label
    return "기타"


def _build_pack_manifest(pack_dir: Path) -> dict:
    pages = sorted(pack_dir.glob("*.html"))
    entries = []
    for p in pages:
        text = p.read_text(encoding="utf-8")
        m = _TITLE_RE.search(text)
        title = m.group(1).strip() if m else p.stem
        entries.append({
            "file": p.name,
            "title": title,
            "domain": _classify_page(p.name),
            "size_bytes": p.stat().st_size,
            "sha256": _sha256_file(p),
            "has_draft_watermark": "[DRAFT" in text,
            "has_provenance": "Reproducibility" in text,
            "has_svg": "<svg" in text,
        })
    domains_count: dict[str, int] = {}
    for e in entries:
        domains_count[e["domain"]] = domains_count.get(e["domain"], 0) + 1
    return {
        "generated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_pages": len(entries),
        "by_domain": domains_count,
        "all_have_watermark": all(e["has_draft_watermark"] for e in entries),
        "all_have_provenance": all(e["has_provenance"] for e in entries),
        "pages": entries,
    }


# ---------- 진입점 ----------

def export_pack(
    pack_dir: str | Path,
    *,
    out_dir: str | Path | None = None,
    stress: bool = False,
    seed: int = 42,
) -> list[Path]:
    pack = Path(pack_dir)
    if not pack.is_dir():
        raise FileNotFoundError(f"pack dir not found: {pack}")
    out = Path(out_dir) if out_dir else pack

    kpi = _kpi_cards(stress, seed)
    heatmap = _heatmap_rows(stress, seed)
    qoq = _qoq_table()
    risk = _risk_watch(stress, seed)
    chg = _change_manifest_summary()
    manifest = _build_pack_manifest(pack)

    written = []

    csv_files = [
        ("kpi.csv", kpi),
        ("heatmap.csv", heatmap),
        ("qoq.csv", qoq),
        ("risk_watch.csv", risk),
        ("change_manifest_summary.csv", chg),
    ]
    for name, rows in csv_files:
        p = out / name
        _write_csv(p, rows)
        written.append(p)

    # 통합 JSON
    consolidated = {
        "generated_at_utc": manifest["generated_at_utc"],
        "stress": stress,
        "seed": seed,
        "kpi": kpi,
        "heatmap": heatmap,
        "qoq": qoq,
        "risk_watch": risk,
        "change_manifest_summary": chg,
    }
    json_path = out / "export.json"
    json_path.write_text(
        json.dumps(consolidated, ensure_ascii=False, indent=2),
        encoding="utf-8")
    written.append(json_path)

    # 팩 인덱스
    manifest_path = out / "pack_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8")
    written.append(manifest_path)

    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="보고서 팩 CSV / JSON / 인덱스 export")
    parser.add_argument("--pack", type=Path, required=True,
                        help="report pack 디렉터리 (index.html 등 포함)")
    parser.add_argument("--out", type=Path, default=None,
                        help="export 출력 디렉터리 (기본: --pack 과 동일)")
    parser.add_argument("--stress", action="store_true")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    written = export_pack(args.pack, out_dir=args.out, stress=args.stress,
                          seed=args.seed)
    for p in written:
        sys.stdout.write(f"{p}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
