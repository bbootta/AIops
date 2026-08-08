# 보안 취약점 모니터링 런북

로컬 머신과 회사 자산의 취약점을 모니터링하는 Claude 에이전트 팀의
운영 절차. 모든 점검은 방어 목적이며 읽기 전용이다.

## 전제 조건

- `templates/asset-inventory.md`에 점검 대상 자산이 등재되고 소유/권한이
  확인돼 있어야 한다. 목록에 없는 자산은 점검하지 않는다.
- 익스플로잇 실행, 능동 스캔(포트 스캔·무차별 대입), 타인 시스템 점검은
  이 하네스의 범위 밖이다.

## 워크플로우 1: 주간 정기 모니터링

주 1회 실행. 산출물은 `templates/weekly-security-watch.md` 형식.

1. **자산 확인** — `security-team-lead`가 자산 목록의 최신 여부를 확인한다.
   변경(신규 서비스, 폐기 자산)이 있으면 먼저 반영한다.
2. **권고 수집** — `advisory-watch-analyst`가 지난 1주간 벤더 공지,
   KISA/KrCERT, CERT 권고를 수집하고 자산 목록과 대조한다.
3. **CVE 대조** — `cve-intelligence-analyst`가 자산 목록의 소프트웨어/버전에
   해당하는 신규 CVE를 조회한다. KEV 신규 등재 항목은 즉시 플래그.
4. **트리아지** — `remediation-prioritizer`가 신규 발견을 P1/P2/P3로 분류하고
   조치 계획을 세운다.
5. **품질 검증** — `findings-quality-reviewer`가 오탐과 근거 누락을 걸러낸다.
6. **보고** — `security-team-lead`가 주간 보고서를 작성하고
   `templates/findings-log.csv`에 발견 사항을 누적 기록한다.

P1 발견 시 주간 주기를 기다리지 않고 즉시 사용자에게 보고한다.

## 워크플로우 2: 로컬 머신 점검

월 1회 또는 사용자 요청 시.

1. `local-host-auditor`가 패치 수준, 리스닝 포트, 서비스, 방화벽, SSH 설정,
   계정 권한을 읽기 전용으로 점검한다.
2. `dependency-audit-analyst`가 로컬의 활성 프로젝트 lockfile을 감사한다.
3. `remediation-prioritizer`가 결과를 트리아지한다.
4. `security-team-lead`가 조치 명령을 사용자가 직접 실행할 수 있는 형태로
   정리해 보고한다. 에이전트가 직접 시스템을 변경하지 않는다.

## 워크플로우 3: 신규 CVE 긴급 대응

중대 취약점 공개 시(예: 주요 프레임워크 RCE) 사용자 요청으로 실행.

1. `cve-intelligence-analyst`가 CVE 상세(영향 버전, 패치, KEV/EPSS)를 확인한다.
2. `dependency-audit-analyst` + `local-host-auditor`가 해당 소프트웨어의
   실제 사용 여부와 버전을 확인한다.
3. 영향이 있으면 `remediation-prioritizer`가 즉시 조치 계획을 만든다.
4. `security-team-lead`가 "영향 있음/없음 + 근거 + 조치"를 한 페이지로 보고한다.

## 워크플로우 4: 회사 노출면 검토

분기 1회 또는 자산 변경 시. 권한 확인이 선행돼야 한다.

1. `infra-exposure-analyst`가 자산 목록의 도메인/서비스에 대해 인증서,
   보안 헤더, DNS, 공개 서브도메인(CT 로그 기반)을 검토한다.
2. 사내 제공 설정 문서/IaC가 있으면 정적 검토를 병행한다.
3. 이후 트리아지·검증·보고는 워크플로우 1의 4–6단계와 동일.

## 보고 규칙

- 발견 사항은 `templates/vuln-finding.md` 형식으로 기록한다.
- 비밀값(키, 토큰, 비밀번호)은 어떤 산출물에도 포함하지 않는다.
- 모든 발견에 확인 일자와 근거를 붙인다. 발행일과 확인일을 구분한다.
- 확인하지 못한 것은 확인하지 못했다고 쓴다.
