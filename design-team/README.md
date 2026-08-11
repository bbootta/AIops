# 금융 AI 디자인 에이전트팀 하네스

금융 AI 프로덕트의 화면 디자인, 브랜딩, 홍보물, 프레젠테이션을 수행하는 Claude Code 에이전트팀입니다.

## 구성

```
design-team/
├── README.md                  # 이 문서
├── knowledge-base/            # 디자인 지식베이스 (에이전트들의 공유 지식)
│   ├── 01-design-foundations.md       # 타이포·컬러·레이아웃 기초
│   ├── 02-fintech-product-ui.md       # 핀테크 화면 패턴, AI UI 패턴
│   ├── 03-data-visualization.md       # 금융 차트·대시보드 규칙
│   ├── 04-brand-identity.md           # 브랜드 포지셔닝·로고·가이드
│   ├── 05-marketing-design.md         # 배너·SNS·랜딩·인쇄물 규격과 원칙
│   ├── 06-presentation-design.md      # 피치덱·세일즈덱·보고 슬라이드
│   └── 07-compliance-accessibility.md # 금융 규제 고지·접근성 (검수 기준)
└── projects/                  # 프로젝트별 산출물 (작업 시 생성)
    └── <프로젝트명>/
        ├── brief.md           # 크리에이티브 브리프 (design-director 작성)
        ├── brand/             # 브랜드 자산 (로고 SVG, 가이드, 토큰)
        ├── ui/                # 화면 시안 (HTML 목업)
        ├── marketing/         # 홍보물 (배너·랜딩·카드뉴스)
        └── deck/              # 프레젠테이션 (outline + pptx)

.claude/agents/                # 에이전트 정의
├── design-director.md         # 총괄: 브리프 작성, 작업 분배
├── ui-designer.md             # 화면 디자인 (앱/웹/대시보드)
├── brand-designer.md          # 브랜딩 (로고/컬러/가이드)
├── marketing-designer.md      # 홍보물 (배너/SNS/랜딩/인쇄물)
├── presentation-designer.md   # PPT (피치덱/소개서/보고)
└── design-reviewer.md         # 검수 (규제/접근성/일관성 QA)
```

## 워크플로우

```
요청 → design-director (브리프) → 전문 에이전트 (제작, 병렬 가능) → design-reviewer (검수) → 완료
                ↑                                                          │
                └────────────── 반려 시 재작업 ←──────────────────────────┘
```

1. **design-director**가 요청을 해석해 `projects/<프로젝트명>/brief.md` 작성 — 타깃, 핵심 메시지, 산출물 규격, 규제 제약, 작업 분배
2. 브랜드 가이드가 없는 신규 프로젝트는 **brand-designer**의 미니 가이드가 항상 선행 (후속 작업의 일관성 기준)
3. 전문 에이전트가 제작 — 매체가 겹치지 않으면 병렬 실행 가능
4. **design-reviewer**가 규제·접근성·일관성·완성도 4개 축으로 검수, `review-report.md`에 승인/조건부/반려 판정

## 사용 예시

에이전트는 요청 내용에 따라 자동 위임되며, 명시적으로 지정할 수도 있습니다:

```
# 총괄부터 (권장 — 여러 매체에 걸치거나 방향이 모호할 때)
"자산관리 AI 앱 출시 캠페인을 준비해줘. 화면 시안, 인스타 광고, 투자자용 덱까지"
→ design-director가 브리프 작성 후 분배

# 단일 매체 직접 요청
"AI 리밸런싱 알림 화면을 디자인해줘"          → ui-designer
"제품 로고와 브랜드 가이드를 만들어줘"          → brand-designer
"신규 가입 이벤트 인스타 카드뉴스 6장"          → marketing-designer
"시리즈A IR 덱 12장 만들어줘"                  → presentation-designer
"marketing/ 폴더 산출물 검수해줘"              → design-reviewer
```

## 원칙

- **지식베이스가 단일 기준**: 모든 에이전트는 작업 전 관련 지식베이스를 읽고 따른다. 규칙 변경은 지식베이스 문서를 수정하는 것으로 팀 전체에 반영된다
- **규제 우선**: 금융 광고 필수 고지·금지 표현·접근성(07 문서)은 시안 단계부터 반영하며, 대외 산출물은 "심의 전 시안" 표기를 유지한다. 실제 집행 전 준법감시/법무 검토는 별도
- **더미 데이터만**: 모든 시안의 이름·계좌·금액은 처음부터 가짜 데이터
- **산출물은 실행 가능하게**: UI·홍보물은 외부 의존성 없는 단일 HTML/SVG, 덱은 pptx — 브라우저나 오피스에서 바로 열어 확인

## 지식베이스 확장

새 지식이 필요하면 `knowledge-base/`에 번호를 이어 문서를 추가하고, 해당 문서를 읽어야 할 에이전트의 정의(`.claude/agents/*.md`)의 "시작 시 필수 행동" 목록에 추가합니다.
