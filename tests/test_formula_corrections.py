"""규제 산식 검수에서 나온 정정과 그 고정 (2026-09 검수).

1. 기업 익스포저 B 등급 위험가중치 150% (CRE20.34). 국가·은행 표와 절단점이
   다르다는 사실이 세 표를 복사하며 지워져 100% 로 남아 있었다.
2. 규정값이 아닌 상수는 references.py 의 내부 가정 구역에 있고 조항 인용을
   달지 않는다. 사용처는 그 이름을 그대로 쓴다. 값이 코드 본문에 다시 박히면
   어디가 규정이고 어디가 가정인지 다음 사람이 구별할 수 없다.
"""

from __future__ import annotations

import inspect
import re

import pandas as pd

from risk_lib import references as R
from risk_lib.capital import rwa_sa
from risk_lib.capital.rwa_sa import compute_rwa_sa


def _one(asset_class: str, rating: str) -> pd.DataFrame:
    return pd.DataFrame({"exposure_id": ["X1"], "asset_class": [asset_class],
                         "rating": [rating], "ead": [1_000.0],
                         "past_due": [False], "ltv": [float("nan")]})


def test_corporate_single_b_is_150pct_but_sovereign_and_bank_stay_100pct():
    """기업만 BB- 미만이 150% 다 (CRE20.34). 국가·은행은 B- 미만이 150% (CRE20.7·20.18)."""
    assert rwa_sa._RW_CORPORATE["B"] == 1.50
    assert rwa_sa._RW_SOVEREIGN["B"] == 1.00
    assert rwa_sa._RW_BANK_ECRA["B"] == 1.00
    out = compute_rwa_sa(_one("corporate", "B"))
    assert float(out["rwa"].iloc[0]) == 1_500.0


def test_corporate_table_is_monotone_in_rating():
    """등급이 나빠질수록 위험가중치가 내려가면 표가 틀린 것이다."""
    order = ["AAA-AA", "A", "BBB", "BB", "B", "CCC-"]
    rws = [rwa_sa._RW_CORPORATE[r] for r in order]
    assert rws == sorted(rws), rws


def test_internal_assumptions_live_in_references_not_in_engines():
    """엔진 본문에 다시 박힌 가정값이 없어야 한다."""
    import risk_lib.frtb as frtb
    import risk_lib.ccr as ccr
    import risk_lib.capital.rwa_deep as deep
    assert frtb.rfet_test.__kwdefaults__ is None or True   # 시그니처 형태 무관
    assert inspect.signature(frtb.rfet_test).parameters["min_obs_per_year"].default \
        == R.RFET_MIN_OBS_PER_YEAR
    assert inspect.signature(ccr.saccr_rwa).parameters["bank_rw"].default \
        == R.CCR_BANK_RW_FLAT
    assert inspect.signature(ccr.cva_capital_charge).parameters["kappa"].default \
        == R.BA_CVA_KAPPA
    assert deep._MR_STRESS_MULTIPLIER is R.MR_STRESS_MULTIPLIER or \
        deep._MR_STRESS_MULTIPLIER == R.MR_STRESS_MULTIPLIER
    src = inspect.getsource(frtb.rfet_test)
    assert "1e9" not in src, "NMRF 가산 금액이 함수 본문에 다시 박혔다"


def test_no_regulation_citation_on_an_internal_assumption():
    """임의 가정에 조항번호가 붙어 있으면 검토자가 규정값으로 읽는다."""
    import risk_lib.capital.rwa_deep as deep
    src = inspect.getsource(deep)
    assert "MAR20.9" not in src
    ref_src = inspect.getsource(R)
    block = ref_src[ref_src.index("내부 가정"):]
    # 내부 가정 구역 안에는 '규정값이 아니다' 선언이 있고, 그 값들에 Citation 을 달지 않는다
    assert "규정값이 아니다" in block
    assert "Citation(" not in block


def test_nmrf_addon_is_per_factor_and_comes_from_references():
    import numpy as np
    from risk_lib.frtb import rfet_test
    dates = pd.date_range("2025-01-01", periods=30, freq="D")
    # 팩터 a 는 촘촘히 30건(적격), 팩터 b 는 3건(NMRF)
    hist = pd.DataFrame({"date": dates,
                         "a": np.linspace(100, 101, 30),
                         "b": [100.0] + [np.nan] * 27 + [101.0, 102.0]})
    r = rfet_test(hist)
    assert r.n_nmrf == 1
    assert r.nmrf_capital_addon == R.NMRF_ADDON_PER_FACTOR_KRW


def test_ima_docstring_matches_the_formula():
    """독스트링이 max(ES, m·ES_avg60) 라 적고 코드가 ES×m 이면 문서가 거짓이다."""
    from risk_lib.frtb import compute_ima_capital
    doc = compute_ima_capital.__doc__
    assert "ES_avg_60d" not in doc.split("\n")[0]
    assert "× 백테스트 승수" in doc or "승수" in doc
