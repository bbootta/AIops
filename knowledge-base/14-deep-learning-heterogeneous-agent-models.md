# 딥러닝을 이용한 이질적 주체·불완전시장 모형 풀이 (Deep Learning for Solving Heterogeneous-Agent Models)

> 주제 14 | 리스크프리미엄 퍼즐 해결 에이전트 연구팀 지식베이스
> 기반 논문: 이재준(성균관대 석사논문), 「개별가계소비자료를 이용한 자산가격결정」

## 개요

리스크프리미엄 퍼즐에 대한 유력한 해답인 가계 이질성·불완전시장 접근(Constantinides-Duffie 1996, Krusell-Smith 1997/1998, Heaton-Lucas 등)은 이론적으로는 매력적이지만, 실제로 모형을 "풀어서" 정량적 프리미엄 함의를 내는 단계에서 차원의 저주(curse of dimensionality)에 부딪힌다. 상태변수가 가계별 자산·소득의 전체 분포이기 때문에 상태공간이 무한(또는 초고차원)이고, 전통적 격자 기반 방법은 Krusell-Smith처럼 분포를 소수의 모멘트로 근사하는 강한 절단에 의존해 왔다. 이 절단이 바로 "근사된 총량법칙(approximate aggregation)"이 성립하는 모형에서만 작동하는데, 프리미엄 퍼즐 해결에 필요한 것은 정반대로 분포의 꼬리·역행적(countercyclical) 특이위험이 자산가격에 강하게 작용하는, 즉 총량법칙이 깨지는 모형이다. 2018년 이후 딥러닝 기반 해법(Deep BSDE, 딥 균형망, DeepHAM, EMINN 등)은 신경망의 고차원 함수근사 능력과 시뮬레이션 기반 확률적 경사하강을 결합해 이 저주를 실질적으로 우회했고, 수백~수천 차원의 이질적 주체 모형을 전역적(global)·비선형적으로 풀 수 있게 만들었다. 이는 Constantinides-Duffie류의 "소비 특이위험이 프리미엄을 만든다"는 가설을 자기보험·포트폴리오 선택이 내생화된 완결 균형 모형 안에서 정량 검증할 수 있는 도구가 생겼음을 의미한다. 나아가 신경망 대리모형(surrogate)을 이용한 구조 추정은 이질적 주체 모형의 파라미터를 실제 미시자료(가계 소비·자산 패널)로 직접 추정하는 길을 열었다. 따라서 이 갈래는 이재준 논문이 실증적으로 보인 "가계 소비 분포의 고차 모멘트와 자산수익률의 관계"를, 한국 가계 데이터로 보정한 불완전시장 모형을 실제로 풀어 이론-실증을 왕복 검증하는 저널급 확장의 핵심 방법론 기반이다.

## 핵심 논문

### Maliar, Maliar & Winant (2021), "Deep Learning for Solving Dynamic Economic Models", Journal of Monetary Economics

- **서지**: Journal of Monetary Economics, Vol. 122, pp. 76–101.
- **핵심 질문**: 고차원 이질적 주체 모형을 포함한 임의의 동태 경제모형을 하나의 통일된 딥러닝 프레임으로 풀 수 있는가?
- **방법론**: 모든 동태 모형을 "참해에서 0이 되는 기대조건(expectation conditions)의 집합"으로 재정식화하고, 이를 종속변수가 0인 비선형 회귀식으로 변환한다. 정책함수·가치함수를 심층신경망으로 매개변수화하고, 시뮬레이션된 경로(all-in-one expectation operator) 위에서 기대잔차제곱을 확률적 경사하강(SGD)으로 최소화한다. 세 가지 목적함수 변형 — 오일러 잔차 최소화(Euler-residual), 벨만 잔차 최소화, 생애효용 직접 극대화(lifetime reward) — 을 제시하고 Krusell-Smith 모형에 적용해 비교했다.
- **주요 결과**: 에이전트 수십 명 규모(수백 차원 상태공간)의 Krusell-Smith 모형을 분포 절단 없이 전역적으로 풀었다. 시뮬레이션 기반 훈련 덕분에 계산이 "에르고딕 집합" 근방에 집중되어 차원의 저주가 완화됨을 보였다. 오늘날 딥러닝 거시 해법 문헌의 사실상 표준 출발점.
- **한계**: 예시 모형은 여전히 실물(RBC) 중심이며 자산가격·포트폴리오 선택(다자산) 문제는 다루지 않았다. SGD 수렴의 이론적 보장이 약하고, 해의 정확도 검증이 잔차 기반 진단에 의존한다.
- **이재준 논문 디벨롭과의 연관성**: 이재준 논문의 실증(가계 소비 분포 모멘트로 SDF를 구성)에 대응하는 이론 모형 — 특이소득위험이 있는 불완전시장 자산가격 모형 — 을 실제로 풀 때 가장 범용적인 출발 도구다. 특히 "기대조건 = 0" 정식화는 가계별 오일러 방정식을 그대로 손실함수로 쓰므로, 논문의 실증 오일러 방정식 추정과 모형 풀이가 같은 수식 위에서 만난다.

