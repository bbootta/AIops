# 리스크관리 팀에이전트 (2선) — 활동 경로

이 디렉터리는 **리스크관리 팀에이전트**가 만든 산출물이 쌓이는 곳이다.
브랜치 `claude/risk-management-agent-harness-B9Kxm`에서 활동한다.

```
teams/risk-management/
  deliverables/
    <기준일자>/                 예) 2026-06-30 — 규제 보고 기준일 (asof)
      <수행일자>_v<판>/          예) 20260729_v01 — 만든 날 + 그 기준일의 판 번호
        01_datamodel/ … 07_independent_validation/
        MANIFEST.txt            각 파일의 SHA-256
        버전정보.json            이 판의 식별자·지문·게이트 상태·코드 리비전
      <수행일자>_v<판>.zip
    이력.csv · 이력.md           전 판 목록 — **스캔해서 생성한다**
```

## 경로가 곧 소유의 기록이다

이 저장소에는 조직이 셋 있다.

| 선 | 조직 | 산출물이 사는 곳 |
|---|---|---|
| 1·2선 | 리스크관리 팀에이전트 | **여기** (`teams/risk-management/`) |
| 3선 | 적합성검증 팀에이전트<br>`claude/validation-team-agent-Pw9F5` | `docs/independent_validation/` (요청·응답 교환) |
| 내부심사 | AIMS 심사자 (ISO/IEC 42001) | `docs/aims_audits/` |

산출물을 저장소 루트에 두면 **누가 만든 판인지가 경로에 남지 않는다**.
2선 산출물과 3선 산출물이 한자리에 섞이면 "독립"이라는 말이 경로 수준에서
무너진다. 제출본은 리스크관리 팀에이전트가 만든 것이므로 이 경로 아래에만 쌓는다.
검사로 고정돼 있다 — `tests/test_archive.py::test_archive_root_lives_under_the_team_home`.

## 왜 판을 덮어쓰지 않는가

같은 기준일자에 최초 제출본·지적 시정본·재제출본이 모두 생긴다. 규제 보고에서
"어느 판을 제출했는가"는 감사 대상이므로 나란히 쌓는다. 판 번호는 기준일자
**안에서** 센다 — 보고의 단위가 기준일자이기 때문이다. 수행일자는 폴더명에
남겨 "언제 만들었나"를 잃지 않는다.

## 이력은 손으로 적지 않는다

`이력.csv` · `이력.md`는 각 판의 `버전정보.json`을 **스캔한 결과**다. 손으로
적은 목록은 낡는다 — 이 저장소에서 그 유형의 지적이 다섯 번 났다
(독립검증 F-103 · F-201 · F-401 · F-501 · F-B02). 판을 지우면 이력에서도 사라진다.

## 공개된 화면 (에이전틱 UI)

산출물 Pack의 `06_agentic_ui/`는 그 자체로 동작하는 단일 HTML 화면이다. 외부
스크립트·폰트·네트워크 호출이 없고 값이 전부 안에 실려 있어, 파일 하나만
열면 16개 탭·자연어 조회·업무보고서 290장이 그대로 돈다.

기준일 2026-06-30 판을 아티팩트로 배포해 두었다:
<https://claude.ai/code/artifact/2613d0db-3fc5-4849-b35a-1041442c1b38>

배포본은 산출물의 사본이 아니라 **같은 생성기**(`risk_lib.ui_studio`)의 출력이며,
아티팩트가 요구하는 뼈대(doctype·head·body) 제거만 거친다. 화면을 예쁘게 다시
그린 것이 아니다 — 제출물과 다른 화면을 "산출물"이라 부르면 F-501 유형이 된다.

```bash
python3 -c "from risk_lib.cli import main; main(['ui-studio','--asof','2026-06-30','--out','studio.html'])"
```

## 쓰는 법

```bash
# 새 판을 만들고 이력을 갱신한다 (게이트가 적합이 아니면 종료코드 1)
python3 -m risk_lib deliverables --asof 2026-06-30

# 이력만 다시 스캔
python3 -c "from risk_lib.archive import write_ledger; write_ledger()"
```

## 무엇이 커밋되는가

판마다 **핵심만** 커밋한다 — `버전정보.json` · `MANIFEST.txt` ·
`05_regulatory/업무보고서_금감원기준.xlsx` · `07_independent_validation/*`
(판당 약 54KB). 정규 테이블·리포트·UI는 seed·asof·코드 리비전이 같으면 비트
단위로 재생성되고 그 셋이 `버전정보.json`에 적혀 있다. 감사에 필요한 것은
"무엇을 제출했고 그 판의 정체가 무엇인가"이지 파생물 사본이 아니다. 제외 규칙은
저장소 루트 `.gitignore`에 있다.
