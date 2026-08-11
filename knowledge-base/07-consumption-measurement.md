# 07. 소비 측정 문제와 대안적 소비 지표 (Consumption Measurement and Alternative Consumption Measures)

> 리스크프리미엄 퍼즐 해결 에이전트 연구팀 지식베이스 — 담당 주제 07
> 최종 목표: 성균관대 이재준 석사논문 「개별가계소비자료를 이용한 자산가격결정」의 저널 논문 디벨롭
> 작성일: 2026-08-08 (웹 검색으로 서지정보 검증 완료)

## 개요 (이 갈래가 퍼즐 해결에 기여하는 방식)

Mehra-Prescott(1985)의 주식프리미엄 퍼즐은 "집계 소비 증가율이 너무 매끄럽고(low volatility) 주식수익률과의 공분산이 너무 작아서, 관측된 프리미엄을 정당화하려면 위험회피계수가 비상식적으로 커야 한다"는 문제다. 이 갈래의 핵심 주장은 **퍼즐의 상당 부분이 경제주체의 선호 문제가 아니라 '소비를 잘못 측정한' 문제**라는 것이다. 국민계정(NIPA) 소비는 (i) 보간·평활화 등 통계작성 과정의 필터링, (ii) 시간집계(time aggregation), (iii) 내구재 지출과 서비스플로우의 혼동, (iv) 표본·구성 오차 때문에 진짜 소비위험을 체계적으로 과소평가한다. 반대로 가계 서베이(CEX, 한국의 가계동향조사 등) 미시자료는 정의상 이론(가계 단위 오일러방정식)에 더 부합하지만, 과소보고와 응답오차라는 또 다른 측정 문제를 안고 있다. 따라서 이 갈래는 두 방향으로 발전했다: 첫째, 측정오차·시간집계가 오일러방정식 추정에 만드는 편의의 방향과 크기를 이론적으로 규명하는 연구(Working 1960; Grossman-Melino-Shiller 1987; Wilcox 1992; Attanasio-Weber 1993, 1995), 둘째, 필터링되지 않은 대안적 소비 지표(쓰레기 배출량, 언필터드 NIPA, 4분기 소비, 장기 누적 소비, 내구재 스톡)로 소비위험을 다시 재는 연구(Savov 2011; Kroencke 2017; Jagannathan-Wang 2007; Parker-Julliard 2005; Yogo 2006). 이들 연구의 공통 결론은 "소비를 제대로 재면 필요한 위험회피계수가 80~100 수준에서 10~20대로 떨어진다"는 것으로, 개별가계소비자료를 쓰는 이재준 논문의 존재 이유(집계·필터링 문제 회피)와 직결되는 동시에, 미시자료 고유의 측정오차를 어떻게 처리했는지가 심사에서 반드시 공격받을 지점임을 예고한다.

---

## 핵심 논문

### Working (1960), "Note on the Correlation of First Differences of Averages in a Random Chain", Econometrica

- **핵심 질문**: 순간(point-in-time) 확률과정이 아니라 구간 평균(time average)으로 관측된 시계열의 1차 차분은 어떤 통계적 성질을 갖는가?
- **방법론·데이터**: 순수 이론(랜덤워크의 구간 평균에 대한 해석적 도출). Econometrica 28(4), 916–918.
- **주요 결과**: 랜덤워크를 구간 평균한 뒤 차분하면, 원계열에 없던 **1차 자기상관 약 +0.25**가 인위적으로 발생한다(구간 분할 수가 커질 때의 극한값). 즉 시간집계는 (i) 측정된 증가율의 분산을 축소하고, (ii) 가짜 양(+)의 자기상관을 만든다.
- **한계**: 랜덤워크라는 특수한 과정에 대한 결과이며, 자산가격 응용은 후속 연구의 몫.
- **이재준 논문 디벨롭과의 연관성**: 분기·연간 가계소비자료는 모두 "조사 기간 중 지출 합계"라는 구간 평균 자료다. 소비증가율의 자기상관이 관측되더라도 습관형성(habit)이 아닌 Working 효과일 수 있음을 논문에서 명시적으로 구분해야 하고, 수익률(시점 자료)과 소비(구간 자료)의 타이밍 정합(beginning/end-of-period timing convention)을 어떻게 택했는지가 위험회피계수 추정치를 크게 바꾼다.