### Azinovic, Gaegauf & Scheidegger (2022), "Deep Equilibrium Nets", International Economic Review

- **서지**: International Economic Review, Vol. 63(4), pp. 1471–1525. 코드 공개(GitHub: sischei/DeepEquilibriumNets).
- **핵심 질문**: 상당한 이질성·불확실성·간헐적 구속 제약(occasionally binding constraints)을 가진 모형의 함수적 합리적 기대균형을 어떻게 계산하는가?
- **방법론**: 딥 균형망(DEQN) — 신경망이 시뮬레이션된 경제 경로 위에서 모든 균형조건(오일러 방정식, 시장청산, KKT 조건)을 동시에 만족하도록 비지도(unsupervised) 방식으로 훈련된다. 사전에 해를 알 필요 없이 균형조건 잔차 자체가 손실함수.
- **주요 결과**: 대표 응용으로 총위험과 유동성제약이 있는 대규모 중첩세대(OLG) 생애주기 모형 — 수십 개 연령 코호트, 위험자산·무위험채권 포트폴리오 선택 포함 — 을 전역적으로 풀었다. 간헐적 구속 제약(차입제약, ZLB류)을 KKT/Fischer-Burmeister 재정식화로 정확히 처리함을 보였다.
- **한계**: 훈련 안정성이 초매개변수(학습률, 표본화 방식)에 민감하며, 상태분포가 훈련 중 이동하는 문제(비정상 데이터)에 대한 체계적 해법은 후속 연구로 미뤄졌다.
- **이재준 논문 디벨롭과의 연관성**: 프리미엄 퍼즐의 핵심 재료인 (i) 차입제약, (ii) 생애주기 소득위험, (iii) 주식-채권 포트폴리오 선택을 모두 갖춘 모형을 풀 수 있는 검증된 공개 코드가 있다. 이재준 논문에서 관찰한 한국 가계의 연령·자산분포별 소비위험 노출을 DEQN 기반 OLG 모형에 이식하면 "한국형 프리미엄 정량 모형"의 가장 현실적인 구현 경로가 된다.

### Han, Yang & E (2026), "DeepHAM: A Global Solution Method for Heterogeneous Agent Models with Aggregate Shocks", Quantitative Economics

- **서지**: Quantitative Economics, Vol. 17(2), pp. 297–341 (arXiv:2112.14377, 2021년 최초 공개). 저자: Jiequn Han, Yucheng Yang, Weinan E.
- **핵심 질문**: 총량충격이 있는 고차원 이질적 주체 모형의 전역해를 효율적·해석가능하게 구하는 방법은?
- **방법론**: 상태분포를 신경망이 학습한 "최적 일반화 모멘트(optimal generalized moments)"로 근사 — Krusell-Smith의 1차 모멘트 절단을 데이터 주도로 일반화한 것. 가치·정책함수를 신경망으로 근사하고 시뮬레이션 경로 위에서 목적함수(생애효용)를 직접 최적화한다.
- **주요 결과**: Krusell-Smith 모형과 전역 비선형성이 강한 변형에서 기존 방법 대비 정확도·속도 우위. "이질성이 거시에 언제·어떻게 중요한가"를 학습된 모멘트로 해석할 수 있음을 보임. 경쟁균형뿐 아니라 사회계획자 문제도 같은 틀로 풀 수 있다.
- **한계**: 모멘트 수를 늘릴 때의 수렴 보장이 없고, 자산가격(위험프리미엄) 응용은 논문 범위 밖이다.
- **이재준 논문 디벨롭과의 연관성**: 이재준 논문의 핵심 실증 질문 — "분포의 어떤 모멘트가 SDF에 유의하게 들어가는가?"(예: 소비증가율의 횡단면 분산·왜도) — 와 정확히 쌍대를 이룬다. DeepHAM이 학습한 최적 일반화 모멘트를 논문의 실증 모멘트(횡단면 분산·왜도)와 대조하면, "모형이 스스로 고른 프라이싱 팩터"와 "데이터가 고른 팩터"의 일치 여부라는 강력한 저널급 논증이 가능하다.

