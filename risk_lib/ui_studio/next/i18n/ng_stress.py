"""위기상황·ICAAP 그룹(screens/stress.js) 카탈로그 (설계 사양 2.8장).

위기상황·거시지표 모니터링·시나리오 설정·역스트레스·ICAAP 인벤토리·
경영조치·제출 여섯 화면이 저자로서 새로 쓴 한국어 문자열만 여기 있다.
기존 카탈로그(i18n.py)와 셸 어휘(ng_frag·ng_gate·ng_shell), 다른 화면
모듈이 이미 가진 문구는 다시 적지 않고 그대로 쓴다.

**원장에서 오는 값은 없다.** 테이블명·컬럼 물리명·카탈로그 한글명·조문
인용·단계명(보통주자본비율·요구치 충족·PD (충격 후))·시나리오명(baseline·
adverse·severely_adverse)·지표명(실질 GDP 성장률)·제출 상태(draft·reviewed·
approved·submitted)는 화면이 원문 그대로 찍으며 이 사전에 넣지 않는다.
"""

from risk_lib.ui_studio.next.i18n_next import _t

MESSAGES: dict[str, dict[str, str]] = {}

_t("ng_stress",
   # 위기상황 (추적표)
   '{n}단계||{n} steps',
   '블록 {n}개 · 단계 {m}개||{n} blocks and {m} steps',
   '전이 단계||Transmission steps',

   # 거시지표 모니터링
   '통합위기상황분석 시나리오의 입력이 되는 거시·금융지표 {n}종이다. 부문별 최근값과 이탈 경보, 계열 추이, 그리고 시나리오 가정값이 어느 지표의 어떤 값에서 나왔는지를 같은 원장에서 읽는다.'
   '||These are the {n} macroeconomic and financial indicators that feed the integrated stress scenarios. The latest value per category, the deviation alerts, the series history and the ledger value each scenario assumption was derived from are all read from the same ledger.',
   '값의 근거는 {mix} 이다. 이 환경은 외부 통계로 나가는 통신이 막혀 있어 실측 피드가 없다. 출처 기관과 통계표 코드는 실제 계열을 가리키므로, 피드가 열리면 관측치만 교체하면 된다.'
   '||The basis of the values is {mix}. This environment has no outbound connection to external statistics, so there is no live feed. The source institution and series code point at real published series, so once a feed is opened only the observations need to be replaced.',
   '모니터링 지표||Monitored indicators',
   '관측치||Observations',
   '이탈 경보||Deviation alerts',
   '시나리오 연결||Scenario links',
   '임계 |z| {z} 이상||Threshold |z| at or above {z}',
   '전년동기대비는 1년 전 값 대비 비율 변화다. 수준이 %인 지표도 같은 기준으로 계산한다.'
   '||The year-on-year figure is the ratio change against the value one year earlier. Indicators whose level is a percentage are computed on the same basis.',
   '{n}기 · 주기 {freq} · 최근값 {v} · 전년동기대비 {yoy} · 출처 {src} {code} · 근거 {basis} · 움직이는 축 {drives}'
   '||{n} periods · frequency {freq} · latest {v} · year on year {yoy} · source {src} {code} · basis {basis} · drives {drives}',
   '이탈 경보. 최근값이 직전 구간 평균에서 표준편차의 {z}배만큼 떨어져 있다.'
   '||Deviation alert. The latest value sits {z} standard deviations away from the mean of the preceding window.',
   '시나리오 가정값은 최근 관측값에 배수와 그 지표의 분기 변동성을 곱해 더한 값이다. 배수를 표준편차 단위로 두는 이유는, 수준이 다른 지표를 같은 비율로 때리면 환율과 실업률이 같은 충격을 받은 셈이 되기 때문이다.'
   '||A scenario assumption is the latest observation plus the multiplier times that indicator quarterly volatility. The multiplier is held in standard deviation units because shocking indicators of different levels by the same percentage would treat the exchange rate and the unemployment rate as equally shocked.',
   '배수가 원장에 없는 지표 {n}종. 값을 채우지 않는다.'
   '||{n} indicators have no multiplier in the ledger. The value is not filled in.',
   '충격 없음. 관측값을 그대로 가정값으로 쓴다.'
   '||No shock. The observation is carried through as the assumption.',
   '{s} {n}행||{s}, {n} rows',
   '지표 목록·출처 코드·움직이는 축은 마스터 원장이 정한다. 화면과 엔진이 같은 원장을 읽으므로 지표를 늘리면 두 곳이 함께 바뀐다.'
   '||The indicator list, the source codes and the axis each indicator drives are set by the master ledger. The screen and the engine read the same ledger, so adding an indicator changes both at once.',

   # 시나리오 설정
   '충격 축 {n}종의 단위충격과 심도 구조를 편집해 변경 제안서를 만든다. 화면은 재계산하지 않는다. 시나리오 파라미터는 RWA·비율·판정 전체에 전이되므로, 적용은 파이프라인 재실행과 검증 두 층을 다시 거쳐야 한다.'
   '||Edit the unit shock and severity structure of the {n} shock axes to produce a change proposal. This screen does not recompute. Scenario parameters propagate through risk-weighted assets, ratios and the verdict, so applying them requires a pipeline rerun and both layers of validation again.',
   '현행 단위충격||Current unit shock',
   '제안 단위충격||Proposed unit shock',
   '유지||keep',
   '시나리오별 정점 심도||Peak severity by scenario',
   '분기별 심도는 정점까지 선형 상승한다||The quarterly severity rises linearly to the peak',
   '숫자가 아니다||not a number',
   '검증 실패||Input validation failed',
   '변경된 축이 없다||No axis was changed',
   '위기상황 시나리오 충격 축 변경||Stress scenario shock axis change',
   '신용파라미터부터 판정까지 전 단계||Every step from the credit parameters to the verdict',
   '업무보고서 위기상황 서식||The stress testing supervisory report form',
   '자본계획·회복계획 연계 경보||The capital plan and recovery plan linkage alert',
   '코드 반영||Land the change in code',
   '자체검증(2선) FAIL 0 확인||Confirm zero FAIL in self validation (second line)',
   '독립검증(3선) 재요청||Request independent validation again (third line)',
   '게이트 통과 후 결재||Approve only after the gate passes',
   '화면은 재계산하지 않는다||The screen does not recompute',
   '경로는 현행 파라미터의 산출 결과다. 제안은 이 경로를 바꾸지 않는다.'
   '||The path is the output of the current parameters. A proposal does not change this path.',

   # 역스트레스
   '대상 지표||Target metric',
   '임계 비율||Threshold ratio',
   '현행 비율||Current ratio',
   '수렴 여부||Convergence',
   '미수렴||not converged',
   '파열점 비율||Ratio at break',
   '파열점 위험가중자산||Risk-weighted assets at break',
   '파열점 기대신용손실||Expected credit loss at break',
   '역산은 자본 임계 비율을 목표로 심도를 이분 탐색해 얻는다. 파열점의 위험가중자산과 기대신용손실은 그 심도에서의 산출값이며, 함의 충격은 그 심도를 거시 축으로 환산한 값이다.'
   '||The inversion bisects on severity against the capital threshold ratio. The risk-weighted assets and expected credit loss at the break are the outputs at that severity, and the implied shock is that severity translated back onto the macro axis.',

   # ICAAP 인벤토리
   '내부자본 소요액||Internal capital requirement',
   '내부자본 소진율||Internal capital utilisation',
   '소진율은 소요액을 가용자본으로 나눈 값이며 모형 산출이다. 이 화면은 다시 계산하지 않는다.'
   '||Utilisation is the requirement divided by the available capital and is a model output. This screen does not recompute it.',
   '중요성 등급은 판정 정책 원장의 축과 기준값, 그리고 중요 판정 최소 초과 축 수로 결정된다. 등급이 자본 매핑의 부과 구분을 정하고, 잠정 사유가 남은 행은 매핑이 확정되지 않은 것이다.'
   '||The materiality grade is decided by the axes and thresholds in the policy ledger together with the minimum number of exceeded axes. The grade sets the capital charge pillar in the mapping, and a row that still carries a provisional reason has no confirmed mapping.',

   # 경영조치·제출
   '제출 상태 분포||Submission status mix',
   '상태별 건수는 x_gate.submission 서버 집계다||The count per status is the server-side tally in x_gate.submission',
   '합성 파이프라인은 submitted 를 부여하지 않는다. 제출 상태는 마감 워크플로의 제출 단계에서만 바뀐다.'
   '||The synthetic pipeline never assigns submitted. The submission status changes only at the submission step of the close workflow.',
   '발동표는 발동 지표와 임계, 승인 주체와 소요 기간을 정한다. 발동 기록은 시나리오·분기별로 임계를 미달한 사실과 그 사유를 남기며, 자본효과 가정이 없는 조치는 경로에 반영하지 않는다.'
   '||The playbook sets the trigger metric, the trigger level, the approving body and the lead time. The action record keeps, per scenario and quarter, the fact that the trigger level was missed and why, and an action with no capital effect assumption is not reflected in the path.',
   into=MESSAGES)
