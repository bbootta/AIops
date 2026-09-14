# LinkedIn DM 실행 가이드 (2026-09-14)

> 작성: sales-lead · 대상: 신규 50명 (people/linkedin/ 배치 파일들) + SocGen Aurelien
> 실행 주체: **전건 PO** [G1]. 에이전트는 LinkedIn에 접근할 수 없고, 설계상으로도
> L1/DM 발신은 PO 슬롯이다.
> **수정 사유**: 마스터 §6.2 후속 DM은 "I emailed you about..."으로 시작하는데,
> 이 50명에게는 이메일이 발송된 적 없다 (초안 전량 삭제, 2026-09-14). 사실과 다른
> 문장을 지우고 직접 오프너로 교체한 수정본이 아래다. 마스터 원문은 이메일 T1을
> 실제로 보낸 수신자에게만 쓴다.

## 1. 실행 순서

1. **커넥션 노트 먼저.** LinkedIn은 1촌이 아니면 일반 DM을 보낼 수 없다(InMail
   제외). 각 배치 파일(banks-1, banks-2a, banks-2b, insurance, brokers-am)에
   인물별 노트가 300자 이내로 준비되어 있다. URL 열어 헤드라인 확인 후 발신.
2. **수락 후 1~2일 뒤 첫 DM** (§2 세그먼트별 문안).
3. **무응답 시 7일 후 마무리 한 줄** (§3). 그 이후 추가 DM 금지.
4. 볼륨: 일 15~25건 분산. 주간 연결 요청 한도 초과 시 계정 제한 위험.

## 2. 첫 DM (커넥션 수락 후, 세그먼트별)

US 은행 31명:

```
Thanks for connecting, {{first_name}}. The reason I reached out: SR 26-2
keeps validation expectations for traditional models and points
generative and agentic AI to a separate governance framework. Short
version of what we build: a deterministic engine computes, AI assists,
humans approve, everything logged. Is that a live topic for your team
this quarter?
```

US 브로커딜러 6명 (IBKR, Edward Jones, LPL 3, Stifel):

```
Thanks for connecting, {{first_name}}. The reason I reached out: FINRA's
2026 report folds AI-agent monitoring into supervisory procedures. Short
version: we build the evidence layer, every agent action logged,
human-approved, replayable. Is that on your desk this quarter?
```

US 보험 10명 (MetLife, Prudential, Allstate, Lincoln, MassMutual):

```
Thanks for connecting, {{first_name}}. The reason I reached out: the
NAIC's 12-state exam pilot is making insurer AI governance an exam item.
Short version: we build the evidence layer, inventory, checks, and
sign-offs in one auditable place. Is exam readiness on your desk this
quarter?
```

US 자산운용 3명 (T. Rowe Agrawal, Franklin Srivastav, AB Chin):

```
Thanks for connecting, {{first_name}}. The reason I reached out: the AI
items in the SEC's FY2026 exam priorities. Short version: we build the
documentation layer, AI-assisted work tied to its checks and a named
approver. Worth comparing notes sometime this quarter?
```

## 3. 무응답 마무리 (첫 DM 후 7일)

```
No reply needed if the timing is off, {{first_name}}. If AI oversight
becomes a live topic later, this thread reaches me. Good luck with the
quarter.
```

## 4. 특별 건: Aurelien Gentile (SocGen Model Risk Manager)

9/10 이메일에 실제 답장("내부 구축 중, LinkedIn으로 연락 환영")을 준 유일한
인물. Gmail 답장 초안은 초안 정리 때 함께 삭제되었으므로 LinkedIn에서 답하는
것으로 대체한다 (본인이 원한 채널이기도 하다). 커넥션 노트 없이 연결 요청 후,
수락 시:

```
Hi Aurelien, thank you for the considered reply to my email, and for the
pointer to connect here. Fair enough on building internally. The one
angle that may still be complementary: an internal automation tool and
an independent check on it are different layers, and that second layer
is what we focus on. If a brief comparison of approaches is ever useful,
happy to share how we think about it.
```

## 5. 제외·보류 리마인더

- **보류**: Paul Whynott (Synchrony). CRO 이동 정황, Jon Mothner 대체 여부 PO 판정 대기.
- **URL 미확인 4명**: Craddock(MassMutual), Evernham(Old National),
  LaQuinta(Edward Jones), Marischen(Stifel). 각 파일의 검색어로 PO가 직접 검색.
  Marischen은 결과 0건이면 채널 제외.
- 육안 재확인 권고 인물은 linkedin/00-index.md §3 참조.
