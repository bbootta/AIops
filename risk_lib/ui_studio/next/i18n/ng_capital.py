"""자본·RWA 그룹(screens/capital.js) 카탈로그 (설계 사양 7장).

신용·조기경보·신용 RWA·ECL·시장·가격검증·백테스팅·VaR·ES·시장 RWA·시장
포트폴리오·포트폴리오 설정·운영·손실·회수·KRI·통제·운영 RWA·NCR·건전성
열여섯 화면이 저자로서 새로 쓴 한국어 문자열만 여기 있다. 기존 카탈로그
(i18n.py)와 셸 어휘(ng_frag·ng_gate·ng_shell)에 이미 있는 문구는 다시 적지
않고 그대로 쓴다.

**원장에서 오는 값은 없다.** 테이블명·컬럼 물리명·카탈로그 한글명·조문
인용·서식 코드(B2326·BA2325-1)·거래 ID·예외 ID·판정 문자열(green·amber·
red·완결·검토·누락·중대·경미)은 화면이 원문 그대로 찍으며 이 사전에 넣지
않는다.
"""

from risk_lib.ui_studio.next.i18n_next import _t

MESSAGES: dict[str, dict[str, str]] = {}

_t("ng_capital",
   # ── 신용·조기경보 ────────────────────────────────────────────────
   '조기경보 신호 유형별 건수||Count by early warning signal type',
   '아래 목록은 이 부문 카탈로그 전량이다. 고른 원장의 입도·기본키·외래키·차트·미리보기를 오른쪽에 편다.'
   '||The list below is the full catalogue of this domain. Picking a ledger opens its grain, primary key, foreign keys, chart and preview on the right.',

   # ── 신용 RWA ─────────────────────────────────────────────────────
   '하한 적용 전후 위험가중자산||Risk-weighted assets before and after the output floor',
   '카탈로그 귀속||Catalogue attribution',
   '시장·운영 위험가중자산 원장(rwa_market_component · rwa_operational_bi)도 카탈로그에서는 PRD-RWA 다. 화면은 시장 RWA · 운영 RWA 에 두었고 제품 코드 칩은 카탈로그 값 그대로 붙는다.'
   '||The market and operational risk-weighted asset ledgers (rwa_market_component and rwa_operational_bi) also sit under PRD-RWA in the catalogue. They are shown on the Market RWA and Operational RWA screens, and the product code chip carries the catalogue value as recorded.',

   # ── ECL ──────────────────────────────────────────────────────────
   '충당금 증감 브리지||Loan loss allowance movement bridge',

   # ── 시장·가격검증·백테스팅 ───────────────────────────────────────
   '미해소 {n}건||{n} open items',
   '경과일은 원장 days_open 이며 5일 초과는 상위보고 대상이다'
   '||The elapsed days come from the ledger column days_open, and more than five days is escalated',
   '예외·조치 연결||Link to the exception and remediation queue',
   '가격검증에서 넘어간 예외가 없다||No exception was raised out of price verification',
   '가격검증 예외 {n}건||{n} price verification exceptions',
   '서식이 payload 에 없다||The form is not in the payload',
   '위험군별 위험가중자산||Risk-weighted assets by risk class',
   '포트폴리오별 위험군 배분 가중치||Risk class allocation weights by portfolio',

   # ── 운영 ─────────────────────────────────────────────────────────
   '채택 방법과 서식 라인은 운영 RWA 화면에 있다||The adopted approach and the form lines are on the Operational RWA screen',
   '마감 워크플로 연결||Link to the close workflow',
   '마감 과제||Close tasks',
   '과제 상태와 게이트 판정은 마감 워크플로 화면이 원장 그대로 싣는다'
   '||The close workflow screen carries the task status and the gate decision as they stand in the ledger',
   '총손실에서 순손실까지||From gross loss to net loss',
   '사업지표(BI) 구성요소별 금액||Amount by business indicator (BI) component',

   # ── NCR·건전성 ───────────────────────────────────────────────────
   '{cat} 구성요소 누계||{cat} components, cumulative',
   '근거 조항은 원장 값이라 번역하지 않는다||The regulatory article is a ledger value and is not translated',
   '재무상태·손익·소유한도·경영실태·적기시정조치는 이 화면이 유일한 자리다. 예전에는 데이터모델 카탈로그 탭에서만 볼 수 있었다.'
   '||The financial position, income statement, ownership limits, management assessment and prompt corrective action ledgers are homed on this screen. They used to be reachable only through the data model catalogue tab.',
   into=MESSAGES)
