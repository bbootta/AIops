# 01. 주식프리미엄 퍼즐의 기원과 정식화 (Equity Premium Puzzle: Foundations)

> 리스크프리미엄 퍼즐 해결 에이전트 연구팀 지식베이스 — 담당 주제 01
> 최종 목표: 성균관대 이재준 석사논문 「개별가계소비자료를 이용한 자산가격결정」의 저널 논문 디벨롭
> 작성일: 2026-08-08 (서지정보 웹 검색 검증 완료)

## 개요

이 갈래는 퍼즐 그 자체의 "출생 증명서"에 해당한다. 주식프리미엄 퍼즐은 Lucas (1978)의 대표소비자 교환경제 모형과 그 실증 버전인 소비기반 자산가격결정모형(CCAPM; Breeden 1979, Hansen & Singleton 1982·1983)이라는 이론적 토대 위에서, Mehra & Prescott (1985)이 "미국 주식의 역사적 초과수익률 약 6%p는 합리적 위험회피계수로는 설명 불가능하다"고 정량적으로 정식화하면서 탄생했다. 이후 Weil (1989)이 무위험이자율 퍼즐이라는 쌍둥이 퍼즐을 추가했고, Hansen & Jagannathan (1991)은 특정 모형에 의존하지 않는 확률할인요소(SDF) 변동성 한계라는 진단 도구를 제공하여 퍼즐을 "어떤 후보 모형이든 통과해야 하는 관문"으로 일반화했다. Kocherlakota (1996)와 Mehra & Prescott (2003), Mehra (2008)의 서베이는 해결 시도들을 체계적으로 분류·평가하며 "퍼즐은 여전히 퍼즐"임을 확인했다. 이 기초 문헌들이 중요한 이유는, 모든 해결 시도(습관형성, 재난위험, 불완전시장, 행동재무 등)가 결국 이 갈래가 설정한 정량적 기준 — 프리미엄 약 6%p, 요구 상대위험회피계수(RRA) 30~50, HJ 변동성 한계 σ(m)/E(m) ≥ 0.5(연간 샤프비율) — 을 통과해야 하기 때문이다. 이재준 논문은 "대표소비자의 총소비" 대신 "개별 가계의 소비"로 SDF를 구성하는 접근이므로, 본 갈래는 (i) 기각당한 기준 모형이 정확히 무엇인지, (ii) 어떤 모멘트(프리미엄 크기, 무위험이자율, HJ 한계)를 개선해야 "퍼즐을 완화했다"고 주장할 수 있는지를 규정하는 출발점이다.

## 핵심 논문

### Lucas (1978), "Asset Prices in an Exchange Economy", Econometrica

- **서지**: Robert E. Lucas, Jr., *Econometrica*, Vol. 46, No. 6, pp. 1429–1445.
- **핵심 질문**: 생산이 외생적 배당(과일나무)으로 주어지는 순수교환경제에서 균형 자산가격은 어떻게 결정되는가?
- **방법론·데이터**: 동일한 대표소비자들이 존재하는 1재화 교환경제의 재귀적 일반균형 이론 모형. 실증 아닌 순수 이론. 균형에서 소비 = 배당이 되고, 자산가격은 오일러 방정식 p_t·u'(c_t) = β·E_t[u'(c_{t+1})(p_{t+1} + d_{t+1})]로 결정된다.
- **주요 결과**: 모든 자산가격이 대표소비자의 한계효용(소비)으로 표현되는 확률할인요소 m_{t+1} = β·u'(c_{t+1})/u'(c_t)에 의해 결정됨을 보임. 이후 모든 소비기반 자산가격 연구(그리고 Mehra-Prescott의 캘리브레이션)의 이론적 모태.
- **한계**: 대표소비자·완비시장 가정. 소비자 이질성, 시장 불완전성, 거래비용이 모두 사상(捨象)됨.
- **이재준 논문 디벨롭과의 연관성**: 이재준 논문이 도전하는 지점이 바로 "대표소비자" 가정이다. 개별 가계 소비로 SDF를 구성하는 것은 Lucas 모형의 집계(aggregation) 전제 — 완비시장 하에서 개별 한계효용이 총소비 한계효용으로 집계된다는 것 — 가 현실에서 성립하지 않음을 실증하는 작업이므로, 논문 서론에서 Lucas 모형의 집계 정리와 그 붕괴 조건을 명확히 서술해야 한다.

