# REVIEW-NOTES — 팀5 (시안 09·10)

작성: 팀5 | 2026-08-08 | 대상: `09-regulator-trust.html`, `10-tech-dossier.html`
검증 기준: `knowledge-base/07-compliance-accessibility.md` 디자인 리뷰 체크리스트 + `brief.md` 규격

## 공통 규격 자가검증 (양 시안 동일)

- `.sheet` 2개 × 297×210mm, CSS Grid `99mm 99mm 99mm` 3열 — 코드 grep으로 확인
- 바깥면 [날개|뒷면|표지] / 안쪽면 [내부1|내부2|내부3] 순서 준수
- `@page{size:A4 landscape;margin:0}` + `print-color-adjust:exact` 포함
- `.fold-guide` 점선 2본 = 화면 전용, `@media print`에서 숨김. 화면 상단 시안명·면 라벨(`.screen-only`)도 인쇄 시 숨김
- 3mm bleed·날개 폭 2~3mm 축소 필요를 파일 상단 주석에 명기 (CMYK 변환·정식 CI 원본 교체 필요도 스니펫 주석 승계)
- 외부 의존성 0 — `http` 매치는 SVG `xmlns` 네임스페이스뿐임을 grep으로 확인. 폰트는 시스템 폴백만
- 콘텐츠 골격·수치 전부 `research/brand-research.md` 원문 기반, 창작 수치 없음
- 한계: 이 환경에 headless 브라우저가 없어 렌더링 스크린샷 검증은 미수행 — design-reviewer가 브라우저 열람으로 오버플로 여부(특히 각 패널 세로 여백) 확인 요망

## 07 체크리스트 — 시안 09 (레귤레이터 트러스트)

- [x] 필수 고지 문구 포함 + 판독 가능: 뒷면 하단, 7pt, `#26352f` on `#e3edea` 틴트(대비 약 10:1), 그린 좌측 룰로 시선 확보
- [x] 금지 표현 없음: "보장/무조건/최고" 미사용. 4지표·소요기간 모두 "(목표)" 병기, 날개·내부3에 "실적 아님 / 기관별 상이" 주석
- [x] 손익·상태 표현에 색상 외 보조 수단: 해결=체크 표시, 문제=X 표시 박스로 형태 구분 (색 단독 전달 없음)
- [x] 텍스트 대비 4.5:1↑: 잉크 `#16241f`(≈13:1), 뮤티드 `#4e5e58`(≈5.1:1), 그린 `#087c69` on `#f2f5f4`(≈4.7:1 — 7.5pt 이상 라벨·괘선에만 사용), 저대비 우려 강조부는 `#065446` 사용. 흰 글자 on `#087c69`(≈5.1:1)
- [x] 더미 데이터만 사용: 실명·직통번호·실데이터 없음. 서명란은 빈 양식
- [x] 수치에 기준·조건 병기: "위탁테스트 목표 기준 · 측정 주체=귀사 · 병행 3~6개월" 명기
- [x] AI 생성/추천 표시: 표지·내부2에 "사람 승인 전 확정되지 않음"(4-Eyes) 명시, 4-Eyes 승인 흐름 도식 포함
- [x] "심의 전 시안" 표기: 고지 문구 말미 "심의 전 시안 · 09 · 2026-08-08" + 화면 헤더에도 표기
- [x] 최소 크기: 4-Eyes 흐름도 SVG 텍스트를 실효 약 7.1pt로 상향 수정 완료(초안 실효 약 6pt) — HTML 텍스트는 최소 7pt(고지)·본문 9pt 이상
- 주의 노트 1: 표지의 원형 도장은 실제 인증마크가 아닌 제품 원칙(4-Eyes) 장식 모티프 — 문구를 "4-EYES · HUMAN DECISION / 판단은 사람이"로 한정해 인증 오인 소지를 차단(07 "근거 없는 인증마크 금지" 대응). "APPROVED" 등 승인 완료 문구 미사용
- 주의 노트 2: 도장 내부 소형 텍스트(실효 약 5~6pt)는 장식 요소로, 동일 문구가 표지 헤드라인(16.5pt)에 판독 가능한 크기로 중복 존재

## 07 체크리스트 — 시안 10 (테크 도시에)

- [x] 필수 고지 문구 포함 + 판독 가능: 뒷면 하단, 7pt, `#24313e` on `#eef0f2`(대비 약 9:1), 네이비 좌측 룰
- [x] 금지 표현 없음: TARGET 열 전 행 "(목표)" 병기 + "달성 실적 아님·성공 여부는 귀사가 판단" 주석. 소요기간 "TARGET / PILOT 기준" 명기
- [x] 색상 단독 정보 전달 없음: 4계층은 컬러 바 + LAYER명 텍스트 병기, As-is/To-be는 열 라벨로 구분
- [x] 텍스트 대비 4.5:1↑: 네이비 `#14283c` on `#faf8f4`(≈12:1), 뮤티드 `#4a5a6b`(≈6.7:1), 스탬프 레드 `#8b1e2d`(≈8.6:1), Ledger 헤더 흰 글자 on 네이비(≈12:1)
- [x] 최소 크기: Ledger 표 th/td를 7pt로 상향 수정 완료(초안 6.7/6.9pt) — 현재 7pt 미만 HTML 텍스트 없음
- [x] 더미 데이터만 사용: Evidence Ledger 표는 "표현 예시 · 더미 데이터" 캡션+각주 이중 명기, 해시는 축약 더미
- [x] 수치에 기준·조건 병기: MODE/PERIOD/MEASURED BY 파라미터 블록으로 조건을 표 상단에 구조화
- [x] AI 생성/추천 표시: Ledger 각주에 "AGENT.DRAFT는 사람 검토·승인 전 확정되지 않음", §02 HUMAN 계층에 4-Eyes 명시
- [x] "심의 전 시안" 표기: 고지 말미 + 표지 DRAFT 스탬프("DRAFT / 심의 전 시안") 이중 표기
- 주의 노트: 표지 DRAFT 스탬프는 심의 전 상태 표기를 디자인 요소화한 것 — 인쇄 확정 시 제거가 아니라 심의 통과 후 별도 처리 필요함을 인수인계에 명기

