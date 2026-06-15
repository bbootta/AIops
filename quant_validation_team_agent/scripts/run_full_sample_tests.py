#!/usr/bin/env python3
"""Run the full quant-validation sample checks and write an HTML result report."""

from __future__ import annotations

import datetime as dt
import html
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
OUTPUT_DIR = ROOT / "outputs"
SAMPLE_PATH = ROOT / "samples" / "risk_domain_samples.json"
MANIFEST_PATH = OUTPUT_DIR / "artifact_manifest.json"
REPORT_PATH = OUTPUT_DIR / "sample_test_report.html"

COMMANDS = [
    [sys.executable, "quant_validation_team_agent/scripts/generate_validation_outputs.py"],
    [sys.executable, "quant_validation_team_agent/tests/validate_output_artifacts.py"],
    [sys.executable, "quant_validation_team_agent/tests/validate_risk_domain_samples.py"],
    [sys.executable, "quant_validation_team_agent/tests/validate_knowledge_graph_links.py"],
]


def esc(value: object) -> str:
    if value is None:
        return "-"
    if isinstance(value, list):
        return html.escape(", ".join(str(item) for item in value) or "-")
    return html.escape(str(value))


def run_command(command: list[str]) -> dict[str, object]:
    completed = subprocess.run(command, cwd=REPO_ROOT, text=True, capture_output=True, check=False)
    display_command = ["python", *command[1:]] if command[0] == sys.executable else command
    return {
        "command": " ".join(display_command),
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def load_samples() -> list[dict[str, object]]:
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))["samples"]


def load_manifest() -> dict[str, object]:
    if not MANIFEST_PATH.exists():
        return {}
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def count_table(title: str, counts: Counter[str]) -> str:
    rows = "".join(
        f"<tr><td>{esc(key)}</td><td class='num'>{count}</td></tr>"
        for key, count in sorted(counts.items())
    )
    return f"<h2>{esc(title)}</h2><table><tr><th>구분</th><th>건수</th></tr>{rows}</table>"


def command_table(results: list[dict[str, object]]) -> str:
    rows = []
    for result in results:
        status = "PASS" if result["returncode"] == 0 else "FAIL"
        rows.append(
            "<tr>"
            f"<td><code>{esc(result['command'])}</code></td>"
            f"<td class='{status.lower()}'>{status}</td>"
            f"<td class='num'>{result['returncode']}</td>"
            f"<td><pre>{esc(result['stdout'])}</pre></td>"
            f"<td><pre>{esc(result['stderr'])}</pre></td>"
            "</tr>"
        )
    return "".join([
        "<h2>실행한 전체 샘플 테스트</h2>",
        "<table>",
        "<tr><th>명령</th><th>상태</th><th>종료코드</th><th>stdout</th><th>stderr</th></tr>",
        *rows,
        "</table>",
    ])


def sample_rows(samples: list[dict[str, object]], manifest: dict[str, object]) -> str:
    fingerprints = manifest.get("sample_fingerprints", {})
    explainability = manifest.get("explainability_index", {})
    rows = []
    for sample in sorted(samples, key=lambda item: str(item["case_id"])):
        case_id = str(sample["case_id"])
        explanation = explainability.get(case_id, {}) if isinstance(explainability, dict) else {}
        rows.append(
            "<tr>"
            f"<td>{esc(case_id)}</td>"
            f"<td>{esc(sample['request_id'])}</td>"
            f"<td>{esc(sample['validation_object_type'])}</td>"
            f"<td>{esc(sample['risk_output_domain'])}</td>"
            f"<td>{esc(sample['primary_risk_output_domain'])}</td>"
            f"<td>{esc(sample['secondary_risk_output_domains'])}</td>"
            f"<td>{esc(sample['data_readiness_status'])}</td>"
            f"<td>{esc(sample['lineage_status'])}</td>"
            f"<td>{esc(sample['expected_provisional_judgement'])}</td>"
            f"<td>{esc(sample['expected_action_notice_required'])}</td>"
            f"<td>{esc(sample['expected_gray_reason_code'])}</td>"
            f"<td><code>{esc(fingerprints.get(case_id, '-'))}</code></td>"
            f"<td>{esc(explanation.get('decision_stage', '-'))}</td>"
            f"<td>{esc(explanation.get('explanation_summary', '-'))}</td>"
            f"<td>{esc(sample['evidence_gaps'])}</td>"
            f"<td>{esc(sample['input_documents'])}</td>"
            f"<td>{esc(sample['audit_trail_items'])}</td>"
            "</tr>"
        )
    return "".join(rows)