### Fernández-Villaverde, Hurtado & Nuño (2023), "Financial Frictions and the Wealth Distribution", Econometrica

- **서지**: Econometrica, Vol. 91(3), pp. 869–901 (NBER WP 26302; 2025년 Corrigendum 있음). 코드·인터랙티브 가이드 공개(GitHub: jesusfv/financial-frictions).
- **핵심 질문**: 금융마찰과 부의 분포가 상호작용할 때 총량-금융 변수 간 비선형 동학은 어떤 모습인가?
- **방법론**: 연속시간 이질적 가계 + 금융중개부문 모형. 총량법칙(PLM, perceived law of motion)을 선형회귀 대신 신경망으로 근사해 강한 비선형성을 포착 — 신경망이 실제 저널 게재 거시 논문의 해법 엔진으로 쓰인 대표 사례.
- **주요 결과**: 금융마찰이 만드는 강한 비선형성, 확정적 정상상태와 성질이 다른 복수의 확률적 정상상태(stochastic steady states), 상태의존적 일반화 충격반응, 레버리지가 높을수록 침체 후 회복이 느린 동학을 정량화했다.
- **한계**: 가계 이질성은 비교적 단순(1자산)이고 주식프리미엄 자체를 타깃하지 않았다. 신경망은 PLM 근사에 국한되며 정책함수는 전통적 방법으로 푼다(하이브리드).
- **이재준 논문 디벨롭과의 연관성**: "위험프리미엄은 상태의존적이며 분포(레버리지·부의 집중)가 그 상태변수"라는 메시지가 이재준 논문의 확장 방향과 직결된다. 한국 가계 부채·자산 분포(가계금융복지조사)를 상태변수로 넣은 모형에서 위기 국면 프리미엄 급등을 설명하는 설계의 청사진이자, "신경망 PLM"이라는 계산적으로 가장 보수적(심사자 친화적)인 딥러닝 도입 방식의 선례다.

### Duarte, Duarte & Silva (2024), "Machine Learning for Continuous-Time Finance", Review of Financial Studies

