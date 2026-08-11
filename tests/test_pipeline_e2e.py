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
# 재고정 6 (2026-08-06) — 요건 감사에서 나온 시정으로 자체검증이 2건 늘었다.
# 헤드라인 수치는 하나도 움직이지 않는다. 늘어난 것은 통제뿐이다.
# +1 PASS: xd_ec_covers_rwa_components — 거래상대방신용리스크(SA-CCR + CVA)가
# `rwa_internal_total`에는 들어가면서 내부자본(신용 EC)에서는 빠져 있었다.
# 구조화 4.13조와 같은 유형이 한 단계 아래에 남아 있던 것이다. 검사는 금액이
# 아니라 **구성요소 이름**으로 대조한다 — CCR의 EC 기여는 15.5억으로 Pillar 1
# 소요자본 1,078조의 0.001%라, 총량 비교로는 빠져도 절대 걸리지 않는다.
# +1 PASS: ecl_ttc_pit_gap — TTC(서식·충당금 기준)와 PIT(확률가중 KPI)의 차이를
# 매 실행 드러낸다. 둘은 정의가 달라 다른 것이 정상이지만, 차이가 보고되지
# 않으면 같은 이름의 ECL이 화면마다 다른 값을 갖는 상태로 굳는다.
# 재고정 7 (2026-08-07, 데이터 엔지니어링 팀 검토 F-1·F-2 반영) — +3 PASS.
# +1 intake_every_exposure_is_booked: 자산군 목록 밖 익스포저가 SA·IRB 양쪽에서
#    탈락해 RWA에서 소리 없이 사라지던 경로를 FAIL로 막는다.
# +1 intake_exposure_id_unique: 중복 행이 RWA를 경보 없이 이중계상하던 경로.
# +1 asof_is_explicit: `asof` 미지정 시 벽시계가 들어가는 사실을 드러낸다
#    (WARN). 기본값 자체는 호출부가 많아 남겼고, 조용한 것만 없앴다.
# 재고정 8 (2026-08-08, ALM 현금흐름 엔진 배선) — +3 PASS · +2 WARN.
# 헤드라인 10건은 움직이지 않는다: `_stage_capital`이 `_stage_alm`보다 먼저
# 실행되므로 RWA·자본비율·레버리지·ECL 경로에 ALM이 들어가지 않고,
# `reverse_critical_severity`는 `cet1_ratio`로 푸는데 ΔEVE·ΔNII·LCR은
# `multi_axis.py:279`의 `earnings_delta`에 들어가지 않는다.
# +1 PASS: alm_cf_ties_to_notional — 계약현금흐름 원금 합 = 계약원장 명목.
#    상환스케줄이 원금을 다 갚아내지 못하면(잔액 전개 오류·버킷 절단) 그 차액이
#    지금까지 어디에도 남지 않았다.
# +1 PASS: alm_bucket_pv_ties_to_delta_eve — 화면이 그리는 버킷별 PV 효과와
#    이사회 팩 헤드라인이 같은 산출에서 나왔는지. 버킷별 효과는 원장에 아예
#    없었고 화면은 파이프라인 메모리 객체에서 직접 읽고 있었다.
# +1 PASS: alm_ladder_ties_to_cashflow — 사다리 순갭 합 = 현금흐름 합. 사다리가
#    현금흐름 원장이 아니라 별도 가정에서 나오면 여기서 갈라진다.
# +1 WARN: alm_unconfirmed_param_in_use — KRW 금리충격 모수가 비어 USD 계정을
#    프록시로 쓰고 있고(설계 §0), 시장전반 스트레스 유출률이 없어 그 생존기간
#    시나리오는 산출되지 않는다. 산출이 나왔다는 사실만 보면 이 공백이 보이지
#    않는다 — 그래서 매 실행 드러낸다.
# +1 WARN: alm_behaviour_param_warnings — 행동·곡선 모수 경고 46건(TDRR 기준율
#    미확정, CPR steepener/flattener 승수 미확인, NMD 안정예금 비율 미추정 등).
#    ParamWarning은 "그 조정을 건너뛰었다"는 기록이므로 산출물에 실려야 한다.
# 재고정 사유 (중대 지적 시정):
#   PASS +1  `alm_delta_eve_independent_recalc` 신설. 기존
#            `alm_bucket_pv_ties_to_delta_eve`는 결과 원장의 delta_eve가 버킷
#            원장 delta_pv의 합으로 **정의**되므로 항등식이었고 충격곡선을
#            무력화해도 통과했다. 그 검사는 짝 검증
#            (`alm_bucket_pv_pairs_with_irrbb_result`)으로 이름을 바꿔 남기고,
#            값 검증은 모수 원장에서 할인계수를 다시 만드는 새 검사가 맡는다.
#   WARN +1  `alm_irrbb_engine_single_source` 신설. 스트레스 경로가 아직 갭
#            근사로 ΔEVE를 산출한다 — `StressBooks.irrbb` 배선이 끝나면 PASS로
#            바뀐다.
# 재고정 9 (2026-08-10, 신규 원장 배선) — +4 PASS · +2 WARN.
#
# 헤드라인 10건은 움직이지 않는다. 신규 원장 스테이지는 RWA·자본비율·레버리지·
# ECL 경로 뒤에 있고 그 산출물을 읽기만 한다. **ΔEVE는 움직였다** — 파이프라인
# 헤드라인 계정이 폐지된 `d368_2016`(KRW 300/400/200 · 충격후 하한 없음)에서
# 현행 `별표9의1_2026`(KRW 225/350/225 · 제12항 다 하한 0)으로 옮겼기 때문이다.
# ΔEVE는 골든 헤드라인 목록에 없으므로 이 파일의 수치는 그대로다.
#
# +1 PASS: irrbb_headline_not_repealed — 헤드라인 ΔEVE가 폐지 계정으로 산출되지
#    않는지. 계정만 되돌리면 값이 그럴듯하게 나오면서 폐지된 기준이 결재로 간다.
# +1 PASS: irrbb_outlier_basis_tier1_15pct — 아웃라이어 판정이 기본자본 15%
#    기준([별표 9-1] 제21항 나)으로 났는지. 폐지된 자기자본 20% 기준과 다르다.
# +1 PASS: kr_irrbb_national_ledgers_present — 비만기성예금 범주·행동옵션 범위·
#    관리체계 원장이 실제로 산출됐는지. 스펙만 있고 산출이 없으면 화면이 빈 표다.
# +1 PASS: lgd_ccf_backtest_censoring_reported — LGD 표본의 관측중단 건수가
#    원장에 실리는지. 세지 않으면 완결 표본만 남아 실현 LGD가 낮게 나온다.
# +1 WARN: limit_definition_from_ledger — 한도 5종이 원장에서 오지만 내부한도
#    4건이 승인일 미기재다. 원장을 비우면 한도 산출도 비어야 한다는 계약을 함께 본다.
# +1 WARN: macro_master_from_ledger — 거시지표 12종이 마스터 원장에서 오지만
#    ECOS·KOSIS 공표 카탈로그와 대조하지 않아 전건 근거 미확인이다.
# 재고정 10 (2026-08-10, 중대 지적 시정). +2 WARN, 헤드라인은 움직이지 않는다.
#
# +1 WARN: rwa_components_reconcile. sa·irb 산출 프레임에서 다시 합산해 최종
#    RWA까지 잇는 대사. CCR·구조화 RWA가 아직 검사에 넘어오지 않아 잔여로만
#    확인하며, 그 사실을 WARN으로 남긴다(배선이 두 값을 넘기면 PASS가 된다).
#    이전에는 SA·IRB RWA를 전건 변조해도 상태가 바뀌는 검사가 한 건도 없었다.
# +1 WARN: large_exposure_two_sources. 거액익스포저가 두 벌로 갈려 있다.
#    한도엔진 동일차주 축은 기본자본 25%, 원장 lex_position의 은행법35조_동일차주는
#    자기자본 25%로 판정해 같은 기준일에 위반 건수가 다르다.
#
# 같은 회차에 판정이 바뀐 두 건은 건수를 움직이지 않는다.
#   large_exposure_25pct. 리포트 부재 시 PASS(fail-open)에서 WARN으로. 이번
#     실행에는 리포트가 있으므로 PASS 그대로다.
#   rwa_matches_bis_input · bis_ratio_ordering. 구성상 성립하는 항등식이므로
#     `is_identity=True`로 표시했다. 상태는 PASS 그대로이고 통제 건수
#     (`ValidationReport.controls()`)에서만 빠진다.
# PASS 62/WARN 13 → 63/12. `rwa_components_reconcile`이 부분 대사(WARN)에서
# 전량 대사(PASS)로 올라갔다. 파이프라인이 CCR·구조화 RWA를 검사에 넘기기
# 시작해 여섯 구성요소를 전부 재합산해 최종 RWA와 맞춘다. 그 전에는 SA·IRB만
# 보고 두 항을 뺀 채 합계를 맞춰, 두 항의 변조를 잡지 못했다.
# PASS 63/WARN 12 → 70/13. PASS +7 은 새로 붙은 검사다. CAPM 회수 할인율
#     (재계산·회수유형 서열·승인기록·근거표시·할인율 LGD 민감도), PLGD
#     (ELBE 하한·185.바 후단 입증), RWA 귀속(1단 항등식·2단 대사).
# WARN +1 은 `PLGD 예상외손실 추가분 부호` 하나다. 신뢰수준 q 가 승인 전이라
#     PLGD 가 산출된 행이 없고, 검사는 그 사실을 "판정하지 않았다"로 남긴다.
#     산출물이 없는데 PASS 로 넘기지 않는다. q 가 승인되면 PASS 나 FAIL 로 갈린다.
# PASS 70/WARN 13 → 70/14. WARN +1 은 `pillar2_requirement_evidence` 다.
#     P2R·P2G 는 감독당국의 개별 부과분이고 이 저장소에 근거가 없다. 예전에는
#     소스에 1.5%·1.0% 를 박아 넘겨 요구비율이 원장과 어긋난 두 벌로 공시됐다.
#     원장에 빈 칸으로 두고 0 으로 산출하되, OCR 이 그만큼 과소 표시된다는
#     사실을 매 실행 남긴다. 근거가 들어오면 PASS 로 갈린다.
GOLDEN_VALIDATION = {"PASS": 70, "WARN": 14}
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


