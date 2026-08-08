# 보안 취약점 모니터링 에이전트 팀

로컬 머신과 회사 자산의 보안 취약점을 모니터링하는 Claude Code
에이전트 팀 하네스. 방어 목적 전용이며 모든 점검은 읽기 전용이다.

## 구성

```
.claude/agents/          에이전트 정의 (Claude Code 서브에이전트)
harness/
  security-monitoring-runbook.md   운영 절차 (워크플로우 4종)
  team.yaml                        팀 구성과 정책
  source-map.md                    참조 소스 목록 (NVD, KEV, KISA 등)
templates/
  asset-inventory.md               점검 대상 자산 등록부
  vuln-finding.md                  발견 사항 기록 양식
  weekly-security-watch.md         주간 보고 양식
  findings-log.csv                 발견 사항 누적 로그
```

## 에이전트

| 에이전트 | 역할 |
|---|---|
| `security-team-lead` | 범위 결정, 작업 배분, 종합 보고 |
| `cve-intelligence-analyst` | CVE/KEV/EPSS 조회와 버전 대조 |
| `advisory-watch-analyst` | 벤더 공지, KISA/KrCERT 권고 모니터링 |
| `dependency-audit-analyst` | 프로젝트 의존성 취약점 점검 (SCA) |
| `local-host-auditor` | 로컬 머신 읽기 전용 보안 점검 |
| `infra-exposure-analyst` | 권한 확인된 회사 자산의 외부 노출면 검토 |
| `remediation-prioritizer` | P1/P2/P3 트리아지와 조치 계획 |
| `findings-quality-reviewer` | 최종 보고 전 오탐·근거 검증 |

## 시작하기

1. `templates/asset-inventory.md`에 점검 대상 자산을 등록한다.
   **등재되고 권한이 확인된 자산만 점검한다.**
2. 원하는 워크플로우를 요청한다. 예:
   - "주간 보안 모니터링 실행해줘" → 런북 워크플로우 1
   - "내 로컬 머신 점검해줘" → 워크플로우 2
   - "CVE-XXXX-XXXXX 우리한테 영향 있어?" → 워크플로우 3
   - "회사 노출면 검토해줘" → 워크플로우 4
3. 발견 사항은 `templates/findings-log.csv`에 누적 기록된다.

## 범위 제한

- 익스플로잇 실행, 능동 스캔(포트 스캔·무차별 대입), 권한 없는 자산
  점검은 하지 않는다.
- 에이전트는 시스템을 변경하지 않는다. 조치는 사용자가 직접 실행할
  명령 형태로 제시된다.
- 비밀값(키, 토큰, 비밀번호)은 어떤 산출물에도 포함하지 않는다.