### Breeden (1979), "An Intertemporal Asset Pricing Model with Stochastic Consumption and Investment Opportunities", Journal of Financial Economics

- **서지**: Douglas T. Breeden, *Journal of Financial Economics*, Vol. 7, No. 3, pp. 265–296.
- **핵심 질문**: Merton의 다요인 ICAPM을 단일 베타로 축약할 수 있는가?
- **방법론·데이터**: 연속시간 이론 모형. 다수 소비재·확률적 투자기회 하에서 자산의 기대초과수익률이 "총소비 증가율에 대한 베타(소비베타)" 하나로 결정됨을 도출(CCAPM).
- **주요 결과**: 자산의 위험은 시장수익률과의 공분산이 아니라 소비와의 공분산으로 측정되어야 한다는 소비베타 정리. 시장베타 CAPM을 소비베타 CCAPM으로 대체하는 이론적 근거 제공.
- **한계**: 이후 실증(예: Breeden, Gibbons & Litzenberger 1989, JF; Mankiw & Shapiro 1986)에서 소비베타는 시장베타보다 수익률 횡단면 설명력이 낮았고, 측정된 총소비의 평활성 때문에 프리미엄 크기를 설명하지 못함.
- **이재준 논문 디벨롭과의 연관성**: CCAPM의 실증 실패가 "이론이 틀려서"인지 "총소비 데이터가 개별 소비자의 위험 노출을 잘못 측정해서"인지가 핵심 쟁점. 이재준 논문은 후자의 가설을 개별 가계 자료로 검증하는 구도이므로, Breeden의 소비베타를 '가계 소비베타' 또는 '가계 소비의 고차 모멘트'로 재정의하는 확장이 자연스럽다.

### Hansen & Singleton (1982), "Generalized Instrumental Variables Estimation of Nonlinear Rational Expectations Models", Econometrica

- **서지**: Lars Peter Hansen & Kenneth J. Singleton, *Econometrica*, Vol. 50, No. 5, pp. 1269–1286.
- **핵심 질문**: 소비 오일러 방정식 E_t[β(c_{t+1}/c_t)^{-γ}·R_{t+1}] = 1을 구조 전체를 특정하지 않고 직접 추정·검정할 수 있는가?
- **방법론·데이터**: Hansen (1982)의 GMM을 CRRA 효용 오일러 방정식에 적용. 미국 전후(postwar) 월별 총소비(비내구재+서비스)와 주식수익률, 시차 변수를 도구변수로 사용.
- **주요 결과**: 과다식별제약(J-test)이 다수 사양에서 기각. 추정된 RRA는 대체로 0~2 수준으로 낮게 나옴. 즉 낮은 γ로는 수익률 횡단면·시계열을 정합적으로 설명 못 함.
- **한계**: 총소비 자료의 시간집계(time aggregation)·측정오차 문제. 대표소비자 가정 유지.
- **이재준 논문 디벨롭과의 연관성**: 이재준 논문의 실증 방법론(오일러 방정식 GMM)의 원형. 저널 디벨롭 시 (i) 가계 자료에 GMM을 적용할 때의 도구변수 선택, (ii) 패널 측정오차가 J-test와 γ 추정치에 미치는 편의를 이 논문 계보의 방법론적 논의로 정당화할 수 있다.

### Hansen & Singleton (1983), "Stochastic Consumption, Risk Aversion, and the Temporal Behavior of Asset Returns", Journal of Political Economy

