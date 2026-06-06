#!/usr/bin/env python3
"""Generate sample validation output artifacts.

The generator creates review artifacts from UAT sample metadata only. It does
not calculate risk metrics; all numeric-looking values are treated as opaque
identifiers from official systems or calculation engines.
"""

from __future__ import annotations

import hashlib
import html
import json
import shutil
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[1]
SAMPLE_PATH = ROOT / "samples" / "risk_domain_samples.json"
OUTPUT_DIR = ROOT / "outputs"
TODAY = "2026-05-14"
DOC_NO = "리스크감리-양검-2026-001"
VALIDATION_OBJECT_TYPES = [
    "credit_rating_model",
    "credit_risk_parameter",
    "risk_factor_validation",
    "aggregation_reporting",
    "hybrid_risk_output",
]
FINGERPRINT_FIELDS = [
    "request_type",
    "validation_object_type",
    "risk_output_domain",
    "primary_risk_output_domain",
    "secondary_risk_output_domains",
    "scope_statement",
    "policy_reference",
    "regulatory_source_reference",
    "calculation_engine_result_reference",
]


RISK_DOMAIN_ALIASES = {
    "credit_risk": "credit_risk",
    "credit risk": "credit_risk",
    "credit-risk": "credit_risk",
    "신용리스크": "credit_risk",
    "신용 위험": "credit_risk",
    "market_risk": "market_risk",
    "market risk": "market_risk",
    "market-risk": "market_risk",
    "시장리스크": "market_risk",
    "시장 위험": "market_risk",
    "operational_risk": "operational_risk",
    "operational risk": "operational_risk",
    "operational-risk": "operational_risk",
    "운영리스크": "operational_risk",
    "interest_rate_risk": "interest_rate_risk",
    "interest rate risk": "interest_rate_risk",
    "interest-rate-risk": "interest_rate_risk",
    "irrbb": "interest_rate_risk",
    "금리리스크": "interest_rate_risk",
    "liquidity_risk": "liquidity_risk",
    "liquidity risk": "liquidity_risk",
    "liquidity-risk": "liquidity_risk",
    "유동성리스크": "liquidity_risk",
    "strategic_risk": "strategic_risk",
    "strategic risk": "strategic_risk",
    "strategic-risk": "strategic_risk",
    "전략리스크": "strategic_risk",
    "reputational_risk": "reputational_risk",
    "reputational risk": "reputational_risk",
    "reputational-risk": "reputational_risk",
    "평판리스크": "reputational_risk",
    "capital_adequacy_aggregation": "capital_adequacy_aggregation",
    "capital adequacy aggregation": "capital_adequacy_aggregation",
    "capital-adequacy-aggregation": "capital_adequacy_aggregation",
    "자본적정성 집계": "capital_adequacy_aggregation",
    "multi_risk_or_unclear": "multi_risk_or_unclear",
    "multi risk or unclear": "multi_risk_or_unclear",
    "multi-risk-or-unclear": "multi_risk_or_unclear",
    "복합 불명확": "multi_risk_or_unclear",
}
RISK_DOMAIN_FIELDS = {"risk_output_domain", "primary_risk_output_domain", "secondary_risk_output_domains"}


def normalize_risk_domain(value: object) -> object:
    if not isinstance(value, str):
        return value
    key = " ".join(value.strip().lower().replace("_", " ").replace("-", " ").split())
    compact = key.replace(" ", "")
    return RISK_DOMAIN_ALIASES.get(value.strip(), RISK_DOMAIN_ALIASES.get(key, RISK_DOMAIN_ALIASES.get(compact, value.strip())))


def canonicalize_field(field: str, value: object) -> object:
    if isinstance(value, list):
        values = [normalize_risk_domain(item) if field in RISK_DOMAIN_FIELDS else item for item in value]
        return sorted(dict.fromkeys(values))
    if field in RISK_DOMAIN_FIELDS:
        return normalize_risk_domain(value)
    if isinstance(value, str):
        return " ".join(value.strip().split())
    return value


