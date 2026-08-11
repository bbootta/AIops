# REVIEW-NOTES — 팀2 (시안 02·03) 자가검증

작성: marketing-designer 팀2 | 2026-08-08 | 대상: `02-control-tower.html`, `03-evidence-blueprint.html`
기준: `design-team/knowledge-base/07-compliance-accessibility.md` 디자인 리뷰 체크리스트 + brief.md 공통 규격

## 07 체크리스트 결과

| 항목 | 02 컨트롤룸 | 03 블루프린트 | 비고 |
|---|---|---|---|
| 필수 고지 문구 포함 + 판독 가능한 크기/대비 | PASS | PASS | 뒷면 하단, brief.md 문구 그대로 + "심의 전 시안 · 시안번호 · 2026-08-08". 7pt, 02: #cfe0ee/#06111d ≈ 12:1, 03: #dcebf7/#062d49 ≈ 11:1 |
| 금지 표현(단정·과장) 없음 | PASS | PASS | "보장/무조건/최고" 미사용. 오차 0건·50%·100%·0건 전부 "목표" 배지/태그 병기(유사 크기·인접 배치), "실적 아님" 명기, 측정 주체=귀사 명기 |
| 손익 표현 색상 외 보조 수단 | N/A~PASS | N/A~PASS | 손익 수치 없음. 계층 구분은 색+텍스트 라벨+번호 병행(색 단독 전달 없음), 03 흐름도에 4계층 텍스트 범례 |
| 텍스트 대비 4.5:1 이상 | PASS | PASS | 소형 텍스트에 뮤티드 #8ea4b8 미사용 — 02는 #a9bfd2(서피스 위 ≈9:1), 03은 #b8d2e6(≈8:1+)으로 밝게 조정. 포인트 컬러(엔진블루 7.6:1, 틸 7.6:1, 앰버 8:1)도 배경 대비 확보 |
| 더미 데이터 사용 (실계좌 정보 없음) | PASS | PASS | 계좌·고객 데이터 자체 없음. 02 표지 상태 램프에 "화면 연출 예시" 캡션 부착 |
| 수치에 기준 시점·출처·조건 병기 | PASS | PASS | 소요기간 "모형 1개당·주 5영업일 환산·목표 기준(실적 아님)" 병기, As-is 2~4주는 "내부 산정 기준, As-is" 표기, 위탁테스트 4지표는 "목표 기준·측정 주체 귀사" |
| AI 생성/추천 요소 표시 | PASS | PASS | 에이전트 계층에 "AI 생성 초안" 배지/표시 + "승인 전 미확정" 문구(제품 철학과 일치) |
| "심의 전 시안" 상태 표기 | PASS | PASS | 뒷면 고지 말미(02·03 공통). 03은 표지 표제란(DATE 행)에도 중복 표기 |

## 규격·구현 자가검증 (brief.md 공통 규격)

- [x] `.sheet` 2개 × 297×210mm, CSS Grid 3열 × 99mm — 바깥면 [날개|뒷면|표지] / 안쪽면 [내부1|내부2|내부3]
- [x] `.fold-guide` 점선 화면 전용, `@media print` 숨김 / `@page{size:A4 landscape;margin:0}` / `print-color-adjust:exact`
- [x] 화면에서 두 시트 세로 배치 + 상단 시안명·면 라벨(`.screen-label`, 화면 전용)
- [x] 외부 의존성 0 — 폰트 시스템 폴백, 그래픽 전부 인라인 SVG (엠블럼·브랜드마크는 brand-snippets.html 다크 배경 버전 복사)
- [x] 콘텐츠 골격 6패널 brief 표 그대로 (날개 4지표 표에 "목표"·측정 주체=귀사 명기)
- [x] 본문 최소 9pt, 캡션·라벨 최소 6.5~8pt(장식성 라벨), 고지 7pt
- [x] 다크 배경 인쇄 유의 주석: 두 파일 모두 상단 HTML 주석에 3mm bleed 배경 연장, 잉크 커버리지·무광 코팅, CMYK 리치블랙, 날개 폭 2~3mm 축소 명기 (03은 그리드 선폭 0.1~0.15mm 확인 추가)
- [x] 애니메이션(02 상태 램프 pulse): 2s 주기(3회/초 미만), `prefers-reduced-motion` 대응, 인쇄 시 정적

## 콘텐츠 출처 검증

- 모든 수치·주장(2~4주→목표 5~10영업일, 4지표, 온프레미스·비보유·특례 불요, 팀 이력, 주소·메일)은 `research/brand-research.md` 원문 범위 내. 창작 수치 없음.
- "10~20영업일 환산"은 2~4주의 주 5영업일 단순 환산이며 그래픽에 환산 기준 명기.
- 03 내부2의 7단계 흐름은 문서화된 4계층 아키텍처·As-is/To-be 항목의 재배열로, "제품 4계층 아키텍처 기반 개념 흐름도"(FIG.2) 캡션으로 성격 명시 — 신규 사실 주장 아님.
- 실명·직통번호 미사용 (info@onelineai.com / 대표 주소만).

