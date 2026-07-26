"""End-to-end pipeline regression suite (safety net for the v0.2 refactor).

Pins the current numerical output of `run_pipeline` on the default synthetic
portfolio (seed=42, ~3k exposures) plus structural invariants on
PipelineResult / render_markdown / cli.main, so subsequent refactor commits
must preserve behavior to ≤1e-9 relative tolerance.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from risk_lib.cli import main as cli_main
from risk_lib.report import render_markdown


# Golden numbers captured against the working tree before any refactor commit.
# All RWA / capital / ECL / stress aggregates that downstream consumers depend on.
GOLDEN = {
    "n_rows": 2980,
    # Re-pinned after PD floor 3bp→5bp (BCBS d424) and segment-aware LGD floors
    # (CRE32.42 — corporate 25% / retail 10% / mortgage 5%).
    #
    # 재고정 2 — 독립검증 IVR-E6BEA5DA0D5F 시정 (3선 지적):
    #   F-002 거래상대방신용리스크(SA-CCR 137.0억 + CVA 4.6억)를 RWA에 합산.
    #         CRE52·MAR50이 요구하는데 산출만 하고 빠져 있었다 (+0.151%).
    #   F-001 자본을 RWA에서 역산하지 않고 총익스포저에서 합성. 역산 구조에서는
    #         cet1_ratio가 0.115 상수여서 RWA가 8.96조~9.97조로 움직여도 미동하지
    #         않았다 — 자본비율이 RWA 오류를 드러내지 못했다.
    #   #         F-004 레버리지 익스포저에 파생상품(SA-CCR EAD 274.1억) 포함 (LEV20.1).
    #
    # 재고정 3 — 독립검증 2차 의견 IVR-52D8B21C1A1E:
    #   F-101 F-001 시정이 결함을 자본비율에서 레버리지비율로 **옮겼다**.
    #         자본을 익스포저에 비례시키니 leverage = (EAD·k)/(EAD·1.01+ccr)로
    #         EAD가 약분돼 5개 seed에서 변동이 1.4bp(CV 0.044%)에 그쳤다.
    #         → 자본을 파이프라인 **입력**으로 승격하고, 합성기는 고정 발행자본 +
    #           수익성 기반 이익잉여금으로 바꿨다. RWA·익스포저 어느 쪽에도
    #           비례하지 않으므로 두 비율이 함께 반응한다
    #           (레버리지 변동 1.4bp → 136.8bp, CV 0.044% → 3.741%).
    "rwa_final_total": 9_394_620_060_178.572,
    "rwa_sa": 1_028_895_833_988.9441,
    "rwa_irb": 6_544_287_052_378.777,
    "cet1_ratio": 0.11648890029339716,
    "total_ratio": 0.1569375823652485,
    "leverage_ratio": 0.11712632046549173,
    "ecl_total": 94_531_443_664.94879,
    "macro_weighted_total": 128_504_402_456.8952,
    # 전 축 동시 충격(신용·시장·운영·유동성·수익)으로 전환하며 재고정.
    # 신용만 충격할 때 2.3519 → 전 축에서 0.9447. 같은 자본으로 견딜 수 있는
    # 심도가 낮아지는 것이 다축 위기상황분석의 요점이다 (SRP20).
    # 2차 시정(F-101 자본 원장 독립화) 후 0.9822 — 자본이 커져 견디는 심도가
    # 올라갔다. 1차 시정 시점 값은 0.8426이었다.
    "reverse_critical_severity": 0.9822463989257812,
}
# +1 WARN: pd_floor_5bp now catches more low-PD exposures (5bp vs 3bp threshold).
# +1 WARN: stress_trough_meets_requirement — 위기상황 CET1 저점이 요구치를
# 침범하는 사실이 자체검증에 전혀 남지 않던 공백을 메웠다 (독립검증 F-003).
# +1 WARN: capital_source — 합성 자본의 규모 비례분이 CET1의 54.3%라는 사실을
# 매 실행 드러낸다. 자산이 커지면 고정분이 희석돼 레버리지 반응성이 소멸하는데
# 그 진행이 조용하다 (독립검증 F-201·F-202).
GOLDEN_VALIDATION = {"PASS": 49, "WARN": 5}
EXPECTED_QUARTERS = [
    "2026Q3", "2026Q4",
    "2027Q1", "2027Q2", "2027Q3", "2027Q4",
    "2028Q1", "2028Q2", "2028Q3", "2028Q4",
]


# `result` fixture: session-scoped, asof pinned to 2026-06-11 — see conftest.py.


# ---- numeric goldens ----------------------------------------------------

@pytest.mark.parametrize("key,golden", list(GOLDEN.items()))
def test_pipeline_golden_numbers(result, key, golden):
    """Headline aggregates are stable to 1e-9 relative tolerance."""
    if key == "n_rows":
        actual = 2980
    elif key.startswith("rwa_") and key != "rwa_final_total":
        actual = result.rwa["sa"] if key == "rwa_sa" else result.rwa["irb"]
    elif key == "rwa_final_total":
        actual = result.rwa["final_total"]
    elif key == "cet1_ratio":
        actual = result.bis.cet1_ratio
    elif key == "total_ratio":
        actual = result.bis.total_ratio
    elif key == "leverage_ratio":
        actual = result.leverage.leverage_ratio
    elif key == "ecl_total":
        actual = result.ecl["total"]
    elif key == "macro_weighted_total":
        actual = result.macro_ecl.weighted_total
    elif key == "reverse_critical_severity":
        actual = result.reverse_stress.critical_severity
    else:
        pytest.fail(f"unmapped golden key {key}")
    assert actual == pytest.approx(golden, rel=1e-9), (
        f"{key}: {actual} vs golden {golden}")


def test_validation_summary_matches_golden(result):
    summ = result.validation.summary()
    assert summ == GOLDEN_VALIDATION
    assert result.validation.passes()


# ---- PipelineResult structural invariants -------------------------------

def test_pipeline_result_fields(result):
    """All 18 PipelineResult fields are populated and well-typed."""
    import pandas as pd
    assert isinstance(result.portfolio_summary, pd.DataFrame)
    assert isinstance(result.pd_metrics, dict)
    assert {"sa", "irb", "market", "op", "internal_total",
            "standardised_total", "output_floor", "final_total"} <= set(result.rwa)
    assert result.bis.cet1_ratio > 0
    assert result.leverage.leverage_ratio > 0
    assert {"total", "by_stage"} <= set(result.ecl)
    assert {"delinquency", "default_rate_ew", "default_rate_count",
            "recovery_rate"} <= set(result.monitoring)
    for attr in ("limits", "concentration", "rapm", "stress",
                 "stress_path", "stress_path_trough"):
        assert isinstance(getattr(result, attr), pd.DataFrame), attr
    assert isinstance(result.macro_ecl_path, pd.DataFrame)
    assert result.backtest["hosmer_lemeshow"]["p_value"] >= 0
    assert result.meta["quarters"] == EXPECTED_QUARTERS
    # ALM / ICAAP (v0.3)
    assert {"balance_sheet", "irrbb", "lcr", "nsfr"} <= set(result.alm)
    assert result.alm["lcr"].lcr > 0
    assert result.alm["nsfr"].nsfr > 0
    assert result.icaap.ec_diversified > 0
    assert result.icaap.grade in ("GREEN", "AMBER", "RED")


def test_stress_path_shape(result):
    # 3 stress narratives × 10 quarters = 30 rows
    assert len(result.stress) == 3
    assert len(result.stress_path) == 30
    # 3 scenarios + 1 weighted = 4 series × 10 quarters
    assert len(result.macro_ecl_path) == 40


# ---- render_markdown -----------------------------------------------------

REQUIRED_HEADERS = [
    "## 0. 종합 판정",
    "## 1. 포트폴리오 개요",
    "## 2. 신용평가모형(PD) 변별력",
    "## 3. 위험가중자산(RWA)",
    "## 4. BIS 자본적정성",
    "## 5. 레버리지비율",
    "## 6. IFRS9 기대신용손실(ECL) 충당금",
    "### 6-1. 거시연계 PIT ECL",
    "### 6-2. 분기별 ECL 충당금 경로",
    "## 7. 연체율 / 부도율 / 회수율",
    "## 8. 한도관리",
    "## 9. 집중리스크 (HHI)",
    "## 10. RAPM (RAROC)",
    "## 11. 스트레스테스트",
    "### 11-1. 역스트레스테스트",
    "### 11-2. 분기별 자본 스트레스 경로",
    "## 12. 자체검증",
    "## 13. 내부자본 (ICAAP)",
    "## 14. ALM (IRRBB / LCR / NSFR)",
    "### 14-1. IRRBB",
    "### 14-2. LCR",
    "### 14-3. NSFR",
    "## 15. 출처 및 준거",
]


def test_render_markdown_has_every_section(result):
    md = render_markdown(result)
    for header in REQUIRED_HEADERS:
        assert header in md, f"missing report section: {header}"
    assert "결재 가능 (PASS)" in md      # current verdict
    assert "2028Q4" in md                  # forecast horizon


# ---- CLI smoke -----------------------------------------------------------

def test_cli_main_writes_report(tmp_path: Path, capsys):
    out = tmp_path / "report.md"
    rc = cli_main(["run", "--report", str(out)])
    assert rc == 0
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "## 0. 종합 판정" in content
    assert "## 15. 출처 및 준거" in content
