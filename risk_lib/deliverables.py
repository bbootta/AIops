"""산출물 패키징 — 테이블·DDL·보고서·업무보고서를 하나의 ZIP으로 (R10).

10라운드 산출물을 검증 가능한 형태로 묶는다:

    deliverables/
      01_datamodel/    테이블 CSV + 통합 DDL + 카탈로그 요약
      02_reports/      경영진·실무진 HTML 전체 (기존 패키지)
      03_evidence/     manifest · audit ledger · 조정 원장 · 검증 결과
      04_work_report/  개발 작업보고서 (HTML · Markdown)
      05_regulatory/   금감원 배포 기준 업무보고서 (.xlsx) + 서식 원장 CSV
      06_agentic_ui/   에이전틱 UI 스튜디오 (자체 완결 HTML)
      07_independent_validation/  독립검증 요청 패키지 + 게이트 상태 (3선 위임)
      MANIFEST.txt     ZIP 내 모든 파일의 SHA-256 + 크기
      README.md        패키지 안내

MANIFEST.txt를 함께 넣는 이유: 전달 후 파일이 바뀌었는지 수신자가 스스로
확인할 수 있어야 산출물이 증빙이 된다 (RYNTA SHA256SUMS 관행과 동일).
"""

from __future__ import annotations

import hashlib
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def export_tables(tables: dict[str, pd.DataFrame], out_dir: Path) -> list[Path]:
    """정규 테이블을 CSV로 내보낸다 (UTF-8 BOM — Excel 한글 깨짐 방지)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for name, df in sorted(tables.items()):
        p = out_dir / f"{name}.csv"
        df.to_csv(p, index=False, encoding="utf-8-sig")
        written.append(p)
    return written


def export_ddl(out_dir: Path) -> Path:
    """전체 카탈로그의 DDL을 하나의 SQL 파일로."""
    from risk_lib.datamodel import catalog as cat
    from risk_lib.datamodel.spec import ddl

    out_dir.mkdir(parents=True, exist_ok=True)
    parts = [
        "-- RYNTA 정규 리스크 데이터모델 DDL",
        f"-- 테이블 {len(cat.ALL_TABLES)}개 · 자동생성 (risk_lib.datamodel.spec.ddl)",
        "-- 스펙이 단일 소스이므로 이 파일을 직접 수정하지 말 것.",
        "",
    ]
    # 참조 대상이 먼저 오도록 FK 의존 순서로 정렬
    ordered, seen = [], set()

    def _emit(spec):
        if spec.name in seen:
            return
        for fk in spec.foreign_keys:
            ref = next((s for s in cat.ALL_TABLES if s.name == fk.ref_table), None)
            if ref is not None:
                _emit(ref)
        seen.add(spec.name)
        ordered.append(spec)

    for s in cat.ALL_TABLES:
        _emit(s)
    for s in ordered:
        parts.append(ddl(s))
        parts.append("")
    p = out_dir / "schema.sql"
    p.write_text("\n".join(parts), encoding="utf-8")
    return p


def export_catalog_summary(out_dir: Path) -> Path:
    from risk_lib.datamodel import catalog as cat
    from risk_lib.datamodel.spec import summary_frame
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "catalog_summary.csv"
    summary_frame(cat.ALL_TABLES).to_csv(p, index=False, encoding="utf-8-sig")
    return p


def write_manifest(root: Path) -> Path:
    """패키지 내 모든 파일의 SHA-256·크기 — 수신자가 무결성을 자가 검증한다."""
    rows = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name != "MANIFEST.txt":
            rows.append((_sha256(p), p.stat().st_size, str(p.relative_to(root))))
    body = [
        "# 산출물 무결성 매니페스트",
        f"# 생성 {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        f"# 파일 {len(rows)}개",
        "# 형식: <sha256>  <bytes>  <경로>",
        "",
    ] + [f"{h}  {n:>10d}  {rel}" for h, n, rel in rows]
    p = root / "MANIFEST.txt"
    p.write_text("\n".join(body) + "\n", encoding="utf-8")
    return p


def make_zip(root: Path, zip_path: Path) -> Path:
    """디렉터리를 ZIP으로 압축한다 (MANIFEST 포함)."""
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED,
                         compresslevel=9) as z:
        for p in sorted(root.rglob("*")):
            if p.is_file():
                z.write(p, p.relative_to(root))
    return zip_path


def verify_zip(zip_path: Path) -> dict:
    """ZIP 내 MANIFEST와 실제 내용이 일치하는지 자가 검증한다.

    포장 후 검증하지 않으면 '만들었다'는 것만 알 뿐 '올바른지'는 모른다.
    """
    import io
    with zipfile.ZipFile(zip_path) as z:
        names = set(z.namelist())
        if "MANIFEST.txt" not in names:
            return {"ok": False, "reason": "MANIFEST.txt 없음",
                    "n_files": len(names)}
        manifest = z.read("MANIFEST.txt").decode("utf-8")
        expected = {}
        for line in manifest.splitlines():
            if line.startswith("#") or not line.strip():
                continue
            parts = line.split(None, 2)
            if len(parts) == 3:
                expected[parts[2]] = (parts[0], int(parts[1]))

        mismatched, missing = [], []
        for rel, (sha, size) in expected.items():
            if rel not in names:
                missing.append(rel)
                continue
            data = z.read(rel)
            if hashlib.sha256(data).hexdigest() != sha or len(data) != size:
                mismatched.append(rel)
        extra = names - set(expected) - {"MANIFEST.txt"}
        return {
            "ok": not (mismatched or missing),
            "n_files": len(names),
            "n_verified": len(expected) - len(missing) - len(mismatched),
            "mismatched": mismatched, "missing": missing,
            "unlisted": sorted(extra),
        }


# ---------------------------------------------------------------- 통합 패키징

def build_deliverables(result, portfolio, out_root, *, manifest=None,
                       adjustment_ledger=None, zip_name: str = "deliverables.zip"
                       ) -> dict:
    """10라운드 산출물 전체를 디렉터리로 구성하고 ZIP으로 묶는다."""
    from risk_lib.html_report import build_full_report_package, institution_label
    from risk_lib.work_report import write_work_report
    from risk_lib.ui_studio.studio import build_studio
    from risk_lib.ui_studio.app import write_app
    from risk_lib.regulatory import write_workbook
    from risk_lib import datamodel as dm

    # 이 패키지의 기관 귀속. 실행이 말하지 않았으면 여기서 경고가 나고 표지·
    # README에 미지정으로 적힌다. 한 번만 풀어 두 곳에 같은 값을 쓴다.
    inst = institution_label(result)

    root = Path(out_root)
    if root.exists():
        import shutil
        shutil.rmtree(root)
    root.mkdir(parents=True)

    # 01 · 데이터모델 — 스튜디오 조립이 카탈로그 전체(세분화·업무보고서·UIX
    # 통제 원장 포함)를 채운다. 부문 엔진만 돌리면 CSV가 카탈로그보다 적어져
    # "선언은 됐지만 산출은 없는" 테이블이 조용히 생긴다.
    studio = build_studio(result, portfolio)
    tables = studio.tables
    dm_dir = root / "01_datamodel"
    csvs = export_tables(tables, dm_dir / "tables")
    sql = export_ddl(dm_dir)
    cat_csv = export_catalog_summary(dm_dir)
    # 검증 결과도 산출물에 포함 — 통과 이력이 있어야 증명이 된다
    viol = dm.validate_all(tables)
    dm.dq_result_frame(viol, asof=result.meta.get("asof", "")).to_csv(
        dm_dir / "schema_validation.csv", index=False, encoding="utf-8-sig")

    # 02 · 보고서
    rep = build_full_report_package(
        result, root / "02_reports", portfolio=portfolio, manifest=manifest,
        adjustment_ledger=adjustment_ledger, studio=studio)

    # 03 · 증빙 (보고서 패키지에서 복사)
    ev_dir = root / "03_evidence"
    ev_dir.mkdir(parents=True, exist_ok=True)
    import shutil
    for key in ("manifest", "audit_ledger", "adjustment_ledger"):
        src = rep.get(key)
        if src and Path(src).exists():
            shutil.copy2(src, ev_dir / Path(src).name)

    # 04 · 개발 작업보고서 (라운드별 산출 이력)
    wr = write_work_report(result, portfolio, tables, root / "04_work_report")

    # 05 · 감독보고 — 금감원 배포 기준 업무보고서
    reg_dir = root / "05_regulatory"
    xlsx = write_workbook(
        studio.built_forms, reg_dir / "업무보고서_금감원기준.xlsx",
        asof=studio.asof,
        meta={"seed": result.meta.get("seed", 42), "institution": inst})
    for name in ("reg_form", "reg_form_line", "reg_form_check",
                 "reg_submission"):
        tables[name].to_csv(reg_dir / f"{name}.csv", index=False,
                            encoding="utf-8-sig")
    # 산출 근거 — 어느 라인이 실측이고 어느 라인이 파생인지, 그리고 어떤
    # 원장을 확보하면 무엇이 실측으로 바뀌는지. 합성 데이터 제출본을 실데이터로
    # 옮길 때 이행 계획의 근거가 된다.
    from risk_lib.regulatory.provenance import (
        basis_summary, ledger_impact_frame, provenance_frame,
    )
    # 문서 대조 커버리지는 **요청서가 아니라 여기**에 남긴다. 요청서에 실으면
    # 요청 식별자가 문서에 의존해 재현이 깨진다 (독립검증 지적 F-C01).
    from risk_lib.validation.doc_figures import coverage_report
    for name, frame in (("산출근거_라인별", provenance_frame(studio.built_forms)),
                        ("산출근거_요약", basis_summary(studio.built_forms)),
                        ("원장확보_영향", ledger_impact_frame(studio.built_forms)),
                        ("문서대조_커버리지",
                         coverage_report(studio.built_forms, studio.asof))):
        frame.to_csv(reg_dir / f"{name}.csv", index=False, encoding="utf-8-sig")

    # 06 · 에이전틱 UI (자체 완결 HTML — 외부 CDN 없음)
    ui_dir = root / "06_agentic_ui"
    ui_html = write_app(studio, ui_dir / "RYNTA_에이전틱UI_스튜디오.html")

    # 07 · 상시 독립검증(3선) 위임 — 요청 패키지는 **항상** 들어간다.
    # 필요할 때만 넣으면 결국 넣지 않게 된다.
    iv_dir = root / "07_independent_validation"
    iv_req = studio.iv_request.write(iv_dir)
    for name in ("val_independent_request", "val_independent_target"):
        tables[name].to_csv(iv_dir / f"{name}.csv", index=False,
                            encoding="utf-8-sig")
    (iv_dir / "GATE.txt").write_text(
        f"상태: {studio.iv_gate.status}\n"
        f"사유: {studio.iv_gate.reason}\n"
        f"요청: {studio.iv_request.request_id}\n"
        f"수신: {studio.iv_request.requested_to} / {studio.iv_request.branch}\n"
        f"\n게이트가 '적합'이 되기 전에는 결재 상신 불가 (fail-closed).\n",
        encoding="utf-8")

    # README + 무결성 매니페스트
    (root / "README.md").write_text(
        _readme(result, tables, len(csvs), studio, institution=inst),
        encoding="utf-8")
    write_manifest(root)
    zip_path = make_zip(root, root.parent / zip_name)
    check = verify_zip(zip_path)
    return {
        "root": str(root), "zip": str(zip_path),
        # `institution` 은 표지 표기(미지정이면 비운다)이고
        # `institution_in_ledgers` 는 원장·run_id 가 실제로 담은 코드다. 실행이
        # 기관을 말하지 않으면 둘이 갈리므로 한 키로 합치지 않는다.
        "institution": inst,
        "institution_in_ledgers": studio.institution_code,
        "institution_source": studio.institution_source,
        "n_tables": len(tables), "n_csv": len(csvs),
        "ddl": str(sql), "catalog": str(cat_csv),
        "work_report": wr, "reports": len(rep),
        "regulatory_xlsx": str(xlsx),
        "n_forms": len(studio.built_forms),
        "n_form_lines": int(len(tables["reg_form_line"])),
        "n_form_checks_failed": int(
            (tables["reg_form_check"]["status"] == "FAIL").sum()),
        "agentic_ui": str(ui_html),
        "independent_validation_request": str(iv_req),
        "independent_validation_status": studio.iv_gate.status,
        "schema_violations": len(viol),
        "zip_verified": check,
    }


def _readme(result, tables, n_csv: int, studio=None, *,
            institution: str = "") -> str:
    from risk_lib.datamodel import catalog as cat
    asof = result.meta.get("asof", "")
    n_forms = len(studio.built_forms) if studio else 0
    n_lines = int(len(tables.get("reg_form_line", []))) if studio else 0
    # 기관 귀속이 실행에서 온 것인지 아닌지를 패키지 첫 화면에 적는다. 미지정을
    # 적지 않으면 받는 쪽은 표지의 기관을 실행이 말한 것으로 읽는다.
    # 표지와 패키지 안 원장은 대체 정책이 다르다. 표지는 미지정으로 비우고,
    # 원장·run_id 는 화면이 그려져야 하므로 기본 기관으로 채운다. 그 사실을
    # 적지 않으면 같은 패키지가 두 기관을 주장하는 것으로 읽힌다.
    subbed = studio.institution_code if studio else ""
    inst_note = "" if result.meta.get("institution_code") else (
        "\n> **기관 미지정.** 이 실행은 기관코드를 지정하지 않았다. 업무보고서\n"
        "> 표지의 제출기관과 이 문서의 기관 표기는 실행이 말한 값이 아니라\n"
        "> 미지정 표기다.\n"
        ">\n"
        f"> 반면 패키지 안의 원장·`run_id`·에이전틱 UI 는 기본 기관\n"
        f"> **{subbed}** 로 채워져 있다. 화면과 원장이 기관코드 없이는 그려지지\n"
        "> 않기 때문이며, 그 값 역시 실행이 말한 귀속이 아니다. 표지와 원장의\n"
        "> 기관이 다르게 보이는 것은 이 두 대체 정책 때문이다.\n"
        ">\n"
        "> 감독 제출 전에 `run_pipeline(institution_code=...)` 로 기관을 지정해\n"
        "> 다시 산출해야 한다. 그때 표지와 원장이 같은 기관을 가리킨다.\n")
    return f"""# 리스크관리 에이전트 하니스 — 산출물 패키지

