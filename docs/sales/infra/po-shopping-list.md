# PO 실행 체크리스트: 발신 인프라 셋업 (D-28 ~ D-0)

> 작성: deliverability-engineer · 기준일: 2026-08-19
> D-0 = 콜드 발송 개시일. 오늘 시작하면 D-0는 약 4주 후다.
> 설계 근거와 상세 명세: docs/sales/infra/infra-design.md
> 각 단계를 마치면 "완료 확인" 항목의 증빙(스크린샷 또는 값)을
> deliverability-engineer에게 전달한다. 검증 통과 기록이 쌓여야 인프라 완료
> 판정이 나오고, 그 전에는 캠페인이 발송 단계로 못 간다 [G5].

## 준비물 (시작 전)

- 결제 수단 (법인 카드)
- onelineai.com DNS를 관리하는 계정 접근 권한 (rua 수신 주소 생성용)
- 월 예산 약 $125~320 + 초기 1회성 $40~60 승인 (infra-design.md §9)

---

## D-28: 도메인 구매 (약 1시간)

1. 레지스트라(Namecheap, Cloudflare Registrar 등) 계정 생성.
2. 아래 우선순위로 **.com 4개** 구매 (가용한 것 상위 4개):
   - tryonelineai.com
   - getonelineai.com
   - onelineaihq.com
   - meetonelineai.com
   - (예비) joinonelineai.com, onelineai-hq.com, onelineai.co
3. 각 도메인에서 WHOIS privacy 켜기, auto-renew 켜기.
4. 각 도메인에 리다이렉트 설정: 루트와 www 모두 → `https://onelineai.com`
   (301 Permanent). 레지스트라의 "URL Redirect/Forwarding" 메뉴 사용.

**완료 확인**: 구매한 도메인 4개 목록 전달. 브라우저에서 각 도메인 접속 시
onelineai.com으로 이동하는지 확인.

## D-28 ~ D-27: 메일박스 계정 개설 (약 2시간)

5. Google Workspace 가입 (Business Starter): 도메인 1, 2번 연결.
6. Microsoft 365 가입 (Business Basic): 도메인 3, 4번 연결.
   - 두 서비스 모두 가입 과정에서 "도메인 소유 확인용 TXT 레코드"를 주면
     레지스트라 DNS 관리 화면에 추가한다.
7. 도메인당 사용자 2명씩, 총 8개 메일박스 생성.
   - 주소는 실명형: 예) jjlee@tryonelineai.com. info@, sales@ 금지.
   - 실존 인물 명의만 사용 (PO 본인 + 실제 팀원).
8. 8개 메일박스 각각: 프로필 사진, 실명, 직함 설정. 서명은 플레인 텍스트로
   이름/직함/회사명/onelineai.com 링크 1개만.

**완료 확인**: 메일박스 8개 주소 목록 + 각 계정 로그인 확인.

## D-27 ~ D-25: DNS 인증 레코드 게시 (약 2시간)

레지스트라의 DNS 관리 화면에서 도메인별로 추가한다. 정확한 값과 화면 경로는
infra-design.md §6.1 참조. 요약:

9. **MX**: Google 도메인은 `smtp.google.com`, Microsoft 도메인은 M365 관리센터가
   보여주는 값 그대로.
10. **SPF** (TXT): Google 도메인은 `v=spf1 include:_spf.google.com ~all`,
    Microsoft 도메인은 `v=spf1 include:spf.protection.outlook.com ~all`.
    도메인당 SPF는 딱 1줄이어야 한다.
11. **DKIM**: Google은 Admin Console > Gmail > Authenticate email에서
    **2048bit** 키 생성 후 TXT 게시하고 "Start authentication" 클릭.
    Microsoft는 security.microsoft.com > DKIM에서 CNAME 2개 게시 후 Enable.
12. **DMARC** (TXT, 이름 `_dmarc`):
    `v=DMARC1; p=none; rua=mailto:dmarc-reports@onelineai.com; fo=1`
    - 먼저 onelineai.com 쪽에 dmarc-reports@ 수신 주소(또는 그룹)를 만든다.
    - 무료 DMARC 파서(Postmark DMARC Digests 등)에 가입해 리포트를 연결한다.
13. 각 메일박스에서 자기 자신·개인 Gmail로 테스트 메일 1통씩 발송해
    송수신이 되는지 확인.

**완료 확인**: 도메인 4개 이름을 deliverability-engineer에게 전달 →
엔지니어가 dig/MXToolbox로 검증 실행 (infra-design.md §6.2). FAIL 항목이
있으면 수정 요청을 받는다.

