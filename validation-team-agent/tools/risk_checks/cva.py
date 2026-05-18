"""CVA (MAR50) 점검.

BA-CVA 산식 정합성 + SA-CVA 의무 여부. SA-CVA 자체 산정은 본 모듈 밖.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Mapping, Sequence

_THRESHOLDS_PATH = (
    Path(__file__).resolve().parent.parent.parent / "harness" / "cva_thresholds.json"
)


def load_thresholds(path: Path | None = None) -> dict:
    p = path or _THRESHOLDS_PATH
    return json.loads(p.read_text(encoding="utf-8"))


def compute_ba_cva(
    counterparty_inputs: Sequence[Mapping],
    *,
    thresholds: Mapping | None = None,
) -> dict:
    """BA-CVA 단순 식 (감독원 표준):

        BA-CVA = α × sqrt( (ρ × Σ SCVA_c)² + (1-ρ²) × Σ SCVA_c² )

    counterparty_inputs 의 각 항목은 {"name", "scva"} 키.
    SCVA_c 산정 자체는 호출자 책임 (RW × M_eff × EAD × discount).
    """
    th = thresholds or load_thresholds()
    rho = float(th["rho_correlation"])
    alpha = float(th["alpha_ba_cva"])
    if not counterparty_inputs:
        raise ValueError("counterparty_inputs must not be empty")
    scvas = []
    for c in counterparty_inputs:
        if "scva" not in c:
            raise KeyError(f"counterparty missing 'scva' key: {c}")
        if c["scva"] < 0:
            raise ValueError(f"scva must be >= 0 for {c.get('name')}")
        scvas.append(float(c["scva"]))
    sum_s = sum(scvas)
    sum_s2 = sum(s * s for s in scvas)
    ba_cva = alpha * math.sqrt((rho * sum_s) ** 2 + (1 - rho * rho) * sum_s2)
    return {
        "ba_cva": ba_cva,
        "alpha": alpha,
        "rho": rho,
        "n_counterparties": len(scvas),
        "sum_scva": sum_s,
    }


def check_sa_cva_required(
    trading_book_size_eur_bn: float,
    *,
    thresholds: Mapping | None = None,
) -> dict:
    """대규모 트레이딩북 SA-CVA 의무 여부."""
    th = thresholds or load_thresholds()
    threshold = float(th["sa_cva_required_for_large_books_eur_bn"])
    return {
        "trading_book_eur_bn": trading_book_size_eur_bn,
        "threshold": threshold,
        "sa_cva_required": trading_book_size_eur_bn >= threshold,
    }