산출 기준일 **{asof}** · seed **{result.meta.get('seed')}** · 제출기관 **{institution}**
{inst_note}
## 구성

| 폴더 | 내용 |
|---|---|
| `01_datamodel/` | 정규 테이블 CSV {n_csv}개 · 통합 DDL(`schema.sql`) · 카탈로그 요약 · 스키마 검증 결과 |
| `02_reports/` | 경영진 보고서 · 실무진 심층 페이지 · 리스크위원회 board pack(국/영문) · 인쇄용 |
| `03_evidence/` | manifest(재현) · audit ledger(산출근거) · 수동조정 원장 |
| `04_work_report/` | **개발 작업보고서** — 라운드별 산출 이력 (Markdown · HTML) |
| `05_regulatory/` | **금감원 배포 기준 업무보고서** — 서식 {n_forms}장 · 라인 {n_lines}행 (.xlsx) + 서식 원장 CSV |
| `06_agentic_ui/` | **에이전틱 UI 스튜디오** — 전 모듈 관리 화면 (자체 완결 HTML) |
| `07_independent_validation/` | **상시 독립검증 위임** — 요청 패키지 · 재계산 대상 · 게이트 상태 |
| `MANIFEST.txt` | 전 파일 SHA-256 + 크기 — 전달 후 무결성 자가검증용 |