- **서지**: Lars Peter Hansen & Kenneth J. Singleton, *Journal of Political Economy*, Vol. 91, No. 2, pp. 249–265. DOI: 10.1086/261141.
- **핵심 질문**: 소비와 수익률의 결합 로그정규성 가정 하에서 최우추정으로 CRRA 모형을 검정하면 어떤 결과가 나오는가?
- **방법론·데이터**: 소비증가율과 수익률의 결합 로그정규분포 가정 + 제약된 로그선형 시계열 표현의 최우추정. 미국 전후 월별 자료(총소비, 주식·국채 수익률).
- **주요 결과**: 단일 수익률만 쓰면 모형이 기각되지 않으나 RRA 추정치가 매우 낮고(대략 0~2), 복수 수익률(주식+단기채)을 함께 부과하면 제약이 기각됨. 즉 CRRA-CCAPM은 주식과 무위험채의 수익률 차이를 동시에 설명하지 못함 — Mehra-Prescott 퍼즐의 계량경제학적 예고편.
- **한계**: 로그정규성·동분산 가정. 총소비 측정 문제 동일.
- **이재준 논문 디벨롭과의 연관성**: "복수 자산(주식 vs 무위험채)을 동시에 부과할 때 기각된다"는 결과는 이재준 논문에서도 검정 설계의 핵심이 되어야 한다. 즉 가계 소비 기반 SDF가 주식수익률 방정식 하나만이 아니라 주식-무위험채 초과수익률 방정식을 함께 만족시키는지(joint test)를 보여야 저널 수준의 기여가 된다.

### Mehra & Prescott (1985), "The Equity Premium: A Puzzle", Journal of Monetary Economics — ★ 퍼즐의 원전

- **서지**: Rajnish Mehra & Edward C. Prescott, *Journal of Monetary Economics*, Vol. 15, No. 2, pp. 145–161.
- **핵심 질문**: 표준 대표소비자 일반균형 모형(Lucas 모형의 변형)이 미국의 역사적 주식프리미엄을 재현할 수 있는가?
- **방법론·데이터**: 미국 1889–1978년(90년) 연간 자료. S&P 종합지수 실질수익률 평균 약 6.98%, 단기 무위험채(T-bill 상당) 실질수익률 평균 약 0.80% → **주식프리미엄 약 6.18%p**. 소비증가율이 2상태 마코프 체인을 따르는 Lucas류 교환경제를 캘리브레이션(소비증가율 평균 약 1.8%, 표준편차 약 3.6%, 자기상관 -0.14). 선험적으로 "합리적" 파라미터 영역을 RRA γ ∈ (0, 10), 시간할인인자 β ∈ (0, 1)로 제한.
- **주요 결과(수치)**: 이 제약 하에서 모형이 낼 수 있는 **최대 주식프리미엄은 약 0.35%p** — 관측치 6.18%p의 1/18 수준. 관측된 프리미엄을 맞추려면 γ가 대략 30~40 이상 필요하며(후속 문헌 기준 최대 50까지 인용됨), 그 경우 무위험이자율이 비현실적으로 높아지는 부작용 발생. 이 정량적 간극이 "주식프리미엄 퍼즐"로 명명됨.
- **한계**: 캘리브레이션 접근(공식 추정·검정 아님), 2상태 마코프 근사, 총소비 = 배당이라는 단순화, 생존편의(survivorship bias) 가능성(Brown-Goetzmann-Ross 1995가 제기), 대표소비자·완비시장 가정.
- **이재준 논문 디벨롭과의 연관성**: 이재준 논문의 "기각 대상 귀무모형"을 제공하는 논문. 디벨롭 시 (i) 한국판 벤치마크 수치(한국의 역사적 주식프리미엄, 총소비 기반 요구 γ)를 Mehra-Prescott 방식으로 먼저 제시하고, (ii) 개별 가계소비로 구성한 SDF가 요구 γ를 얼마나 낮추는지를 "M-P 대비 개선 폭"으로 보고하는 구성이 표준적이다. 한국은 미국보다 프리미엄이 작아 퍼즐이 약하다는 국내 선행연구(아래 김인수·홍정훈 2008)가 있으므로, "한국에서 퍼즐이 존재하는 표본·측정 방식"을 먼저 확정하는 것이 필수 선결과제다.

### Weil (1989), "The Equity Premium Puzzle and the Risk-Free Rate Puzzle", Journal of Monetary Economics

