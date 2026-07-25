"""정규 리스크 데이터모델 — 스펙·검증·DDL 엔진 (RDM-003 · DAT-001).

평면 DataFrame은 산출은 되지만 **통제되지 않는다**: 키가 없어 중복을 못 잡고,
참조무결성이 없어 고아 레코드가 지나가며, 단위·허용값·출처가 코드에만 있어
감사에서 재현할 근거가 되지 못한다.

본 모듈은 테이블을 1급 객체로 만든다:

  ColumnSpec   이름·타입·널 허용·단위·허용값·범위·규정 출처
  TableSpec    입도(grain)·기본키·외래키·컬럼·담당 Product
  validate()   DataFrame ↔ 스펙 대조 → 위반 목록 (통과/실패가 아니라 무엇이 왜)
  ddl()        SQL DDL 생성 — 스펙이 곧 물리 스키마
  check_refs() 테이블 간 참조무결성

검증은 **실패할 수 있어야** 통제다. 모든 규칙은 위반 사례를 만들 수 있고,
tests/test_datamodel.py가 각 규칙마다 위반 케이스로 발동을 확인한다.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd

# 지원 논리 타입 → (pandas dtype 후보, SQL 타입)
_TYPES: dict[str, tuple[tuple[str, ...], str]] = {
    # pandas 3.0의 기본 문자열 dtype은 'str' — object/string과 함께 받아야
    # 버전 차이로 스키마가 통째로 FAIL 나지 않는다.
    "string":  (("object", "string", "str"), "VARCHAR(64)"),
    "text":    (("object", "string", "str"), "VARCHAR(256)"),
    "int":     (("int64", "Int64", "int32"), "BIGINT"),
    "float":   (("float64", "float32"), "DOUBLE PRECISION"),
    "bool":    (("bool", "boolean", "object"), "BOOLEAN"),
    "date":    (("object", "string", "str", "datetime64[ns]"), "DATE"),
}


class SchemaError(ValueError):
    """스펙 정의 자체가 잘못됐을 때 (런타임 데이터 위반과 구분)."""


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    dtype: str                       # _TYPES 키
    korean: str = ""                 # 업무 명칭
    nullable: bool = True
    unit: str = ""                   # KRW · ratio · years · bp · count …
    allowed: tuple[Any, ...] | None = None    # 허용값 집합 (범주형)
    min_value: float | None = None
    max_value: float | None = None
    citation: str = ""               # 규정·정의 출처
    note: str = ""

    def __post_init__(self):
        if self.dtype not in _TYPES:
            raise SchemaError(f"{self.name}: 미지원 타입 {self.dtype!r}")
        if (self.min_value is not None and self.max_value is not None
                and self.min_value > self.max_value):
            raise SchemaError(f"{self.name}: min > max")
        if self.allowed is not None and len(self.allowed) == 0:
            raise SchemaError(f"{self.name}: allowed가 빈 집합 — 어떤 값도 통과 불가")

    @property
    def sql_type(self) -> str:
        return _TYPES[self.dtype][1]


@dataclass(frozen=True)
class ForeignKey:
    columns: tuple[str, ...]
    ref_table: str
    ref_columns: tuple[str, ...]

    def __post_init__(self):
        if len(self.columns) != len(self.ref_columns):
            raise SchemaError(f"FK 컬럼 수 불일치: {self.columns} → {self.ref_columns}")


@dataclass(frozen=True)
class TableSpec:
    name: str
    korean: str
    grain: str                       # 1행이 무엇인가 — 입도를 못 쓰면 설계가 안 된 것
    columns: tuple[ColumnSpec, ...]
    primary_key: tuple[str, ...] = ()
    foreign_keys: tuple[ForeignKey, ...] = ()
    product: str = ""                # RYNTA Canonical Product ID
    note: str = ""

    def __post_init__(self):
        names = [c.name for c in self.columns]
        dup = {n for n in names if names.count(n) > 1}
        if dup:
            raise SchemaError(f"{self.name}: 컬럼명 중복 {sorted(dup)}")
        if not self.grain.strip():
            raise SchemaError(f"{self.name}: grain(입도) 미기재")
        missing = set(self.primary_key) - set(names)
        if missing:
            raise SchemaError(f"{self.name}: PK에 없는 컬럼 {sorted(missing)}")
        for fk in self.foreign_keys:
            miss = set(fk.columns) - set(names)
            if miss:
                raise SchemaError(f"{self.name}: FK에 없는 컬럼 {sorted(miss)}")
        # PK 컬럼은 널 허용 불가 — 허용하면 유일성 자체가 무의미
        for pk in self.primary_key:
            col = self.column(pk)
            if col.nullable:
                raise SchemaError(f"{self.name}.{pk}: PK 컬럼은 nullable일 수 없다")

    def column(self, name: str) -> ColumnSpec:
        for c in self.columns:
            if c.name == name:
                return c
        raise SchemaError(f"{self.name}: 컬럼 없음 {name}")

    @property
    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]


@dataclass
class Violation:
    table: str
    rule: str                        # not_null · dtype · allowed · range · pk_unique · fk …
    column: str
    n_rows: int
    detail: str
    severity: str = "FAIL"           # FAIL · WARN

    def __str__(self) -> str:
        loc = f"{self.table}.{self.column}" if self.column else self.table
        return f"[{self.severity}] {loc} {self.rule}: {self.detail} ({self.n_rows}건)"


# ---------------------------------------------------------------- 검증

def _dtype_ok(series: pd.Series, dtype: str) -> bool:
    if dtype == "bool":
        return series.dropna().map(lambda v: isinstance(v, (bool, np.bool_))).all()
    if dtype == "date":
        s = series.dropna()
        if s.empty:
            return True
        return s.map(lambda v: isinstance(v, str) and len(v) == 10 and v[4] == "-").all()
    return str(series.dtype) in _TYPES[dtype][0]


def validate(df: pd.DataFrame, spec: TableSpec, *,
             strict_columns: bool = True) -> list[Violation]:
    """DataFrame을 스펙과 대조해 위반 목록을 반환한다 (예외를 던지지 않는다).

    통과/실패 한 글자가 아니라 **무엇이 왜 틀렸는지**를 돌려줘야 조치가 된다.
    """
    v: list[Violation] = []
    have, want = set(df.columns), set(spec.column_names)

    for miss in sorted(want - have):
        v.append(Violation(spec.name, "missing_column", miss, 0, "컬럼 없음"))
    if strict_columns:
        for extra in sorted(have - want):
            v.append(Violation(spec.name, "unknown_column", extra, 0,
                               "스펙에 없는 컬럼", severity="WARN"))

    for col in spec.columns:
        if col.name not in df.columns:
            continue
        s = df[col.name]

        if not col.nullable:
            n = int(s.isna().sum())
            if n:
                v.append(Violation(spec.name, "not_null", col.name, n,
                                   "널 불허 컬럼에 결측"))
        if not _dtype_ok(s, col.dtype):
            v.append(Violation(spec.name, "dtype", col.name, len(s),
                               f"기대 {col.dtype}, 실제 {s.dtype}"))
        if col.allowed is not None:
            bad = s.dropna()[~s.dropna().isin(col.allowed)]
            if len(bad):
                v.append(Violation(spec.name, "allowed", col.name, len(bad),
                                   f"허용값 밖: {sorted(set(bad))[:5]}"))
        if col.dtype in ("int", "float"):
            num = pd.to_numeric(s, errors="coerce")
            if col.min_value is not None:
                n = int((num < col.min_value).sum())
                if n:
                    v.append(Violation(spec.name, "range", col.name, n,
                                       f"최솟값 {col.min_value} 미만"))
            if col.max_value is not None:
                n = int((num > col.max_value).sum())
                if n:
                    v.append(Violation(spec.name, "range", col.name, n,
                                       f"최댓값 {col.max_value} 초과"))

    if spec.primary_key and set(spec.primary_key) <= have:
        dup = int(df.duplicated(subset=list(spec.primary_key)).sum())
        if dup:
            v.append(Violation(spec.name, "pk_unique",
                               "+".join(spec.primary_key), dup, "기본키 중복"))
    return v


def check_refs(tables: dict[str, pd.DataFrame],
               specs: dict[str, TableSpec]) -> list[Violation]:
    """테이블 간 참조무결성 — 고아 레코드는 집계에서 조용히 누락된다."""
    v: list[Violation] = []
    for name, spec in specs.items():
        if name not in tables:
            continue
        df = tables[name]
        for fk in spec.foreign_keys:
            if fk.ref_table not in tables:
                v.append(Violation(name, "fk_missing_table",
                                   "+".join(fk.columns), 0,
                                   f"참조 테이블 없음: {fk.ref_table}"))
                continue
            ref = tables[fk.ref_table]
            if not set(fk.columns) <= set(df.columns):
                continue
            if not set(fk.ref_columns) <= set(ref.columns):
                continue
            left = df[list(fk.columns)].dropna().apply(tuple, axis=1)
            right = set(ref[list(fk.ref_columns)].dropna().apply(tuple, axis=1))
            orphan = int((~left.isin(right)).sum()) if len(left) else 0
            if orphan:
                v.append(Violation(
                    name, "fk_orphan", "+".join(fk.columns), orphan,
                    f"{fk.ref_table}에 없는 참조"))
    return v


# ---------------------------------------------------------------- DDL

def ddl(spec: TableSpec, *, dialect: str = "ansi") -> str:
    """스펙에서 SQL DDL을 생성한다 — 스펙이 곧 물리 스키마의 단일 소스."""
    lines = [f"-- {spec.korean} ({spec.name})",
             f"-- 입도: {spec.grain}",
             f"-- 담당 Product: {spec.product or '—'}",
             f"CREATE TABLE {spec.name} ("]
    # (정의문, 주석) 쌍으로 만들고 쉼표를 **정의문 뒤**에 붙인다 — 주석 뒤에
    # 붙이면 줄 끝 주석이 쉼표를 삼켜 유효하지 않은 SQL이 된다.
    body: list[tuple[str, str]] = []
    for c in spec.columns:
        decl = f"    {c.name:24s} {c.sql_type:20s}"
        if not c.nullable:
            decl += "NOT NULL"
        body.append((decl.rstrip(),
                     " · ".join(x for x in (c.korean, c.unit, c.citation) if x)))
    if spec.primary_key:
        body.append((f"    PRIMARY KEY ({', '.join(spec.primary_key)})", ""))
    for fk in spec.foreign_keys:
        body.append((f"    FOREIGN KEY ({', '.join(fk.columns)}) "
                     f"REFERENCES {fk.ref_table} ({', '.join(fk.ref_columns)})", ""))
    rendered = []
    for i, (decl, comment) in enumerate(body):
        sep = "," if i < len(body) - 1 else ""
        rendered.append(decl + sep + (f"    -- {comment}" if comment else ""))
    lines.append("\n".join(rendered))
    lines.append(");")
    # CHECK 제약 — 허용값·범위를 물리 스키마에도 남긴다
    for c in spec.columns:
        if c.allowed is not None and c.dtype in ("string", "text"):
            vals = ", ".join(f"'{x}'" for x in c.allowed)
            lines.append(f"ALTER TABLE {spec.name} ADD CONSTRAINT "
                         f"chk_{spec.name}_{c.name} CHECK ({c.name} IN ({vals}));")
        if c.dtype in ("int", "float") and (c.min_value is not None
                                            or c.max_value is not None):
            conds = []
            if c.min_value is not None:
                conds.append(f"{c.name} >= {c.min_value}")
            if c.max_value is not None:
                conds.append(f"{c.name} <= {c.max_value}")
            lines.append(f"ALTER TABLE {spec.name} ADD CONSTRAINT "
                         f"chk_{spec.name}_{c.name}_rng CHECK ({' AND '.join(conds)});")
    return "\n".join(lines)


def summary_frame(specs: Sequence[TableSpec]) -> pd.DataFrame:
    """카탈로그 요약 — 테이블·입도·컬럼수·PK·FK·담당."""
    return pd.DataFrame([{
        "table": s.name, "korean": s.korean, "grain": s.grain,
        "n_columns": len(s.columns),
        "primary_key": ", ".join(s.primary_key) or "—",
        "foreign_keys": ", ".join(
            f"{'+'.join(f.columns)}→{f.ref_table}" for f in s.foreign_keys) or "—",
        "product": s.product or "—",
    } for s in specs])
