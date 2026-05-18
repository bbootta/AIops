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
├── docs/                         # 운영 모델·위험통제·HITL 정책
├── harness/                      # 시스템 프롬프트, 정책, 변경 매니페스트
├── skills/                       # 도메인별 절차 지식
├── subagents/                    # 서브에이전트 역할 정의
├── tools/                        # 검증용 Python 함수
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
```

또는 패키지 형태로:

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

전체 CLI 인덱스는 `python -m tools.cli_index` 로 출력된다. 자주 쓰는 도구:

| 도구 | 용도 |
|---|---|
| `python -m tools.run_validation --demo` | 신용/PD 모형 thin runner |
| `python -m tools.run_macro_validation --demo` | 거시 / forward-looking 모형 runner |
| `python -m tools.run_ifrs9_validation --demo` | IFRS 9 ECL 통합 runner |
| `python -m tools.run_audit demo` | 매트릭스 plan vs 실제 실행 감사 |
| `python -m tools.dry_run --demo` | 오케스트레이터 호출 시뮬레이션 |
| `python -m tools.dry_run_diff --before A --after B` | 두 매트릭스 plan 비교 |
| `python -m tools.manifest list / add / promote / validate / export` | change_manifest 운영 |
| `python -m tools.findings list / sync / add / bump` | recurring_findings JSON↔md |
| `python -m tools.model_notes list / sync` | model_specific_notes JSON↔md |
| `python -m tools.limitations list / sync` | known_limitations JSON↔md |
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
| 보고서 도메인 사전 | `harness/report_glossary.json` | `harness/report_glossary.schema.json` |
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
