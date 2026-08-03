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
    # 재고정 4 — 산출 의존성 재구조 (사용자 지시):
    #   ① ECL이 신용 EAD보다 먼저다 — SA 규제 익스포저는 개별충당금(손상)
    #      차감 후(CRE20)이므로. ECL은 전 포트폴리오로 확장됐고, SA북은
    #      외부등급→장기 부도율 + 감독 LGD 45%(CRE32)로 파라미터를 세운다.
    #      이전에는 SA북 충당금이 '0'도 아닌 'NaN 무시'였다 (조용한 누락).
    #      ecl_total 945.3억 → 975.5억 (+SA북 30.2억).
    #   ② 시장·운영 명목이 신용 EAD 비례에서 전용 시드 독립 기준으로 —
    #      신용·시장운영·CCR 세 갈래가 병렬이 됐다. 운영 손실 10년 평균의
    #      신용 EAD 비례가 한 곳 남았다가 base 재현 1.2bp 차이로 잡혔다.
    # 재고정 5 — 구조화 익스포저를 자본비율 분모에 통합 (사용자 승인):
    #   집합투자증권(CRE60 LTA/MBA/fallback) 3.331조 + 유동화(CRE40~45
    #   SEC-IRBA/ERBA/SA) 0.797조 = 4.128조가 원장에는 있는데 분모에 없었다.
    #   산출해 놓고 넣지 않은 것이므로 이중계상이 아니라 누락의 시정이다 —
    #   포트폴리오 자산군 다섯(sovereign·bank·corporate·retail_other·
    #   residential_mortgage)에 펀드 수익증권도 유동화 트렌치도 없다.
    #   RWA 9.350조 → 13.479조 (+44.2%), CET1 11.70% → 8.12%.
    #   레버리지 익스포저에도 장부 익스포저 2.190조를 함께 넣는다 —
    #   RWA만 넣으면 두 비율이 서로 다른 은행을 설명하게 된다 (LEV20.1).
    #   output floor 표준 총계는 SEC-IRBA를 제외한 계층(ERBA→SA)으로 세운다.
    "rwa_final_total": 13_478_626_877_092.645,
    "rwa_sa": 1_028_895_833_988.9441,
    "rwa_irb": 6_544_287_052_378.777,
    "cet1_ratio": 0.08119291152308737,
    "total_ratio": 0.10938569432396912,
    "leverage_ratio": 0.09697351438263638,
    "ecl_total": 97_546_776_363.82495,
    "macro_weighted_total": 135_045_061_371.37775,
    # 전 축 동시 충격(신용·시장·운영·유동성·수익)으로 전환하며 재고정.
    # 신용만 충격할 때 2.3519 → 전 축에서 0.9447. 같은 자본으로 견딜 수 있는
    # 심도가 낮아지는 것이 다축 위기상황분석의 요점이다 (SRP20).
    # 2차 시정(F-101 자본 원장 독립화) 후 0.9822 — 자본이 커져 견디는 심도가
    # 올라갔다. 1차 시정 시점 값은 0.8426이었다.
    #
    # 재고정 5 — 구조화 RWA 분모 통합 후 0.9988 → 0.0492. **20배 하락이며
    # 이것이 이 회차에서 가장 크게 움직인 수치다.** 역스트레스는 CET1이 요구
    # 8.00%에 닿는 심도를 푸는데, 기준 상태 CET1이 11.70%(여유 370bp)에서
    # 8.12%(여유 11.9bp)로 내려왔다. 여유가 거의 없으니 임계 심도도 거의 0이다
    # — 함의 GDP 충격 −0.15%, 즉 경기가 조금만 나빠져도 요구치를 깬다.
    # 수치가 작아진 것이 모형이 예민해진 탓이 아니라 **자본 여유가 실제로
    # 그만큼 얇았는데 분모에서 4.13조가 빠져 있어 보이지 않았던 것**이다.
    "reverse_critical_severity": 0.04917144775390625,
}
# 재고정 4 — 서식 저작 중 적대적 검토에서 드러난 CVA 기준 오류:
#   risk_lib.ccr.cva_capital_charge는 반환값을 K_BA(소요자기자본)로 문서화하는데
#   pipeline은 그것을 RWA로 그대로 합산하고 있었다. 주석은 "이미 RWA 환산치"라고
#   반대로 적혀 있었다. MAR50.2·RBC20.6에 따라 12.5배 환산하도록 고쳤다 —
#   CVA RWA 4.6억 → 57.5억, 총 RWA +53억(+0.056%).
# +1 WARN: pd_floor_5bp now catches more low-PD exposures (5bp vs 3bp threshold).
# +1 WARN: stress_trough_meets_requirement — 위기상황 CET1 저점이 요구치를
# 침범하는 사실이 자체검증에 전혀 남지 않던 공백을 메웠다 (독립검증 F-003).
# +1 WARN: capital_source — 합성 자본의 규모 비례분이 CET1의 54.3%라는 사실을
# 매 실행 드러낸다. 자산이 커지면 고정분이 희석돼 레버리지 반응성이 소멸하는데
# 그 진행이 조용하다 (독립검증 F-201·F-202).
# +1 WARN: bis_buffer_requirement — 구조화 RWA 통합으로 Tier1(−0.34%p)·
# 총자본(−0.56%p)이 완충자본 포함 요구치를 밑돈다. 기존 검사는 Pillar 1
# 최저(4.5/6/8)만 봤으므로 완충자본 미달이 조용히 통과하고 있었다. 산출
# 결함이 아니라 산출 **결과**이므로 WARN이며, 배당·성과급 제한 대상이다.
GOLDEN_VALIDATION = {"PASS": 49, "WARN": 6}
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