### Grossman, Melino & Shiller (1987), "Estimating the Continuous-Time Consumption-Based Asset-Pricing Model", Journal of Business & Economic Statistics

- **핵심 질문**: CCAPM은 순간 소비플로우와 시점 자산가격에 대한 이론인데, 실제로는 소비의 시간 평균만 관측된다. 시간집계를 보정하면 위험회피계수 추정은 어떻게 달라지는가?
- **방법론·데이터**: 연속시간 CCAPM에서 시간 평균화가 소비증가율–수익률 공분산에 미치는 효과를 해석적으로 도출하고, 최우추정법(ML)으로 6개 자료셋에서 상대위험회피계수와 순간 공분산을 일치추정. JBES 5(3), 315–327.
- **주요 결과**: 시간집계를 무시하면 소비–수익률 공분산이 체계적으로 **과소** 측정되고(대략 절반 수준으로), 그 결과 프리미엄을 맞추기 위한 위험회피계수는 **과대** 추정된다. 시간집계를 보정해도 위험회피계수는 여전히 높은 편이어서 퍼즐이 완전히 해소되지는 않지만, 보정 전보다 유의하게 낮아진다.
- **한계**: 연속시간·로그정규 구조에 의존; 측정오차(집계 외의 오류)는 다루지 않음.
- **이재준 논문 디벨롭과의 연관성**: 가계조사 소비는 "조사월 기준 지출"이므로 시간집계 보정 논리를 그대로 적용할 수 있다. 공분산 기반 모멘트를 쓸 때 GMS(1987)식 보정계수를 감도분석으로 제시하면 위험회피계수 추정의 강건성 주장이 강해진다.

### Hall (1988), "Intertemporal Substitution in Consumption", Journal of Political Economy

- **핵심 질문**: 실질이자율 변화에 대한 소비증가율의 반응, 즉 기간간 대체탄력성(EIS)은 얼마인가?
- **방법론·데이터**: 미국 20세기 집계 소비 자료로 오일러방정식(선형근사)을 도구변수 추정. 시간집계로 인한 오차의 MA 구조를 감안해 2기 이상 lag 도구를 사용. JPE 96(2), 339–357.
- **주요 결과**: EIS는 **0.1 내외, 사실상 0에 가깝고** 양(+)이라는 강한 증거가 없다. 시간 평균 자료를 쓰면 소비증가율 오차가 MA(1)이 되어 1기 lag 도구가 무효가 됨을 지적 — 시간집계를 무시한 기존 추정(예: Hansen-Singleton)이 편의를 가짐을 보임.
- **한계**: 집계 자료 사용 자체가 문제(아래 Attanasio-Weber). CRRA에서는 EIS=1/γ이므로 EIS≈0은 γ가 무한대라는, 퍼즐을 오히려 심화시키는 함의.
- **이재준 논문 디벨롭과의 연관성**: 미시 오일러방정식을 로그선형화해 추정할 때 도구변수의 lag 선택(측정오차·시간집계로 인한 MA 오차 때문에 최소 2기 lag)이 필수라는 실무 지침을 제공. 이재준 논문의 추정 설계에서 도구 타당성 논의의 근거 문헌.

### Breeden, Gibbons & Litzenberger (1989), "Empirical Tests of the Consumption-Oriented CAPM", Journal of Finance

- **핵심 질문**: 보고된 소비자료의 측정 문제(시간집계, 발표 지연, 낮은 빈도)를 보정한 뒤 CCAPM은 시장포트폴리오 기반 CAPM과 비교해 어떤 성과를 내는가?
- **방법론·데이터**: (i) 시간 평균화된 소비의 베타를 해석적으로 보정(시간집계 시 공분산이 축소되는 정도를 조정), (ii) 소비와 최대상관인 자산 포트폴리오(consumption-mimicking portfolio, CMP)를 구성해 소비 대신 사용. 미국 월별/분기별 자료. JF 44(2), 231–262.
- **주요 결과**: 소비위험의 시장가격은 유의하게 양(+)이고 실질이자율 추정치는 0에 가까움 — CCAPM의 질적 예측과 부합. 다만 전통적 CAPM과 CCAPM의 설명력은 대동소이. 시간집계 보정과 모방포트폴리오는 이후 문헌의 표준 도구가 됨.
- **한계**: 모방포트폴리오 구성이 표본 의존적; 소비자료의 측정오차 자체(보고오차)는 미해결.
- **이재준 논문 디벨롭과의 연관성**: 가계소비자료로 소비모방포트폴리오를 만들면 월별 수익률 빈도로 검정을 확장할 수 있다. 한국 주식시장 횡단면에서 "가계소비 모방포트폴리오 요인"을 구성하는 것은 이재준 논문의 자연스러운 확장 축이다.