- **서지**: Philippe Weil, *Journal of Monetary Economics*, Vol. 24, No. 3, pp. 401–421. (NBER WP 2829)
- **핵심 질문**: CRRA 효용의 제약 — 상대위험회피계수(RRA)와 기간간대체탄력성(EIS)이 역수 관계로 묶이는 것 — 을 풀면(Kreps-Porteus 비기대효용, 이른바 Epstein-Zin-Weil 선호) 퍼즐이 해결되는가?
- **방법론·데이터**: RRA와 EIS를 분리한 재귀적 선호 하의 일반균형 자산가격 이론 + Mehra-Prescott식 캘리브레이션.
- **주요 결과(수치)**: RRA와 EIS의 분리만으로는 주식프리미엄 퍼즐이 해결되지 않으며, 오히려 **무위험이자율 퍼즐**이 새로 등장. 프리미엄을 맞출 만큼 RRA를 높이면(예: γ = 45 수준의 극단적 캘리브레이션) 소비평활 동기 때문에 모형의 무위험이자율이 관측치(실질 약 1% 미만)보다 훨씬 높아진다. "사람들이 그렇게 위험을 싫어하고 미래 소비가 성장하는데 왜 무위험이자율은 이토록 낮은가"가 쌍둥이 퍼즐로 정식화됨.
- **한계**: 여전히 대표소비자 틀. 선호 일반화라는 한 방향만 탐색.
- **이재준 논문 디벨롭과의 연관성**: 저널 심사에서 반드시 나오는 질문이 "당신의 가계소비 SDF는 프리미엄뿐 아니라 무위험이자율 수준도 맞추는가?"이다. 이재준 논문 디벨롭 시 평가 모멘트에 무위험이자율(그리고 가능하면 그 변동성)을 반드시 포함하고, 가계 소비 이질성이 예비적 저축 경로를 통해 무위험이자율을 낮추는 메커니즘(Weil 1992, Huggett 1993 계열)과 연결지어 해석해야 한다.

### Hansen & Jagannathan (1991), "Implications of Security Market Data for Models of Dynamic Economies", Journal of Political Economy

- **서지**: Lars Peter Hansen & Ravi Jagannathan, *Journal of Political Economy*, Vol. 99, No. 2, pp. 225–262.
- **핵심 질문**: 특정 효용함수를 가정하지 않고, 자산수익률 자료만으로 유효한 확률할인요소(SDF, 기간간한계대체율)가 만족해야 할 제약을 도출할 수 있는가?
- **방법론·데이터**: 무차익 조건에서 SDF의 평균-표준편차 조합이 만족해야 할 하한(HJ bounds)을 비모수적으로 도출: **σ(m)/E(m) ≥ |E(R^e)|/σ(R^e)** (수익률 프런티어와의 쌍대성). 미국 주식·채권 수익률과 총소비 자료로 실증.
- **주요 결과(수치)**: 미국 주식의 연간 샤프비율 약 0.4~0.5(프리미엄 6~8%p, 변동성 16~20%)를 대입하면 SDF 변동성은 σ(m) ≥ 대략 0.4~0.5 × E(m) ≈ 0.4~0.5가 필요. 반면 CRRA-총소비 SDF의 변동성은 근사적으로 γ × σ(Δlnc) ≈ γ × 0.01~0.036에 불과 → 낮은 γ의 총소비 SDF는 한계를 크게 미달(퍼즐의 SDF 변동성 버전). 요구 γ는 다시 수십 단위.
- **한계**: 한계 자체는 진단 도구일 뿐 해결책을 주지 않음. 표본오차를 고려한 검정(Burnside 1994, Cecchetti-Lam-Mark 1994 등)은 후속 과제로 남음.
- **이재준 논문 디벨롭과의 연관성**: 이재준 논문 디벨롭의 **핵심 실증 프레임으로 가장 직접적**. 개별 가계소비로 구성한 후보 SDF들(가계 소비증가율의 횡단면 평균, 분산·왜도 반영 SDF 등)이 한국 자산수익률로 그린 HJ 한계 내부에 들어오는지를 그림 하나로 보여주는 것이 저널 논문의 표준적 "머니 샷"이다. Brav-Constantinides-Geczy (2002, JPE)가 미국 CEX 자료로 정확히 이 작업을 했으므로, 한국 가계 자료(가계동향조사/한국노동패널 등)로의 복제·확장이 명확한 기여 포인트가 된다.