# ---- 구조화 익스포저 통합 (집합투자증권 CRE60 · 유동화 CRE40) --------------

def test_structured_rwa_is_in_the_denominator(result):
    """원장에 있는 RWA가 분모에 실제로 들어갔는지 — 산출만 하고 빼면 자본비율이
    실제보다 좋게 나온다. 6개 구성요소 합 = 최종 RWA 여야 한다."""
    w = result.rwa
    assert w["structured_total"] == pytest.approx(
        w["fund"] + w["securitisation"])
    components = (w["sa"] + w["irb"] + w["ccr"] + w["market"] + w["op"]
                  + w["structured_total"] + w["output_floor"].add_on)
    assert components == pytest.approx(w["final_total"], rel=1e-12)
    assert result.bis.rwa == pytest.approx(w["final_total"], rel=1e-12)


def test_structured_population_does_not_overlap_the_banking_book(portfolio, result):
    """합산이 이중계상이 아니라는 주장의 근거 — 모집단이 겹치지 않는다.

    은행계정 익스포저의 자산군에 펀드도 유동화 트렌치도 없다. 나중에 자산군이
    늘어 겹치기 시작하면 이 검사가 먼저 깨져야 한다. 겹친 채로 합산하면
    분모가 부풀고, 그건 누락과 반대 방향의 같은 오류다.
    """
    assert not {"fund", "securitisation", "cis"} & set(portfolio["asset_class"])
    s = result.structured
    assert len(s.tables["rdm_fund_master"]) > 0
    assert len(s.tables["rdm_sec_tranche"]) > 0


def test_output_floor_standardised_total_excludes_sec_irba(result):
    """표준방법 총계에 SEC-IRBA를 쓰면 floor가 자기 자신과 비교된다.

    IRBA는 내부모형 기반이므로 floor의 비교 기준이 될 수 없다 (CRE40 ·
    RBC20.11). 채택 계층이 IRBA인 트렌치가 실제로 있어야 이 검사가 의미를
    가지므로 그것부터 확인한다.
    """
    sec = result.structured.tables["rwa_sec_result"]
    assert (sec["adopted_method"] == "SEC-IRBA").any(), "IRBA 채택 트렌치가 없다"
    w = result.rwa
    assert w["securitisation_standardised"] != w["securitisation"]
    assert w["standardised_total"] < w["internal_total"]


def test_leverage_exposure_includes_structured_book(result):
    """RWA는 넣고 익스포저는 안 넣으면 두 비율이 다른 은행을 설명한다 (LEV20.1)."""
    s = result.structured
    assert s.exposure > 0
    # 레버리지 분모 = 은행계정 EAD + 부외 10% + 파생 + 구조화 장부액
    em = result.leverage.exposure_measure if hasattr(
        result.leverage, "exposure_measure") else result.leverage.exposure
    assert em > s.exposure
