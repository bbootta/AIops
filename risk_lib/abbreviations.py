"""약어 사전 — 경영진 보고서에 hover tooltip + 하단 사전 카드.

CRO 보고서에 등장하는 모든 약어를 한곳에서 관리한다.
HTML `<abbr title="...">` 태그를 자동 생성하여 hover 시 설명을 보여주고,
보고서 마지막 약어 카드(card)도 같은 사전에서 생성한다.

사용:
    from risk_lib.abbreviations import abbr, abbr_dict_card_html
    text = abbr("CET1") + " 비율"  # → <abbr title="...">CET1</abbr> 비율
    card = abbr_dict_card_html()    # → 보고서 하단 약어 사전 카드 HTML
"""

from __future__ import annotations

import html as _html

# 약어 → (영문 원어, 한글 설명)
ABBREVIATIONS: dict[str, tuple[str, str]] = {
    # ── 자본·자본적정성 ──
    "BIS":    ("Bank for International Settlements",
               "국제결제은행. 보통 'BIS 비율'은 위험가중자산(RWA) 대비 자기자본 비율로, 8% 이상 유지가 규제 기준"),
    "CET1":   ("Common Equity Tier 1",
               "보통주자본. 자기자본 중 가장 안정적인 핵심자본. 보통주·이익잉여금 등이 해당, 규제 최저 4.5%"),
    "AT1":    ("Additional Tier 1",
               "기타기본자본. CET1 외 자본증권으로 영구신종자본증권, 누적적 우선주 등"),
    "Tier1":  ("Tier 1 capital",
               "기본자본 = CET1 + AT1. 규제 최저 6%"),
    "Tier2":  ("Tier 2 capital",
               "보완자본. 후순위채(잔존만기 5년 이상), 대손충당금(IRB 한도내) 등"),
    "AOCI":   ("Accumulated Other Comprehensive Income",
               "기타포괄손익누계액. 매도가능증권 평가손익 등을 자본에 반영한 항목"),
    "CCB":    ("Capital Conservation Buffer",
               "자본보전버퍼. 상시 2.5% 추가 유지, 위반 시 분배 제한(MDA)"),
    "CCyB":   ("Countercyclical Capital Buffer",
               "경기대응완충자본. 호황기 0~2.5% 추가 적립, 침체기 회수"),
    "DSIB":   ("Domestic Systemically Important Bank",
               "국내 시스템상 중요 은행. 1~5등급별 1~3.5% 가산자본 부과 (인뱅은 통상 미해당)"),
    "GSIB":   ("Global Systemically Important Bank",
               "글로벌 시스템상 중요 은행. 자본 가산 + 레버리지 가산 부과"),
    "CBR":    ("Combined Buffer Requirement",
               "통합버퍼요건 = CCB + CCyB + DSIB. 위반 시 MDA 분배 제한"),
    "MDA":    ("Maximum Distributable Amount",
               "최대분배가능액. CBR 위반 시 4분위(quartile)별 분배가능이익 상한 (배당·자기주식·AT1 쿠폰 제한)"),
    "P2R":    ("Pillar 2 Requirement",
               "감독당국이 SREP 통해 부과하는 추가자본요구. CET1·Tier1·Total 각 비율 가산"),
    "P2G":    ("Pillar 2 Guidance",
               "비공식 자본 가이드. 스트레스 결과 따라 1~3% 수준 권고"),
    "SREP":   ("Supervisory Review and Evaluation Process",
               "감독 점검·평가 절차. 연간 1회 자본·유동성·거버넌스 등 종합 평가"),
    "ICAAP":  ("Internal Capital Adequacy Assessment Process",
               "내부자본 적정성 평가. Pillar 2 — 위험유형별 경제자본 산출 후 가용자본과 비교"),
    "EC":     ("Economic Capital",
               "경제자본. 99.9% 신뢰수준의 비예상손실(UL) 기반 내부 자본 추정치"),
    "AFR":    ("Available Financial Resources",
               "가용자본. ICAAP에서 EC 대비 비교 대상 (보통 총자본 또는 CET1)"),

    # ── 신용리스크·RWA ──
    "RWA":    ("Risk-Weighted Assets",
               "위험가중자산. 자산별 위험 정도를 가중한 자본 산출 분모"),
    "SA":     ("Standardised Approach",
               "표준방법. 외부신용평가(ECRA) 기반 정해진 RW 표 적용"),
    "IRB":    ("Internal Ratings-Based",
               "내부등급법. 자체 PD/LGD/EAD 추정으로 자본 산출 (FIRB/AIRB)"),
    "FIRB":   ("Foundation IRB",
               "기초내부등급법. 은행이 PD만 추정, LGD·EAD는 감독치 사용 (LGD 무담보 45%, 후순위 75%)"),
    "AIRB":   ("Advanced IRB",
               "고급내부등급법. 은행이 PD/LGD/EAD 모두 자체 추정"),
    "PD":     ("Probability of Default",
               "부도확률. 12개월 또는 잔존기간 내 부도 발생 확률 (Basel III PD 하한 3bp)"),
    "LGD":    ("Loss Given Default",
               "부도시손실률. 부도 시 회수 불가능한 비율 (= 1 - 회수율)"),
    "EAD":    ("Exposure at Default",
               "부도시 노출액. 부도 시점의 잔액 + 인출 가능 한도 × CCF"),
    "EL":     ("Expected Loss",
               "기대손실. PD × LGD × EAD. 손익(P&L)으로 반영"),
    "UL":     ("Unexpected Loss",
               "비예상손실. EL을 초과하는 손실분, 자본으로 흡수"),
    "CRM":    ("Credit Risk Mitigation",
               "신용리스크경감. 담보·보증·신용파생을 통한 익스포저 축소"),
    "CCF":    ("Credit Conversion Factor",
               "신용환산율. 약정·미사용 한도 등을 EAD로 환산하는 비율"),
    "CCR":    ("Counterparty Credit Risk",
               "거래상대방신용리스크. 파생거래 등 양방향 노출에서의 신용리스크"),
    "SA-CCR": ("Standardised Approach for CCR",
               "CCR 표준방법. EAD = α(=1.4) × (RC + PFE)"),
    "RC":     ("Replacement Cost",
               "재조달비용 (= 시가 - 담보, 0 floor). SA-CCR EAD 구성"),
    "PFE":    ("Potential Future Exposure",
               "잠재미래노출. 자산군별 감독계수·만기계수 적용한 add-on"),
    "CVA":    ("Credit Valuation Adjustment",
               "신용평가조정. 거래상대방 부도 가능성을 derivative 평가에 반영"),
    "BA-CVA": ("Basic Approach CVA",
               "BA 방식 CVA 자본 산출 (κ × √Σ(S·EAD)²)"),
    "XVA":    ("X-Valuation Adjustments",
               "파생거래 가격조정 일괄 (CVA · DVA · FVA · ColVA · MVA). V_total = V_risk-free + XVAs"),
    "DVA":    ("Debit Valuation Adjustment",
               "자행 부도 시 채무경감 효익. CVA 분석과 대칭, 자행 CDS 기반"),
    "FVA":    ("Funding Valuation Adjustment",
               "비담보 파생거래의 자행 funding cost. EPE × funding spread"),
    "ColVA":  ("Collateral Valuation Adjustment",
               "담보 funding 비용 (OIS-CSA spread). 담보 부도 risk 별도 측정"),
    "MVA":    ("Margin Valuation Adjustment",
               "Initial Margin funding 비용. SIMM IM × funding spread"),
    "SIMM":   ("Standard Initial Margin Model",
               "ISDA 표준 IM 모형. 비청산 OTC 파생거래 IM 산출"),
    "EPE":    ("Expected Positive Exposure",
               "기대 positive 노출. 시점별 V > 0인 경우 평균. CVA/FVA 핵심 input"),
    "ENE":    ("Expected Negative Exposure",
               "기대 negative 노출. 시점별 V < 0인 경우 평균. DVA input"),
    "PFE":    ("Potential Future Exposure",
               "잠재 미래 노출. 95% / 99% quantile EPE. limit 모니터링"),
    "dV01":   ("Dollar value of 1 basis point",
               "1bp 평행 IR 충격 시 PV 변동 (KRW). IR delta hedge 측정"),
    "CS01":   ("Credit Spread 01",
               "1bp credit spread 충격 시 PV 변동. CDS hedge 측정"),
    "PLAT":   ("P&L Attribution Test",
               "FRTB IMA 적격성 — risk-theoretical P&L vs hypothetical P&L 차이"),
    "RFET":   ("Risk Factor Eligibility Test",
               "FRTB IMA — 충분한 시장 데이터로 modellable risk factor 여부 판정"),
    "NMRF":   ("Non-Modellable Risk Factors",
               "RFET 불통과 risk factor → stressed VaR 가산"),
    "IMA":    ("Internal Models Approach",
               "내부모형방법. 시장리스크 자체 ES 모형 사용 (FRTB 승인 필요)"),
    "BCBS 239":("BCBS Risk Data Aggregation and Reporting",
                "리스크 데이터 통합·보고 원칙. audit trail / data lineage 표준"),
    "SR 11-7": ("Fed SR Letter 11-7",
                "미 연준 모형리스크관리 지침. 모형 카드·검증·챔피언/챌린저"),
    "RC":     ("Risk Committee",
               "리스크 위원회. 이사회 산하 위원회로 전사 리스크 의사결정"),
    "HPL":    ("Hypothetical P&L",
               "프론트오피스 가격결정 모형의 가상 P&L. PLAT의 reference"),
    "RTPL":   ("Risk-Theoretical P&L",
               "리스크 모형의 이론 P&L. PLAT에서 HPL과 비교"),
    "SES":    ("Stressed Expected Shortfall",
               "스트레스 시 ES. NMRF에 대해 가산되는 자본"),
    "SA-CCR": ("Standardised Approach for Counterparty Credit Risk",
               "거래상대방신용리스크 표준방법. EAD = α(=1.4) × (RC + PFE)"),
    "VaR":    ("Value at Risk",
               "위험가치. 신뢰수준에서의 최대 손실 (예: 99% 1d VaR)"),
    "ES":     ("Expected Shortfall",
               "기대 손실. VaR 초과 시 평균 손실. FRTB IMA의 표준 metric"),

    # ── 유동성·ALM ──
    "ALM":    ("Asset Liability Management",
               "자산부채관리. 유동성·금리리스크의 통합 관리 부문"),
    "LCR":    ("Liquidity Coverage Ratio",
               "유동성커버리지비율 = HQLA / 30일 순현금유출. 100% 이상 유지"),
    "NSFR":   ("Net Stable Funding Ratio",
               "순안정조달비율 = ASF / RSF. 100% 이상 유지"),
    "HQLA":   ("High Quality Liquid Assets",
               "고유동성자산. Level 1(현금·국채), Level 2A(15% haircut), Level 2B(50%) 구분"),
    "ASF":    ("Available Stable Funding",
               "가용안정자금조달. NSFR 분자. 자본·예금·장기조달 가중"),
    "RSF":    ("Required Stable Funding",
               "필요안정자금조달. NSFR 분모. 자산별 만기·유동성 가중"),
    "IRRBB":  ("Interest Rate Risk in the Banking Book",
               "은행계정 금리리스크. ΔEVE/ΔNII로 측정"),
    "EVE":    ("Economic Value of Equity",
               "자기자본의 경제적가치. 자산·부채 현가 차이"),
    "ΔEVE":   ("Delta EVE",
               "금리 충격에 따른 EVE 변동. 6대 표준 시나리오의 최악 감소가 Tier1의 15% 초과 시 outlier"),
    "NII":    ("Net Interest Income",
               "순이자수익 = 이자수익 - 이자비용"),
    "ΔNII":   ("Delta NII",
               "금리 평행충격에 따른 향후 12개월 순이자수익 변동"),
    "NMD":    ("Non-Maturity Deposits",
               "비만기성예금 (요구불·저축성). IRRBB에서 행동 만기 별도 모형 적용"),

    # ── IFRS9 / 충당금 ──
    "IFRS9":  ("International Financial Reporting Standards 9",
               "국제회계기준 9호 — 금융상품. 3-stage ECL 충당금 모형 도입"),
    "ECL":    ("Expected Credit Loss",
               "기대신용손실 = PD × LGD × EAD. Stage 1: 12M, Stage 2/3: 잔존기간"),
    "SICR":   ("Significant Increase in Credit Risk",
               "신용위험 유의적 증가. 발생 시 Stage 1 → 2 이동 (PD 2x, 30 DPD 등 트리거)"),
    "TTC":    ("Through-the-Cycle",
               "시점평균. 거시변수 영향 제거한 안정 PD/LGD 추정"),
    "PIT":    ("Point-in-Time",
               "시점기반. 거시 시나리오에 조건부 PD/LGD (forward-looking)"),
    "EIR":    ("Effective Interest Rate",
               "유효이자율. ECL 현가 할인 시 사용"),
    "NPL":    ("Non-Performing Loans",
               "무수익여신/부실채권. 통상 90일 이상 연체 또는 손상 인식 자산"),
    "DPD":    ("Days Past Due",
               "연체일수. 30/60/90 버킷으로 자산건전성 분류"),

    # ── 모형리스크·검증 ──
    "PSI":    ("Population Stability Index",
               "표본안정성지수. <0.10 안정 / 0.10-0.25 경미 / >0.25 중대 이동"),
    "AUC-ROC":("Area Under ROC Curve",
               "ROC 곡선 아래 면적. 0.5 무작위 ~ 1.0 완벽. PD 모형 변별력"),
    "ROC":    ("Receiver Operating Characteristic",
               "이진 분류기의 TPR vs FPR 곡선"),
    "AUPRC":  ("Area Under Precision-Recall Curve",
               "정밀도-재현율 곡선 아래 면적. 불균형 데이터에 적합"),
    "KS":     ("Kolmogorov-Smirnov statistic",
               "부도자/비부도자 누적분포 최대 거리. PD 모형 변별력"),
    "HL":     ("Hosmer-Lemeshow",
               "캘리브레이션 χ² 검정. p ≥ 0.05 양호"),
    "SR 11-7":("Federal Reserve SR Letter 11-7",
               "미 연준 모형리스크관리 지침. 모형 카드·검증·챔피언/챌린저 표준"),

    # ── 위험성과·집중도·한도 ──
    "RAPM":   ("Risk-Adjusted Performance Measure",
               "위험조정 성과지표. 대표적으로 RAROC"),
    "RAROC":  ("Risk-Adjusted Return on Capital",
               "위험조정자본수익률 = (수익 - 비용 - EL + 자본운용수익) / EC"),
    "EVA":    ("Economic Value Added",
               "경제적 부가가치 = (RAROC - hurdle) × EC"),
    "SVA":    ("Shareholder Value Added",
               "주주가치 부가. RAROC를 hurdle 대비 측정"),
    "RORWA":  ("Return on RWA",
               "RWA 대비 수익률. 단순 수익성 지표"),
    "HHI":    ("Herfindahl-Hirschman Index",
               "시장집중도지수 = Σ(w_i)². > 0.18 고집중, > 0.25 매우 고집중"),
    "LEX":    ("Large Exposures framework",
               "BCBS 거대익스포저 규제. Tier1의 10% 이상 차주 별도 보고"),
    "KRI":    ("Key Risk Indicator",
               "핵심위험지표. RAF 3단 한계(board/management/operational) 채점 대상"),
    "RAF":    ("Risk Appetite Framework",
               "리스크 어페타이트 체계. KRI를 GREEN/WATCH/AMBER/RED로 등급"),

    # ── 시장리스크·운영리스크 ──
    "VaR":    ("Value at Risk",
               "위험가치. 99%/99.9% 신뢰수준 최대 손실"),
    "SVaR":   ("Stressed VaR",
               "스트레스 시기 데이터 기반 VaR. 시장리스크 자본 가산"),
    "ES":     ("Expected Shortfall",
               "기대손실. VaR 초과 손실의 평균 (CVaR)"),
    "MAR":    ("Market Risk framework",
               "BCBS 시장리스크 프레임워크 (구 IMA·새 FRTB)"),
    "FRTB":   ("Fundamental Review of the Trading Book",
               "BCBS 시장리스크 전면 개편. SA·IMA 정교화"),
    "SMA":    ("Standardised Measurement Approach (Op risk)",
               "운영리스크 표준측정법. BIC × ILM"),
    "BI":     ("Business Indicator",
               "운영리스크 SMA 산식의 BI = ILDC + SC + FC"),
    "BIC":    ("Business Indicator Component",
               "BI에 마진(α₁=0.12 / α₂=0.15 / α₃=0.18) 곱한 자본 산출 베이스"),
    "ILM":    ("Internal Loss Multiplier",
               "내부손실배수. 10년 평균 손실/BIC. 손실 이력 클수록 가산"),
    "ILDC":   ("Interest, Lease & Dividend Component",
               "BI 구성요소 - 이자·리스·배당"),
    "SC":     ("Services Component", "BI 구성요소 - 서비스 (수수료 등)"),
    "FC":     ("Financial Component", "BI 구성요소 - 금융 (트레이딩 등)"),
    "LDA":    ("Loss Distribution Approach",
               "손실분포접근법. Poisson 빈도 × Lognormal 심도로 99.9% VaR"),

    # ── 기후·기타 ──
    "NGFS":   ("Network for Greening the Financial System",
               "중앙은행·감독당국의 기후리스크 네트워크. 시나리오 3종(orderly/disorderly/hot house)"),
    "EAR":    ("Exposure At Risk",
               "기후·신용 충격 시 영향받는 노출액"),
    "CCAR":   ("Comprehensive Capital Analysis and Review",
               "미 연준의 종합자본분석. 9분기 horizon 다년 스트레스"),
    "DFAST":  ("Dodd-Frank Act Stress Test",
               "미 연준의 의무 스트레스 테스트"),
    "DPD":    ("Days Past Due",
               "연체일수"),

    # ── 거버넌스 ──
    "CRO":    ("Chief Risk Officer",
               "최고리스크관리책임자"),
    "IPO":    ("Initial Public Offering",
               "기업공개 — 신규 상장으로 자본 확충"),
    "QoQ":    ("Quarter over Quarter",
               "전분기 대비 변동"),
    "YoY":    ("Year over Year",
               "전년동기 대비 변동"),

    # ── Basel 규제 섹션 (참고) ──
    "CRE":    ("Credit Risk standards",
               "Basel III 신용리스크 섹션 (CRE10~CRE36)"),
    "RBC":    ("Risk-Based Capital",
               "Basel III 자본 섹션 (RBC10·RBC20 버퍼·RBC30 output floor)"),
    "OPE":    ("Operational risk standards",
               "Basel III 운영리스크 섹션 (OPE25 SMA)"),
    "LEV":    ("Leverage Ratio standards",
               "Basel III 레버리지 섹션 (LEV10·LEV30·LEV40)"),
    "OCR":    ("Overall Capital Requirement",
               "전체 자본요구 = P1 + CBR + P2R + P2G"),
}