### Wilcox (1992), "The Construction of U.S. Consumption Data: Some Facts and Their Implications for Empirical Work", American Economic Review

- **핵심 질문**: 미국 집계 소비지출 통계는 실제로 어떻게 만들어지며, 그 작성 방식이 실증연구에 어떤 함정을 만드는가?
- **방법론·데이터**: NIPA 개인소비지출(PCE)의 원천자료(소매판매 서베이 등)와 작성 절차를 추적한 제도 분석 + 예시 실증. AER 82(4), 922–941.
- **주요 결과**: 월별 PCE의 상당 부분이 **직접 관측이 아니라 보간·배분·추세 외삽으로 임퓨테이션**되며, (i) 표본오차(sampling error)와 (ii) 구성오차(compositional error)라는 두 결함이 있다. 특히 월별 자료의 평활화 절차는 소비증가율에 인위적 시계열 상관과 분산 축소를 만든다 — 이것이 이후 Kroencke(2017)의 "필터링" 모형의 제도적 근거다.
- **한계**: 편의의 방향을 정량화한 것이 아니라 사실 기술 중심; 미국 제도에 특화.
- **이재준 논문 디벨롭과의 연관성**: 한국 국민계정 민간소비 역시 도소매판매·서비스업조사 기반 배분과 보간을 거친다. "한국판 Wilcox" 격으로 한국은행 국민계정 소비 작성 절차를 한 절로 정리해 '집계자료의 필터링 문제 → 가계 미시자료 사용의 정당화' 논리를 세우면 논문 서론의 설득력이 크게 올라간다.

### Attanasio & Weber (1993), "Consumption Growth, the Interest Rate and Aggregation", Review of Economic Studies

- **핵심 질문**: 오일러방정식이 집계 자료에서 기각되는 것은 이론의 실패인가, 집계(aggregation)의 실패인가?
- **방법론·데이터**: 영국 FES(Family Expenditure Survey) 반복 횡단면으로 코호트(출생연도 집단) 평균 소비를 구축, 집계 소비와 코호트 평균 소비 각각에 대해 로그선형 오일러방정식을 추정·비교. REStud 60(3), 631–649.
- **주요 결과**: 이론이 요구하는 것은 **로그 소비의 평균**인데 집계자료는 **소비 합계의 로그**를 쓰므로 젠센 부등식 항(횡단면 분산의 변동)이 누락된다. 집계 자료에서는 EIS 추정치가 체계적으로 낮고 모형이 기각되지만, 코호트 평균 자료에서는 기각되지 않고 EIS도 더 크게 추정된다(유동성 제약이 약한 집단에서 약 0.8까지).
- **한계**: 코호트 평균도 여전히 준(準)집계 자료이며, 반복 횡단면이라 개별 가계 패널 동학은 추적 불가.
- **이재준 논문 디벨롭과의 연관성**: 이재준 논문이 개별가계자료를 쓰는 핵심 명분이 바로 이 집계편의다. 가계동향조사도 반복 횡단면이므로 Attanasio-Weber식 코호트 구축이 직접 이식 가능한 방법론이고, "집계 소비 vs 코호트 평균 vs 가계 평균 로그 소비증가율"의 3단 비교표는 저널 버전의 킬러 테이블이 될 수 있다.

### Attanasio & Weber (1995), "Is Consumption Growth Consistent with Intertemporal Optimization? Evidence from the Consumer Expenditure Survey", Journal of Political Economy