### Kocherlakota (1996), "The Equity Premium: It's Still a Puzzle", Journal of Economic Literature

- **서지**: Narayana R. Kocherlakota, *Journal of Economic Literature*, Vol. 34, No. 1 (March), pp. 42–71.
- **핵심 질문**: 1985~1995년의 해결 시도들은 퍼즐을 실제로 해결했는가?
- **방법론·데이터**: 서베이 + 자체 GMM 재검정(미국 연간 자료, 1889–1978 및 전후 표본). 해결 시도를 (i) 선호의 수정(비기대효용, 습관형성), (ii) 시장 불완전성(비보험화 개별 소득위험), (iii) 거래비용·차입제약의 세 갈래로 분류.
- **주요 결과(수치)**: 표준 모형으로 프리미엄을 설명하려면 RRA가 8.5를 초과해야 한다는 검정 결과 제시(그의 t-검정 기준). 무위험이자율 퍼즐은 β > 1을 허용해야만 완화됨. 세 갈래 모두 부분적 성공에 그치며, 특히 불완전시장 모형은 "개별 소비 위험이 지속적(persistent)이고 경기역행적(countercyclical)일 때만" 프리미엄을 만들 수 있다고 정리 — 결론은 "퍼즐은 여전히 퍼즐".
- **한계**: 1996년 시점 서베이라 이후의 재난위험(Rieder 2008 아님 — Rietz 1988/Barro 2006), 장기위험(Bansal-Yaron 2004), 미시자료 기반 실증(Brav et al. 2002 등)은 미포함.
- **이재준 논문 디벨롭과의 연관성**: 이재준 논문이 속하는 갈래가 (ii) 불완전시장임을 문헌 지도상에서 확정해 주는 논문. 특히 "개별 소비 위험의 지속성·경기역행성이 관건"이라는 Kocherlakota의 정리는 이재준 논문 디벨롭 시 검증할 가설 목록(한국 가계 소비 위험의 횡단면 분산이 경기침체기에 커지는가, 왜도가 음(-)으로 기우는가 — Constantinides-Duffie 1996, Constantinides-Ghosh 2017 계열)을 직접 제공한다.

### Mehra & Prescott (2003), "The Equity Premium in Retrospect", Handbook of the Economics of Finance

- **서지**: Rajnish Mehra & Edward C. Prescott, in G.M. Constantinides, M. Harris & R. Stulz (eds.), *Handbook of the Economics of Finance*, Vol. 1B, Ch. 14, Elsevier, pp. 889–938. (NBER WP 9525; 자매 논문 Mehra 2003 "The Equity Premium: Why Is It a Puzzle?", *Financial Analysts Journal* 59(1), NBER WP 9512)
- **핵심 질문**: 원 논문 이후 18년간의 데이터 갱신과 해결 시도들을 어떻게 평가할 것인가?
- **방법론·데이터**: 미국 1889–2000년으로 표본 연장 — 실질 주식수익률 평균 약 7.9%, 무위험 약 1.0% → **프리미엄 약 6.9%p로 오히려 확대**. 영국·독일·프랑스·일본 등 국제 자료에서도 4~7%p 수준의 프리미엄 확인(생존편의 반론에 대한 응답).
- **주요 결과**: 위험 기반 설명(선호 수정, 습관, 재난위험)과 비위험 기반 설명(세금, 규제, 유동성, 차입제약)을 재평가. 저자들의 결론은 여전히 "표준 위험 기반 설명은 실패"이며, 프리미엄은 사전적(ex ante) 개념이므로 미래 프리미엄 전망은 과거 평균보다 낮을 수 있음을 인정.
- **한계**: 저자 자신들의 서베이라는 관점 편향 가능성. 미시 소비자료 기반 문헌에 대한 취급이 제한적.
- **이재준 논문 디벨롭과의 연관성**: (i) 논문 서론의 "퍼즐 현황" 인용의 표준 출처, (ii) 국제 비교 표는 한국 프리미엄의 상대적 크기를 자리매김하는 데 직접 사용 가능, (iii) 비위험 기반 설명(차입제약, 세금)은 한국 가계 자료에서 관측 가능한 변수(주식보유 여부, 유동성 제약 더미)로 통제·검증할 수 있어 이재준 논문의 강건성 분석 항목이 된다.

