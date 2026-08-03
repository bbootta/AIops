"""평면 포트폴리오 → 정규 테이블 분해 (RDM-002 · RDM-003).

카탈로그가 문서로만 있으면 스펙과 실제 데이터가 갈라진다. 이 모듈은 하니스의
합성 포트폴리오를 정규 테이블로 실제 분해하고, 그 결과가 스펙 검증을 통과하는지
테스트로 고정한다 — 스펙이 살아 있는 계약이 되게 하는 장치다.
"""

from __future__ import annotations

import hashlib
from datetime import date

import numpy as np
import pandas as pd

from risk_lib.datamodel import catalog as cat
from risk_lib.datamodel.spec import TableSpec, Violation, validate, check_refs

# 담보 종류 배정 — 자산군별 관행. 결정론적으로만 배정한다.
_COLL_BY_CLASS = {
    "residential_mortgage": "real_estate",
    "corporate": "corporate_bond_ig",
    "retail_other": "cash",
    "bank": "sovereign_aaa_gt1y",
    "sovereign": "sovereign_aaa_le1y",
}
_HAIRCUT = {"cash": 0.00, "gold": 0.15, "sovereign_aaa_le1y": 0.005,
            "sovereign_aaa_gt1y": 0.04, "corporate_bond_ig": 0.06,
            "equity_main_index": 0.20, "real_estate": 0.25}


def _fingerprint(df: pd.DataFrame) -> str:
    h = hashlib.sha256()
    h.update(",".join(map(str, df.columns)).encode())
    for row in df.itertuples(index=False):
        h.update("|".join(f"{v:.12g}" if isinstance(v, (float, np.floating))
                          else str(v) for v in row).encode())
    return h.hexdigest()


def decompose(portfolio: pd.DataFrame, *, asof: str,
              seed: int = 42) -> dict[str, pd.DataFrame]:
    """평면 포트폴리오를 RDM 정규 테이블 dict로 분해한다."""
    rng = np.random.default_rng(seed + 31337)
    p = portfolio.copy()

    # ---- 차주 원장 (익스포저에서 유일 차주 추출) ----
    obligor = (p[["obligor_id", "asset_class", "sector", "country"]]
               .drop_duplicates(subset=["obligor_id"])
               .reset_index(drop=True))
    # 그룹 차주: 기업은 상위 그룹으로 묶고, 나머지는 자기 자신
    obligor["group_id"] = np.where(
        obligor["asset_class"] == "corporate",
        "GRP_" + obligor["obligor_id"].str.extract(r"(\d+)")[0].fillna("0")
        .astype(int).floordiv(10).astype(str).str.zfill(4),
        obligor["obligor_id"])

    # ---- 익스포저 원장 ----
    n = len(p)
    ccf_pool = np.array(cat.CCF_TYPES)
    has_commit = rng.random(n) < 0.35
    drawn = p["balance"].to_numpy(dtype=float)
    undrawn = np.where(has_commit, drawn * rng.uniform(0.1, 0.6, n), 0.0)
    exposure = pd.DataFrame({
        "exposure_id": p["exposure_id"],
        "obligor_id": p["obligor_id"],
        "asset_class": p["asset_class"],
        "balance": drawn,
        "drawn": drawn,
        "undrawn": undrawn,
        "ccf_type": np.where(has_commit, rng.choice(ccf_pool, n), None),
        "ead": p["ead"].to_numpy(dtype=float),
        "maturity": p["maturity"].to_numpy(dtype=float),
        "ltv": p["ltv"].to_numpy(dtype=float) if "ltv" in p else np.nan,
        "rating": p["rating"] if "rating" in p else None,
    })
    # 계정·상품 코드 — 익스포저는 원장 계정에 앉고 상품 인스턴스다. 코드가
    # 없으면 "이 익스포저가 어느 계정인가"에 답할 수 없고, 계정 단위 집계는
    # 자산군으로 대신 세다가 중복 계상된다 (사용자 지적).
    from risk_lib.datamodel.code_scope import EXPOSURE_CODES
    _codes = exposure["asset_class"].map(EXPOSURE_CODES)
    exposure["account_code"] = [c[0] if isinstance(c, tuple) else None
                                for c in _codes]
    exposure["product_code"] = [c[1] if isinstance(c, tuple) else None
                                for c in _codes]
    assert exposure["account_code"].notna().all(), (
        "코드 미매핑 익스포저 — 매핑 없는 자산군은 모든 계정 집계에서 조용히 빠진다")

    # ---- 담보 원장 (담보부 익스포저만) ----
    secured = p[p["asset_class"].isin(
        ["residential_mortgage", "corporate", "retail_other"])].copy()
    ctype = secured["asset_class"].map(_COLL_BY_CLASS)
    coll = pd.DataFrame({
        "collateral_id": "COL_" + secured["exposure_id"].astype(str),
        "exposure_id": secured["exposure_id"],
        "collateral_type": ctype,
        "market_value": secured["ead"].to_numpy(dtype=float)
        * rng.uniform(0.3, 0.9, len(secured)),
        "haircut": ctype.map(_HAIRCUT).astype(float),
        "seniority": 1,
    }).reset_index(drop=True)

    # ---- 연체·건전성 스냅샷 ----
    delinq = pd.DataFrame({
        "exposure_id": p["exposure_id"],
        "asof": asof,
        "dpd": p["dpd"].to_numpy(dtype=int),
        "past_due": p["past_due"].to_numpy(dtype=bool),
        "default_flag": (p["dpd"].to_numpy(dtype=int) >= 90).astype(int),
    })

    tables = {"rdm_obligor": obligor, "rdm_exposure": exposure,
              "rdm_collateral": coll, "rdm_delinquency": delinq}

    # ---- 스냅샷 원장 (분해 결과 자체의 출처 기록) ----
    tables["rdm_snapshot"] = pd.DataFrame([{
        "snapshot_id": f"SNAP_{name}_{asof}",
        "source_system": "synthetic",
        "table_name": name,
        "asof": asof,
        "row_count": int(len(df)),
        "fingerprint": _fingerprint(df),
    } for name, df in tables.items()])
    return tables