`04_work_report`(개발 진행 보고)와 `05_regulatory`(감독당국 제출 서식)는 서로
다른 문서다. 감독보고용은 **05**다.

## 확인 순서

1. `06_agentic_ui/RYNTA_에이전틱UI_스튜디오.html` — 전 모듈 통제 상태 한 화면
2. `05_regulatory/업무보고서_금감원기준.xlsx` — 감독보고 서식 (표지 → 목차 → 서식 → 검증)
3. `02_reports/executive.html` — 리스크 결과 (CRO용)
4. `02_reports/ops/index.html` — 부문별 심층 (실무진용)
5. `01_datamodel/schema.sql` — 물리 스키마 (테이블 {len(cat.ALL_TABLES)}개)

## 검증의 두 층

이 패키지의 자체검증(2선) 결과는 **같은 코드·같은 가정**으로 점검한 것이다.
결재에는 적합성검증 팀에이전트(`claude/validation-team-agent-Pw9F5`)의 상시
독립검증(3선)이 함께 필요하다. `07_independent_validation/GATE.txt`가 현재
게이트 상태를 담고 있으며, `적합`이 아니면 결재 상신 대상이 아니다.

## 업무보고서 서식번호에 관한 전제

금융감독원 배포 서식 파일이 입력으로 주어지지 않아 서식 식별자는 내부 코드
(`BR-01` …)를 쓴다. 배포본과 연결할 때는 `reg_form.form_id ↔ 배포 서식번호`
매핑 한 장만 추가하면 되며, 라인 코드·산식·규정 근거는 그대로 쓸 수 있다.

## 무결성 검증

```bash
# MANIFEST.txt의 sha256과 실제 파일을 대조
awk '!/^#/ && NF==3 {{print $1"  "$3}}' MANIFEST.txt | sha256sum -c
```

## 한계

합성 데이터 기반 예시 산출이며 **규제 제출용이 아닙니다**. 허용오차·임계값은
내부 관리값이므로 기관 승인 사양으로 교체가 전제입니다.
"""
