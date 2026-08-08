# research/ — 연구 사이클 산출물 규약

`risk-premium-lab` 워크플로우와 개별 팀 에이전트의 산출물이 저장되는 디렉토리.

| 경로 | 산출팀 | 내용 |
|---|---|---|
| `briefs/` | 리드 교수 | 연구 브리프 (`brief.md`) |
| `literature/` | 선행연구 조사팀 | 주제별 심층조사 보고서 |
| `methodology/` | 방법론 개발팀 → 리드 교수 | 설계안 `proposal-N.md`, 채택 통합 스펙 `spec.md` |
| `simulations/` | 시뮬레이션팀 | `src/`, `run_*.py`, `output/`(결과 표·`results.md`), 재현용 `README.md` |
| `validation/` | 검증팀 | 검증 보고서 `round-N.md` (PASS/FAIL 판정 포함) |
| `paper/` | 논문 작성팀 | `draft-vN.md`, `changelog.md` |
| `reviews/` | 피어 리뷰팀 | `round-N-referee-M.md` |
| `agenda/` | 후속연구 발굴팀 | `future-research.md` (누적 관리) |
| `correspondence/` | 교신팀 | 커버레터, 심사위원 대응문, 대외 문서 |

## 규칙

- 파일은 덮어쓰지 말고 버전/라운드 번호를 올려 남긴다 (감사 추적 가능하게).
- 모든 수치 표에는 생성 스크립트 경로를 각주로 기재한다.
- 시뮬레이션은 시드 고정, `README.md`의 명령만으로 전체 재현 가능해야 한다.
