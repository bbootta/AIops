# validation-team-agent

은행 리스크관리 검증팀을 지원하는 Agentic Harness Engineering(AHE) 기반 검증 자동화
하니스 프로젝트.

---

## 프로젝트 목적

- 신용평가모형, PD/LGD/EAD, IFRS 9 ECL, 거시 시나리오 예측모형, 스트레스 테스트,
  운영 모니터링, 검증 보고서 작성을 **데이터·방법론·운영·내부통제·문서화** 관점에서
  자동 점검한다.
- 검증 산출물의 **재현성**, **설명가능성**, **감사추적성**을 확보한다.
- 반복 검증 업무를 표준화하되, **최종 판단은 인간 검증자**가 수행하도록 한다.
- AHE 방식으로 하니스를 컴포넌트화하고, 실행 로그와 변경 이력을 남기며, 실패 시
  원인 분석과 개선안을 기록한다.

---

## 디렉터리 구조

```
validation-team-agent/
├── CLAUDE.md                     # 최상위 운영 지침
├── README.md                     # 본 문서
├── pyproject.toml                # 패키지/도구 설정
├── requirements.txt              # 런타임 의존성
├── .gitignore
│
├── docs/                         # 운영 모델·위험통제·HITL 정책·검증 기준 층(criteria_layers.md)
├── harness/                      # 시스템 프롬프트, 정책, 변경 매니페스트
├── skills/                       # 도메인별 절차 지식
├── subagents/                    # 서브에이전트 역할 정의
├── tools/                        # 검증용 Python 함수 (v1 진입점 python -m tools.*)
├── src/vta/                      # v2 패키지: domains/ 핸들러·워크플로우·python -m vta
├── middleware/                   # 실행 전후 통제 미들웨어
├── tests/                        # pytest 단위 테스트
├── examples/                     # 입력 스키마·요청·보고서 예시
├── logs/                         # 실행 로그 (커밋 제외)
├── memory/                       # 반복 finding·모형별 노트·알려진 한계
└── reports/                      # 산출 보고서 (커밋 제외)
```

---

## 설치

Python 3.10+ 권장.

```bash
cd validation-team-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .   # `python -m vta` (v2 CLI) 사용을 위해 필요
```

`-e .` 를 생략하면 v1 진입점 (`python -m tools.*`) 만 사용 가능하다.
v2 dispatch (`python -m vta`) 가 `src/vta/` 패키지를 찾으려면 editable
install 또는 `PYTHONPATH=src` 가 필요하다.

또는 패키지만 설치 (의존성 포함):

```bash
pip install -e .
```

---

## 테스트 실행

```bash
pytest -q
```

샘플 테스트는 외부 데이터 의존성 없이 합성 표본으로 동작한다.

---

## 검증 요청 예시

`examples/sample_validation_request.md`를 참고하여 다음 항목을 채워 요청한다.

- 검증 대상 (모형명, 모형군, 버전)
- 검증 목적
- 검증 범위
- 입력 데이터 위치 및 컬럼 정의
- 표본 기간 (개발/운영)
- 목표변수 정의
- 사용 가능한 도구
- 성공 기준

도메인별 입력 예시: `examples/sample_validation_request.md` (신용),
`examples/sample_ifrs9_request.md` (IFRS 9), `examples/sample_macro_request.md` (거시).

---

## CLI 카탈로그

### v2 단일 진입점 (권장)

```
python -m vta --help                   # 전체 subcommand 카탈로그
python -m vta workflow demo --stress   # 동적 워크플로우 데모
python -m vta workflow demo --async    # 독립 step 병렬 실행 (기본은 sync)
python -m vta manifest validate        # change_manifest 검증
python -m vta policy list              # SSoT 정책 파일 인덱스
python -m vta policy show <name>       # 정책 JSON 출력
python -m vta classify <cmd>           # 6분류 에러 분류기
```

v2 CLI 는 v1 의 `python -m tools.*` 명령을 runpy 로 dispatch 하므로 v1 호출도
그대로 동작합니다. `python -m vta` 와 `python -m tools.*` 어느 쪽이든 결과는
동일합니다.

### v1 직접 호출 (호환)

전체 CLI 인덱스는 `python -m tools.cli_index` 로 출력된다. 자주 쓰는 도구:

| 도구 | 용도 |
|---|---|
| `python -m tools.run_validation --demo` | 신용/PD 모형 thin runner |
| `python -m tools.run_macro_validation --demo` | 거시 / forward-looking 모형 runner |
| `python -m tools.run_ifrs9_validation --demo` | IFRS 9 ECL 통합 runner |
| `python -m tools.run_workflow_demo --stress / --async` | 동적 워크플로우 합성 데이터 데모 |
| `python -m tools.run_audit demo` | 매트릭스 plan vs 실제 실행 감사 |
| `python -m tools.dry_run --demo` | 오케스트레이터 호출 시뮬레이션 |
| `python -m tools.dry_run_diff --before A --after B` | 두 매트릭스 plan 비교 |
| `python -m tools.benchmark --n 100000 --runs 5` | workflow step 별 성능 측정 |
| `python -m tools.workflow_viz --log <run.jsonl>` | 실행 로그 → mermaid 다이어그램 |
| `python -m tools.dashboard --out <html>` | 실행 로그 → 정적 HTML 대시보드 |
| `python -m tools.report_pdf --demo --out <pdf>` | 보고서 → PDF (DRAFT 워터마크 강제) |
| `python -m tools.report_pack --out <dir>` | 계층형 HTML 보고서 팩 (요약+부문상세+심화) |
| `python -m tools.report_pack --input-csv <csv> --mapping <json> --out <dir>` | 운영 추출 파일로 보고서 팩 빌드 (어댑터 boundary 경유) |
| `python -m tools.report_export --pack <dir>` | 팩 → CSV/JSON/페이지 manifest export |
| `python -m tools.findings_mapping --log <jsonl>` | audit log → recurring_findings 후보 매핑 |
| `python -m tools.pack_diff --prev A --curr B` | 두 보고서 팩 간 변화 detection |
| `python -m tools.pack_verify --pack <dir> [--deep]` | 팩 재현성 자체검증 (입력해시·정책·코드·페이지 재빌드) |
| `python -m tools.val_coverage report / verify` | PRD-VAL 업무요건 대비 구현 커버리지 (근거 실재성 강제) |
| `python -m tools.domain_criteria list / report / verify` | 도메인 업무요건 131건 → 적합성검증 기준 항목: 부문·검증관점별 집계, 자동 통제의 근거 실재성 강제 |
| `python -m tools.gen_domain_criteria --out <json>` | 기준 항목 원장 생성기: RYNTA BRD 레지스터가 바뀌면 재실행 (손으로 고치지 않는다) |
| `python -m tools.regulatory_criteria list / report / precedence / thresholds / cite-check / verify` | 규제 기준 검증 항목: 기준 스택(규정→세칙→바젤), 인용의 원문 해석, 규정 임계 대 하니스 임계 대조 |
| `python -m tools.gen_regulatory_criteria --out <json>` | 규제 검증 항목 생성기: 라인 번호·지배기준을 손으로 적지 않고 파생 |
| `python -m tools.pd_cyclicality demo / analyse / convert` | PD 설계 구분(TTC·PIT) 검증: 등급별 PD 경기 민감도, 등급 수준 시점 추종성, 단일요인 변환 왕복 |
| `python -m tools.validation_trigger triggers / evaluate / queue` | 상시 모니터링 트리거 평가 → 검증 사례 생성·검토 큐 |
| `python -m tools.validation_finding open / remediate / reverify / close / queue / lineage / blockers` | Finding 원장 — 재검증 없는 종결 차단·재발 시 중대도 상향 |
| `python -m tools.validation_memory rounds / patterns / self-defects / carryover / verify` | 검증 기억 원장 — 회차·결함 계보·자기결함·이월을 생성·상호 대조 (손으로 세지 않는다) |
| `python -m tools.reg_rules list / effective / calendar / verify` | 규제 규칙 카탈로그 — 근거수준·원문주기·유효일자 분리, 경과조치 파생, 검증 캘린더(법정/내부 이중 표시) |
| `python -m tools.independent_recalc list / run` | 독립 재계산 + 차이 원인 분해 (데이터/모형/산식/구현 기여도). 비율형 6종 + 합계형(RWA 합계와 산출하한·총자본비율·ECL 합계·대손준비금 소요액) |
| `python -m tools.ivr_response validate / build` | 독립검증 응답(response.json) 작성·검증: 요청 대조(run_id·request_id·재계산 대상 전수), 판정을 지적에서 파생, 2선 게이트가 거절할 응답을 먼저 잡는다 (`harness/ivr_response.schema.json`) |
| `python -m tools.golden_regression run [--change-request <json>]` | Golden Case 회귀검증 — 범위 밖 변경 시 배포 차단 |
| `python -m tools.validation_scope tiers / score / check` | 모형 중요도 등급 + 검증계획 최소 심도·주기 강제 |
| `python -m tools.conditional_approval grant / fulfil / status / check-scope` | 조건부 승인 — 잔여위험·후속조건·제한 배포 범위 |
| `python -m tools.adversarial_review challenges / review --request <json>` | 적대적 검증 — 반증 중심 검토 + 검증의견 초안 |
| `python -m tools.pack_archive add/list/latest/prune --archive <dir>` | 분기별 팩 archive 관리 |
| `python -m tools.data_adapter validate/convert --input <csv>` | 운영 추출 파일 안전 로더 (PII 차단) |
| `python -m tools.cro_digest --out <html>` | CRO 분기 요약 이메일 초안 (발송 없음 — HITL) |
| `python -m tools.manifest list / add / promote / validate / export` | change_manifest 운영 |
| `python -m tools.findings list / sync / add / bump` | recurring_findings JSON↔md |
| `python -m tools.model_notes list / sync` | model_specific_notes JSON↔md |
| `python -m tools.limitations list / sync` | known_limitations JSON↔md |
| `python -m tools.governance_kpi report` | 분기 거버넌스 KPI 보고 |
| `python -m tools.policy_lint --include-sample-size` | 정책 임계값 일관성 lint |
| `python -m tools.classify_error classify / suggest / feedback / rule-patch` | harness_debugger 6분류 |
| `python -m tools.feedback_retention prune / anonymize` | 학습 시그널 retention |
| `python -m tools.audit_retention prune / truncate` | audit.jsonl retention |
| `python -m tools.runner_result --runner credit/macro/ifrs9` | runner 결과 schema 검증 |