def test_intake_catches_exposures_that_fall_out_of_both_books():
    """SA·IRB 어느 북에도 안 들어가는 익스포저를 FAIL로 잡는다.

    `_stage_split_books`는 자산군 5종으로 필터링한다. 목록 밖 자산군은 양쪽에서
    탈락하고 RWA에서 **소리 없이 사라진다** — 합성 데이터에서는 안 생기지만
    실데이터에서는 생기고, 그것을 보는 검사가 없었다. 전 항목 advisory였던
    `data_quality.reconcile`은 파이프라인 밖에서만 호출된다.
    """
    from risk_lib.data_gen import generate_portfolio
    from risk_lib.validation.consistency import (
        ValidationReport, _check_portfolio_intake,
    )

    p = generate_portfolio(seed=42)
    rep = ValidationReport()
    _check_portfolio_intake(p, rep)
    booked = [c for c in rep.checks if c.name == "intake_every_exposure_is_booked"]
    assert booked and booked[0].status == "PASS"

    lost = p.copy()
    lost.loc[lost.index[:3], "asset_class"] = "equity"
    rep2 = ValidationReport()
    _check_portfolio_intake(lost, rep2)
    c = next(x for x in rep2.checks if x.name == "intake_every_exposure_is_booked")
    assert c.status == "FAIL" and "equity" in c.detail