## design-reviewer 검수 요청 사항

1. 브라우저 열람으로 패널별 세로 오버플로 확인 (특히 09 날개 서명 블록, 10 내부2 Ledger 표)
2. 인쇄 진행 시: CMYK 변환, 정식 CI 벡터 원본 교체(`brand-snippets.html` 주석 참조), 날개 폭 축소 반영

## EN versions

작성: 팀5 | 2026-08-08 | 대상: `en/09-regulator-trust.html`, `en/10-tech-dossier.html` (글로벌 금융기관 배포용 영어판)

- 카피 출처: `research/copy-deck-en.md` 전면 적용 — 사실·수치 변경 없음. "consignment test" 미사용, **Parallel-Run Evaluation** 사용. 요청·부탁형 어투 없음(확신형 선언문)
- 국내 맥락 제거: 태그라인 "대한민국 금융 선진화" → *Financial-grade AI, built by validators.* / 09 내부3·10 SEC-03 "신규 규제 특례 불요" → 덱의 MRM 문구("fits existing model risk management frameworks") — 특정 규정(SR 11-7 등) 준수 주장 없음
- 디자인 동결: 레이아웃·그리드(99mm×3)·컬러 토큰·인쇄 CSS(@page, bleed·날개 축소 주석) 한국어 최종본과 동일. 변경은 카피와 라틴 조판 최적화뿐
- 라틴 조판: 원본에 `word-break:keep-all` 부재 확인(제거 대상 없음 — normal 동작). 헤드라인 letter-spacing -.02em → **-.01em** 완화(`panel-title`, `.oneliner`). 서체 스택 기존 유지(시스템 폴백이 라틴 커버)
- [x] 필수 고지: 덱 영문 고지 **원문 그대로** + "Pre-clearance draft · 09 · 2026-08-08" / "· 10 ·" — 기존과 동일 위치(뒷면 하단 notice 블록)·크기(7pt)·대비(틴트 배경 동일). 10 표지 DRAFT 스탬프는 "PRE-CLEARANCE"로 이중 표기, 화면 헤더에도 Pre-clearance draft 표기
- [x] 목표 수치 전건 "(target)" 병기: 09 KPI 4행 + 10 T-01~T-04 전행, 소요기간(5–10 bus. days)은 "Target · Parallel-Run Evaluation" 라벨 + "evaluation target" 각주 — grep으로 파일당 "(target)" 5회 확인
- [x] 금지 표현 0건: guaranteed / revolutionary / best-in-class / zero-risk grep 검사 통과. "Targets, not commitments" 각주 유지
- [x] 09 4-Eyes 흐름도 영어 라벨: Agent **Draft** → Reviewer **1st Eye** → Approver **2nd Eye** → **Recorded** to Ledger. 확정 박스 흰색 텍스트 `fill="#ffffff"` 2건 유지 확인
- [x] 화면 전용 라벨 영어화: "Outside — [Flap | Back | Cover]" / 09 "Inside — [01 Diagnosis | 02 Architecture | 03 Transition]" / 10은 § 변형 "[§01 Diagnosis | §02 Architecture | §03 Transition]". 내부 step-no·sec-tag도 동일 문법(01 / DIAGNOSIS, RYNTA-§01 등)
- [x] 10 모노스페이스 문서 장치 강화: DOC NO. **RYNTA-BRO-2026-10-EN**, panel-foot 전부 -EN 승계(§01~§03·ANNEX A). Ledger 표 EVENT/ACTOR 영문 정리(done/created/REVIEW·1st Eye/APPROVE·2nd Eye), 더미 데이터 각주 유지
- 오버플로 확인: 이 환경에 headless 브라우저 부재로 렌더링 검증 미수행(한국어판과 동일 한계) — 문자수 기반 추정으로 대응: 긴 영어 카피 지점은 (a) 09/10 내부1 제목 2행화(패널 여백 내 흡수, margin-top:auto 콜아웃이 완충), (b) 소요기간 위젯 값 "2–4 wks"·"5–10 bus. days"로 축약해 nowrap 폭 확보, (c) 09 KPI·10 TARGET 열 "0 discrepancies"→"0"으로 축약(의미 동일, 지표명에 variance 명시). 폰트 크기 추가 축소는 불필요 판단 — design-reviewer 브라우저 열람 시 09 날개(sub 4행+서명 블록), 10 날개(명세 표 지표명 2행 랩), 양 시안 뒷면 about(영문 약 8행) 세로 여백 우선 확인 요망
- 도장 모티프(09): 하단 텍스트 "판단은 사람이" → "Judgment by people" (SVG font-size 9.5→8, 원 내부 폭 수용 목적 — 장식 요소이며 동일 문구가 헤드라인에 판독 크기로 존재, 기존 주의 노트 2와 동일 논리)