---

## 정책 파일 (SSoT)

코드와 분리된 정책은 모두 `harness/` 또는 `memory/` 에 있고 schema 로 강제된다.

| 정책 | SSoT | Schema |
|---|---|---|
| 변경 매니페스트 | `harness/change_manifest.json` | `harness/change_manifest.schema.json` |
| 오케스트레이션 매트릭스 | `harness/orchestration_matrix.json` | `harness/orchestration_matrix.schema.json` |
| 권한 패턴 | `harness/permission_matrix.json` | `harness/permission_matrix.schema.json` |
| 시나리오 floor | `harness/scenario_floors.json` | `harness/scenario_floors.schema.json` |
| Basel 리스크 택소노미 | `harness/basel_risk_taxonomy.json` | `harness/basel_risk_taxonomy.schema.json` |
| 부문별 임계값 (자본/시장/운영/유동성/IRRBB/CVA/CCR/집중/내부자본/ALM) | `harness/{capital_adequacy,market_risk,operational_risk,liquidity_risk,irrbb,cva,ccr,concentration,icaap,alm}_thresholds.json` | (tools/policy_lint 게이트) |
| 보고서 도메인 사전 | `harness/report_glossary.json` | `harness/report_glossary.schema.json` |
| 임계 설명가능성 attribution | `harness/explainability_attributions.json` | (tools/explainability 게이트) |
| PRD-VAL 요건 커버리지 | `harness/val_requirement_coverage.json` | (tools/val_coverage verify 게이트) |
| `harness/regulatory_rule_catalog.json` | 규제 규칙 카탈로그 — 근거수준(국내구속/Basel/내부권고)·원문주기·유효일자(출력하한 경과조치)·RETIRED 차단·의견 코드 5종 매핑 |
| `harness/domain_requirement_criteria.json` | RYNTA BRD Level 1 도메인 업무요건 131건 → 적합성검증 기준 항목 (부문·검증관점·자동/수동/범위밖 · 근거 실재성 강제) |
| `harness/regulatory_criteria.json` | 규제 검증 항목 63건 + 계량 임계 10건: 근거 원문 3종(`harness/reference/` 은행업감독규정·시행세칙·Basel Framework 소스북, 지문 고정). 국내 우선·모호 시 바젤 보충 |
| `harness/pd_design_thresholds.json` | PD 설계(TTC·PIT) 판정 임계. 관측기간 5년은 세칙 별표 3 인용값이며 임계 원장이 원문과 대조 |
| `harness/valdoc_coverage.json` | 적합성검증 요건문서(개요서·해설서·BRD v9.6.0 DDOC-VAL) 대비 하니스 커버리지 — v9.6.0 정규 부모 master_ref 연결 |
| `harness/valdoc_discrepancy_registry.json` | 요건 마스터 자체 불일치 6건(VAL-GAP, PENDING_4_EYES) 참조 사본 — 인지·추적 전용, 해소 권한은 마스터 소유자 |
| 검증 트리거 원장 | `harness/validation_triggers.json` | (tools/validation_trigger 게이트) |
| 직무분리(SoD) 정책 | `harness/sod_policy.json` | (middleware/sod_guard 게이트) |
| Golden Case 집합 | `harness/golden_cases.json` | (tools/golden_regression 게이트) |
| 모형 중요도 기준 | `harness/model_materiality.json` | (tools/validation_scope 게이트) |
| 적대적 검증 프로토콜 | `harness/adversarial_protocol.json` | (tools/adversarial_review 게이트) |
| 인쇄 CSS | `harness/report_print.css` | — |
| 감사 보고서 schema | — | `harness/audit_report.schema.json` |
| Runner 결과 schema | — | `harness/runner_result{,_credit,_macro,_ifrs9}.schema.json` |
| 반복 발견 | `memory/recurring_findings.json` | (sync gate) |
| 모형군 노트 | `memory/model_specific_notes.json` | (sync gate) |
| 알려진 한계 | `memory/known_limitations.json` | (sync gate) |

