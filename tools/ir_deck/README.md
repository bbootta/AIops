# IR 덱 자동 버전관리·취합 (디캠프 9기)

Slack 채널 `C0BK4SCJUBV`에 올라온 1슬라이드 PPTX를 버전으로 등록하고, 승인·채택 명령을 기록하고, 요청 시 S01~S20 순서로 병합한 PPTX·PDF를 스레드에 올린다.

## 동작 구조

| 단계 | 담당 | 내용 |
| --- | --- | --- |
| 업로드 | 작성자 | `OLA_DCAMP9_S09_BusinessModel_v0.2.0_20261005_JJ.pptx` 형식 파일을 채널에 업로드 |
| 버전 등록 | 실행기 | 1슬라이드·파일명 확인, sha256 기록, 초안 등록. 버전 미기재 시 다음 patch 자동 부여, 같은 버전 다른 내용은 거부 |
| 승인·반려 | 검토자 | `승인 S09 v0.2.0` / `반려 S09 v0.2.0 사유`. 업로더 본인은 불가(4-Eyes) |
| 채택 | 책임자 | `채택 S09 v0.2.0`. 승인본만 가능, 이전 채택본은 `대체` |
| 취합 | 누구나(취합 버튼 포함) | `취합`: S01~S20 채택본 전부 필요, 누락 시 중단 / `취합 초안`: 장표별 최신 비반려본, 제출용 아님 |
| 산출 | 실행기 | 병합 PPTX·PDF를 명령 스레드에 업로드, 현황 캔버스 재작성, 메인 캔버스 `최신 취합본:` 줄 갱신 |

- 실행 주기: GitHub Actions `ir-deck run`, 10분마다(지연 가능). 수동 실행은 Actions 화면의 Run workflow
- 실행 시간: 평소 1분 안팎. 취합 명령이 있을 때만 LibreOffice·폰트를 설치하고 이어서 처리
- 상태 저장: Slack에 봇 비공개 파일 `ir_deck_state.json`으로 저장. 바뀔 때마다 새 파일을 올리고 이전 파일은 삭제. 저장소가 공개라서 커밋하지 않음
- 메시지 범위: 최상위 메시지와 최근 14일 안에 시작된 스레드의 새 답글
- 봇 메시지: 봇·워크플로 메시지는 `취합`·`취합 초안`만 받음. 업로드·승인·반려·채택은 사람 메시지만(4-Eyes 신원 확인)
- 무결성: 취합 시 파일을 다시 내려받아 등록 당시 sha256과 비교, 다르면 중단
- 실패 처리: 실패 빌드는 이력에만 남기고 직전 성공본 링크는 유지. 메시지 1건 처리 오류는 그 스레드에 오류 답글을 남기고 다음 메시지로 진행
- 병합 방식: 슬라이드 파트와 레이아웃·마스터·테마·이미지·차트를 패키지 단위로 복사. 같은 템플릿은 재사용, 다른 템플릿은 마스터 추가. 발표노트는 텍스트로 복사(서식은 유지되지 않음)

## 설정 (1회)

1. Slack 앱 생성: https://api.slack.com/apps → Create New App → From a manifest → 아래 매니페스트 붙여넣기
2. 워크스페이스 설치: 관리자 승인이 필요한 워크스페이스는 승인 요청 후 설치
3. 채널 초대: IR 채널(C0BK4SCJUBV)에서 `/invite @IR Deck Bot`
4. GitHub 저장소 설정
   - Settings → Secrets and variables → Actions → Secret `SLACK_BOT_TOKEN` = 봇 토큰(`xoxb-...`)
   - 같은 화면 Variables 탭 → `IR_DECK_ENABLED` = `true`
5. 메인 캔버스 편집 권한(선택): 메인 캔버스 공유 설정에서 IR 채널 권한을 "편집 가능"으로 두면 봇이 `최신 취합본:` 줄을 갱신한다. 권한이 없으면 현황 캔버스만 갱신된다
6. 첫 실행: Actions → `ir-deck run` → Run workflow → `bootstrap` 체크 후 실행. 상태 파일과 현황 캔버스를 만들고 채널에 현황 캔버스 링크를 올린다. 첫 실행 시각 이후 메시지만 처리한다
   - `bootstrap`은 처음 1회만 켠다. 이후 예약 실행이 상태 파일을 찾지 못하면 새로 시작하지 않고 실패로 멈춘다
   - 첫 실행은 봇이 올린 비공개 상태 파일을 다시 찾을 수 있는지도 확인한다. 이 확인이 실패하면 실행이 빨간색으로 끝난다

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
- 버튼이 올린 메시지는 봇 메시지라 취합 요청만 처리된다. 빌드 이력의 요청자는 워크플로 봇 ID로 남는다

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
- 오래된 스레드: 14일보다 전에 시작된 스레드의 새 답글은 처리하지 않는다. 새 메시지로 다시 입력
- Slack 호출 한도: 사내 전용 앱 기준으로 설계. Slack이 2025-05에 비마켓플레이스 앱의 대화 조회 한도를 낮췄는데, 이 앱에 적용되는지는 확인하지 못함. 적용되면 429 응답마다 대기 후 재시도하므로 실행이 느려질 수 있음
- 실행 환경: GitHub Actions 예약 실행을 상시 봇처럼 쓰는 임시 구성. 제출 이후에도 쓰려면 사내 서버나 클라우드 실행 환경으로 옮기는 것을 권장(GitHub Actions 이용 약관의 용도 제한 검토 필요)