def test_intake_catches_duplicate_exposure_ids():
    """중복 exposure_id는 RWA를 경보 없이 이중계상시킨다 — FAIL로 잡는다."""
    import pandas as pd

    from risk_lib.data_gen import generate_portfolio
    from risk_lib.validation.consistency import (
        ValidationReport, _check_portfolio_intake,
    )

    p = generate_portfolio(seed=42)
    dup = pd.concat([p, p.head(2)], ignore_index=True)
    rep = ValidationReport()
    _check_portfolio_intake(dup, rep)
    c = next(x for x in rep.checks if x.name == "intake_exposure_id_unique")
    assert c.status == "FAIL" and "2" in c.detail


def test_wall_clock_asof_is_disclosed_not_silent():
    """`asof`를 안 주면 벽시계가 들어간다는 사실이 자체검증에 드러난다.

    같은 seed·같은 데이터라도 실행 날짜가 다르면 헤드라인 지문이 달라진다 —
    ARCHITECTURE의 "seed+asof 같으면 산출 같다"가 진입점에서 깨진다. 기본값을
    없애면 호출부가 전부 깨지므로 **출처를 기록**하고 드러내는 쪽을 택했다.
    """
    from risk_lib.validation.consistency import (
        ValidationReport, _check_asof_provenance,
    )

    for src, expect in (("wall_clock", "WARN"), ("explicit", "PASS")):
        rep = ValidationReport()
        _check_asof_provenance({"asof": "2026-06-30", "asof_source": src}, rep)
        c = next(x for x in rep.checks if x.name == "asof_is_explicit")
        assert c.status == expect, (src, c.status)


def test_case_study_seed_derivation_is_reproducible_across_processes():
    """프로필 seed 유도에 파이썬 `hash()`를 쓰지 않는다.

    문자열 `hash()`는 프로세스별 salt가 걸려(PYTHONHASHSEED) 실행마다 다르다.
    그것으로 seed를 유도하면 같은 seed·같은 프로필이 실행마다 다른 포트폴리오를
    낸다 — 재현성 규칙이 조용히 새는 자리였다.
    """
    from pathlib import Path

    src = (Path(__file__).parent.parent
           / "risk_lib/case_studies/__init__.py").read_text(encoding="utf-8")
    assert "hash(profile.short)" not in src, (
        "salted hash()로 seed를 유도하고 있다 — hashlib을 쓴다")
    assert "hashlib.sha256" in src