---

## 권한 제한

본 에이전트는 다음 작업을 **수행하지 않는다**.

- 운영계 DB 직접 접속 또는 변경
- 운영 시스템 파일 삭제
- 대외 제출 문서 / 감독기관 제출용 수치 최종 확정
- 실제 고객 식별정보 저장 (주민번호, 계좌번호, 전화번호, 이메일 등)
- API Key, 비밀번호, 토큰의 출력 또는 저장
- 사용자 승인 없는 배포 / 커밋 / 푸시
- 검증 기준의 임의 완화

---

## 운영계 반영 금지 / 인간 승인 필요 영역

다음 항목은 **반드시 인간 검증자의 검토와 승인** 후에만 진행될 수 있다.

- 모형 승인 또는 부적합 의견 확정
- 검증보고서 / 검증의견서의 외부 제출본 확정
- 운영계 ECL 산식, PD/LGD/EAD 캘리브레이션 적용
- 스트레스 테스트 결과의 자본 계획 반영
- 감독기관 대응 문안 확정

---

## 도입 단계 (제안)

본 하니스 도입은 단계적 적용을 권고한다. 상세는 `docs/executive_summary.md`.

| Phase | 기간 | 종료 조건 |
|---|---|---|
| Phase 0 — 모형위험 분류 | 1개월 | MRMC 가 본 하니스를 Tier 2 보조 모형으로 분류 + 감독원 사전 공유 |
| Phase 1 — 병행 운영 | 6개월 | 기존 수기 검증과 병행. 분기 KPI 보고. |
| Phase 2 — 통합 운영 | 이후 | 매니페스트 validated 비율 ≥ 70% + 분기 결과 차이 < 5% |
| Phase 3 — 확장 검토 | TBD | 보험·시장리스크 등 인접 모형군 확장 검토 |

분기 KPI 는 `python -m tools.governance_kpi report` 로 산출한다.

---

## 라이선스 및 책임

본 하니스의 모든 산출물은 **검증 보조 자료**다. 최종 검증 의견과 책임은 인간
검증자에게 있다. 본 하니스 자체가 검증 의견에 영향을 주는 모형이므로 MRMC 의
분류·승인을 받아야 한다 (`docs/executive_summary.md` 1·6절 참조).