def validate_all(tables: dict[str, pd.DataFrame], *,
                 specs: tuple[TableSpec, ...] = cat.ALL_TABLES
                 ) -> list[Violation]:
    """모든 테이블을 스펙과 대조하고 참조무결성까지 검사한다."""
    spec_map = {s.name: s for s in specs}
    out: list[Violation] = []
    for name, df in tables.items():
        if name in spec_map:
            out.extend(validate(df, spec_map[name]))
    out.extend(check_refs(tables, {k: v for k, v in spec_map.items()
                                   if k in tables}))
    return out


def dq_result_frame(violations: list[Violation], *, asof: str) -> pd.DataFrame:
    """검증 결과를 rdm_dq_result 스펙 형태로 — 통과 이력도 저장돼야 증명이 된다."""
    if not violations:
        # 빈 프레임도 스펙 dtype을 지켜야 한다 — object로 두면 위반 0건일 때만
        # 스키마 검증이 실패하는, 가장 헷갈리는 형태의 오류가 된다.
        return pd.DataFrame({
            "asof": pd.Series(dtype="object"),
            "table_name": pd.Series(dtype="object"),
            "column_name": pd.Series(dtype="object"),
            "rule": pd.Series(dtype="object"),
            "severity": pd.Series(dtype="object"),
            "n_rows": pd.Series(dtype="int64"),
            "detail": pd.Series(dtype="object"),
        })
    return pd.DataFrame([{
        "asof": asof, "table_name": v.table,
        "column_name": v.column or None, "rule": v.rule,
        "severity": v.severity, "n_rows": int(v.n_rows), "detail": v.detail,
    } for v in violations])


def decompose_from_result(result, portfolio: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return decompose(portfolio, asof=result.meta.get("asof",
                                                     date.today().isoformat()),
                     seed=result.meta.get("seed", 42))
