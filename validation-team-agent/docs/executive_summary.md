# Executive Summary — Governance for Adopting validation-team-agent

본 문서는 CRO / 모형위험관리위원회(MRMC) / 감사위원회의 의사결정용 거버넌스
요약이다. 본 하니스를 운영에 도입하기 전 반드시 검토해야 한다.

본 문서 자체는 메타 의견 초안이며, 정책 부서·법무·감독 대응 부서의 협의를 거쳐
공식 정책으로 확정되어야 한다.

---

## 1. 본 하니스의 위치 (Tier 분류 제안)

| 항목 | 내용 |
|---|---|
| 분류 (제안) | **Tier 2 보조 모형** (validation aid, not validation opinion) |
| 산출물 성격 | 검증보고서 초안 / 점검표 / 감사추적 |
| 산출물 권한 | 외부 제출본 / 감독기관 제출본 / 모형 승인의견 확정 **불가** |
| 자동화 의존도 | 수치 산출은 결정론적, 의견 확정은 인간 검증자 |

본 하니스 자체가 "검증 의견에 영향을 주는 모형"이므로 MRMC 승인 절차를 거쳐야
한다. 도구가 만들어내는 의견이 아니라 **도구 자체가 모형**이다.

---

## 2. 도입 단계 (제안)

| Phase | 기간 | 종료 조건 |
|---|---|---|
| Phase 0 — 모형위험 분류 | 1개월 | MRMC가 본 하니스를 Tier 2로 분류 + 감독원 사전 공유 |
| Phase 1 — 병행 운영 | 6개월 | 기존 수기 검증과 병행. 분기별 비교 보고. |
| Phase 2 — 통합 운영 | 이후 | 매니페스트 validated 비율 ≥ 70% + 분기 결과 차이 < 5% |
| Phase 3 — 확장 검토 | TBD | 보험·시장리스크 등 인접 모형군 확장 검토 |

각 Phase 전환은 `python -m tools.governance_kpi report` 결과를 첨부하여
MRMC 결의로 진행.

---

## 3. 권한 분리 매트릭스 (제안)

| 권한 | 담당 | 도구 |
|---|---|---|
| 매니페스트 항목 추가 (`status=proposed`) | 모든 검증팀원 | `tools.manifest add` |
| `proposed → applied` 전환 | **검증팀장** | `tools.manifest promote-if-passing --to applied --i-am-human` |
| `applied → validated` 전환 | **CRO 또는 위임자** | `tools.manifest promote-if-passing --to validated --i-am-human` |
| `rolled_back` 전환 | 검증팀장 (긴급) | `tools.manifest promote --to rolled_back` |
| `harness/scenario_floors.json` 등 정책 파일 수정 | 리스크관리정책부 | (매니페스트 동반 필수, CI gate) |
| `harness/policies/*.md` 임계 수정 | 리스크관리정책부 | (매니페스트 동반 필수, CI gate) |
| `harness/permission_matrix.json` 수정 | 정보보안부 | (매니페스트 동반 필수) |
| 코드 변경 (`tools/`, `middleware/`) | IT (검증팀 검토) | PR 리뷰 + pytest |

---

## 4. KPI / 모니터링 (분기)

`python -m tools.governance_kpi report` 가 다음을 산출한다.

- 매니페스트: `proposed_count`, `applied_count`, `validated_count`, `validated_ratio`
- 학습 시그널: `feedback_total`, `agreement_rate`, `mismatch_top_pairs`
- 감사: `latest_run_executed`, `latest_run_missing`, `latest_run_skipped`
- 정책 일관성: `policy_lint` / `sample_size_alignment` pass 여부

본 KPI는 **분기 1회** CRO/감사위원회 보고 의무 (제안).

---

## 5. 절대 금지선

다음은 본 하니스 도입 후에도 절대 허용되지 않는다.

1. 산출물을 **검증의견서 갈음 자료로 외부 제출**
2. `promote-if-passing` 의 **CI 무인 실행** (반드시 인간 명령에서만)
3. 임계값(`metric_policy.md`, `scenario_floors.json`)을 코드 수정만으로 완화
4. 자동 분류기 결과를 `confidence=low` 인 채로 매니페스트에 확정
5. **본 하니스 도입을 검증팀 인력 감축 사유로 사용**

---

## 6. 핵심 리스크 (Round 12 시점)

| 리스크 | 통제 |
|---|---|
| Automation bias | 보고서 DRAFT 워터마크 + 인간 검증자 책임 명시 + 분기 병행 검토 |
| 2차 모형위험 | MRMC 분류 + 본 문서의 도입 단계 강제 |
| 정책 schema 통과 ≠ 정책 적정성 | 정책 변경 시 매니페스트 root_cause / expected_benefit 의무 |
| 민감정보 false negative | 비식별 처리는 데이터팀 사전 책임, hardness 가드는 2차 방어 |
| 분류기 휴리스틱 한계 | `--allow-sensitive` / `confidence=low` 경고 + 분기 agreement_rate 검토 |

---

## 7. 본 의견의 한계

- 본 문서는 작업 산출물 기반의 **메타 의견 초안**이다. 도입 정책 / 권한 매트릭스 /
  KPI 임계는 정책 부서가 확정한다.
- "검증 사이클 시간 30~50% 절감"은 추정값이다. Phase 1 병행 운영 결과로 실측 필요.
- 감독원 사전 공유 및 분류 의견은 본 하니스의 권한이 아니다.
