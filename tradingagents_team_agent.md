# TradingAgents 팀 에이전트 (재조사 반영본)

이 문서는 `TauricResearch/TradingAgents` 저장소의 공개 문서(README 중심)를 기준으로 다시 작성한 **간결한 팀 에이전트 템플릿**입니다.

## 1) 확인된 프레임워크 구조

TradingAgents는 실제 트레이딩 조직을 모사한 다중 에이전트 구조를 사용하며, 기본 파이프라인은 아래 순서를 따릅니다.

1. **Analyst Team**
   - Fundamental Analyst
   - Sentiment Analyst
   - News Analyst
   - Technical Analyst
2. **Research Team**
   - Bull Researcher
   - Bear Researcher
   - (v0.2.4 기준) Research Manager 구조화 출력
3. **Trader**
4. **Risk Management Team**
5. **Portfolio Manager**

> 위 구조는 README의 프레임워크 설명/릴리즈 노트(구조화 출력 에이전트 추가) 기준으로 정리함.

## 2) 최소 실행 프로토콜

- 입력: `ticker`, `date`, `horizon`, `risk_budget`
- 라운드:
  1) Analyst Team 개별 보고
  2) Bull/Bear 상반 주장 정리
  3) Trader 단일 액션 제안
  4) **불일치 해소 라운드** (Bull과 Bear의 결론이 상충하고 confidence 격차가 0.15 이하일 때):
     - Research Manager 가 양측 thesis 와 risks 를 비교하고 critical assumptions 충돌을 표로 출력.
     - Trader 의 기본 액션은 HOLD. 단, Risk Manager 가 명시적으로 `bias_resolution: "bull"|"bear"` 를 사이즈 0 이상으로 승인한 경우에만 그 방향을 따른다.
  5) Risk Manager가 사이즈/손실 한도 조정
  6) Portfolio Manager 최종 승인/보류/거절

## 3) 공통 출력 스키마 (최소형)

```json
{
  "agent": "<role>",
  "ticker": "<symbol>",
  "action": "BUY|HOLD|SELL",
  "confidence": 0.0,
  "rationale": "...",
  "size": 0.0,
  "entry_price": null,
  "stop_loss": null,
  "time_horizon": "intraday|short|medium|long",
  "thesis": ["..."],
  "risks": ["..."],
  "invalidators": ["..."],
  "evidence": []
}
```

- `action`: BUY/SELL/HOLD 중 하나.
- `confidence`: 해당 결론에 대한 확신도.
- `rationale`: 단문 요약 (한 문장).
- `size`: 포트폴리오 대비 비중 (0.0~1.0). HOLD 의 경우 반드시 0.0.
- `entry_price`: 지정 진입가. HOLD 또는 시장가일 경우 null.
- `stop_loss`: 손절가. 미설정 시 null.
- `time_horizon`: intraday/short/medium/long 중 하나.
- `evidence`: 근거 출처 리스트 (선택).

> 소유권: `size` 와 `stop_loss` 는 **Risk Manager** 소유. Trader 는 제안하고 Risk Manager 가 조정한다. 포트폴리오 누적 `size` 에 대한 최종 권한은 **Portfolio Manager** 에 있다.

## 4) 역할 프롬프트 (최소형)

### Analyst Team 공통
"""
너는 {role}이다.
역할에 맞는 근거 3개 이내로 요약하고 action/confidence를 제시하라.
확실하지 않으면 HOLD를 선택하라.
출력은 JSON만.
"""

### Bull Researcher
"""
상승 시나리오 근거만 강화하라.
Bear 측 반론 2개를 반박하라.
출력은 JSON만.
"""

### Bear Researcher
"""
하락/회피 시나리오 근거만 강화하라.
Bull 측 주장 2개를 반박하라.
출력은 JSON만.
"""

### Trader
"""
Bull/Bear 결과를 합쳐 BUY/HOLD/SELL 중 하나를 선택하라.
진입 무효화 조건을 반드시 포함하라.
출력은 JSON만.
"""

### Risk Manager
"""
Trader 제안을 risk_budget 안으로 조정하라.
손실 한도 초과 가능성이 있으면 사이즈 축소 또는 HOLD로 변경하라.
출력은 JSON만.
"""

### Portfolio Manager
"""
최종 승인/보류/거절을 결정하라.
기대수익 대비 리스크가 불리하면 거절하라.
출력은 JSON만.
"""

## 5) 오케스트레이터 출력

```json
{
  "ticker": "",
  "final_action": "BUY|HOLD|SELL",
  "final_size": 0.0,
  "rationale": ["..."],
  "key_risks": ["..."],
  "invalidators": ["..."]
}
```

## 6) 조사 근거 링크

- GitHub Repo: https://github.com/TauricResearch/TradingAgents
- README(프레임워크/팀 구성): https://github.com/TauricResearch/TradingAgents/blob/main/README.md
- 릴리즈 노트(v0.2.4 언급): README의 News 섹션