### Mehra, ed. (2008), Handbook of the Equity Risk Premium

- **서지**: Rajnish Mehra (ed.), *Handbook of the Equity Risk Premium*, Handbooks in Finance, North-Holland/Elsevier, Amsterdam. (Mehra & Prescott의 "Non-Risk-based Explanations of the Equity Premium" 등 수록)
- **핵심 질문**: 퍼즐 제기 이후 20여 년의 이론·실증 전체를 집대성.
- **방법론·데이터**: 편저. 재난위험(Barro), 습관형성(Constantinides), 불완전시장, 세금·제도, 장기 데이터(Goetzmann-Ibbotson) 등 각 갈래 대표 연구자들의 챕터와 상호 논평(discussion) 수록.
- **주요 결과**: 단일 해법의 합의는 없으며, 유력 후보들(재난위험, 장기위험, 습관, 이질적 소비자)이 각자 일부 모멘트를 설명한다는 "다원적 현황"을 공식화.
- **한계**: 2008년 이후 문헌(금융위기 이후의 재난위험 재평가, 관리비용 기반 중개자 자산가격이론 등) 미포함.
- **이재준 논문 디벨롭과의 연관성**: 저널 논문의 문헌연구 장을 구조화할 때의 분류 체계(위험 기반 vs 비위험 기반 × 대표소비자 vs 이질적 소비자)를 제공. 이재준 논문을 "이질적 소비자 × 위험 기반" 칸에 위치시키고 나머지 칸과의 차별성을 서술하는 데 사용.

### Cochrane (2005), Asset Pricing (Revised Edition)

- **서지**: John H. Cochrane, *Asset Pricing: Revised Edition*, Princeton University Press. (초판 2001)
- **핵심 질문**: 모든 자산가격 모형을 p = E(mx)라는 단일 SDF 프레임으로 통합하면 퍼즐은 어떻게 보이는가?
- **방법론·데이터**: 교과서이지만 연구 관점이 뚜렷함. 주식프리미엄 퍼즐을 HJ 한계의 언어로 재서술: 미국 주식의 연간 샤프비율 약 0.5와 총소비증가율 표준편차 1~2%를 결합하면 σ(m) ≥ 0.5가 필요하고, CRRA에서는 σ(m) ≈ γσ(Δlnc)이므로 **γ ≥ 25~50**이 필요함을 표준 계산으로 제시. GMM/SDF 추정·검정의 방법론 통합(Hansen-Jagannathan 거리 포함).
- **주요 결과**: 퍼즐의 본질은 "SDF가 총소비 자료보다 훨씬 변동성이 크고 경기역행적이어야 한다"는 것이며, 유망한 방향으로 습관형성(Campbell-Cochrane 1999)과 함께 **개별(이질적) 소비자 위험** — 총소비가 아닌 개별 소비의 높은 변동성·경기역행적 횡단면 분산 — 을 명시적으로 거론.
- **한계**: 교과서 특성상 자체 신규 실증은 없음.
- **이재준 논문 디벨롭과의 연관성**: 이재준 논문의 실증 설계 전체(SDF 정의 → HJ 한계 → GMM 추정 → HJ 거리로 모형 비교)를 조직하는 방법론 교범. 특히 "가계소비 SDF가 총소비 SDF보다 변동성이 크고 경기역행적인가"라는 Cochrane식 질문을 논문의 중심 가설로 삼으면 저널 심사자에게 익숙한 언어가 된다.

### 김인수·홍정훈 (2008), "우리나라 주식시장에서의 주식프리미엄 퍼즐에 관한 연구", 재무연구 — 한국 벤치마크