def case_fingerprint(sample: dict[str, object]) -> str:
    payload = {field: canonicalize_field(field, sample.get(field)) for field in FINGERPRINT_FIELDS}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def decision_stage(sample: dict[str, object]) -> str:
    judgement = sample["expected_provisional_judgement"]
    if sample["risk_output_domain"] == "multi_risk_or_unclear":
        return "리스크 영역 게이트"
    if judgement == "Gray":
        if sample["expected_gray_reason_code"] in {"POLICY_UNDEFINED"}:
            return "공식 기준 게이트"
        if not sample["calculation_engine_result_reference"]:
            return "계산엔진 게이트"
        return "데이터·증적 게이트"
    if judgement == "Yellow":
        return "보완 가능 이슈 게이트"
    if judgement == "Red":
        return "명시적 위반 게이트"
    return "중대 이슈 미발견 게이트"


def explanation_summary(sample: dict[str, object]) -> str:
    judgement = sample["expected_provisional_judgement"]
    gaps = sample["evidence_gaps"]
    if judgement == "Green":
        return "필수 정책·데이터·계산엔진 참조가 제공되어 현재 증적 기준 중대 이슈 후보가 발견되지 않음"
    if judgement == "Yellow":
        return "계산엔진 결과와 정책 참조는 존재하나 보완 설명 또는 조치 추적이 필요함"
    if judgement == "Red":
        return "공식 증적으로 중대 정책 위반 또는 결과 신뢰성 훼손 후보가 확인됨"
    return "판단 보류: " + (", ".join(str(gap) for gap in gaps) or str(sample["expected_gray_reason_code"]))


def reproducibility_record(sample: dict[str, object]) -> list[object]:
    return [
        sample["case_id"],
        case_fingerprint(sample),
        "|".join(FINGERPRINT_FIELDS),
        sample["policy_reference"],
        sample["regulatory_source_reference"],
        sample["calculation_engine_result_reference"],
        decision_stage(sample),
        explanation_summary(sample),
    ]


def zip_writestr(zf: zipfile.ZipFile, name: str, data: str | bytes) -> None:
    info = zipfile.ZipInfo(name)
    info.date_time = (2026, 5, 14, 0, 0, 0)
    info.compress_type = zipfile.ZIP_DEFLATED
    if isinstance(data, str):
        data = data.encode("utf-8")
    zf.writestr(info, data)


def load_samples() -> list[dict[str, object]]:
    return json.loads(SAMPLE_PATH.read_text(encoding="utf-8"))["samples"]


def judgement_counts(samples: list[dict[str, object]]) -> dict[str, int]:
    counts = {"Green": 0, "Yellow": 0, "Red": 0, "Gray": 0}
    for sample in samples:
        counts[str(sample["expected_provisional_judgement"])] += 1
    return counts


def xml_text(value: object) -> str:
    if isinstance(value, list):
        value = ", ".join(str(item) for item in value)
    if value is None:
        value = ""
    return escape(str(value))


def xlsx_cell(ref: str, value: object) -> str:
    return f'<c r="{ref}" t="inlineStr"><is><t>{xml_text(value)}</t></is></c>'


def column_name(index: int) -> str:
    name = ""
    while index:
        index, rem = divmod(index - 1, 26)
        name = chr(65 + rem) + name
    return name


def sheet_xml(rows: list[list[object]]) -> str:
    row_xml = []
    for r_idx, row in enumerate(rows, start=1):
        cells = [xlsx_cell(f"{column_name(c_idx)}{r_idx}", value) for c_idx, value in enumerate(row, start=1)]
        row_xml.append(f'<row r="{r_idx}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<sheetData>' + "".join(row_xml) + '</sheetData></worksheet>'
    )