## D-25 ~ D-24: 모니터링·발송 도구 준비 (약 1시간)

14. Google Postmaster Tools (postmaster.google.com)에 도메인 4개 등록,
    소유권 확인(TXT) 완료.
15. 발송 도구(Instantly 또는 Smartlead 급, 웜업 내장형) 가입.
16. 메일박스 8개를 발송 도구에 연결 (OAuth 또는 앱 비밀번호).
17. 각 도메인의 커스텀 트래킹 도메인 연결: DNS에
    `track.<도메인>` CNAME을 도구가 지정하는 호스트로 추가, 도구 화면에서
    SSL 발급 완료(자물쇠 표시)까지 확인. 공유 트래킹 도메인 사용 금지.

**완료 확인**: Postmaster 등록 화면, 도구의 메일박스 연결 상태(8/8 connected),
트래킹 도메인 상태 스크린샷 전달.

## D-24: 웜업 시작 (약 30분 설정, 이후 3주 자동)

18. 발송 도구의 웜업 기능을 8개 메일박스 전부 켠다. 설정값:
    - 시작 볼륨: 일 5통, 매주 5~10통씩 증가, 3주차에 일 30통 도달
    - 웜업 답장률: 30~40%
    - 주말 축소 옵션: 켜기
19. **이 기간 동안 콜드 발송 절대 금지.** 웜업 3주(최소 2주)가 끝나고
    지표 기준(인박스율 90%+)을 통과해야 개시할 수 있다.

**완료 확인**: 웜업 활성 상태(8/8) 스크린샷. 이후 주 1회 웜업 대시보드의
인박스율/답장률 수치를 엔지니어에게 공유.

## D-7 ~ D-3: 발송 도구 안전장치 4종 설정 (약 1시간)

infra-design.md §8 명세대로 설정한다. 요약:

20. **Stop on reply**: 답장 오면 그 사람에게 후속 메일 자동 중단. 캠페인
    기본값으로 켜기.
21. **하드바운스 자동 차단**: 반송된 주소는 자동으로 블록리스트에 들어가고
    다시는 발송되지 않게 설정.
22. **Suppression 동기화**: 마스터 suppression 리스트와 도구 블록리스트를
    최소 일 1회 동기화하는 절차 합의 (수동이면 담당·시각 고정).
23. **자동 중단 임계값**: 캠페인 바운스율 2% 초과 시 자동 일시정지, 메일박스당
    일일 한도 하드캡, 메일 간 랜덤 딜레이 5~15분 설정.

**완료 확인**: 설정 화면 4종 스크린샷 전달 → 엔지니어가 기능 테스트
(테스트 답장, 테스트 바운스, 동기화 대조) 후 검증 기록. **이 검증 없이는
인프라 미완료이고 발송 스케줄이 배정되지 않는다 [G5][G6].**

## D-3 ~ D-0: 최종 점검과 판정 (약 1시간 + 대기)

24. mail-tester.com 테스트: 실제 쓸 카피로 각 도메인 그룹에서 발송, 10/10 확인.
25. 인박스 배치 테스트(MailReach/GlockApps 류): 실 캠페인과 동일 조건으로
    실행, 결과 공유 (기준 85%+).
26. 웜업 3주 지표 확인: 인박스율 90%+, 답장률 30~40%.
27. deliverability-engineer가 infra-design.md §10 완료 조건 전건을 대조해
    **인프라 완료/미완료 판정**. 미완료면 차단 항목과 해소 조건을 받는다.
28. 완료 판정 시 인프라 런북에 PO 서명 → 이후 캠페인 프리플라이트(G5)로 진행.

## D-0 이후: 운영 중 PO가 계속 하는 일

- 콜드 개시 후 웜업을 끄지 않는다 (백그라운드 일 5~10통/메일박스 유지).
- 램프업 준수: 1주차 메일박스당 10통(전체 80통) → 4주차 15~20통(전체
  120~160통). 도구의 일일 한도를 주 단위로만 올린다 (infra-design.md §2).
- 개시·증량 후 3일간은 엔지니어의 일간 점검 결과를 매일 확인 [G6].
- 답장·수신거부는 24시간 내 처리. 수신거부에 재발송 금지.
- 서킷브레이커 발동 통보를 받으면 즉시 도구에서 해당 캠페인/도메인 발송을
  중단한다. 재개는 원인 제거 확인 + PO 승인 둘 다 필요하다 [G6].
