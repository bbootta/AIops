"""산출물 패키징 — 테이블·DDL·보고서·업무보고서를 하나의 ZIP으로 (R10).

10라운드 산출물을 검증 가능한 형태로 묶는다:

    deliverables/
      01_datamodel/    테이블 CSV + 통합 DDL + 카탈로그 요약
      02_reports/      경영진·실무진 HTML 전체 (기존 패키지)
      03_evidence/     manifest · audit ledger · 조정 원장 · 검증 결과
      04_work_report/  업무보고서 (HTML · Markdown)
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
    from risk_lib.datamodel.materialize import materialize_all
    from risk_lib.html_report import build_full_report_package
    from risk_lib.work_report import write_work_report
    from risk_lib import datamodel as dm

    root = Path(out_root)
    if root.exists():
        import shutil
        shutil.rmtree(root)
    root.mkdir(parents=True)

    # 01 · 데이터모델
    tables = materialize_all(result, portfolio)
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
        adjustment_ledger=adjustment_ledger)

    # 03 · 증빙 (보고서 패키지에서 복사)
    ev_dir = root / "03_evidence"
    ev_dir.mkdir(parents=True, exist_ok=True)
    import shutil
    for key in ("manifest", "audit_ledger", "adjustment_ledger"):
        src = rep.get(key)
        if src and Path(src).exists():
            shutil.copy2(src, ev_dir / Path(src).name)

    # 04 · 업무보고서
    wr = write_work_report(result, portfolio, tables, root / "04_work_report")

    # README + 무결성 매니페스트
    (root / "README.md").write_text(_readme(result, tables, len(csvs)),
                                    encoding="utf-8")
    write_manifest(root)
    zip_path = make_zip(root, root.parent / zip_name)
    check = verify_zip(zip_path)
    return {
        "root": str(root), "zip": str(zip_path),
        "n_tables": len(tables), "n_csv": len(csvs),
        "ddl": str(sql), "catalog": str(cat_csv),
        "work_report": wr, "reports": len(rep),
        "schema_violations": len(viol),
        "zip_verified": check,
    }


def _readme(result, tables, n_csv: int) -> str:
    from risk_lib.datamodel import catalog as cat
    asof = result.meta.get("asof", "")
    return f"""# 리스크관리 에이전트 하니스 — 산출물 패키지

산출 기준일 **{asof}** · seed **{result.meta.get('seed')}**

## 구성

| 폴더 | 내용 |
|---|---|
| `01_datamodel/` | 정규 테이블 CSV {n_csv}개 · 통합 DDL(`schema.sql`) · 카탈로그 요약 · 스키마 검증 결과 |
| `02_reports/` | 경영진 보고서 · 실무진 심층 페이지 · 리스크위원회 board pack(국/영문) · 인쇄용 |
| `03_evidence/` | manifest(재현) · audit ledger(산출근거) · 수동조정 원장 |
| `04_work_report/` | 업무보고서 (Markdown · HTML) |
| `MANIFEST.txt` | 전 파일 SHA-256 + 크기 — 전달 후 무결성 자가검증용 |

## 확인 순서

1. `04_work_report/업무보고서.html` — 무엇을 만들었고 무엇이 남았는지
2. `02_reports/executive.html` — 리스크 결과 (CRO용)
3. `02_reports/ops/index.html` — 부문별 심층 (실무진용)
4. `01_datamodel/schema.sql` — 물리 스키마 (테이블 {len(cat.ALL_TABLES)}개)

## 무결성 검증

```bash
# MANIFEST.txt의 sha256과 실제 파일을 대조
awk '!/^#/ && NF==3 {{print $1"  "$3}}' MANIFEST.txt | sha256sum -c
```

## 한계

합성 데이터 기반 예시 산출이며 **규제 제출용이 아닙니다**. 허용오차·임계값은
내부 관리값이므로 기관 승인 사양으로 교체가 전제입니다.
"""