- **핵심 질문**: 미국 CEX 미시자료에서 인구·노동공급 변수를 통제하면 기간간 최적화(오일러방정식)는 기각되는가?
- **방법론·데이터**: 미국 CEX(1980년대) 코호트 자료. 비내구재+서비스 소비, 가구구성·노동공급 통제 변수를 포함한 오일러방정식 추정. JPE 103(6), 1121–1157.
- **주요 결과**: 집계 자료에서 나타나는 소비의 소득 과잉민감성(excess sensitivity)과 오일러방정식 기각은 (i) 집계편의와 (ii) 인구·노동공급 변수 누락 때문이며, 이를 통제한 미시자료에서는 **기간간 최적화가 기각되지 않는다**. EIS 추정치도 집계 추정보다 유의하게 크다.
- **한계**: CEX 자체의 과소보고·측정오차(아래 Bee-Meyer-Sullivan)가 남는다. 셀 평균화로 개별 측정오차를 줄였으나 완전히 제거하지는 못함.
- **이재준 논문 디벨롭과의 연관성**: "미시자료 + 인구통계 통제"라는 이재준 논문의 설계가 국제 문헌의 표준과 정합적임을 보여주는 준거 논문. 저널 버전에서는 가구구성(가구원수, 성인등가화), 가구주 연령·노동상태 통제가 오일러방정식 추정치를 얼마나 움직이는지 명시적으로 보고해야 한다.

### Parker & Julliard (2005), "Consumption Risk and the Cross Section of Expected Returns", Journal of Political Economy

- **핵심 질문**: 소비가 수익률 충격에 느리게 반응한다면(조정비용, 정보 지연, 측정 시차), 동시점 공분산이 아니라 **수익률 이후 여러 분기에 걸쳐 누적된 소비증가율과의 공분산("궁극적 소비위험")**이 올바른 위험 척도 아닌가?
- **방법론·데이터**: 미국 분기 NIPA 비내구재+서비스 소비, Fama-French 25 규모·가치 포트폴리오. 수익률 시점부터 S분기 후까지의 누적 소비증가율로 베타를 정의하고 2단계 횡단면 회귀·GMM. JPE 113(1), 185–222.
- **주요 결과**: 동시점(S=0) 소비위험은 25개 포트폴리오 평균수익률 변동을 거의 설명하지 못하지만, **약 3년(S=11분기) 누적 소비위험은 그 변동의 큰 부분을 설명**한다(S=11에서 베타의 산포가 커지고 평균수익률과의 정렬이 뚜렷해짐). 궁극적 소비위험 기반의 위험회피계수·실질무위험수익률 추정치는 동시점 기반보다 훨씬 상식적인 값이 된다.
- **한계**: S 선택의 자의성; 장기 누적 공분산은 표본오차가 큼; 왜 소비가 느리게 반응하는지(진짜 마찰 vs 측정 시차)를 식별하지 못함.
- **이재준 논문 디벨롭과의 연관성**: 가계자료의 응답 시차·조사 주기 때문에 미시 소비는 집계보다도 더 느리게 수익률 충격을 반영할 수 있다. 이재준 논문의 소비베타를 동시점뿐 아니라 1~3년 누적 지평으로 재추정하는 것은 계산 비용이 낮고 기여가 분명한 확장이다.

### Yogo (2006), "A Consumption-Based Explanation of Expected Stock Returns", Journal of Finance

- **핵심 질문**: 통상 CCAPM 검정에서 버려지는 **내구재** 소비를 명시적으로 모형화하면 횡단면·시계열 자산가격 퍼즐이 얼마나 설명되는가?
- **방법론·데이터**: 비내구재와 내구재 서비스플로우가 비분리(nonseparable)인 Epstein-Zin 효용. 미국 내구재 스톡(BEA), Fama-French 포트폴리오, GMM 추정. JF 61(2), 539–580.
- **주요 결과**: 두 재화 간 대체탄력성이 충분히 높으면 내구재 소비가 감소할 때 한계효용이 상승 → 내구재 증가율이 추가 가격결정요인이 된다. 내구재 소비는 경기순환에 강하게 민감(불황에서 급락)해서, 불황에 약한 소형·가치주의 높은 평균수익률(가치 프리미엄)과 주식프리미엄의 시간변동을 설명한다.
- **한계**: 내구재 스톡은 감가상각 가정으로 구성된 추정치라 그 자체가 측정오차 대상. 후속 연구가 복제 코드의 버그를 보고했으나(ResearchGate: "A Consequential Bug in Yogo (2006)") 핵심 기여는 유지되는 것으로 평가.
- **이재준 논문 디벨롭과의 연관성**: 가계조사에서 내구재 '지출'과 '서비스플로우'의 괴리는 집계자료보다 훨씬 심하다(자동차 구입이 있는 분기의 지출 폭등). 이재준 논문에서 (i) 비내구재+서비스만 쓰는 기본 사양과 (ii) 내구재 지출 포함 사양의 결과 차이를 보고하고 Yogo식 비분리 효용으로 해석하는 것이 방어 논리가 된다.