# ----------------------------------------------------------------- helpers

def abbr(term: str, *, show: str | None = None) -> str:
    """`<abbr title="영문 — 한글 설명">표시문자</abbr>` 태그를 생성.

    사전에 없으면 plain text 반환. show 미지정 시 term 그대로 보여줌.
    """
    label = show or term
    if term not in ABBREVIATIONS:
        return _html.escape(label)
    full, ko = ABBREVIATIONS[term]
    tooltip = f"{full} — {ko}"
    return (f'<abbr title="{_html.escape(tooltip)}" '
            f'style="border-bottom:1px dotted #6b7280;cursor:help;'
            f'text-decoration:none">{_html.escape(label)}</abbr>')


def abbr_dict_card_html(*, ids_only: list[str] | None = None) -> str:
    """보고서 하단에 들어갈 약어 사전 카드 HTML."""
    if ids_only is None:
        terms = sorted(ABBREVIATIONS.keys())
    else:
        terms = [t for t in ids_only if t in ABBREVIATIONS]
    # 카테고리별 그룹 — 사전 등장순서를 보존
    rows = []
    for t in terms:
        full, ko = ABBREVIATIONS[t]
        rows.append(
            f'<tr><td style="font-weight:600;font-family:Menlo,Consolas,monospace;'
            f'white-space:nowrap;padding:4px 8px;border-bottom:1px solid #e5e7eb">'
            f'{_html.escape(t)}</td>'
            f'<td style="padding:4px 8px;border-bottom:1px solid #e5e7eb;'
            f'color:#374151;font-size:12px">{_html.escape(full)}</td>'
            f'<td style="padding:4px 8px;border-bottom:1px solid #e5e7eb;'
            f'font-size:12px">{_html.escape(ko)}</td></tr>')
    return f"""
<div class="card">
<h2>📖 약어 사전</h2>
<p class="section-lead">본 보고서에서 사용된 주요 약어. 본문 약어에 마우스를 올리면 동일 설명이 tooltip으로 표시됩니다.</p>
<div style="max-height:400px;overflow-y:auto;border:1px solid #e5e7eb;border-radius:6px">
<table style="width:100%;border-collapse:collapse;font-size:13px">
<thead>
<tr style="background:#f3f4f6;position:sticky;top:0">
<th style="padding:6px 8px;text-align:left;font-size:11px;
  text-transform:uppercase;letter-spacing:.04em">약어</th>
<th style="padding:6px 8px;text-align:left;font-size:11px;
  text-transform:uppercase;letter-spacing:.04em">영문 원어</th>
<th style="padding:6px 8px;text-align:left;font-size:11px;
  text-transform:uppercase;letter-spacing:.04em">설명</th>
</tr>
</thead>
<tbody>
{''.join(rows)}
</tbody>
</table>
</div>
</div>
"""


def annotate_text(text: str) -> str:
    """주어진 plain text에서 사전 등록 약어를 자동으로 <abbr> 태그로 wrap.

    각 약어는 본문에서 처음 등장 시에만 abbr 처리 (중복 hover 방지).
    """
    import re
    seen: set[str] = set()
    out = text
    # 가장 긴 약어부터 매치하여 LCR이 LCR-NSFR 같은 합성에 잘리지 않도록
    for term in sorted(ABBREVIATIONS, key=lambda t: -len(t)):
        if term in seen:
            continue
        # word boundary 매치 — Δ 같은 특수문자도 포함되도록 lookahead/lookbehind 우회
        pattern = re.escape(term)
        repl = abbr(term)
        # 단 1회만 (첫 등장)
        new_out, n = re.subn(pattern, lambda m: repl,
                              out, count=1)
        if n > 0:
            seen.add(term)
            out = new_out
    return out