- **서지**: 김인수·홍정훈, 『재무연구』(한국재무학회), 제21권 제1호, pp. 1–32.
- **핵심 질문**: 한국에도 주식프리미엄 퍼즐이 존재하는가?
- **방법론·데이터**: 1980–2004년 한국 자료로 역사적 주식프리미엄을 측정하고, Mehra-Prescott류 소비기반 모형이 이를 재현할 수 있는지 검토.
- **주요 결과**: 한국의 주식프리미엄은 미국 등 주요 선진국(약 6%p 내외)에 비해 현저히 낮은 수준이며, 추정 위험회피계수도 극단적으로 크지 않아 미국식의 강한 퍼즐은 관측되지 않는다는 결론. (같은 계열로 이지현·김진용 류의 연구는 1987–2008년 분기자료에서 위험회피계수가 이론적 적정범위보다 오히려 작게 추정됨을 보고.)
- **한계**: 총소비(국민계정) 자료 사용 — 개별 가계 소비의 이질성 정보가 전혀 반영되지 않음. 표본이 짧고 외환위기 구조변화에 민감.
- **이재준 논문 디벨롭과의 연관성**: 이재준 논문이 넘어야 할 국내 선행연구의 현황선. "한국은 퍼즐이 약하다"는 기존 결론이 (i) 짧은 표본과 낮은 실현 프리미엄 탓인지, (ii) 총소비 집계가 가계 위험을 가려서인지 구분하는 것이 디벨롭의 핵심 차별점. 개별 가계 자료로 SDF 변동성이 커지면 "한국에서도 총소비 기준으로는 설명 안 되는 횡단면·시계열 모멘트가 가계 기준으로 설명된다"는 형태의 기여 주장이 가능하다.

## 실증적 쟁점과 미해결 질문

1. **퍼즐의 크기 자체의 불확실성**: 6%p는 1889–1978(또는 –2000) 미국 실현수익률의 산술평균이다. 표본기간·기하/산술평균·생존편의·사전적 기대 보정(Fama-French 2002는 배당성장모형으로 사전적 프리미엄을 2.5~4.3%로 추정)에 따라 3~7%p까지 흔들린다. 한국은 표본이 짧고 구조변화(외환위기)가 커서 "설명해야 할 프리미엄"의 확정부터 쟁점이다.
2. **소비 자료의 측정 문제**: 총소비는 시간집계·내구재 포함 여부·계절조정으로 평활화되어 SDF 변동성을 과소평가할 수 있다. 개별 가계 자료는 반대로 측정오차가 커서 SDF 변동성을 과대평가할 수 있다(측정오차가 HJ 한계 통과를 '공짜로' 만들어주는 문제 — Brav et al. 2002의 핵심 논쟁점).
3. **결합 검정의 어려움**: 프리미엄(위험보상)과 무위험이자율(수준), 그리고 수익률 변동성(변동성 퍼즐, Shiller 1981 계열)을 동시에 맞추는 모형은 여전히 드물다. 단일 모멘트 개선만으로는 "해결" 주장이 성립하지 않는다.
4. **γ의 해석**: 요구 γ 30~50이 정말 "불합리"한가에 대한 논쟁(Kandel-Stambaugh 1991은 높은 γ 옹호). γ의 합리적 범위에 대한 실험·미시 증거와의 정합성 문제.
5. **HJ 한계의 통계적 추론**: 한계 자체의 표본오차를 반영한 공식 검정(표본 HJ 한계는 과대 기각 경향)이 필요하며, 한국처럼 짧은 표본에서는 특히 중요하다.

## 후속연구 아이디어 (이재준 논문 확장 방향)

