# AIMS 내부심사 기록 — 2026-07-12 (제1차)

ISO/IEC 42001:2023 조항 9.2에 따른 내부심사. 기준 문서: `AIMS_POLICY.md`.

| 항목 | 값 |
|---|---|
| 심사 대상 | `out/aims_audit_run/` 보고 패키지 (73개 산출물) |
| 패키지 식별 | headline_digest `7b726ac648518dd3…` · portfolio sha256 `71c9319b…` |
| 산출 조건 | seed=42 · asof=2026-06-11 · risk_lib (branch claude/risk-management-agent-harness-B9Kxm) |
| 심사 방법 | 통제 작동 증거 확인 (수치 재계산 없음) + 재현성 재실행 대조 |
| 심사자 | aims-compliance-auditor 절차 준용 (독립 — 산출·1차 검증 미참여) |

## 판정표

| # | 통제 | 판정 | 증거 |
|---|---|---|---|
| 1 | A.7.2 manifest 필수 키 | 적합 | portfolio.sha256·parameters.seed·parameters.asof·headline_digest·validation 모두 존재 |
| 2 | A.6.2.8 audit ledger 인용 완비 | 적합 | 14 entries, code_module/code_function/citation 보유율 100% |
| 3 | A.6.2.7 모델 인벤토리 검증일 | 적합 | Tier 1 표기 19회, last/next validation 일자 표기 |
| 4 | A.9.2 결재 페이지 3단 서명란 | 적합 | 산출 책임자/검증 책임자/최종 결재(CRO) 서명란 |
| 5 | A.8 검증 결과 공개 | 적합 | ops/12_validation.html 존재 |
| 6 | A.8 약어 주석 | 적합 | 약어 카드 렌더, 본문 약어(CET1/RWA/LCR/NSFR/IRRBB) 커버 |
| 7 | **A.7.2 재현성 (재실행)** | **적합** | 동일 (seed=42, asof=2026-06-11) 재실행 → headline_digest `7b726ac648518dd3` 일치, 포트폴리오 sha256 일치 |
| 8 | 정책 §2-4 검증 FAIL=0 | 적합 | validation 요약 {PASS: 49, WARN: 3, FAIL: 0} |
| 9 | 정책 §6 WARN 사유 공개 | 적합 | WARN 3건, validation 페이지에 항목명·상세 16회 표기 |
| 10 | A.7.2 digest 노출(printable) | 적합 | printable.html에 headline_digest 앞 16자리 표기 |
| 11 | A.8 executive 산출 기준일 | 적합* | executive.html L86 "산출 기준 2026-06-11 · seed 42 · 규제 준거 …" + footer repro 라인 |
| 12 | A.9.2 사전 결재 요구 문구 | 적합 | attestation 페이지 "CRO 서명 전 산출/검증 책임자의 사전 결재" 명시 |
| 13 | A.8 규정 준거 인용 | 적합 | validation 페이지에 Basel/감독세칙 조항 인용 |

\* 항목 11은 1차 스캔에서 경부적합으로 표기되었으나 반박 검증에서 기각됨 —
체크 문자열("산출 기준일")이 실제 표기("산출 기준")보다 과도하게 엄격했던
심사 도구 오류로 판정. 패키지 자체는 적합. (심사 정확성을 위해 기각 이력을
기록으로 남김.)

## 종합

- **적합 13 / 경부적합 0 / 중부적합 0** → 본 패키지는 AIMS 통제 관점에서
  결재 상신 가능. (최종 결재는 정책 §2-1에 따라 인간(CRO/현업)의 몫.)
- 부적합·시정조치: **해당 없음** (정책 §6 요구에 따른 명시).

## 관찰 사항 (부적합 아님, 개선 참고)

1. audit ledger가 headline 14건을 커버 — 심층 페이지의 파생 수치까지 확대할
   여지 있음 (커버리지 확대는 지속적 개선 후보, 조항 10.3).
2. 본 차수는 심사 절차를 스크립트로 수행 — 차기 심사부터는
   `aims-compliance-auditor` 에이전트 호출로 수행해 심사 자체의 독립 실행
   증적을 남길 것.

## 이전 조치 이력

- 2026-07-12 (심사 준비 중 발견): manifest `parameters.asof` 미기록 공백 →
  `repro.build_manifest`에서 유효 asof 자동 기록으로 시정 (커밋 26e9b32,
  회귀 테스트 포함). 본 심사에서 시정 효과 확인 (항목 1 적합).