## 알려진 한계 / 검수자 참고

1. 헤드리스 브라우저 부재 환경으로 픽셀 렌더링 검증 미수행 — design-reviewer가 브라우저에서 패널 오버플로(특히 03 내부2 흐름도 SVG 높이) 확인 요망.
2. 대비 수치는 WCAG 상대휘도 공식 수기 계산값 — 도구 재검증 권장.
3. 엠블럼·브랜드마크는 스니펫의 재구성본 — 최종 인쇄 전 정식 CI 원본 교체 필요(스니펫 원주석과 동일).
4. 다크 전면 배경 2종 모두 인쇄소 협의 필요: bleed 연장, 무광 코팅, 리치블랙 값.

→ design-reviewer 검수 요청: 규제 표기·대비·브랜드 일관성·규격 준수 4축 (`marketing/review-report.md`).

## EN versions

작성: marketing-designer 팀2 | 2026-08-08 | 대상: `en/02-control-tower.html`, `en/03-evidence-blueprint.html` (글로벌 금융기관 배포용)

- **카피 출처**: 전 문안 `research/copy-deck-en.md` 사용. 사실·수치 변경 없음(디자인별 어순·강조 조정만). "consignment test" 미사용 — **Parallel-Run Evaluation** 통일. 요청·부탁형 어투 없음(확신형 선언문). 국내 맥락(태그라인 직역·"신규 규제 특례 불요") 제거 → 덱의 EN 태그라인 "Financial-grade AI, built by validators." 및 "designed to fit existing model risk management frameworks" 문안으로 교체.
- **필수 고지**: 덱 §Back의 영문 고지 원문 그대로 + "— Pre-clearance draft · 02/03 · 2026-08-08". 위치·크기·대비 KO판과 동일(뒷면 하단 `.notice` 7pt, 02: #cfe0ee/#06111d, 03: #dcebf7/#062d49). 03은 표지 표제란 DATE 행에도 "Pre-clearance draft" 중복 표기(KO판과 동일 구조).
- **(target) 병기**: 목표 수치 전건에 TARGET 배지/태그 인접 병기(0 discrepancies, ≥50%, 100%, 0 exceptions, 5–10 business days) + 본문·캡션에 "(target)", "target, not actual results", "targets, not commitments" 명기. 금지 표현(guaranteed/revolutionary/best-in-class/zero-risk) 미사용 — grep 검증 완료.
- **라틴 조판**: 원본 두 파일 모두 `word-break:keep-all` 미사용 확인(제거 대상 없음 — 기본 normal). 헤드라인 letter-spacing 타이트 조정: `h2.panel-title` 및 커버 h1 -.01em→-.02em(03 h1은 미지정→-.02em). 서체 스택 기존 유지.
- **오버플로 대응(디자인 불변 범위 내)**:
  - 02 커버 h1 19.5pt→18.5pt (3행 영문 헤드라인 99mm 패널 폭 대응).
  - 02 커버 KPI 큰 숫자를 "5–10"으로 하고 단위 "business days"는 캡션으로 이동(타일 폭 33mm 내 유지).
  - 02 날개 KPI 라벨 축약(VARIANCE/CYCLE TIME/AUDIT TRAIL/4-EYES) + 상세는 하단 설명행으로, `.ktile .k`에 `flex-wrap:wrap` 안전장치 추가.
  - 02 내부2 모토는 커버와 동일한 3행 배열로 변경(1행당 83mm 초과 방지).
  - 03 날개 표 TARGET 열(24mm)은 값 축약(0/≥50%/100%/0) + 단위·조건을 지표 셀에 병기. tblock 키는 17mm 폭 내 단어 사용(PROGRAM/VERDICT).
  - 03 내부2 SVG 회전 라벨은 브래킷 길이 내 단어(CALCULATION/DRAFT/JUDGMENT/RECORD), 타임라인 축 라벨은 숫자만 + 축 단위는 캡션("Axis/Scale: business days, 5-day week")으로 이동.
  - 잔여 한글 0건(Python 정규식 검증), 화면 라벨·주석까지 영문화.
- **화면 전용 라벨**: Outside — [Flap | Back | Cover] / Inside — [01 Diagnosis | 02 Architecture | 03 Transition] (03은 SHEET A/B · B-01~B-03 도면 문법으로 변형).
- **알려진 한계**: KO판과 동일(헤드리스 브라우저 부재로 픽셀 렌더링 미검증 — 특히 02 내부1의 3행 헤드라인, 03 날개 lead 추가로 인한 표 하단 여백을 design-reviewer가 브라우저에서 확인 요망). 인쇄 유의사항(3mm bleed·리치블랙·날개 폭 축소)은 파일 상단 주석에 영문으로 유지.

→ design-reviewer 검수 요청: EN 카피 정합(copy-deck-en.md 대조) + 오버플로 육안 확인 추가.