def workbook_rows(samples: list[dict[str, object]]) -> dict[str, list[list[object]]]:
    case_rows = [[
        "case_id", "case_fingerprint", "request_id", "validation_object_type", "risk_output_domain",
        "primary_risk_output_domain", "secondary_risk_output_domains", "judgement",
        "decision_stage", "explanation_summary", "action_notice_required", "gray_reason",
        "engine_result_reference", "policy_reference",
    ]]
    gap_rows = [["case_id", "risk_output_domain", "evidence_gap"]]
    notice_rows = [["case_id", "judgement", "action_notice_required", "gray_reason", "owner_placeholder", "due_date_placeholder"]]
    audit_rows = [["case_id", "audit_trail_item"]]
    reproducibility_rows = [[
        "case_id", "case_fingerprint", "fingerprint_fields", "policy_reference",
        "regulatory_source_reference", "calculation_engine_result_reference", "decision_stage", "explanation_summary",
    ]]
    explanation_rows = [[
        "case_id", "judgement", "decision_stage", "explanation_summary",
        "evidence_gaps", "human_reviewer_required",
    ]]

    for sample in samples:
        case_rows.append([
            sample["case_id"], case_fingerprint(sample), sample["request_id"], sample["validation_object_type"],
            sample["risk_output_domain"], sample["primary_risk_output_domain"],
            sample["secondary_risk_output_domains"], sample["expected_provisional_judgement"],
            decision_stage(sample), explanation_summary(sample),
            sample["expected_action_notice_required"], sample["expected_gray_reason_code"],
            sample["calculation_engine_result_reference"], sample["policy_reference"],
        ])
        reproducibility_rows.append(reproducibility_record(sample))
        explanation_rows.append([
            sample["case_id"], sample["expected_provisional_judgement"], decision_stage(sample),
            explanation_summary(sample), sample["evidence_gaps"], sample["human_reviewer_required"],
        ])
        for gap in sample["evidence_gaps"]:
            gap_rows.append([sample["case_id"], sample["risk_output_domain"], gap])
        if sample["expected_action_notice_required"]:
            notice_rows.append([
                sample["case_id"], sample["expected_provisional_judgement"], True,
                sample["expected_gray_reason_code"], "담당부서 지정 필요", "인간 검증자 지정 필요",
            ])
        for item in sample["audit_trail_items"]:
            audit_rows.append([sample["case_id"], item])

    readme_rows = [
        ["문서번호", DOC_NO],
        ["시행일자", TODAY],
        ["주의", "본 엑셀 검증파일은 샘플 증적 기반 검토표이며 수치 계산을 수행하지 않는다."],
        ["판정라벨", "Green / Yellow / Red / Gray only"],
        ["재현가능성", "case_fingerprint, fingerprint_fields, 정책/감독기준/계산엔진 참조를 기록"],
        ["설명가능성", "decision_stage와 explanation_summary로 판정 후보의 결정경로를 기록"],
    ]
    return {
        "README": readme_rows,
        "Case_Register": case_rows,
        "Evidence_Gaps": gap_rows,
        "Action_Notices": notice_rows,
        "Audit_Trail": audit_rows,
        "Reproducibility": reproducibility_rows,
        "Explainability": explanation_rows,
    }