- **서지**: Review of Financial Studies, Vol. 37(11), pp. 3217–3271 (Editor's Choice). 저자: Victor Duarte, Diogo Duarte, Dejanir Silva. (SSRN 최초 공개 2018)
- **핵심 질문**: 고차원 비선형 연속시간 금융 모형(자산가격·기업금융·포트폴리오 선택)을 딥러닝으로 풀 수 있는가?
- **방법론**: 가치·정책함수를 신경망으로 근사하고, 자동미분 + 이토 보조정리(Ito's lemma) 조합으로 조건부 기대(무한소 생성작용소)를 몬테카를로 없이 정확히 계산한다. 이 비용이 상태변수 수와 무관해 차원의 저주가 기대 계산 단계에서 제거된다.
- **주요 결과**: 자산가격(장기위험 모형 포함), 기업금융, 다자산 포트폴리오 선택 등 기존에 못 풀던 고차원 문제를 풀고 새로운 경제적 함의를 도출. 금융 분야 top-3 저널이 딥러닝 해법을 정면으로 승인한 이정표.
- **한계**: 연속시간·확산과정 구조에 특화되어 이산시간 미시 패널과의 직접 연결에는 변환이 필요하다. 이질적 주체 일반균형보다는 단일 의사결정자/대표 프라이서 문제 중심.
- **이재준 논문 디벨롭과의 연관성**: 자산가격 저널 심사 관행에서 "딥러닝 해법의 수용 가능성"을 입증한 선례로 인용 가치가 크다. 방법적으로는 이재준 논문을 연속시간 불완전시장 모형(예: 특이소득위험 + 포트폴리오 선택)으로 확장할 때 기대연산 처리의 표준 기법을 제공한다.

### Gopalakrishna (2021, 개정판 Gopalakrishna & Wu), "ALIENs for Continuous Time Economies", Swiss Finance Institute Research Paper 21-34

- **서지**: SSRN 3848657 (SFI Research Paper 21-34). 최신 버전은 Yuntao Wu와 공저, Deep-Macrofin+ 라이브러리 동반.
- **핵심 질문**: 총량충격·자유경계(free boundary)·강한 비선형성을 가진 연속시간 이질적 주체 자산가격 모형(Brunnermeier-Sannikov, He-Krishnamurthy 계열)을 안정적으로 푸는 법은?
- **방법론**: ALIENs(Actively Learned and Informed Equilibrium Nets) — 시간전진(time-stepping)으로 비선형 문제를 축약사상(contraction mapping)의 연쇄로 바꿔 수렴을 안정화하고, 능동학습(active learning)으로 경제적으로 중요한 상태영역(위기 영역 등)에 계산을 집중한다. 경제 정보를 정칙화항(regularizer)으로 인코딩.
- **주요 결과**: 자유경계가 있는 이질적 주체 모형부터 고차원 자산가격 모형까지 검증. 순수 PINN 방식이 실패하는 거시금융 균형 PDE에서 수렴을 확보했다. 동반 라이브러리로 재현성 제공.
- **한계**: 워킹페이퍼 단계(저널 게재 전)이며, 이질성이 "전문가 vs 가계" 2유형 중심 — 연속 분포 가계 이질성으로의 확장은 별도 작업이 필요하다.
- **이재준 논문 디벨롭과의 연관성**: 프리미엄이 폭등하는 위기 영역은 에르고딕 분포에서 드물게 방문되므로 시뮬레이션 기반 방법이 그 영역을 잘 못 배운다는 문제를, 능동학습으로 정면 해결한다. 이재준 논문 확장에서 "위기 시 소비 특이위험 급증 → 프리미엄 급등"의 비선형 구간을 정확히 풀려면 이 표본화 전략이 사실상 필수다.

### Gopalakrishna (2022 JMP), "A Macro-Finance Model with Realistic Crisis Dynamics", Working Paper

- **서지**: Princeton BCF/EPFL 잡마켓 페이퍼(2022). 동반 방법론 논문은 위 ALIENs.
- **핵심 질문**: 위기의 깊이(높은 위험프리미엄, 산출 급락)와 지속성(느린 회복)을 동시에 맞추는 거시금융 모형은 가능한가?
- **방법론**: 확률적 생산성과 상태의존적 퇴출(exit)을 가진 레버리지 금융중개인이 있는 중첩세대·불완전시장 자산가격 모형을 딥러닝(경제 정보를 정칙화항으로 인코딩)으로 전역해를 구함.
- **주요 결과**: 산출 급락, 높은 위험프리미엄, 중개기능 위축, 장기 침체라는 위기의 실증적 특징을 정량적으로 재현. 이 특징이 없는 모형은 증폭 vs 지속성 간 트레이드오프에 갇힘을 보임.
- **한계**: 여전히 워킹페이퍼이며 가계 측 이질성은 단순화되어 있다. 무조건부(평시) 주식프리미엄 퍼즐보다는 위기 동학에 초점.
- **이재준 논문 디벨롭과의 연관성**: "프리미엄의 시변성·상태의존성"을 딥러닝 전역해로 정량화한 실전 사례. 이재준 논문의 시계열 확장(한국 외환위기·금융위기·코로나 국면에서 횡단면 소비위험과 프리미엄의 공변동)을 모형 안에서 재현하는 벤치마크 설계로 삼을 수 있다.

### Gu, Laurière, Merkel & Payne (2024), "Global Solutions to Master Equations for Continuous Time Heterogeneous Agent Macroeconomic Models", arXiv:2406.13726 / JPE Macroeconomics 게재확정

- **서지**: arXiv:2406.13726, SSRN 4871228. 2026년 2월 기준 Journal of Political Economy Macroeconomics 게재확정.
- **핵심 질문**: 총량충격이 있는 연속시간 이질적 주체 경제의 균형을 특징짓는 마스터 방정식(master equation) — 분포를 상태변수로 갖는 무한차원 PDE — 의 전역해를 어떻게 구하는가?
- **방법론**: 분포를 (i) 유한 에이전트 이산화, (ii) 상태변수 이산화, (iii) 기저함수 투영 세 방식으로 유한차원화한 뒤, 가치함수를 신경망으로 표현하고 미분방정식 잔차를 최소화하는 EMINN(Economic Model Informed Neural Network)으로 훈련. 평균장게임(mean-field games) 수학과 거시경제학을 연결.
- **주요 결과**: Krusell-Smith, HANK류 등 표준 모형에서 세 근사법을 체계 비교. 마스터 방정식 접근이 순차적 몬테카를로 없이도 분포 의존적 가격함수를 직접 학습할 수 있음을 보임.
- **한계**: 신경망이 마스터 방정식의 참해(viscosity solution)로 수렴한다는 이론 보장은 부분적이며, 분포 근사 방식 간 우열이 모형 의존적.
- **이재준 논문 디벨롭과의 연관성**: SDF가 "분포의 함수"임을 가장 원리적으로 정식화한 틀. 이재준 논문의 실증 SDF(분포 모멘트의 함수)를 마스터 방정식 균형의 가격커널과 직접 비교할 수 있어, 실증 → 이론 정합성 검증의 최상위 벤치마크가 된다. 평균장게임 수학 기반이라 방법론적 엄밀성 어필에도 유리하다.

### Ebrahimi Kahou, Fernández-Villaverde, Perla & Sood (2021), "Exploiting Symmetry in High-Dimensional Dynamic Programming", NBER Working Paper 28981

- **서지**: NBER WP 28981 / CEPR DP16285 / SSRN 3875995.
- **핵심 질문**: 유한하지만 많은 수(N)의 이질적 주체가 있는 동적계획·재귀경쟁균형을 차원의 저주 없이 푸는 구조적 원리는 무엇인가?
- **방법론**: 네 가지 상보적 기법 — (1) 총량법칙·가치함수의 교환대칭성(permutation symmetry/invariance)을 신경망 구조에 내장, (2) 측도집중(concentration of measure)으로 고차원 기대를 단일 몬테카를로 추출로 계산, (3) 관심 다양체(manifold)에 맞춘 표본화, (4) 과매개변수화 신경망의 일반화 성질을 이용해 정상분포 계산·횡단조건 부과 없이 해 선택.
- **주요 결과**: Lucas-Prescott(1971) 불확실성하 투자 모형의 다기업 버전을 전역적으로 풀었다. 대칭성 내장이 표본 효율을 극적으로 높임을 입증 — 이후 permutation-invariant 아키텍처(DeepSet류)가 이질적 주체 딥러닝의 표준 부품이 됨.
- **한계**: 응용이 기업 투자 모형이며 총량충격·자산가격은 미포함. "심층학습이 어떤 해를 고르는가"(implicit bias)의 경제학적 해석은 열린 문제로 남김.
- **이재준 논문 디벨롭과의 연관성**: 가계 수천 가구의 분포를 상태로 갖는 모형에서 "가구는 교환가능하다"는 대칭성은 한국 가계패널을 모형에 넣을 때 그대로 성립한다. 확장 모형의 신경망 설계 시 이 논문의 대칭성 내장 아키텍처를 쓰면 훈련 비용을 자릿수 단위로 절감할 수 있다.

### Han, Jentzen & E (2018), "Solving High-Dimensional Partial Differential Equations Using Deep Learning", PNAS

- **서지**: Proceedings of the National Academy of Sciences, Vol. 115(34), pp. 8505–8510. DOI: 10.1073/pnas.1718942115.
- **핵심 질문**: 수백 차원의 (반)선형 포물형 PDE를 수치적으로 푸는 것이 가능한가?
- **방법론**: Deep BSDE — PDE를 후방확률미분방정식(BSDE)으로 재정식화하고, 미지해의 기울기(gradient)를 신경망으로 근사해 시간 이산화된 경로 위에서 종말조건 오차를 최소화. 기울기가 정책함수 역할을 하는 심층강화학습과 구조적으로 유사.
- **주요 결과**: 100차원 비선형 Black-Scholes(부도위험 포함), HJB, Allen-Cahn 방정식을 실용적 정확도로 풀었다. "고차원 PDE는 못 푼다"는 통념을 깬 이 분야 전체의 원류 논문.
- **한계**: 경제 균형 문제(고정점·시장청산이 얽힌)로의 직접 적용은 비자명하며, 전역해가 아닌 특정 초기점 기준 해를 준다는 제약이 있다(이후 변형들이 보완).
- **이재준 논문 디벨롭과의 연관성**: 딥러닝-거시금융 문헌 전체의 수학적 기초로, 방법론 섹션의 계보 서술에 필수 인용. 연속시간 불완전시장 모형의 가계 HJB를 고차원에서 푸는 백엔드 기술이며, "차원의 저주를 딥러닝이 왜 피할 수 있는가"에 대한 이론적 근거(BSDE 재정식화 + 신경망 근사) 제공.

### Kase, Melosi & Rottner (2022, 개정 2025), "Estimating Nonlinear Heterogeneous Agent Models with Neural Networks", CEPR DP17391 / BIS WP 1241

- **서지**: CEPR Discussion Paper 17391, Chicago Fed WP 2022-26, BIS Working Paper 1241(2025년 1월). 저자: Hanno Kase, Leonardo Melosi, Matthias Rottner.
- **핵심 질문**: 이질성·비선형 제약(ZLB)·총량 불확실성을 모두 가진 모형을 전역적으로 풀고 동시에 실제 데이터로 추정할 수 있는가?
- **방법론**: 신경망으로 모형을 전역해로 풀되, 구조 파라미터 자체를 신경망 입력에 포함시켜(surrogate/대리모형) 파라미터 공간 전체에서 한 번에 해를 학습 → 우도 기반 추정 시 파라미터가 바뀔 때마다 다시 풀 필요가 없다.
- **주요 결과**: 시뮬레이션 데이터에서 ZLB 제약이 있는 비선형 HANK 모형의 파라미터를 정확히 복원. 미국 데이터로 실제 추정했으며, ZLB와 특이소득위험의 상호작용이 총산출 변동성의 핵심 원천임을 발견.
- **한계**: 추정 대상 모멘트가 거시 총량 시계열 중심이고, 미시 횡단면 모멘트(분포 자료)를 우도에 통합하는 일반 절차는 미완.
- **이재준 논문 디벨롭과의 연관성**: 이재준 논문을 "실증 논문"에서 "구조 추정 논문"으로 승격시키는 직접 경로. 파라미터-포함 신경망 대리모형을 쓰면 한국 가계 소비 패널의 횡단면 모멘트 + 주식프리미엄 시계열을 동시에 타깃하는 SMM/우도 추정이 계산적으로 가능해진다. 이것이 저널 디벨롭의 가장 차별적인 기여 후보다.

### Valaitis & Villa (2024), "A Machine Learning Projection Method for Macro-Finance Models", Quantitative Economics

- **서지**: Quantitative Economics, Vol. 15(1) (2024). SSRN 3209934/4119888.
- **핵심 질문**: 다수 자산(만기)·다중공선성 때문에 전통적 PEA(parameterized expectations algorithm)가 실패하는 거시금융 모형을 어떻게 푸는가?
- **방법론**: 최적성 조건 안의 조건부 기대를 신경망으로 근사하는 시뮬레이션 기반 PEA. 신경망의 정칙화 성질이 시뮬레이션 데이터의 다중공선성을 자연스럽게 처리함을 보임.
- **주요 결과**: 4개 만기 국채가 있는 최적 부채관리 문제를 풀어, 중기 만기의 능동적 역할과 지출충격 대응에서의 재정수익 확보 메커니즘을 발견. 채권 위험프리미엄이 내생적으로 움직이는 모형을 다뤘다.
- **한계**: 이질적 가계보다는 정부(계획자) 문제 중심이고, 주식프리미엄이 아닌 국채 만기구조가 초점.
- **이재준 논문 디벨롭과의 연관성**: 다자산(주식+채권+예금) 불완전시장 모형에서 가계 포트폴리오 오일러 방정식의 기대항을 근사할 때 만나는 다중공선성 문제 — 자산수익률들이 강하게 공행 — 의 해법을 제공한다. 한국 가계의 실제 자산구성(부동산 편중, 예금 우위)을 반영한 다자산 확장에 실무적으로 유용.

### Zheng, Trott, Srinivasa, Parkes & Socher (2022), "The AI Economist: Taxation Policy Design via Two-Level Deep Multiagent Reinforcement Learning", Science Advances

- **서지**: Science Advances, Vol. 8, eabk2607 (2022년 5월). DOI: 10.1126/sciadv.abk2607.
- **핵심 질문**: 경제주체와 정책당국이 공진화(co-adapt)하는 환경에서 강화학습으로 최적 조세정책을 설계할 수 있는가?
- **방법론**: 2단계 심층 다중에이전트 강화학습 — 하위 레벨에서 노동·거래·건설을 학습하는 AI 노동자 에이전트들, 상위 레벨에서 평등-생산성 가중 사회후생을 극대화하는 정부 RL 에이전트. 커리큘럼 학습으로 이중 학습의 불안정성을 제어.
- **주요 결과**: 학습된 세제가 Saez 공식 등 해석적 기준을 평등-생산성 트레이드오프에서 파레토 지배. 합리적 기대·균형 가정 없이 시뮬레이션만으로 정책 함의를 도출하는 에이전트 기반 대안 패러다임 제시.
- **한계**: 게임 환경이 양식화(stylized)되어 실증 보정과 거리가 있고, 학습된 행동이 균형 개념(재귀경쟁균형)과 어떤 관계인지 불명확. 자산시장이 없다.
- **이재준 논문 디벨롭과의 연관성**: "합리적 기대 균형을 푸는" 주류 접근의 대척점으로, 제한적 합리성·학습하는 가계가 있는 경제에서 프리미엄이 어떻게 형성되는지 실험할 수 있는 틀이다. 연구팀의 "퍼즐 해결 에이전트" 비전(AI 에이전트로 모형 탐색 자동화)과 방법적으로 가장 가까운 계열이며, 프리미엄 퍼즐의 행동적(behavioral) 채널 탐색용 보조 도구로 위치시킬 수 있다.

### Fernández-Villaverde, Nuño & Perla (2024), "Taming the Curse of Dimensionality: Quantitative Economics with Deep Learning", NBER Working Paper 33117

- **서지**: NBER WP 33117 / SSRN 5030252 / Banco de España WP 2444.
- **핵심 질문**: 왜, 그리고 어떤 조건에서 딥러닝이 정량경제학의 차원의 저주를 길들이는가? (서베이 + 방법론 통합)
- **방법론**: 동태 균형모형 풀이의 고유한 난점(균형 고정점, 횡단조건, 해의 다중성)을 정리하고, 확률적 신고전파 성장모형을 신경망으로 풀어 전통 해법과 체계 비교. 신경망의 암묵적 편향(implicit bias)과 일반화가 왜 경제모형 해법에 유리한지 논증.
- **주요 결과**: 딥러닝 해법의 성공·실패 조건을 정리한 현 시점 최고 수준의 로드맵. "신중한 낙관론"과 함께 응용 문헌 전반을 계보화.
- **한계**: 서베이 성격상 새 정리는 제한적이며, 자산가격 응용의 정확도 진단(오일러 잔차가 프리미엄 오차로 어떻게 전파되는가)은 열린 문제로 남긴다.
- **이재준 논문 디벨롭과의 연관성**: 저널 논문의 방법론·문헌 섹션을 조직하는 표준 참고문헌. 특히 "프리미엄은 해의 미세한 비선형성에 민감하므로 해법 정확도가 곧 경제적 결론을 좌우한다"는 논지를 세울 때, 이 서베이의 정확도 진단 논의가 프레이밍의 근거가 된다.

## 실증적 쟁점과 미해결 질문

1. **해법 정확도와 프리미엄의 민감성**: 주식프리미엄은 SDF의 고차 모멘트에 의해 결정되므로, 오일러 잔차 기준 10⁻³~10⁻⁴ 수준의 근사 오차가 프리미엄 추정에서는 수십 bp의 오차로 증폭될 수 있다. 딥러닝 해법의 잔차 진단이 "가격 함의의 오차"로 어떻게 번역되는지에 대한 표준이 아직 없다.
2. **드문 상태(위기 영역)의 학습 문제**: 시뮬레이션 기반 훈련은 에르고딕 분포를 따라 표본을 뽑으므로, 프리미엄을 실제로 만들어내는 드문 재난·위기 상태를 과소 학습한다. Gopalakrishna의 능동학습이 부분 해답이지만, 어떤 표본화가 프리미엄 정량화에 최적인지는 미해결.
3. **총량법칙 붕괴의 정량화**: Krusell-Smith의 "근사 총량화"가 성립하면 이질성은 프리미엄에 거의 기여하지 못한다(퍼즐 미해결). 딥러닝은 총량화가 깨지는 모형(역행적 특이위험, 제약 밀착 가계 비중 변동)을 풀 수 있게 했지만, "얼마나 깨져야 프리미엄 6%가 나오는가"의 체계적 지도는 아직 없다.
4. **미시 모멘트를 이용한 구조 추정의 통합**: Kase-Melosi-Rottner류 대리모형 추정은 거시 시계열 중심이다. 가계 패널의 횡단면 분포 모멘트(이재준 논문의 데이터)를 우도/GMM에 정식으로 통합하는 절차 — 특히 측정오차가 큰 소비자료의 처리 — 는 열린 문제다.
5. **해의 다중성과 신경망의 암묵적 선택**: 불완전시장 모형은 균형이 유일하지 않을 수 있는데, SGD로 훈련된 신경망이 "어떤" 균형을 고르는지(횡단조건을 암묵적으로 부과하는지) 이론이 불완전하다. 자산가격 함의가 균형 선택에 의존한다면 심각한 문제.
6. **검증(validation) 관행의 부재**: 전통 방법과 교차검증 가능한 저차원 벤치마크 밖에서, 딥러닝 해의 정확성을 독립적으로 확인할 표준 프로토콜(예: 이중 해법, 사후 오일러 잔차의 상태별 분해)이 정착되지 않았다.

## 후속연구 아이디어

1. **한국 가계자료로 보정한 불완전시장 모형의 딥러닝 전역해와 프리미엄 정량화**: 이재준 논문에서 추정한 한국 가계 소비증가율의 횡단면 분산·왜도의 경기역행성(가계동향조사/가계금융복지조사 기반)을 특이위험 과정으로 보정한 Constantinides-Duffie/Krusell-Smith 혼합 모형을 DEQN 또는 DeepHAM으로 풀어, 모형이 내생적으로 산출하는 주식프리미엄·무위험이자율을 한국 데이터(KOSPI 초과수익률)와 대조한다. 핵심 검증: "실증에서 관찰된 특이위험의 크기가, 자기보험과 포트폴리오 선택을 허용한 완결 균형에서도 프리미엄을 얼마나 설명하는가."
2. **신경망 대리모형 기반 구조 추정으로의 승격**: Kase-Melosi-Rottner 방식대로 구조 파라미터(위험회피도, 특이위험의 경기민감도, 차입제약 강도)를 신경망 입력에 포함해 파라미터 공간 전체의 해를 한 번에 학습한 뒤, 한국 가계 패널의 횡단면 모멘트와 프리미엄 시계열을 동시 타깃하는 SMM 추정을 수행한다. 이는 이재준 논문의 축약형 오일러 방정식 추정을 완전 구조 추정으로 확장해 저널급 기여(방법+실증)를 만든다.
3. **DeepHAM 최적 일반화 모멘트와 실증 프라이싱 팩터의 대조 실험**: DeepHAM으로 모형을 풀 때 학습되는 "가격결정에 충분한 분포 모멘트"를 추출해, 이재준 논문의 실증에서 유의했던 횡단면 모멘트(분산·왜도)와 일치하는지 검정한다. 일치하면 "데이터가 고른 팩터 = 모형이 고른 팩터"라는 강한 정합성 논거, 불일치하면 모형 재설계의 진단 정보가 된다. 부수적으로, 위기 영역 정확도를 위해 Gopalakrishna식 능동학습 표본화를 결합해 위기 국면(1998, 2008, 2020) 프리미엄 급등의 재현 여부를 별도 보고한다.

---

### 참고 링크 (서지 검증 출처)

- Maliar, Maliar & Winant (2021): [Stanford PDF](https://web.stanford.edu/~maliars/Files/JME2021.pdf), [EconPapers](https://econpapers.repec.org/RePEc:eee:moneco:v:122:y:2021:i:c:p:76-101)
- Azinovic, Gaegauf & Scheidegger (2022): [Wiley](https://onlinelibrary.wiley.com/doi/full/10.1111/iere.12575), [GitHub](https://github.com/sischei/DeepEquilibriumNets)
- Han, Yang & E (DeepHAM): [arXiv:2112.14377](https://arxiv.org/abs/2112.14377), [Quantitative Economics](https://www.econometricsociety.org/publications/quantitative-economics/2026/05/01/DeepHAM-A-Global-Solution-Method-for-Heterogeneous-Agent-Models-with-Aggregate-Shocks)
- Fernández-Villaverde, Hurtado & Nuño (2023): [Econometrica](https://www.econometricsociety.org/publications/econometrica/2023/05/01/Financial-Frictions-and-the-Wealth-Distribution), [GitHub](https://github.com/jesusfv/financial-frictions)
- Duarte, Duarte & Silva (2024): [RFS](https://academic.oup.com/rfs/article-abstract/37/11/3217/7749384), [SSRN](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3012602)
- Gopalakrishna (ALIENs): [SSRN 3848657](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3848657), [최신 버전 PDF](https://goutham-atwork.github.io/assets/pdf/paper2.pdf)
- Gopalakrishna (JMP): [Princeton BCF PDF](https://bcf.princeton.edu/wp-content/uploads/2022/09/jmp.pdf)
- Gu, Laurière, Merkel & Payne: [arXiv:2406.13726](https://arxiv.org/abs/2406.13726), [SSRN 4871228](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4871228)
- Kahou, Fernández-Villaverde, Perla & Sood (2021): [NBER w28981](https://www.nber.org/papers/w28981)
- Han, Jentzen & E (2018): [OSTI/PNAS](https://www.osti.gov/pages/biblio/1540276)
- Kase, Melosi & Rottner: [CEPR DP17391](https://cepr.org/publications/dp17391), [BIS WP 1241](https://www.bis.org/publ/work1241.pdf), [Chicago Fed WP 2022-26](https://www.chicagofed.org/publications/working-papers/2022/2022-26)
- Valaitis & Villa (2024): [Quantitative Economics](https://www.econometricsociety.org/publications/quantitative-economics/2024/01/01/A-Machine-Learning-Projection-Method-for-Macro-Finance-Models), [Wiley](https://onlinelibrary.wiley.com/doi/full/10.3982/QE1403)
- Zheng et al. (2022): [Science Advances](https://www.science.org/doi/10.1126/sciadv.abk2607)
- Fernández-Villaverde, Nuño & Perla (2024): [NBER w33117](https://www.nber.org/papers/w33117)