def render_report(results: list[dict[str, object]], samples: list[dict[str, object]], manifest: dict[str, object]) -> str:
    passed = all(result["returncode"] == 0 for result in results)
    status = "PASS" if passed else "FAIL"
    judgement_counts = Counter(str(sample["expected_provisional_judgement"]) for sample in samples)
    domain_counts = Counter(str(sample["risk_output_domain"]) for sample in samples)
    object_counts = Counter(str(sample["validation_object_type"]) for sample in samples)
    non_green = sum(1 for sample in samples if sample["expected_provisional_judgement"] != "Green")
    action_notice = sum(1 for sample in samples if sample["expected_action_notice_required"])
    manifest_artifacts = manifest.get("artifacts", [])
    artifact_total = len(manifest_artifacts) + (1 if manifest else 0)
    generated_at = dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M:%S UTC")

    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8"/>
<title>전체 샘플 테스트 상세 결과 보고서</title>
<style>
body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', Arial, sans-serif; margin: 32px; color: #17202a; }}
h1 {{ border-bottom: 4px solid #243b53; padding-bottom: 12px; }}
h2 {{ margin-top: 30px; border-left: 6px solid #486581; padding-left: 10px; }}
table {{ border-collapse: collapse; width: 100%; margin: 14px 0 24px; font-size: 12px; }}
th, td {{ border: 1px solid #bcccdc; padding: 7px; vertical-align: top; }}
th {{ background: #f0f4f8; }}
pre {{ white-space: pre-wrap; margin: 0; font-family: Consolas, monospace; }}
code {{ font-family: Consolas, monospace; word-break: break-all; }}
.summary {{ display: grid; grid-template-columns: repeat(4, minmax(150px, 1fr)); gap: 12px; }}
.card {{ border: 1px solid #bcccdc; border-radius: 8px; padding: 14px; background: #f8fafc; }}
.card strong {{ display: block; font-size: 22px; margin-top: 6px; }}
.pass {{ color: #0b6b3a; font-weight: 700; }}
.fail {{ color: #b42318; font-weight: 700; }}
.num {{ text-align: right; }}
.notice {{ background: #fffbea; border-left: 6px solid #f0b429; padding: 12px; }}
</style>
</head>
<body>
<h1>전체 샘플 테스트 상세 결과 보고서</h1>
<p class="notice">본 보고서는 샘플 데이터와 생성 산출물의 구조·규칙·재현가능성 검증 결과를 보여준다. LLM 수치 계산 또는 최종 승인 판단은 포함하지 않는다.</p>
<div class="summary">
  <div class="card">종합 상태<strong class="{status.lower()}">{status}</strong></div>
  <div class="card">샘플 수<strong>{len(samples)}</strong></div>
  <div class="card">비Green 샘플<strong>{non_green}</strong></div>
  <div class="card">Action Notice 대상<strong>{action_notice}</strong></div>
  <div class="card">생성 산출물<strong>{artifact_total}</strong></div>
  <div class="card">fingerprint 필드<strong>{len(manifest.get('fingerprint_fields', []))}</strong></div>
  <div class="card">실행 시각<strong>{esc(generated_at)}</strong></div>
  <div class="card">보고서 파일<strong>{esc(REPORT_PATH.relative_to(ROOT))}</strong></div>
</div>
{command_table(results)}
{count_table('판정 후보 분포', judgement_counts)}
{count_table('리스크 산출 영역 분포', domain_counts)}
{count_table('1축 검증대상 유형 분포', object_counts)}
<h2>케이스별 상세 검증 결과</h2>
<table>
<tr>
<th>case_id</th><th>request_id</th><th>validation_object_type</th><th>risk_output_domain</th><th>primary_domain</th><th>secondary_domains</th><th>data_readiness</th><th>lineage</th><th>judgement</th><th>action_notice</th><th>gray_reason</th><th>case_fingerprint</th><th>decision_stage</th><th>explanation_summary</th><th>evidence_gaps</th><th>input_documents</th><th>audit_trail_items</th>
</tr>
{sample_rows(samples, manifest)}
</table>
<h2>검증 기준</h2>
<ul>
<li>모든 표준 risk_output_domain 샘플 존재 여부</li>
<li>모든 validation_object_type 샘플 존재 여부</li>
<li>case_id/request_id 유일성</li>
<li>Green/Yellow/Red/Gray 라벨 및 Gray 사유코드 유효성</li>
<li>비Green Action Notice 요구 규칙</li>
<li>case_fingerprint 64자리 SHA-256 형식 및 결정성</li>
<li>통합 및 1축별 XLSX/MD/HTML/HWPX/PDF 산출물 존재와 기본 구조</li>
<li>artifact_manifest.json의 fingerprint와 explainability index 일관성</li>
</ul>
</body>
</html>
"""


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    results = [run_command(command) for command in COMMANDS]
    samples = load_samples()
    manifest = load_manifest()
    REPORT_PATH.write_text(render_report(results, samples, manifest), encoding="utf-8")
    print(f"wrote {REPORT_PATH.relative_to(REPO_ROOT)}")
    return 0 if all(result["returncode"] == 0 for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