### Jagannathan & Wang (2007), "Lazy Investors, Discretionary Consumption, and the Cross-Section of Stock Returns", Journal of Finance

- **핵심 질문**: 투자자가 소비·포트폴리오 계획을 늘 재검토하지 않고 특정 시점(연말·세금연도 말)에만 정렬한다면, 소비위험은 어느 시점 소비로 재야 하는가?
- **방법론·데이터**: 미국 분기 소비자료에서 **4분기 대 4분기(Q4–Q4) 연간 소비증가율**로 소비베타를 계산, Fama-French 25 포트폴리오 횡단면 검정. JF 62(4), 1623–1661.
- **주요 결과**: Q4–Q4 소비증가율을 쓰면 **CCAPM이 Fama-French 3요인 모형에 필적하는 횡단면 설명력**을 보인다. 다른 분기 기준(Q1–Q1 등)으로 재면 성과가 급락 — 소비 측정의 '시점 선택'만으로 CCAPM 성패가 갈린다. 저자들은 세금연도 말(12월)에 투자자들이 소비·포트폴리오를 재정렬할 유인이 크기 때문으로 해석.
- **한계**: 미국 제도(12월 결산 세제)에 특화된 해석; 연간 빈도로 표본이 짧아짐; 4분기 소비에 계절적 재량 지출(연말 소비)이 섞임.
- **이재준 논문 디벨롭과의 연관성**: 한국 가계동향조사의 월별/분기별 구조에서 어떤 관측 시점(예: 연말 vs 설·추석이 낀 분기)의 소비증가율을 쓰느냐에 따라 결과가 달라질 수 있음을 시사. 한국의 세제·상여금 일정(연말정산, 설 상여)에 맞춘 "한국판 4분기 소비" 검정은 그 자체로 독립적 기여가 될 수 있다.

### Savov (2011), "Asset Pricing with Garbage", Journal of Finance

- **핵심 질문**: 국민계정 소비 대신, 소비의 물리적 부산물인 **쓰레기 배출량(garbage)**으로 소비위험을 재면 주식프리미엄 퍼즐은 어떻게 되는가?
- **방법론·데이터**: 미국 EPA 연간 도시고형폐기물(MSW) 발생량(1960–2006)을 소비 프록시로 사용. 주식프리미엄 캘리브레이션 + 규모·가치·산업 포트폴리오 횡단면 GMM. 유럽 자료로 외적 타당성 확인. JF 66(1), 177–201.
- **주요 결과**: 쓰레기 증가율은 NIPA 소비지출 증가율보다 **더 변동성이 크고 주식수익률과의 상관이 더 높다**. 쓰레기 기반 CCAPM은 미국 주식프리미엄을 **상대위험회피계수 17**로 맞추는 반면 NIPA 소비로는 **81**이 필요하며, 무위험수익률 퍼즐도 회피한다. 횡단면에서 쓰레기 증가율은 가격결정요인으로 유의하며 NIPA 소비증가율을 구축(drive out)한다. NIPA 소비는 임퓨테이션·평활화 때문에 자기상관이 있지만 쓰레기는 Hall(1978)의 항상소득가설 예측대로 자기상관이 없다.
- **한계**: 연간 빈도·짧은 표본; 쓰레기에는 소비 외 요인(포장재 규제, 재활용 확대)이 섞임; 내구재·서비스 소비를 반영하지 못하는 재화 편중 프록시.
- **이재준 논문 디벨롭과의 연관성**: "공식 소비통계의 필터링이 소비위험을 지운다"는 명제의 가장 극적인 증거. 이재준 논문에서 가계자료 기반 소비증가율의 변동성·수익률 상관을 한국 국민계정 소비와 나란히 보고하고, Savov의 표(변동성·상관·자기상관 비교)를 한국 버전으로 재현하면 미시자료 사용의 가치를 정량적으로 보여줄 수 있다.

### Kroencke (2017), "Asset Pricing without Garbage", Journal of Finance

