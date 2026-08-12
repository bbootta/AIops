"""Maximum Distributable Amount (MDA) — buffer breach restrictions.

Basel III RBC30 / 감독세칙 자본보전버퍼: 자본보전버퍼 구간을 침범하면 4분위
(quartile)별로 배당·자기자본·성과보수·AT1 쿠폰의 상한이 적용된다.

이 모듈은 현 CET1이 어느 quartile에 있는지, 가용 MDA 금액과 비율을 산출.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from risk_lib.references import BIS_MIN_CET1


# RBC30.5 분배제한 비율 — Combined Buffer Requirement(CBR) 침범 시
# 사분위별 직전기 분배가능이익의 보유율(retention ratio).
# 사분위 = (CBR - shortfall) ÷ CBR/4
_MDA_RETENTION = {
    1: 1.00,    # 1분위(가장 깊은 침범) → 100% 보유 (분배 0%)
    2: 0.80,
    3: 0.60,
    4: 0.40,    # 4분위(가장 얕은 침범) → 40% 보유 (분배 60%)
}


@dataclass
class MDAResult:
    cet1_ratio: float
    cet1_amount: float
    cbr_total: float            # combined buffer requirement (CCB+CCyB+DSIB)
    buffer_shortfall: float     # 0 if no breach
    buffer_quartile: int        # 0 = no breach; 1~4 = quartile of breach
    retention_ratio: float      # required retention of distributable earnings
    distributable_pct: float    # 1 - retention_ratio
    excess_above_cbr: float     # KRW excess above the full CBR

    @property
    def in_breach(self) -> bool:
        return self.buffer_quartile > 0


def compute_mda(cet1_ratio: float, cet1_amount: float, rwa: float,
                *, buffers: dict[str, float] | None = None) -> MDAResult:
    """Compute MDA constraint for current CET1.

    Combined Buffer Requirement (CBR) = CCB(2.5%) + CCyB + DSIB.
    If CET1 ratio is at or above (4.5% + CBR), no constraint.
    Otherwise distance into the buffer determines the quartile and the
    required retention of distributable earnings.
    """
    if buffers is None:
        buffers = {"capital_conservation": 0.025, "countercyclical": 0.0, "dsib": 0.01}
    cbr = sum(buffers.values())
    cbr_top = BIS_MIN_CET1 + cbr    # top of combined buffer
    excess = (cet1_ratio - cbr_top) * rwa

    if cet1_ratio >= cbr_top:
        return MDAResult(cet1_ratio=cet1_ratio, cet1_amount=cet1_amount,
                         cbr_total=cbr, buffer_shortfall=0.0,
                         buffer_quartile=0, retention_ratio=0.0,
                         distributable_pct=1.0, excess_above_cbr=excess)

    if cet1_ratio < BIS_MIN_CET1:
        # below 4.5% Pillar 1 minimum → 100% retention, also outside CBR
        return MDAResult(cet1_ratio=cet1_ratio, cet1_amount=cet1_amount,
                         cbr_total=cbr,
                         buffer_shortfall=(cbr_top - cet1_ratio) * rwa,
                         buffer_quartile=1, retention_ratio=1.0,
                         distributable_pct=0.0, excess_above_cbr=excess)

    # In the buffer zone — split into 4 quartiles.
    shortfall_pct = cbr_top - cet1_ratio
    quartile_width = cbr / 4
    quartile_from_bottom = min(4, max(1, int(shortfall_pct / quartile_width) + 1))
    # convert "depth into buffer" to RBC30.5 quartile index (1 = deepest)
    q = 5 - quartile_from_bottom
    retention = _MDA_RETENTION[q]
    return MDAResult(
        cet1_ratio=cet1_ratio, cet1_amount=cet1_amount, cbr_total=cbr,
        buffer_shortfall=shortfall_pct * rwa,
        buffer_quartile=q, retention_ratio=retention,
        distributable_pct=1 - retention, excess_above_cbr=excess,
    )


def mda_ladder(cet1_amount: float, rwa: float,
               *, buffers: dict[str, float] | None = None,
               step: float = 0.005) -> pd.DataFrame:
    """Show the MDA constraint at a range of CET1 ratios above/below current."""
    if buffers is None:
        buffers = {"capital_conservation": 0.025, "countercyclical": 0.0, "dsib": 0.01}
    cbr = sum(buffers.values())
    base = cet1_amount / rwa if rwa else 0.0
    cet1_grid = [round(BIS_MIN_CET1 + cbr - 0.04 + i * step, 4)
                 for i in range(int(0.10 / step) + 1)]
    rows = []
    for r in cet1_grid:
        cap = r * rwa
        m = compute_mda(r, cap, rwa, buffers=buffers)
        rows.append({
            "cet1_ratio": r,
            "buffer_quartile": m.buffer_quartile,
            "retention_ratio": m.retention_ratio,
            "distributable_pct": m.distributable_pct,
            "in_breach": m.in_breach,
            "is_current": abs(r - base) < step / 2,
        })
    return pd.DataFrame(rows)
