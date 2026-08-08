# REVIEW NOTES — 팀3 (시안 04·05) · 2026-08-08

담당: 팀3 | 대상: `04-kinetic-frontier.html`, `05-boardroom-lux.html`
검증 기준: `knowledge-base/07-compliance-accessibility.md` 디자인 리뷰 체크리스트 + brief.md 공통 규격

## 시안 04 — Kinetic Frontier 자가검증

| 체크 항목 | 결과 | 근거 |
|---|---|---|
| 필수 고지 문구 포함 + 판독 가능 | PASS | 뒷면 하단 전용 박스, 7pt/행간 1.6, `#d9d4f2` on `#0e0730` (대비 약 13:1). 문구는 brief 원문 그대로 + "심의 전 시안 · 04 · 2026-08-08" |
| 금지 표현(단정·과장) 없음 | PASS | "보장/무조건/최고" 미사용. 성공 4지표 전 행에 "목표" 태그 병기, "측정·판단 주체는 귀사" 명기. 5~10영업일에도 "목표" 접두 |
| 목표 수치를 실적처럼 쓰지 않음 | PASS | 날개 표 각주 "위 수치는 위탁테스트 목표 기준이며 실적이 아닙니다", 내부3 기간에 "위탁테스트 목표 기준" 캡션 |
| 텍스트 대비 4.5:1 이상 | PASS | 그라데이션 밝은 구간(틸 `#15aeb7`, 흰 텍스트 약 2.7:1) 위 직접 텍스트 없음 — 전 텍스트를 다크 카드(`#150b36` 계열)로 받침. 카드 위 본문 `#f2f0ff` ≈15:1, 뮤티드 `#bdb6e6` ≈8:1, 틸 강조 `#7ef0e4` ≈13:1, 표지 3색 헤드라인(엔진블루 7.4:1 / 퍼플 6.8:1 / 앰버 10.7:1, 21pt 900) |
| 색상 단독 정보 전달 없음 | PASS | 파이프라인 노드는 색+텍스트 라벨(Alert/Hold·Block/Review/Release), 4계층은 색칩+명칭 병기, As-is→To-be는 화살표+열 제목 |
| 더미 데이터만 사용 | PASS | 실계좌·실명·직통번호 없음. 연락처는 대표 주소·대표 메일만 (research 유의사항 준수) |
| 수치에 기준·조건 병기 | PASS | 모든 수치는 research/brand-research.md 원문 소스(2~4주, 목표 5~10영업일, 3~6개월, 4지표). 창작 수치 없음 |
| AI 생성/추천 요소 표시 | PASS | 내부2 "AI 산출물 표시" 노트 — AVI·ARI 산출물은 AI 생성물 표시 + 4-Eyes 승인 전 미확정 |
| "심의 전 시안" 표기 | PASS | 뒷면 고지 말미 + 화면 헤더 |
| 규격 준수 | PASS | `.sheet` 297×210mm ×2, Grid 99mm×3, 패널 순서(날개-뒷면-표지 / 내부1-2-3), `.fold-guide` 화면 전용, `@page A4 landscape margin:0`, `print-color-adjust:exact`, bleed 3mm·날개 축소·CMYK 변환 노트 주석 명기, 외부 의존성 0 |
| 폰트 최소 크기 | PASS | 본문 9pt 이상(레이어·표·보안 항목 9pt로 상향 조정 완료), 고지 7pt, SVG 파이프라인 라벨 약 7.5pt 상당 |

특기: 브리프의 "큰 이탤릭 헤드라인 허용" 적용(표지 21pt italic 900). 안쪽면 3패널 스태거(10/18/26mm)와 관통 플로우 곡선은 접는 선 세이프존(패딩 10mm) 침범 없음. 곡선·이동점·속도선은 전부 장식 SVG(aria-hidden)로 텍스트 가독성에 간섭 없음.

## 시안 05 — Boardroom Lux 자가검증

| 체크 항목 | 결과 | 근거 |
|---|---|---|
| 필수 고지 문구 포함 + 판독 가능 | PASS | 뒷면 하단 골드 룰 위 "Notice" 블록, 7pt/행간 1.7, `#c9c2b2` on `#0e0e0f` (대비 약 11:1). brief 원문 + "심의 전 시안 · 05 · 2026-08-08" |
| 금지 표현 없음 | PASS | 04와 동일 카피 원칙. 4지표 각 행 "목표" 프레임 태그, "측정·판단 주체는 귀사" 명기 |
| 목표 수치를 실적처럼 쓰지 않음 | PASS | 날개 각주 + 내부3 "모형 1개당 검증 소요 · 위탁테스트 목표 기준" 캡션 |
| 텍스트 대비 4.5:1 이상 | PASS | `#0e0e0f` 위 본문 `#f4f0e8` ≈17:1, 뮤티드 `#a9a294` ≈8:1, 골드 `#d6b56d` ≈9.9:1(룰·넘버·소제목 한정), 고지 `#c9c2b2` ≈11:1 |
| 색상 단독 정보 전달 없음 | PASS | 4계층 컬러는 도트 마커로만 사용하고 계층명·설명 텍스트 병기, 스트라타 다이어그램에 텍스트 라벨(ENGINE/AGENT/HUMAN/LEDGER) |
| 더미 데이터만 사용 | PASS | 04와 동일 |
| 수치에 기준·조건 병기 | PASS | 04와 동일 — 리서치 문서 외 수치 창작 없음 |
| AI 생성/추천 요소 표시 | PASS | 내부2 "AI 산출물 표시" 노트 동일 적용 |
| "심의 전 시안" 표기 | PASS | 뒷면 고지 말미 + 화면 헤더 |
| 규격 준수 | PASS | 04와 동일 구조. 패널 패딩 11mm(세이프존 5mm 초과 확보). bleed·날개 축소·CMYK 노트 주석 명기 + 골드 별색(Pantone 871C 계열)·리치블랙·헤어라인 최소 선폭 인쇄 노트 추가 |
| 폰트 최소 크기 | PASS | 본문 9pt 이상(표·레이어·보안 9pt 상향 완료), 고지 7pt, 아이브로·라벨 7~7.5pt(캡션 한정) |
| 디렉션 준수(골드 절제) | PASS | 골드는 헤어라인 룰·소문자 로만 넘버(i.~v.)·아이브로 소제목·아이콘 스트로크에만. 본문 웜 화이트. 헤드라인 "Noto Serif KR",serif 폴백. RYNTA 브랜드마크는 브랜드 원형(블루→퍼플 그라데이션) 유지 후 골드 프레임으로만 감쌈 |