- **핵심 질문**: 왜 쓰레기는 NIPA 소비보다 자산가격 성과가 좋은가? NIPA 작성 과정의 **필터링(측정오차 완화용 평활화)을 역산(unfilter)**하면 공식 소비자료로도 같은 결과를 얻을 수 있는가?
- **방법론·데이터**: NIPA 작성 절차를 "진짜 소비 + 측정오차의 최적 평활화"로 모형화하고, 관측된 NIPA 소비에서 필터링을 되돌린 **unfiltered NIPA consumption**을 구축. 주식프리미엄 캘리브레이션과 횡단면 검정. JF 72(1), 47–98.
- **주요 결과**: 필터링을 되돌린 언필터드 소비는 주식프리미엄을 **훨씬 낮은 위험회피계수(쓰레기와 유사한 10~20대 수준)**로 설명하고 주식수익률 횡단면에서도 가격결정된다. 즉 Savov(2011)의 결과는 '쓰레기'라는 프록시의 마법이 아니라 **NIPA 필터링 제거의 효과**다. 연간 NIPA 소비의 저변동성·자기상관이 필터링 모형으로 정량적으로 설명됨.
- **한계**: 언필터드 소비는 필터링 모형(파라미터)에 의존하는 구성 변수라 모형 오설정 위험; 진짜 소비위험과 측정오차 분산의 식별이 가정에 의존.
- **이재준 논문 디벨롭과의 연관성**: 편의 방향의 핵심 준거: **평활화된 공식 소비 → 소비위험 과소측정 → 위험회피계수 과대추정**. 이재준 논문이 가계 미시자료로 추정한 위험회피계수가 집계자료 추정치보다 낮게 나온다면 Kroencke의 필터링 논리로 해석 가능하고, 반대로 높게 나온다면 미시 측정오차(아래 참조)의 반대 방향 편의로 해석해야 한다 — 두 힘의 상쇄 구조를 논문에서 명시적으로 다뤄야 한다.

### Bee, Meyer & Sullivan (2015), "The Validity of Consumption Data: Are the Consumer Expenditure Interview and Diary Surveys Informative?", in *Improving the Measurement of Consumer Expenditures* (NBER/University of Chicago Press)

- **핵심 질문**: CEX(면접조사·가계부조사)의 지출 보고는 국민계정 대비 얼마나 정확하며, 어떤 항목이 신뢰할 만한가?
- **방법론·데이터**: CEX Interview/Diary의 항목별 집계치를 정의를 일치시킨 PCE 항목과 비교(보고율 = CEX/PCE). NBER 서적 챕터(pp. 204–240), 편집: Carroll, Crossley & Sabelhaus; NBER WP 18308.
- **주요 결과**: (i) 정의 차이를 무시한 단순 비교는 CEX 과소보고를 크게 과장하며, CEX-NIPA 총액 격차의 약 절반은 정의·범위 차이로 설명된다. (ii) 임대료+공과금, 자동차 구입 등 **대형·정기 지출 항목의 보고율은 높고 시간에 걸쳐 안정적**인 반면, 주류·담배·외식 등은 심각하게 과소보고된다. (iii) 총지출 기준 CEX/PCE 비율은 시간에 걸쳐 하락 추세 — 서베이 품질 악화 우려(Meyer-Sullivan 2015 JEP "Household Surveys in Crisis"와 연결).
- **한계**: 집계 대 집계 비교라 개별 가계 수준 오차의 분산(횡단면 측정오차)은 직접 식별하지 못함.
- **이재준 논문 디벨롭과의 연관성**: 심사자가 반드시 물을 질문 — "한국 가계동향조사 소비는 국민계정 대비 보고율이 얼마인가, 항목별로 어디가 약한가" — 에 대한 분석 템플릿. 이재준 논문 저널 버전에는 가계동향조사 항목별 집계치 대 국민계정 민간소비의 보고율 표를 넣고, 보고율이 높은 항목만으로 구성한 소비 지표의 강건성 검정을 추가하는 것이 바람직하다.

---

## 측정오차가 오일러방정식·위험회피계수 추정에 미치는 편의의 방향 (종합)