def write_xlsx(samples: list[dict[str, object]], output_dir: Path = OUTPUT_DIR) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "validation_workbook.xlsx"
    sheets = workbook_rows(samples)
    sheet_names = list(sheets)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zip_writestr(zf, "[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/></Types>')
        zip_writestr(zf, "_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        workbook_sheets = "".join(f'<sheet name="{name}" sheetId="{idx}" r:id="rId{idx}"/>' for idx, name in enumerate(sheet_names, start=1))
        zip_writestr(zf, "xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' + workbook_sheets + '</sheets></workbook>')
        rels = "".join(f'<Relationship Id="rId{idx}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{idx}.xml"/>' for idx in range(1, len(sheet_names) + 1))
        zip_writestr(zf, "xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + rels + '</Relationships>')
        for idx, name in enumerate(sheet_names, start=1):
            zip_writestr(zf, f"xl/worksheets/sheet{idx}.xml", sheet_xml(sheets[name]))
    return path


def official_header(title: str) -> str:
    return f"""문서번호: {DOC_NO}
시행일자: {TODAY}
공개구분: 내부검토
보존기간: 5년
수신: 리스크감리팀장
참조: 모형검증, 리스크관리, 준법감시, IT·데이터 담당부서
제목: {title}
"""


def practitioner_markdown(samples: list[dict[str, object]]) -> str:
    counts = judgement_counts(samples)
    lines = [
        "# 양적검증 결과 보고서(실무자용 상세본)",
        "",
        official_header("양적검증 결과 검토 및 조치안내(실무자용)"),
        "## 1. 검토 목적",
        "본 문서는 리스크 산출 영역별 샘플 검증 요청에 대한 실무자 검토용 산출물이다. 본 문서는 최종 승인 문서가 아니며, 수치 계산을 수행하지 않는다.",
        "",
        "## 2. 판정 요약",
        f"- Green: {counts['Green']}",
        f"- Yellow: {counts['Yellow']}",
        f"- Red: {counts['Red']}",
        f"- Gray: {counts['Gray']}",
        "",
        "## 3. 케이스별 상세 검토표",
        "| case_id | fingerprint | risk_output_domain | validation_object_type | judgement | 결정경로 | Action Notice | Gray 사유 | 증적 공백 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for sample in samples:
        lines.append(
            "| {case_id} | {fingerprint} | {risk_output_domain} | {validation_object_type} | {judgement} | {stage} | {notice} | {gray} | {gaps} |".format(
                case_id=sample["case_id"],
                fingerprint=case_fingerprint(sample)[:12],
                risk_output_domain=sample["risk_output_domain"],
                validation_object_type=sample["validation_object_type"],
                judgement=sample["expected_provisional_judgement"],
                stage=decision_stage(sample),
                notice=sample["expected_action_notice_required"],
                gray=sample["expected_gray_reason_code"],
                gaps=", ".join(sample["evidence_gaps"]) or "-",
            )
        )
    lines.extend([
        "",
        "## 4. 재현가능성 및 설명가능성",
        "- 각 케이스는 `case_fingerprint`로 식별되며, fingerprint 입력 필드는 request type, 1축/2축 분류, 정책·감독기준·계산엔진 참조로 고정된다.",
        "- `decision_stage`는 deterministic decision protocol의 어느 게이트에서 판정 후보가 결정되었는지 나타낸다.",
        "- `explanation_summary`는 계산이 아니라 증적 상태와 정책/엔진 참조의 존재 여부를 요약한다.",
        "",
        "## 5. 조치 및 확인사항",
        "- Yellow/Red/Gray 케이스는 Action Notice를 생성하고 담당부서, 목표기한, 필요 증적, 재검증 조건을 지정한다.",
        "- Green 케이스도 최종 승인 또는 무결성 보증이 아니며 인간 검증자의 검토가 필요하다.",
        "- 모든 계산값은 공식 계산엔진 결과 ID와 원천 증적을 통해서만 확인한다.",
        "",
        "## 6. 붙임",
        "1. validation_workbook.xlsx",
        "2. artifact_manifest.json",
        "3. risk_domain_samples.json",
    ])
    return "\n".join(lines) + "\n"


def executive_markdown(samples: list[dict[str, object]]) -> str:
    counts = judgement_counts(samples)
    non_green = [s for s in samples if s["expected_provisional_judgement"] != "Green"]
    lines = [
        "# 양적검증 결과 보고서(경영진 요약본)",
        "",
        official_header("양적검증 결과 및 주요 조치사항 보고(경영진용)"),
        "## 1. 보고 요지",
        "본 보고서는 리스크 산출 영역별 검증 샘플의 주요 판정 후보와 조치 필요사항을 경영진 보고 형식으로 요약한 내부 검토 초안이다.",
        "",
        "## 2. 종합 현황",
        f"- 총 검토 건수: {len(samples)}",
        f"- Green: {counts['Green']} / Yellow: {counts['Yellow']} / Red: {counts['Red']} / Gray: {counts['Gray']}",
        f"- Action Notice 대상: {len(non_green)}",
        "",
        "## 3. 재현가능성 및 설명가능성 요약",
        "- 모든 케이스는 case_fingerprint로 재실행 비교가 가능하다.",
        "- 비Green 케이스는 decision_stage와 explanation_summary를 통해 조치 사유를 추적한다.",
        "",
        "## 4. 경영진 확인 필요사항",
    ]
    for sample in non_green:
        lines.append(f"- {sample['case_id']} ({sample['risk_output_domain']}): {sample['expected_provisional_judgement']} - 증적/조치 확인 필요")
    lines.extend([
        "",
        "## 5. 유의사항",
        "- 본 보고서는 최종 승인 문서가 아니며 공식 조직의 검토와 결재가 필요하다.",
        "- LLM은 수치 계산을 수행하지 않았고, 계산엔진 결과 참조의 존재 여부만 검토했다.",
    ])
    return "\n".join(lines) + "\n"


def markdown_to_html(markdown: str, title: str) -> str:
    body = []
    in_table = False
    for line in markdown.splitlines():
        if line.startswith("# "):
            body.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            if in_table:
                body.append("</table>"); in_table = False
            body.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("|") and line.endswith("|"):
            raw_cells = [cell.strip() for cell in line.strip("|").split("|")]
            if all(cell and set(cell) <= {"-", ":"} for cell in raw_cells):
                continue
            cells = [html.escape(cell) for cell in raw_cells]
            if not in_table:
                body.append("<table>"); in_table = True
            tag = "th" if "case_id" in raw_cells[0] else "td"
            body.append("<tr>" + "".join(f"<{tag}>{cell}</{tag}>" for cell in cells) + "</tr>")
        elif line.startswith("- "):
            body.append(f"<p class='bullet'>• {html.escape(line[2:])}</p>")
        elif line.strip():
            body.append(f"<p>{html.escape(line)}</p>")
        else:
            body.append("<br/>")
    if in_table:
        body.append("</table>")
    return f"""<!doctype html>
<html lang="ko">
<head>
<meta charset="utf-8"/>
<title>{html.escape(title)}</title>
<style>
body {{ font-family: 'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; margin: 36px; color: #111; }}
h1 {{ text-align: center; border-bottom: 3px double #111; padding-bottom: 12px; }}
h2 {{ margin-top: 28px; border-left: 6px solid #333; padding-left: 10px; }}
p {{ line-height: 1.55; }}
.bullet {{ margin-left: 16px; }}
table {{ width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 12px; }}
th, td {{ border: 1px solid #555; padding: 6px; vertical-align: top; }}
th {{ background: #f0f0f0; }}
</style>
</head>
<body>
{''.join(body)}
</body>
</html>
"""


def write_hwpx(text: str, path: Path) -> None:
    paragraphs = "".join(f"<p>{xml_text(line)}</p>" for line in text.splitlines() if line.strip())
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zip_writestr(zf, "mimetype", "application/hwp+zip")
        zip_writestr(zf, "version.xml", "<?xml version='1.0' encoding='UTF-8'?><version>1.0</version>")
        zip_writestr(zf, "Contents/content.hpf", "<?xml version='1.0' encoding='UTF-8'?><package><metadata><title>양적검증 결과 보고서</title></metadata><manifest><item href='Contents/section0.xml'/></manifest></package>")
        zip_writestr(zf, "Contents/section0.xml", f"<?xml version='1.0' encoding='UTF-8'?><document><body>{paragraphs}</body></document>")


def pdf_text(text: str) -> str:
    encoded = ("\ufeff" + text).encode("utf-16-be").hex().upper()
    return f"<{encoded}>"


def write_pdf(text: str, path: Path) -> None:
    lines = [line[:80] for line in text.splitlines() if line.strip()][:34]
    commands = ["BT", "/F1 10 Tf", "50 790 Td"]
    first = True
    for line in lines:
        if not first:
            commands.append("0 -20 Td")
        commands.append(f"{pdf_text(line)} Tj")
        first = False
    commands.append("ET")
    stream = "\n".join(commands).encode("utf-8")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for idx, obj in enumerate(objects, start=1):
        offsets.append(len(out))
        out.extend(f"{idx} 0 obj\n".encode())
        out.extend(obj)
        out.extend(b"\nendobj\n")
    xref = len(out)
    out.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        out.extend(f"{offset:010d} 00000 n \n".encode())
    out.extend(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    path.write_bytes(bytes(out))


def write_reports(samples: list[dict[str, object]], output_dir: Path = OUTPUT_DIR) -> list[Path]:
    reports = {
        "practitioner_report": practitioner_markdown(samples),
        "executive_report": executive_markdown(samples),
    }
    paths: list[Path] = []
    for stem, md in reports.items():
        output_dir.mkdir(parents=True, exist_ok=True)
        md_path = output_dir / f"{stem}.md"
        html_path = output_dir / f"{stem}.html"
        hwpx_path = output_dir / f"{stem}.hwpx"
        pdf_path = output_dir / f"{stem}.pdf"
        md_path.write_text(md, encoding="utf-8")
        html_path.write_text(markdown_to_html(md, stem), encoding="utf-8")
        write_hwpx(md, hwpx_path)
        write_pdf(md, pdf_path)
        paths.extend([md_path, html_path, hwpx_path, pdf_path])
    return paths


def group_by_validation_object_type(samples: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
    grouped = {object_type: [] for object_type in VALIDATION_OBJECT_TYPES}
    for sample in samples:
        grouped[str(sample["validation_object_type"])].append(sample)
    return grouped


def axis_package_summary(grouped: dict[str, list[dict[str, object]]]) -> str:
    lines = [
        "# 1축(validation_object_type) 기준 산출물 구성",
        "",
        "| validation_object_type | 케이스 수 | 산출물 폴더 | 최적화 목적 |",
        "|---|---:|---|---|",
    ]
    purpose = {
        "credit_rating_model": "모형문서·등급체계·override·성능검증 중심 검토",
        "credit_risk_parameter": "PD/LGD/EAD 파라미터와 계산엔진 결과 중심 검토",
        "risk_factor_validation": "위험요소·거시변수·외부지표 정의와 lineage 중심 검토",
        "aggregation_reporting": "집계 로직·reconciliation·보고서 증적 중심 검토",
        "hybrid_risk_output": "ST/ICAAP/IRRBB 등 복합 산출물의 주영역·부영역 중심 검토",
    }
    for object_type in VALIDATION_OBJECT_TYPES:
        lines.append(
            f"| `{object_type}` | {len(grouped[object_type])} | `by_validation_object_type/{object_type}/` | {purpose[object_type]} |"
        )
    lines.extend([
        "",
        "각 폴더에는 해당 1축 유형에 필터링된 `validation_workbook.xlsx`, `practitioner_report.md/html/hwpx/pdf`, `executive_report.md/html/hwpx/pdf`가 생성된다.",
        "모든 산출물은 샘플 증적과 계산엔진 결과 참조를 정리할 뿐, 수치 계산이나 최종 승인 판단을 수행하지 않는다.",
    ])
    return "\n".join(lines) + "\n"


def write_axis_packages(samples: list[dict[str, object]]) -> tuple[list[Path], dict[str, list[str]]]:
    grouped = group_by_validation_object_type(samples)
    base_dir = OUTPUT_DIR / "by_validation_object_type"
    if base_dir.exists():
        shutil.rmtree(base_dir)
    axis_paths: list[Path] = []
    axis_manifest: dict[str, list[str]] = {}
    summary_path = base_dir / "README.md"
    base_dir.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(axis_package_summary(grouped), encoding="utf-8")
    axis_paths.append(summary_path)
    axis_manifest["_summary"] = [str(summary_path.relative_to(ROOT))]

    for object_type in VALIDATION_OBJECT_TYPES:
        object_samples = grouped[object_type]
        object_dir = base_dir / object_type
        paths = [write_xlsx(object_samples, object_dir), *write_reports(object_samples, object_dir)]
        axis_paths.extend(paths)
        axis_manifest[object_type] = [str(path.relative_to(ROOT)) for path in paths]
    return axis_paths, axis_manifest


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    samples = load_samples()
    axis_paths, axis_packages = write_axis_packages(samples)
    paths = [write_xlsx(samples), *write_reports(samples), *axis_paths]
    manifest = {
        "generated_on": TODAY,
        "document_number": DOC_NO,
        "source_sample": str(SAMPLE_PATH.relative_to(ROOT)),
        "artifacts": [str(path.relative_to(ROOT)) for path in paths],
        "axis_packages": axis_packages,
        "sample_fingerprints": {str(sample["case_id"]): case_fingerprint(sample) for sample in samples},
        "explainability_index": {
            str(sample["case_id"]): {
                "decision_stage": decision_stage(sample),
                "explanation_summary": explanation_summary(sample),
            }
            for sample in samples
        },
        "fingerprint_fields": FINGERPRINT_FIELDS,
        "controls": [
            "No LLM numeric calculation",
            "Green/Yellow/Red/Gray only",
            "Non-Green requires Action Notice",
            "Human final approval required",
        ],
    }
    manifest_path = OUTPUT_DIR / "artifact_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"generated {len(paths) + 1} artifacts in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()