## 공통 참고 (design-reviewer 인계)

- 두 시안 모두 브라우저에서 바로 열어 확인 가능. 인쇄 미리보기(A4 가로)에서 시트당 1페이지, 접는 선·화면 라벨 자동 숨김.
- 엠블럼·브랜드마크는 `assets/brand-snippets.html`의 다크 배경용 버전을 그대로 인라인 복사 (재구성본 — 최종 인쇄 전 정식 CI 원본 교체 권장, 스니펫 원주석 참조).
- 잔여 리스크: ① 그라데이션(04)·골드(05)의 CMYK 재현은 인쇄 교정 필요(파일 내 주석 명기) ② SVG `<text>` 라벨은 브라우저 렌더 기준 — 래스터 내보내기 시 폰트 임베드 확인 필요.
- design-reviewer 검수(규제 표기·대비·브랜드 일관성·규격 4축, `marketing/review-report.md`)를 요청함. 치명 이슈 발견 시 팀3이 재작업.

## EN versions

대상: `en/04-kinetic-frontier.html`, `en/05-boardroom-lux.html` · 2026-08-08 · 카피 소스: `research/copy-deck-en.md` (사실·수치 변경 없음, "Parallel-Run Evaluation" 사용, 요청·부탁형 어투 없음)

| 체크 항목 | 결과 | 근거 |
|---|---|---|
| 필수 고지 (영문 원문 verbatim) | PASS | 카피 덱 §Back panel 고지 원문 그대로 + "Pre-clearance draft · 04(/05) · 2026-08-08". 위치·크기·대비 KO와 동일 (04: 7pt 전용 박스, 05: 7pt Notice 블록) |
| 금지 표현 없음 | PASS | grep 검증: guaranteed / revolutionary / best-in-class / zero-risk / consignment 0건 |
| 목표 수치 target 병기 | PASS | 검증 사이클 "5–10 business days (target)" + 캡션 "evaluation target, not a commitment". 날개 KPI 4지표는 KO의 "목표" 칩과 동일 위치에 "Target" 칩으로 전 행 병기 + 각주 "Targets, not commitments — outcomes vary by institution and environment" (덱 원문). As-is "2–4 weeks"는 내부 추정치로 "(as-is, internal estimate)" 병기 |
| @page·인쇄 CSS 유지 | PASS | `@page A4 landscape margin:0`, `@media print`, `.sheet` 297×210mm Grid 99mm×3, 패널 순서·컬러·데코 SVG 전부 KO 원본과 동일 (diff는 텍스트·아래 조판 항목뿐) |
| 라틴 조판 최적화 | PASS | KO 원본에 `word-break:keep-all` 없음(기본값 normal — 제거 대상 없음 확인). 04: 표지 h1 21→16.5pt(ls -.02em), h2.big 16.5→14.5pt(ls -.015em) — 영문 헤드라인 행 길이 대응. 05: 세리프 스택 전건 Georgia,"Noto Serif KR",serif로 교체, 표지 sub ls .12→.06em, 로만 넘버링 i.~v. 유지. 산세리프 스택은 기존 유지 |
| 화면 라벨 영어화 | PASS | screen-head 영문, 시트 라벨 "Outside — [Flap \| Back \| Cover]" / "Inside — [01 Diagnosis \| 02 Architecture \| 03 Transition]" |
| 패널 오버플로 확인 | PASS(주의) | 헤드리스 브라우저 부재로 렌더 캡처 불가 — 글자폭 추정(pt→mm 환산) 기반으로 전 패널 검토. 가장 긴 요소(04 표지 h1 1행 "Numbers by the engine." ≈64mm < 67mm 가용폭, 날개 본문 4행, 뒷면 About 8행)는 KO 대비 여유 슬랙(margin-top:auto 흡수 구간) 내. 04·05의 기간 박스("5–10 business days (target)")는 flex-wrap으로 자연 줄바꿈 허용. **최종 인쇄 전 브라우저 A4 가로 인쇄 미리보기에서 시트당 1페이지·패널 넘침 육안 확인 필수** |

특기: 날개 KPI에 카피 덱의 "Measured by" 3열은 추가하지 않음(디자인 변경 금지 — KO 2열 구조 유지). 해당 정보는 각주로 압축: "Measurement rests with your validators and audit function; judgment rests with your institution" (덱 사실관계 보존). KO의 "신규 규제 특례 불요" 항목은 덱 지침대로 글로벌 MRM 어휘("Fits your framework — designed to fit existing model risk management frameworks")로 교체(덱 §Inside 3 원문). 태그라인은 덱 EN "Financial-grade AI, built by validators." 사용(국내 태그라인 직역 미사용). design-reviewer 검수 요청: EN 2종에 대해 규제 표기·대비·오버플로(렌더 확인 포함) 재검 바람.