| 측정 문제 | 메커니즘 | 편의 방향 |
|---|---|---|
| 집계자료의 필터링·평활화 (Wilcox 1992; Savov 2011; Kroencke 2017) | 소비증가율 분산·수익률과의 공분산 축소, 인위적 자기상관 | 소비베타 하향 → 프리미엄을 맞추는 **위험회피계수 γ 과대추정** (81 vs 17) |
| 시간집계 (Working 1960; Grossman-Melino-Shiller 1987; Breeden et al. 1989) | 구간 평균화로 공분산 축소(대략 1/2), 차분에 MA(1) 자기상관 +0.25 유발 | γ 과대추정; 1기 lag 도구 사용 시 EIS 추정 불일치 (Hall 1988) |
| 집계편의(젠센 항 누락) (Attanasio-Weber 1993, 1995) | 로그 평균 대신 평균의 로그 사용, 인구·노동공급 이질성 누락 | 집계 EIS 하향편의(=γ 상향), 오일러방정식의 허위 기각 |
| 미시자료의 고전적(백색) 측정오차 (CEX; Bee-Meyer-Sullivan 2015) | 개별 소비증가율 분산 과대 + 수익률과 무상관 잡음 → 공분산/분산 희석(attenuation) | 소비베타 하향편의 → 횡단면 λ(소비위험 가격) 과대추정 가능; 비선형(CRRA) 오일러방정식에서는 잡음이 고차 모멘트를 오염시켜 γ가 어느 방향으로도 튈 수 있음 — 셀/코호트 평균화로 완화 |
| 내구재 혼입 (Yogo 2006) | 지출 ≠ 서비스플로우, 구입 시점의 스파이크 | 비분리 효용 무시 시 모형 오설정; 미시자료에서 특히 심함 |
| 관측 시점 선택 (Jagannathan-Wang 2007) | 계획 재정렬 시점(4분기) 외 소비는 수익률과의 정렬이 약함 | 시점을 잘못 고르면 소비위험 과소측정 → γ 과대추정 |
| 궁극적(누적) 소비위험 (Parker-Julliard 2005) | 소비의 느린 조정으로 동시점 공분산이 진짜 위험 과소반영 | 동시점 베타 사용 시 γ 과대추정; 3년 누적 시 상식적 γ |

핵심 요약: **집계·필터링·시간집계는 한 방향(γ 과대)으로 편의를 만들고, 미시자료의 응답 잡음은 주로 감쇠(attenuation) 방향으로 작동한다.** 미시자료 연구는 전자를 피하는 대신 후자를 떠안는 구조이므로, 코호트/셀 평균화, 보고율 높은 항목 선별, 도구변수 lag 조정, 누적 지평 베타가 표준 처방이다.

## 실증적 쟁점과 미해결 질문

1. **미시 측정오차의 분산 식별**: 개별 가계 소비증가율 분산 중 진짜 이질적 소비위험과 응답오차의 비중을 어떻게 분해할 것인가? 검증자료(validation data)가 없는 한국에서는 반복 관측 구조(가계동향조사의 연속 조사월)나 항목 간 상관을 이용한 식별이 필요하다.
2. **두 편의의 상쇄 문제**: 집계 필터링 편의(γ 과대)와 미시 잡음 편의(감쇠)가 상쇄되면, 미시자료 추정치가 "덜 틀려 보이는" 것이 진짜 개선인지 우연인지 구분하기 어렵다.
3. **필터링 모형의 이식성**: Kroencke(2017)의 unfiltering은 미국 NIPA 절차에 맞춘 것 — 한국 국민계정 소비에 같은 필터링 구조가 성립하는지는 검증된 바 없다.
4. **시점·계절성 문제의 일반화**: Jagannathan-Wang의 4분기 효과가 세제 때문인지 계절적 재량소비 때문인지 미해결이며, 12월 결산이 아닌 제도(한국 연말정산은 1~2월 환급)에서 어느 시점이 '재정렬 시점'인지 불명확하다.
5. **서베이 품질의 시계열 악화**: CEX/PCE 보고율 하락(Household Surveys in Crisis)은 미시 소비자료 기반 시계열 연구의 비교가능성을 위협한다 — 한국 가계동향조사도 2017~2019년 표본 개편으로 단절이 있어 같은 쟁점이 있다.

## 후속연구 아이디어 (이재준 논문 확장 방향)

