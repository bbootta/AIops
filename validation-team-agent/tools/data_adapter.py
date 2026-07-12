"""운영 데이터 연계 어댑터 — CSV/Parquet 안전 로더 (Phase 1 병행 운영 입구).

합성 데이터 대신 실제 추출 파일 (CSV/Parquet) 을 워크플로우 request 로
변환한다. **안전 boundary 3중**:

1. **PII 차단**: 로드 즉시 ``data_safety_guard.scan_dataframe`` — 민감정보
   패턴 발견 시 기본 동작은 **차단 (PIIDetectedError)**. ``pii_action="drop"``
   이면 해당 컬럼 제거 후 진행 (감사로그에 기록).
2. **스키마 검증**: 필수 컬럼 존재 + dtype 검사 (schema_guard 재사용).
3. **Pseudonymize**: id 컬럼을 per-run salt SHA-256 으로 치환 (기본 on) —
   원본 식별자는 request 에 실리지 않는다.

CLAUDE.md §5: 운영계 DB 직접 접속은 하지 않는다 — 본 어댑터는 **추출 파일**
만 다룬다. 실제 고객 식별정보 저장 금지 원칙에 따라 pseudonymize 기본 적용.

사용:
    python -m tools.data_adapter validate --input data.csv --mapping mapping.json
    python -m tools.data_adapter convert --input data.csv --mapping mapping.json \\
        --out request_meta.json
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class PIIDetectedError(RuntimeError):
    """입력 파일에서 민감정보 패턴 발견 — 로드 차단."""


class MappingError(ValueError):
    """컬럼 매핑 불일치."""


#: 표준 매핑 키 → 의미. request 의 *_col 파라미터와 1:1.
MAPPING_KEYS = {
    "id_col": "고객/계좌 식별자 (pseudonymize 대상)",
    "date_col": "관측 일자",
    "score_col": "모형 점수",
    "target_col": "부도 여부 (0/1)",
    "grade_col": "등급",
    "pd_col": "추정 PD",
    "set_col": "dev/oot 구분",
}

REQUIRED_KEYS = ("score_col", "target_col")


def load_mapping(path: str | Path) -> dict[str, str]:
    m = json.loads(Path(path).read_text(encoding="utf-8"))
    unknown = set(m) - set(MAPPING_KEYS)
    if unknown:
        raise MappingError(f"알 수 없는 매핑 키: {sorted(unknown)}")
    missing = [k for k in REQUIRED_KEYS if k not in m]
    if missing:
        raise MappingError(f"필수 매핑 키 누락: {missing}")
    return {str(k): str(v) for k, v in m.items()}


def _read_table(path: str | Path):
    import pandas as pd

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    if p.suffix.lower() in (".parquet", ".pq"):
        return pd.read_parquet(p)
    if p.suffix.lower() in (".csv", ".txt"):
        return pd.read_csv(p)
    raise ValueError(f"지원하지 않는 형식: {p.suffix} (csv/parquet 만)")


def _pseudonymize(series, salt: bytes):
    """식별자 → salt SHA-256 16 hex. 원본은 반환 데이터에 남지 않는다."""
    def _h(v: object) -> str:
        return hashlib.sha256(salt + str(v).encode("utf-8")).hexdigest()[:16]
    return series.map(_h)


def load_validation_input(
    path: str | Path,
    mapping: Mapping[str, str],
    *,
    pii_action: str = "block",     # block | drop
    pseudonymize: bool = True,
    salt: bytes | None = None,
) -> dict[str, Any]:
    """추출 파일을 안전 boundary 3중 통과 후 request dict 로 변환.

    반환 request 는 run_workflow_demo.build_request 와 동일 형태의 신용
    부문 키를 포함한다 (df + *_col). 부문별 스칼라 입력 (capital_* 등) 은
    포함하지 않는다 — 호출자가 병합.

    Raises:
        PIIDetectedError: pii_action="block" 이고 민감정보 발견 시.
        MappingError: 매핑 컬럼이 파일에 없을 때.
    """
    from middleware.data_safety_guard import scan_dataframe

    if pii_action not in ("block", "drop"):
        raise ValueError("pii_action must be 'block' or 'drop'")

    df = _read_table(path)

    # 매핑 컬럼 존재 확인
    missing = [f"{k}={v}" for k, v in mapping.items() if v not in df.columns]
    if missing:
        raise MappingError(f"파일에 없는 매핑 컬럼: {missing}")

    # 일자 컬럼 정규화 — datetime dtype 강제. 문자열 날짜 (YYYY-MM-DD) 가
    # 계좌번호 패턴에 오탐되는 것을 방지하고 (R19 known limitation),
    # 이후 date coverage 점검의 전제 조건이기도 하다.
    if "date_col" in mapping:
        import pandas as pd

        try:
            df = df.copy()
            df[mapping["date_col"]] = pd.to_datetime(df[mapping["date_col"]])
        except (ValueError, TypeError) as e:
            raise MappingError(
                f"date_col={mapping['date_col']} datetime 변환 실패: {e}") from e

    # 1) PII boundary
    scan = scan_dataframe(df)
    dropped_columns: list[str] = []
    if not scan["clean"]:
        pii_cols = sorted({f["column"] for f in scan["findings"]})
        if pii_action == "block":
            raise PIIDetectedError(
                f"민감정보 패턴 {len(scan['findings'])}건 발견 "
                f"(컬럼: {pii_cols}). 원문은 로그에 남지 않음. "
                "pii_action='drop' 으로 해당 컬럼 제거 후 진행 가능.")
        # drop 모드: 매핑에 사용되는 컬럼이면 차단 (분석 불가)
        mapped_cols = set(mapping.values())
        conflict = [c for c in pii_cols if c in mapped_cols]
        if conflict:
            raise PIIDetectedError(
                f"매핑 대상 컬럼에 민감정보: {conflict} — drop 불가, 원천 정제 필요.")
        df = df.drop(columns=pii_cols)
        dropped_columns = pii_cols

    # 2) 스키마 검증 (필수 컬럼 dtype)
    from middleware.schema_guard import ColumnSpec, Schema, check_schema

    required_specs = [ColumnSpec(mapping["score_col"], "numeric"),
                      ColumnSpec(mapping["target_col"], "binary")]
    if "pd_col" in mapping:
        required_specs.append(ColumnSpec(mapping["pd_col"], "numeric"))
    if "date_col" in mapping:
        required_specs.append(ColumnSpec(mapping["date_col"], "date"))
    schema_result = check_schema(df, Schema(required=tuple(required_specs)))
    if not schema_result["passed"]:
        raise MappingError(
            f"스키마 위반: {schema_result['violations']}")

    # 3) pseudonymize
    pseudonymized = False
    if pseudonymize and "id_col" in mapping:
        run_salt = salt if salt is not None else os.urandom(16)
        df = df.copy()
        df[mapping["id_col"]] = _pseudonymize(df[mapping["id_col"]], run_salt)
        pseudonymized = True

    request: dict[str, Any] = {
        "title": f"운영 추출 검증 ({Path(path).name})",
        "df": df,
    }
    for key in ("score_col", "target_col", "grade_col", "pd_col",
                "set_col", "date_col"):
        if key in mapping:
            request[key] = mapping[key]
    if "id_col" in mapping and "date_col" in mapping:
        request["key_cols"] = [mapping["id_col"], mapping["date_col"]]

    request["_adapter_meta"] = {
        "source_file": str(path),
        "n_rows": int(len(df)),
        "pii_findings": len(scan["findings"]),
        "pii_action": pii_action,
        "dropped_columns": dropped_columns,
        "pseudonymized": pseudonymized,
        "schema_passed": True,
    }
    return request


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="운영 추출 파일 → 검증 request 어댑터 (PII 차단 boundary)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_val = sub.add_parser("validate", help="파일 안전성/매핑 dry-run 검사")
    p_val.add_argument("--input", type=Path, required=True)
    p_val.add_argument("--mapping", type=Path, required=True)
    p_val.add_argument("--pii-action", choices=["block", "drop"],
                       default="block")

    p_conv = sub.add_parser("convert", help="request 메타데이터 출력 (df 제외)")
    p_conv.add_argument("--input", type=Path, required=True)
    p_conv.add_argument("--mapping", type=Path, required=True)
    p_conv.add_argument("--pii-action", choices=["block", "drop"],
                        default="block")
    p_conv.add_argument("--out", type=Path, default=None)

    args = parser.parse_args(argv)
    mapping = load_mapping(args.mapping)

    try:
        request = load_validation_input(
            args.input, mapping, pii_action=args.pii_action)
    except (PIIDetectedError, MappingError) as e:
        sys.stderr.write(f"차단: {e}\n")
        return 1

    meta = request["_adapter_meta"]
    if args.cmd == "validate":
        sys.stdout.write(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
        sys.stdout.write("OK — boundary 3중 통과 (PII/스키마/pseudonymize)\n")
        return 0

    out_meta = {k: v for k, v in request.items() if k != "df"}
    text = json.dumps(out_meta, ensure_ascii=False, indent=2, default=str)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text + "\n")
    return 0


__all__ = [
    "PIIDetectedError", "MappingError", "MAPPING_KEYS",
    "load_mapping", "load_validation_input",
]


if __name__ == "__main__":
    raise SystemExit(main())
