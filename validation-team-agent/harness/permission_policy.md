# Permission Policy

본 하니스의 권한 매트릭스.

---

## 1. 작업 분류

| 분류 | 설명 | 자동 허용 | 인간 승인 필요 |
|---|---|---|---|
| READ-LOCAL | 로컬 파일 읽기, 합성/비식별 데이터 분석 | O | - |
| WRITE-LOCAL | `reports/`, `logs/`, `memory/`, `harness/change_manifest.json` 쓰기 | O | - |
| WRITE-CODE | `tools/`, `middleware/`, `tests/` 코드 수정 | O (사용자 요청 시) | - |
| GIT-LOCAL | 로컬 커밋 | - | O |
| GIT-PUSH | 원격 푸시 | - | O |
| OPS-DB | 운영계 DB 접속/변경 | - | 금지 |
| OPS-FS | 운영계 파일 시스템 변경 | - | 금지 |
| EXTERNAL-IO | 외부 네트워크 호출, 데이터 전송 | - | 금지 |
| FINAL-OPINION | 모형 의견 / 외부 제출 문안 확정 | - | 금지 |

---

## 2. 미들웨어 통제 매핑

| 미들웨어 | 통제 항목 |
|---|---|
| `permission_guard.py` | 위험 명령어, 운영계 반영성 작업, 삭제/배포/외부전송 |
| `data_safety_guard.py` | 주민번호/계좌번호/전화번호/이메일 패턴 |
| `sample_size_guard.py` | 표본 수 / 부도 건수 / 등급별 표본 |
| `leakage_guard.py` | target/outcome 변수의 설명변수 사용 |
| `output_completeness_guard.py` | 보고서 필수 섹션 / 한계 / 추가 확인사항 |
| `run_logger.py` | 실행 메타데이터 기록 |

---

## 3. 우회 금지

- 미들웨어 우회를 위한 `--no-verify`, sandbox 무력화 등은 금지.
- 미들웨어가 차단하면 사용자에게 사유와 근거를 요청한다.