1. **한국판 '필터링 대 미시' 3단 비교**: 국민계정 민간소비, 가계동향조사 코호트 평균 소비(Attanasio-Weber 방식), 가계 평균 로그 소비증가율의 (i) 변동성, (ii) 주식수익률과의 상관, (iii) 자기상관, (iv) 함의된 위험회피계수를 하나의 표로 비교(Savov Table 1의 한국 재현). 여기에 보고율 높은 항목만의 소비 지표(Bee-Meyer-Sullivan 처방)를 4번째 열로 추가하면 측정 문제 장 전체를 관통하는 실증 기여가 된다.
2. **누적 지평·시점 선택 강건성**: 이재준 논문의 소비베타를 Parker-Julliard식 1~3년 누적 지평과 Jagannathan-Wang식 관측시점 변경(연말 vs 명절 분기)으로 재추정. 미시자료의 측정 시차가 크다면 누적 지평에서 성과 개선이 집계자료보다 더 극적으로 나타날 것이라는 검정 가능한 가설을 제시.
3. **미시 측정오차 명시 모형화**: 오일러방정식 GMM에 승법적 측정오차를 명시적으로 넣고(로그정규 가정 시 상수항으로 흡수되는 부분과 남는 편의 분리), 셀 크기를 바꿔가며 평균화 수준–추정치 관계를 그려 감쇠편의 곡선을 직접 보여주는 방법론 절 추가. 이는 "개별가계자료" 사용의 신뢰성을 심사자에게 정면으로 입증하는 장치가 된다.

---

### 참고 서지 (검증된 원문 링크)

- Working, H. (1960). "Note on the Correlation of First Differences of Averages in a Random Chain." *Econometrica* 28(4), 916–918.
- Grossman, S. J., A. Melino & R. J. Shiller (1987). "Estimating the Continuous-Time Consumption-Based Asset-Pricing Model." *Journal of Business & Economic Statistics* 5(3), 315–327. https://www.tandfonline.com/doi/abs/10.1080/07350015.1987.10509594
- Hall, R. E. (1988). "Intertemporal Substitution in Consumption." *Journal of Political Economy* 96(2), 339–357. https://ideas.repec.org/a/ucp/jpolec/v96y1988i2p339-57.html
- Breeden, D. T., M. R. Gibbons & R. H. Litzenberger (1989). "Empirical Tests of the Consumption-Oriented CAPM." *Journal of Finance* 44(2), 231–262. https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.1989.tb05056.x
- Wilcox, D. W. (1992). "The Construction of U.S. Consumption Data: Some Facts and Their Implications for Empirical Work." *American Economic Review* 82(4), 922–941. https://ideas.repec.org/a/aea/aecrev/v82y1992i4p922-41.html
- Attanasio, O. P. & G. Weber (1993). "Consumption Growth, the Interest Rate and Aggregation." *Review of Economic Studies* 60(3), 631–649. https://academic.oup.com/restud/article-abstract/60/3/631/1570435
- Attanasio, O. P. & G. Weber (1995). "Is Consumption Growth Consistent with Intertemporal Optimization? Evidence from the Consumer Expenditure Survey." *Journal of Political Economy* 103(6), 1121–1157.
- Parker, J. A. & C. Julliard (2005). "Consumption Risk and the Cross Section of Expected Returns." *Journal of Political Economy* 113(1), 185–222. https://www.journals.uchicago.edu/doi/10.1086/426042
- Yogo, M. (2006). "A Consumption-Based Explanation of Expected Stock Returns." *Journal of Finance* 61(2), 539–580. https://onlinelibrary.wiley.com/doi/10.1111/j.1540-6261.2006.00848.x
- Jagannathan, R. & Y. Wang (2007). "Lazy Investors, Discretionary Consumption, and the Cross-Section of Stock Returns." *Journal of Finance* 62(4), 1623–1661. https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.2007.01253.x
- Savov, A. (2011). "Asset Pricing with Garbage." *Journal of Finance* 66(1), 177–201. https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.2010.01629.x
- Kroencke, T. A. (2017). "Asset Pricing without Garbage." *Journal of Finance* 72(1), 47–98. https://onlinelibrary.wiley.com/doi/abs/10.1111/jofi.12438
- Bee, A., B. D. Meyer & J. X. Sullivan (2015). "The Validity of Consumption Data: Are the Consumer Expenditure Interview and Diary Surveys Informative?" In *Improving the Measurement of Consumer Expenditures*, eds. Carroll, Crossley & Sabelhaus, NBER/University of Chicago Press, 204–240. https://www.nber.org/papers/w18308