1. **한국판 Brav-Constantinides-Geczy + HJ 한계 종합 실증**: 한국 가계 미시자료(가계동향조사, 한국노동패널, 재정패널)로 (i) 가계 소비증가율 횡단면 평균 SDF, (ii) 2·3차 모멘트(분산·왜도) 반영 SDF, (iii) 주식보유 가계 한정 SDF를 구성하고, 각각이 한국 주식프리미엄·무위험이자율·HJ 한계를 얼마나 개선하는지 단일 프레임으로 비교. 측정오차 보정(구간 추정, 준모수 보정)을 명시적으로 수행하면 국내 문헌 대비 명확한 신규 기여.
2. **가계 소비 위험의 경기역행성 검정**: Constantinides-Duffie (1996)의 이론 조건 — 개별 소비 충격의 횡단면 분산(및 음의 왜도)이 경기침체·주가하락기에 커지는가 — 을 한국 자료로 직접 검정하고, 이를 SDF에 삽입해 요구 γ가 얼마나 하락하는지 정량화. "한국에서 퍼즐이 약하다"는 기존 결론이 총소비 집계의 산물인지 판별하는 설계.
3. **주식시장 참가 제한과 이중 퍼즐**: 한국 가계의 낮은 직접 주식보유율을 이용해 참가가계 vs 비참가가계의 소비 기반 SDF를 분리 추정(Mankiw-Zeldes 1991의 한국판). 참가가계 소비가 주식수익률과 더 높은 공분산을 보이면, 프리미엄 퍼즐과 무위험이자율 퍼즐(Weil 1989)을 동시에 완화하는 경로로 저널 논문의 중심 결과가 될 수 있음.

---

### 참고 출처 (서지 검증에 사용한 주요 링크)

- Mehra & Prescott (1985): [ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/0304393285900613), [IDEAS/RePEc](https://ideas.repec.org/a/eee/moneco/v15y1985i2p145-161.html), [NBER w9512 (Mehra 2003)](https://www.nber.org/system/files/working_papers/w9512/w9512.pdf)
- Weil (1989): [IDEAS/RePEc](https://ideas.repec.org/a/eee/moneco/v24y1989i3p401-421.html), [NBER w2829](https://www.nber.org/papers/w2829)
- Hansen & Jagannathan (1991): [JPE](https://www.journals.uchicago.edu/doi/10.1086/261749), [저자 원문 PDF](https://larspeterhansen.org/wp-content/uploads/2016/11/ImplicationsofSecurityMarketData.pdf)
- Kocherlakota (1996): [EconPapers](https://econpapers.repec.org/RePEc:aea:jeclit:v:34:y:1996:i:1:p:42-71), [원문 PDF](https://faculty.econ.ucdavis.edu/faculty/kdsalyer/LECTURES/Ecn200e/Kocherla.pdf)
- Lucas (1978): [Econometric Society](https://www.econometricsociety.org/publications/econometrica/1978/11/01/asset-prices-exchange-economy), [IDEAS/RePEc](https://ideas.repec.org/a/ecm/emetrp/v46y1978i6p1429-45.html)
- Breeden (1979): [원문 PDF](https://static.secure.website/wscfus/8149792/uploads/Breeden_1979_JFE_Consumption_CAPM_Theory.pdf)
- Hansen & Singleton (1983): [JPE](https://www.journals.uchicago.edu/doi/abs/10.1086/261141), [IDEAS/RePEc](https://ideas.repec.org/a/ucp/jpolec/v91y1983i2p249-65.html)
- Mehra & Prescott (2003): [ASU](https://asu.elsevierpure.com/en/publications/chapter-14-the-equity-premium-in-retrospect/), [NBER w9525](https://www.nber.org/papers/w9525), [원문 PDF](https://www.academicwebpages.com/preview/mehra/pdf/epp_retrospect.pdf)
- Cochrane (2005): [Princeton University Press](https://press.princeton.edu/books/hardcover/9780691121376/asset-pricing)
- 김인수·홍정훈 (2008): [KCI](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART001232056), [DBpia](https://www.dbpia.co.kr/Journal/articleDetail?nodeId=NODE10916457), [국회도서관](https://dlps.nanet.go.kr/SearchDetailView.do?cn=KINX2008076515&sysid=nhn)
- 한국 관련 추가: [한국 자본시장의 주식프리미엄과 위험회피계수 추정 (KCI)](https://www.kci.go.kr/kciportal/landing/article.kci?arti_id=ART001300946), [전망이론효용과 주식프리미엄 퍼즐 (KCI)](https://www.kci.go.kr/kciportal/ci/sereArticleSearch/ciSereArtiView.kci?sereArticleSearchBean.artiId=ART002903940)
