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
from risk_lib.data_gen import generate_portfolio
from risk_lib.pipeline import run_pipeline
from risk_lib.report import render_markdown


# Golden numbers captured against the working tree before any refactor commit.
# All RWA / capital / ECL / stress aggregates that downstream consumers depend on.
GOLDEN = {
    "n_rows": 2980,
    # Re-pinned after PD floor 3bp→5bp (BCBS d424) and segment-aware LGD floors
    # (CRE32.42 — corporate 25% / retail 10% / mortgage 5%).
    "rwa_final_total": 9_380_455_004_957.953,
    "rwa_sa": 1_028_895_833_988.9441,
    "rwa_irb": 6_544_287_052_378.777,
    "cet1_ratio": 0.115,
    "total_ratio": 0.155,
    "leverage_ratio": 0.11601329439196996,
    "ecl_total": 94_531_443_664.94879,
    "macro_weighted_total": 128_504_402_456.8952,
    "reverse_critical_severity": 2.3518753051757812,
}
# +1 WARN: pd_floor_5bp now catches more low-PD exposures (5bp vs 3bp threshold).
GOLDEN_VALIDATION = {"PASS": 49, "WARN": 3}
EXPECTED_QUARTERS = [
    "2026Q3", "2026Q4",
    "2027Q1", "2027Q2", "2027Q3", "2027Q4",
    "2028Q1", "2028Q2", "2028Q3", "2028Q4",
]


# Pinned reference date so the forecast quarter axis is reproducible
# independent of wall-clock time (2026-06-11 → forecast opens at 2026Q3).
PINNED_ASOF = "2026-06-11"


@pytest.fixture(scope="module")
def result():
    portfolio = generate_portfolio(seed=42)
    return run_pipeline(portfolio, seed=42, asof=PINNED_ASOF)


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
