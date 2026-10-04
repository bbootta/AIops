# IR 덱 자동 버전관리·취합 (디캠프 9기)

Slack 채널 `C0BK4SCJUBV`에 올라온 1슬라이드 PPTX를 버전으로 등록하고, 승인·채택 명령을 기록하고, 요청 시 S01~S20 순서로 병합한 PPTX·PDF를 스레드에 올린다.

## 동작 구조

| 단계 | 담당 | 내용 |
| --- | --- | --- |
| 업로드 | 작성자 | `OLA_DCAMP9_S09_BusinessModel_v0.2.0_20261005_JJ.pptx` 형식 파일을 채널에 업로드 |
| 버전 등록 | 실행기 | 1슬라이드·파일명 확인, sha256 기록, 초안 등록. 버전 미기재 시 다음 patch 자동 부여, 같은 버전 다른 내용은 거부 |
| 승인·반려 | 검토자 | `승인 S09 v0.2.0` / `반려 S09 v0.2.0 사유`. 업로더 본인은 불가(4-Eyes) |
| 채택 | 책임자 | `채택 S09 v0.2.0`. 승인본만 가능, 이전 채택본은 `대체` |
| 취합 | 누구나 | `취합`: S01~S20 채택본 전부 필요, 누락 시 중단 / `취합 초안`: 장표별 최신 비반려본, 제출용 아님 |
| 산출 | 실행기 | 병합 PPTX·PDF를 명령 스레드에 업로드, 현황 캔버스 재작성, 메인 캔버스 `최신 취합본:` 줄 갱신 |

- 실행 주기: GitHub Actions `ir-deck run`, 10분마다(지연 가능). 수동 실행은 Actions 화면의 Run workflow
- 상태 저장: `deliverables/ir_deck/dcamp9/registry.json` (실행 후 자동 커밋)
- 무결성: 취합 시 파일을 다시 내려받아 등록 당시 sha256과 비교, 다르면 중단
- 실패 처리: 실패 빌드는 이력에만 남기고 직전 성공본 링크는 유지
- 병합 방식: 슬라이드 파트와 레이아웃·마스터·테마·이미지·차트를 패키지 단위로 복사. 같은 템플릿은 재사용, 다른 템플릿은 마스터 추가. 발표노트는 텍스트로 복사(서식은 유지되지 않음)

## 설정 (1회)

1. Slack 앱 생성: https://api.slack.com/apps → Create New App → From a manifest → 아래 매니페스트 붙여넣기
2. 워크스페이스 설치: 관리자 승인이 필요한 워크스페이스는 승인 요청 후 설치
3. 채널 초대: IR 채널(C0BK4SCJUBV)에서 `/invite @IR Deck Bot`
4. GitHub 저장소 설정
   - Settings → Secrets and variables → Actions → Secret `SLACK_BOT_TOKEN` = 봇 토큰(`xoxb-...`)
   - 같은 화면 Variables 탭 → `IR_DECK_ENABLED` = `true`
5. Actions → `ir-deck run` → Run workflow로 첫 실행. 첫 실행 시각 이후 메시지만 처리하며, 현황 캔버스를 만들어 채널에 링크를 올린다

```yaml
display_information:
  name: IR Deck Bot
  description: 디캠프 9기 IR 장표 버전관리·취합
features:
  bot_user:
    display_name: IR Deck Bot
    always_online: false
oauth_config:
  scopes:
    bot:
      - channels:history
      - groups:history
      - chat:write
      - files:read
      - files:write
      - canvases:read
      - canvases:write
      - users:read
settings:
  org_deploy_enabled: false
  socket_mode_enabled: false
  token_rotation_enabled: false
```

## 취합 버튼 (선택)

Slack 캔버스는 실행 버튼을 지원하지 않는다. 클릭 한 번으로 요청하려면 Workflow Builder로 링크 트리거를 만든다.

- Workflow Builder → 새 워크플로 → 시작: "링크에서 시작" → 단계: "채널에 메시지 보내기"(채널 C0BK4SCJUBV, 메시지 `취합 초안` 또는 `취합`)
- 게시 후 받은 링크를 메인 캔버스 `취합·다운로드` 섹션에 붙인다

## 테스트

```bash
pip install -r tools/ir_deck/requirements.txt pytest
python -m pytest tools/ir_deck -q --noconftest -p no:cacheprovider
```

- CI(`ir-deck CI`)는 LibreOffice를 설치해 병합본 PDF 장수까지 확인한다(`IR_REQUIRE_PDF=1`)

## 한계

- 반영 지연: 최대 10~20분(GitHub 예약 실행 지연 포함)
- 캔버스 표 직접 편집 불가: 현황 캔버스는 매 실행 시 다시 쓴다. 메인 캔버스는 `최신 취합본:` 한 줄만 바꾼다
- 발표노트 서식, SmartArt·OLE 등 특수 개체는 PowerPoint에서 최종 확인 필요
- 승인 권한 범위: 채널 구성원 중 업로더가 아닌 사람이면 승인 가능. 승인자 명단 제한이 필요하면 별도 설정 추가
