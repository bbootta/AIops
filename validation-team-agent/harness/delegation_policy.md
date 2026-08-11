# Delegation Policy

서브에이전트 호출 정책. 서브에이전트는 남발하지 않는다.

---

## 1. 호출 조건 (모두 만족해야 호출 가능)

1. 작업 단위가 독립적으로 검증 가능하다.
2. 산출물 형식이 명확하다.
3. 결과를 오케스트레이터가 통합할 수 있다.
4. 완료 기준이 객관적이다.
5. 전체 맥락이 사라지지 않는다.

---

## 2. 호출 우선순위

1. `tools/`로 해결 가능한 작업은 도구를 직접 사용한다.
2. `skills/`로 절차가 정의된 작업은 스킬 절차를 따른다.
3. 위 둘로 안 되는 작업만 서브에이전트를 호출한다.
4. 인간 판단이 필요한 영역은 서브에이전트가 아니라 사용자에게 질의한다.

---

## 3. 서브에이전트 간 자유 대화 금지

- 서브에이전트끼리 직접 대화하지 않는다.
- 모든 산출물은 오케스트레이터가 수집·통합한다.
- 한 서브에이전트의 출력이 다른 서브에이전트의 입력이 될 때는 반드시
  오케스트레이터가 입력 형식을 확인하고 전달한다.

---

## 4. 호출 매트릭스

| 작업 | 우선 도구/스킬 | 보조 서브에이전트 |
|---|---|---|
| 데이터 품질 점검 | `tools/data_profile.py`, `skills/data_quality_review.md` | `data_quality_reviewer.md` |
| 변별력 / 안정성 / 캘리브레이션 | `tools/metric_*` | `quantitative_validator.md` |
| 가정 / 변수 / 시나리오 검토 | `skills/methodology_*` | `methodology_reviewer.md` |
| 내부통제 / 문서화 | `middleware/output_completeness_guard.py` | `regulatory_checker.md` |
| 보고서 작성 | `tools/report_template.py`, `skills/validation_report_writing.md` | `report_writer.md` |
| 실행 실패 분석 | `middleware/run_logger.py` 로그 | `harness_debugger.md` |

---

## 5. 완료 기준

서브에이전트는 다음을 만족할 때 완료로 간주한다.

- 입력 명세 충족
- 출력 명세 충족
- 자기 검증 통과
- 한계와 추가 확인사항 명시
