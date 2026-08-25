# 이메일 전달성과 발신 인프라 실무 가이드

> KB 기준일: 2026-08-18 · 구축: 세일즈 KB 리서치 워크플로

> **한 줄 요약**: 콜드 아웃바운드의 성패는 카피보다 인프라가 먼저 결정한다. 루트 도메인은 절대 발신에 쓰지 않고, 세컨더리 도메인 + 도메인당 2~3 메일박스 + 메일박스당 일 20~50통 상한 + 2~4주 웜업 + SPF/DKIM/DMARC 완비가 기본 골격이다. 2024-02 Google/Yahoo, 2025-05 Microsoft의 대량 발신자 정책 이후 인증 미비는 "감점"이 아니라 "수신 거부" 사유가 되었다.

---

## 1. 발신 도메인 전략

### 1.1 대원칙: 루트 도메인 보호

- **회사 메인 도메인(예: onelineai.com)으로는 콜드 메일을 절대 보내지 않는다.** 콜드 발신으로 도메인 평판이 훼손되면 고객 응대, 거래 메일, 사내 메일까지 전부 스팸함으로 밀린다. 복구에는 수 주~수 개월이 걸리고, 블랙리스트에 오르면 사실상 도메인을 버려야 하는 경우도 있다.
- 콜드 발신은 전용 **세컨더리 도메인**에서만 한다. 세컨더리 도메인이 오염되면 그 도메인만 폐기하고 교체하면 된다: 이것이 세컨더리 도메인의 존재 이유다.
- 메인 도메인은 회신(replies) 수신, 웹사이트, 거래 메일(트랜잭셔널), 뉴스레터 등 "허가 기반" 채널에만 쓴다.

### 1.2 세컨더리 도메인 설계 기준

| 항목 | 권장 기준 | 비고 |
|---|---|---|
| 도메인당 메일박스 수 | **2~3개** | 3개 초과는 도메인 평판 리스크 집중 |
| 메일박스당 일일 콜드 발송 | **20~50통** (웜업 완료 후) | 보수적 운영은 20~30통, 상세는 4장 |
| 도메인당 일일 콜드 발송 총량 | **30~50통 수준으로 관리** | 업계 통설 기준 |
| TLD | **.com 최우선**, 대안 .co / .org | .com 대비 .io/.co의 격차는 2~4%p 수준(업계 통설). 저가 TLD(.xyz, .top, .live 등)는 회피 |
| 하이픈 | 0개 권장, 1개까지 허용 | 하이픈 2개 이상 도메인은 인박스 도달이 유의미하게 낮다는 조사 있음(업계 통설: 약 18% 하락) |
| 도메인 나이 | 구매 후 **최소 2~4주 숙성 + 웜업**, 3~6개월 이상이면 유리 | 갓 등록한 도메인의 즉시 대량 발송은 최악의 신호 |
| 리다이렉트 | 세컨더리 도메인 접속 시 **메인 사이트로 301 리다이렉트** | 수신자/필터가 도메인을 조회했을 때 실체 확인 가능하게 |

**도메인 네이밍**: 메인 브랜드의 자연스러운 변형을 쓴다. 예: `onelineai.com`이 메인이면 `tryonelineai.com`, `getonelineai.com`, `onelineai.co`, `onelineaihq.com` 등. 스팸성 어휘(offer, deal, promo 등)가 들어간 이름은 피한다.

### 1.3 목표 발송량 역산 공식

```
필요 도메인 수 = 목표 일일 발송량 ÷ (도메인당 메일박스 수 × 메일박스당 일일 발송량)
```

| 목표 일일 콜드 발송 | 권장 구성 (보수적: 메일박스당 25통 기준) |
|---|---|
| ~50통 | 도메인 1~2개 × 메일박스 2개 |
| 100~150통 | 도메인 2~3개 × 메일박스 2~3개 |
| 500통 | 도메인 7~10개 × 메일박스 2~3개 |
| 1,000통 | 도메인 14~20개 × 메일박스 2~3개 |

- 볼륨 확장은 **"메일박스 하나를 더 세게 돌리는 것"이 아니라 "웜업된 메일박스를 늘리고 로테이션하는 것"**이다. 단일 메일박스 과부하는 반드시 평판 하락으로 돌아온다.
- 도메인 전체가 한꺼번에 오염되는 것을 막기 위해, 캠페인을 도메인 그룹별로 분산하고 한 그룹의 지표 악화가 전체로 번지지 않게 한다.

### 1.4 메일박스 제공자 선택

| 옵션 | 특징 | 실무 판단 |
|---|---|---|
| Google Workspace | Gmail 수신자 대상 인박스 도달률 최상위(업계 통설: 94~96%) | 기본 선택지. 단 2025년 이후 계정 어뷰징 단속 강화, "시트 5개 사서 돌려쓰기" 식 운영은 정지 위험 |
| Microsoft 365 | 계정당 발송 한도는 높으나(1일 1만 수신자) 콜드 안전 볼륨은 동일하게 20~40통 | Outlook/기업 수신자 비중 높은 타깃에 병행 |
| 전용 SMTP 인프라(Mailforge, Maildoso, Inframail 등) | 도메인+메일박스 대량 프로비저닝, DNS 자동 설정 | 대규모 확장 시 비용 효율적. 단 공유 IP 풀 품질 확인 필수 |

수신자 분포에 맞춰 발신 인프라를 섞는 것(Google 계열 + Microsoft 계열 병행)이 특정 필터 편향을 줄인다.

---

## 2. 인증: SPF, DKIM, DMARC

### 2.1 왜 필수인가

- **2024-02 Google/Yahoo 정책** 이후 인증은 선택이 아니다. SPF/DKIM/DMARC가 모두 갖춰진 도메인은 그렇지 않은 도메인보다 인박스 도달 확률이 크게 높다(업계 통설: 최대 10배).
- **2025-05-05부터 Microsoft(Outlook.com, Hotmail, Live)**도 일 5,000통 이상 발신 도메인에 SPF/DKIM/DMARC 통과를 요구하며, 미준수 메일은 SMTP 단계에서 `550 5.7.15 Access denied` 로 거부한다.

### 2.2 레코드별 설정 기준

**SPF (TXT 레코드)**
- 형식 예: `v=spf1 include:_spf.google.com ~all`
- **DNS 조회 10회 제한**(RFC 7208): include, a, mx, ptr, exists, redirect가 각각 1회씩 카운트. 초과 시 PermError로 인증 실패. include 정리, 발신 서비스 분리(서브도메인 활용)로 해결.
- `-all`(하드페일)보다 `~all`(소프트페일)을 쓰고 집행은 DMARC에 맡기는 것이 콜드 인프라의 일반 관행.
- Return-Path 도메인과 From 도메인의 정렬(alignment)을 확인한다.

**DKIM (TXT/CNAME, 셀렉터 방식)**
- **2048비트 키** 권장(DNS가 지원하는 한).
- Google Workspace: Admin Console에서 생성 → DNS 게시 → "인증 시작". Microsoft 365: Defender 포털에서 셀렉터 CNAME 2개 게시 후 활성화.
- 키 값 붙여넣기 오류(문자 누락)가 흔한 실패 원인이므로 게시 후 반드시 검증 도구로 확인.

**DMARC (TXT, `_dmarc.도메인`)**
- 최소 요건: `v=DMARC1; p=none; rua=mailto:dmarc-report@수신주소`
- **p=none은 모니터링 전용**이다. Google/Yahoo 최소 요건은 충족하지만 위조 차단 효과는 없다. 운영 안정화 후 `p=quarantine` → `p=reject`로 단계 상향하되, 모든 정당한 발신 경로가 정렬을 통과하는지 rua 집계 리포트로 확인한 뒤 올린다. `pct=` 로 점진 적용 가능.
- **정렬(alignment)**: From 헤더 도메인이 SPF 도메인 또는 DKIM 도메인과 일치해야 DMARC 통과. 둘 중 하나면 되지만 둘 다 정렬이 바람직.
- rua 리포트는 XML 24시간 집계로 오므로 파서/서비스(dmarcian, EasyDMARC, Postmark 무료 리포트 등)를 쓴다.

### 2.3 인증 외 기술 요건 (Gmail 발신자 가이드라인)

- 발신 IP의 **정방향/역방향 DNS(PTR) 레코드** 유효할 것.
- **TLS** 연결로 전송할 것.
- 메일 포워딩·메일링리스트 운영 시 **ARC 헤더** 추가.
- From 헤더 위장 금지(특히 gmail.com 사칭 시 DMARC quarantine 적용).

### 2.4 검증 체크리스트 (신규 도메인 셋업 시 매번)

```
[ ] SPF 게시 + 조회 10회 이내 (MXToolbox SPF lookup)
[ ] DKIM 2048bit 게시 + 활성화 확인
[ ] DMARC p=none 이상 + rua 수신 확인
[ ] From 도메인과 SPF 또는 DKIM 정렬 통과
[ ] PTR/rDNS 유효 (자체 SMTP인 경우)
[ ] 커스텀 트래킹 도메인(CNAME) 설정: 공유 트래킹 도메인 사용 금지
[ ] 세컨더리 도메인 → 메인 사이트 301 리다이렉트
[ ] mail-tester.com 10점 만점 또는 도달률 테스트 통과
[ ] Google Postmaster Tools 도메인 등록 + Compliance Status 녹색 확인
```

### 2.5 Google/Yahoo 2024 대량 발신자 정책 (요건 요약)

적용 대상: **Gmail 개인 주소로 일 5,000통 이상** 보내는 발신자(도메인 기준, 한 번 도달하면 계속 적용). Yahoo도 유사 기준.

| 요건 | 기준 |
|---|---|
| SPF + DKIM | 둘 다 통과 필수 |
| DMARC | 최소 p=none, From 정렬 필수 |
| 스팸 신고율 | **0.1% 미만 유지, 0.3% 절대 초과 금지** (Postmaster Tools 기준) |
| 원클릭 수신거부 | RFC 8058 List-Unsubscribe(-Post) 헤더, **2일 내 처리** |
| PTR/TLS | 유효한 rDNS, TLS 전송 |

콜드 메일 운영은 메일박스당 20~50통이라 대량 발신자 기준에 형식상 미달하지만, **0.3% 스팸 신고율과 인증 요건은 사실상 모든 발신자에게 적용되는 실질 기준**으로 취급해야 한다. Gmail은 2024년 이후 단계적으로 비준수 메일 거부(임시 오류 → 반송)를 확대했다.

---

## 3. 웜업 (Warm-up)

### 3.1 원칙

- **신규 도메인/메일박스는 웜업 없이 콜드 발송 금지.** 새 도메인에서 첫날부터 수십 통을 쏘는 것은 스팸 필터가 가장 잘 아는 패턴이다.
- 표준 웜업 기간: **최소 2~3주, 권장 3~4주.** 신규 도메인 전체가 안정 볼륨에 도달하는 데는 4~8주로 보는 견해도 있다(업계 통설). Google Postmaster 기준 "High" 평판 도달은 빠르면 3~4주.
- 웜업의 본질은 "받은 메일이 열리고, 답장되고, 스팸함에서 꺼내지는" **긍정적 참여 신호를 축적**하는 것이다.

### 3.2 주차별 표준 스케줄 (메일박스 1개 기준)

| 주차 | 일일 발송(웜업 메일) | 목표 |
|---|---|---|
| 0주 (사전) | 발송 없음 | 도메인 구매 후 DNS/인증 세팅, 2주 숙성 |
| 1주 | 5 → 10통 | 수동으로도 가능: 지인/동료와 실제 대화. 답장률 30% 이상 |
| 2주 | 10 → 20통 | 웜업 툴 가동, 매주 5~10통씩 증량 |
| 3주 | 20 → 30통 | 답장률 40~50% 유지, 반송률 2% 미만 확인 |
| 4주 | 30~40통 | 지표 정상이면 콜드 발송 개시 준비 완료 |

- 콜드 발송 개시 후에도 **웜업을 끄지 않는다.** 백그라운드 웜업을 일 5~10통 수준(또는 총 발송량의 20~40%)으로 상시 유지해 참여 신호를 보충한다.
- 웜업 답장률 설정은 30~40%가 적정. 90~100% 답장 같은 비정상 패턴은 오히려 봇으로 탐지된다.

### 3.3 웜업 도구

| 도구 | 비고 |
|---|---|
| Instantly / Smartlead 내장 웜업 | 발송 플랫폼 일체형, 실 메일박스 P2P 네트워크 |
| MailReach | 웜업 + 인박스 배치 테스트 결합 |
| Warmforge, Mailivery, Lemwarm(lemlist), TrulyInbox 등 | 독립형 웜업 네트워크 |

주의사항:
- Google/Microsoft는 웜업 네트워크를 공식 인정하지 않으며, **봇/헤드리스 브라우저 기반 가짜 참여형 도구는 오히려 탐지 대상**이다. 실제 메일박스 간 자연스러운 대화를 만드는 P2P형을 쓴다.
- 웜업 메일에 흔한 고유 태그 문자열이 노출되는 도구는 필터에 시그니처로 잡힐 수 있다. 도구 선택 시 최근 평판을 확인한다.
- 웜업 지표가 나쁠 때(웜업 메일의 스팸함 착지 증가) 콜드 발송을 늘리면 안 된다. 볼륨을 절반으로 줄이고 회복을 기다린다.

---

## 4. 발송량 규칙 (Sending Limits & Ramp-up)

### 4.1 상한 기준

| 구분 | 기준 |
|---|---|
| 신규(웜업 중) 메일박스 | 일 10~20통 이하 |
| 웜업 완료 메일박스 | **일 20~50통** (콜드 기준, 웜업 메일 포함 총량 관리) |
| 절대 상한 (업계 통설) | 일 50통. 50~100통 주장도 있으나 2024 정책 이후 보수 운영이 정석 |
| 증량 속도 | 한 번에 **20% 이하**, 주 단위로 증량 |
| 발송 간격 | 메일 간 랜덤 딜레이(예: 5~15분), 동시 폭주 발송 금지 |
| 발송 시간대 | 수신자 시간대 기준 평일 업무시간(화~목 오전이 통계상 우수) |

참고: Google Workspace의 기술적 한도는 일 2,000 수신자, Microsoft 365는 일 10,000 수신자지만, **기술 한도와 "스팸으로 안 찍히는 한도"는 완전히 다른 수치**다. 콜드 발송은 항상 후자를 따른다.

### 4.2 램프업 스케줄 (웜업 완료 후 콜드 볼륨)

| 주차 (콜드 개시 후) | 메일박스당 일일 콜드 발송 |
|---|---|
| 1주 | 10통 |
| 2주 | 15~20통 |
| 3주 | 20~30통 |
| 4주~ | 30~40통 (상한 유지) |

램프업 중 하나라도 걸리면 즉시 증량 중단:
- 반송률 2% 초과 → 리스트 재검증
- 스팸 신고 발생 → 타깃/카피 점검
- 오픈율 급락(예: 50% → 20%) → 스팸함 착지 의심, 볼륨 절반 감축 + 배치 테스트

### 4.3 볼륨 운영 규칙

- **분산이 곧 안전**: 같은 양이면 메일박스 4개 × 25통이 1개 × 100통보다 압도적으로 안전하다.
- 새 캠페인 시작일에 볼륨을 몰지 말고, 시퀀스 스텝(후속 메일)을 포함한 총 발송량으로 상한을 관리한다.
- 메일박스별/도메인별 발송량과 지표를 대시보드로 상시 추적한다(6장).

---

## 5. 정당한 도달: 콘텐츠, 리스트 위생, 수신거부

목표는 "스팸 필터 회피"가 아니라 **정당한 메일로 판정받을 조건을 갖추는 것**이다. 현대 필터는 단어보다 발신자 평판·인증·참여 신호를 우선하므로, 꼼수보다 인프라와 위생이 답이다.

### 5.1 콘텐츠 규칙 (콜드 1통 기준)

| 요소 | 기준 |
|---|---|
| 형식 | **플레인 텍스트 우선**, 무거운 HTML 템플릿 금지 |
| 링크 | **0~1개.** 첫 메일은 링크 없이, 필요 시 회신 후 공유. 링크는 자체 도메인/캘린더 링크로 한정, 단축 URL(bit.ly 등) 금지 |
| 이미지/첨부 | 첫 메일에는 이미지·GIF·PDF 첨부 없음. 서명의 소형 이미지 1개 정도는 평판이 좋으면 무해(업계 통설) |
| 오픈 트래킹 | 켜려면 반드시 **커스텀 트래킹 도메인**으로. 공유 트래킹 도메인은 남의 평판을 물려받는다. 도달이 흔들리면 오픈 트래킹부터 끈다 |
| 길이 | 50~120단어 내외, 수신자별 개인화 1~2요소 이상 |
| 스팸 어휘 | "무료", "100% 보장", "지금 바로", 과도한 느낌표/대문자/이모지 회피. 단, 단어 자체보다 **패턴(느낌표 3개 + 링크 4개 + 첨부)**이 문제라는 것이 최근 컨센서스 |
| 변형(spintax) | 동일 문면 대량 발송을 피하기 위해 문장 변형 사용. 수신자별 개인화가 최선의 변형이다 |

### 5.2 리스트 위생 (Deliverability의 절반)

- **발송 전 100% 검증**: 모든 리스트는 발송 전 이메일 검증 도구(ZeroBounce, NeverBounce, MillionVerifier, Reoon, Bouncer 등)를 통과시킨다. `valid`만 발송하고 `invalid`는 폐기.
- **catch-all/accept-all/unknown/risky 판정 주소는 원칙적으로 제외**하거나, 별도 저볼륨 세그먼트로 격리 발송한다.
- **하드바운스 즉시 억제**: 하드바운스 주소는 즉시 전역 suppression 리스트에 넣고 재발송을 영구 차단한다.
- **바운스율 관리 기준**: 2% 미만 정상, 2~5% 경고(발송 중단 후 리스트 재검증), 5% 초과 위험(도메인 평판 손상 진행 중).
- **구매 리스트 금지**: 스팸트랩(pristine trap)의 최대 유입 경로. pristine trap 1건으로도 Gmail 도메인 평판이 하루 만에 Low로 떨어질 수 있다.
- **스팸트랩 3종 이해**: pristine(처음부터 존재하지 않던 미끼 주소: 스크래핑/구매 리스트 신호), recycled(6~24개월 방치 후 트랩으로 전환된 주소: 오래된 리스트 신호), typo(gmial.com 등 오타 도메인). 대응책은 최신 데이터 + 검증 + 미참여자 정리.
- **리스트 노화**: 이메일 리스트는 연 20~25%씩 부패한다(업계 통설). 90일 이상 지난 리스트는 재검증 후 사용.
- **미참여자 정리(sunset policy)**: 90~180일 무반응 주소는 시퀀스에서 제외.

### 5.3 수신거부 처리

- **모든 콜드 메일에 명확한 옵트아웃 수단**을 넣는다. 형태는 (a) 수신거부 링크 또는 (b) "회신으로 수신거부 의사를 알려주시면 다시 연락드리지 않겠습니다" 문구. B2B 콜드 저볼륨에서는 (b)가 자연스럽고 스팸 신고를 줄인다.
- **처리 시한**: 미국 CAN-SPAM은 10영업일 내 처리 + 옵트아웃 수단 30일 유지 의무. 실무는 **즉시(24시간 내) 처리**가 표준. Google/Yahoo 원클릭 수신거부는 2일 내 처리.
- 수신거부는 **주소 단위가 아니라 회사/인물 단위 전역 suppression**으로 관리한다. 다른 메일박스/캠페인에서 같은 사람에게 다시 보내는 사고가 신고로 직결된다.
- 수신거부 링크가 깨져 있으면 그 자체가 법 위반이자 신고 사유다. 정기 점검한다.
- 수신거부 요청에 항변하거나 추가 발송하지 않는다. 신고 1건(0.3% 기준 환산 시 몇 통 안 됨)이 도메인 하나를 잠식한다.
- **한국 수신자 대상 발송 주의**: 정보통신망법상 영리목적 광고성 정보는 사전 동의(옵트인)가 원칙이고 제목 앞 "(광고)" 표기 등 별도 요건이 있다. B2B 콜드 메일의 적법 범위는 법무 KB(kb/legal/)와 법무팀 검토를 따른다. 이 문서는 기술적 전달성 기준만 다룬다.

---

## 6. 모니터링

### 6.1 상시 추적 지표와 임계값

| 지표 | 정상 | 경고 | 위험(즉시 조치) |
|---|---|---|---|
| 반송률(전체) | < 2% | 2~5% | > 5% |
| 하드바운스 | < 1% | 1~2% | > 2% |
| 스팸 신고율 | < 0.1% | 0.1~0.3% | ≥ 0.3% |
| 오픈율(트래킹 시) | 40~60% | 30~40% | < 30% 또는 급락 |
| 답장률(B2B 콜드) | 5~10% 양호 | 3~5% | < 2% (도달 문제 의심) |
| 인박스 배치율(시드 테스트) | ≥ 85~90% | 70~85% | < 70% |
| 웜업 메일 인박스율 | > 90% | 80~90% | < 80% |

- 오픈율은 트래킹 픽셀 차단 확산으로 절대값 신뢰도가 낮다. **추세(급락 감지)** 용도로만 쓰고, 도달 판단은 배치 테스트와 답장률로 한다.
- "오픈율 급락 + 답장 소멸"은 스팸함 착지의 전형적 신호다. 즉시 볼륨 50% 감축, 배치 테스트, 원인 점검(신규 리스트? 카피 변경? 트래킹 도메인?).

### 6.2 Google Postmaster Tools (필수)

- 모든 발신 도메인을 등록한다(무료).
- **v2 전환 완료(2025-09-30 이후 v1 종료)**: 기존 도메인/IP 평판 대시보드는 폐지되고 **Compliance Status(준수 여부 녹색/적색 체크)** 중심으로 재편되었다. 스팸 신고율, 인증 통과율, 발신자 요건 준수 여부를 여기서 확인한다.
- 주 1회 정기 점검 + 캠페인 개시/볼륨 증량 후 3일간 집중 관찰.
- Microsoft 계열은 SNDS(Smart Network Data Services)로 IP 평판을 확인한다(자체 IP 발신 시).

### 6.3 블랙리스트 점검

- **주요 리스트**: Spamhaus(SBL/XBL/DBL: 영향력 최대), Barracuda, SpamCop, SORBS. 한국 수신자 대상이면 **KISA RBL**도 확인(네이버 등 국내 포털이 참조).
- **점검 방법**: MXToolbox blacklist check로 발신 도메인·IP 일괄 조회(주 1회) → 걸린 항목은 check.spamhaus.org, barracudacentral.org에서 재확인.
- **해제(delisting) 절차**: ① 등재 원인 파악(트랩 히트, 신고, 오픈릴레이) → ② **원인 제거 먼저**(제거 없이 해제 신청하면 재등재되고 두 번째는 더 오래 간다) → ③ 각 리스트 절차로 해제 신청. 셀프서비스형(Spamhaus, SpamCop)은 1~12시간, 수동 심사형(Barracuda)은 12~24시간, 해제 후 평판 정상화까지 24~72시간(업계 통설).
- 공유 IP 인프라 사용 시 남의 잘못으로 등재될 수 있다. 인프라 제공자의 IP 풀 관리 정책을 확인한다.
- **네이버/국내 포털 참고**: 네이버는 KISA·Spamhaus 등 RBL 참조 + 동시 다중 접속 차단 정책을 운영한다. 국내 기업 도메인 대상 대량 발송이 필요한 경우 KISA 화이트도메인 등록 제도를 검토한다.

### 6.4 테스트 도구

| 용도 | 도구 |
|---|---|
| 콘텐츠/인증 스팸 점수 | mail-tester.com (발송 전 10/10 확인), Mailgenius |
| 인박스 배치(시드 테스트) | MailReach, GlockApps, Validity Everest, TrulyInbox |
| DNS/인증 검증 | MXToolbox (SPF/DKIM/DMARC/blacklist), dmarcian, EasyDMARC |
| 웜업 겸 모니터링 | Instantly/Smartlead 대시보드, MailReach |

- 배치 테스트는 **실제 캠페인과 동일 조건**(같은 발신 도메인, 같은 카피, 같은 트래킹 설정)으로 해야 의미가 있다.
- 정기 리듬: 신규 도메인 개시 전 1회 + 캠페인마다 개시 전 1회 + 운영 중 격주 1회.

### 6.5 사고 대응 런북 (요약)

```
[스팸함 착지 감지]
1. 해당 도메인 콜드 발송 즉시 50% 감축 (심하면 전면 중단)
2. 배치 테스트로 착지 위치 확인 (Gmail/Outlook 분리 확인)
3. 점검 순서: 블랙리스트 → 인증(SPF/DKIM/DMARC 통과율) → 최근 리스트 품질
   → 카피/링크 변경 이력 → 트래킹 도메인 → 발송량 급증 여부
4. 원인 제거 후 웜업 볼륨 비중을 높여 1~2주 회복 운전
5. 회복 불능(2~3주 후에도 배치율 < 50%)이면 도메인 폐기·교체 결정

[반송률 급등]
1. 발송 전면 중단
2. 리스트 재검증, 데이터 소스 확인 (catch-all 비중, 리스트 나이)
3. 하드바운스 전역 suppression 반영 후 재개
```

---

## 7. 셋업-운영 통합 체크리스트

**신규 인프라 셋업 (D-14 ~ D-0)**
```
[ ] 세컨더리 도메인 구매 (.com, 브랜드 변형, 하이픈 최소화)
[ ] 메인 사이트로 301 리다이렉트
[ ] 메일박스 2~3개/도메인 생성, 프로필 사진·서명 설정
[ ] SPF/DKIM/DMARC 게시 + 검증 (2.4 체크리스트)
[ ] 커스텀 트래킹 도메인 CNAME
[ ] Google Postmaster Tools 등록
[ ] 웜업 툴 가동 (2~4주)
```

**캠페인 개시 전 (매 캠페인)**
```
[ ] 리스트 100% 검증, catch-all/risky 제외, suppression 대조
[ ] mail-tester + 배치 테스트 통과
[ ] 카피: 플레인 텍스트, 링크 0~1, 첨부 0, 옵트아웃 문구 포함
[ ] 메일박스당 일일 한도·램프업 스케줄 설정 (4장)
[ ] 발송 간격 랜덤 딜레이 설정
```

**운영 중 (주간)**
```
[ ] Postmaster Compliance/스팸 신고율 확인
[ ] 반송률·답장률·(추세용) 오픈율 점검, 임계값 대조 (6.1)
[ ] MXToolbox 블랙리스트 스캔
[ ] 수신거부 처리 로그 확인 (24시간 내 처리 여부)
[ ] 웜업 백그라운드 가동 상태 확인
```

---

## 출처

조사에 사용한 주요 출처 (2026-08-18 검색 기준):

- Gmail Email sender guidelines (Google 공식): https://support.google.com/mail/answer/81126
- Yahoo Sender Hub (Yahoo 공식): https://senders.yahooinc.com/best-practices/
- Microsoft Outlook 고볼륨 발신자 요건 (Microsoft Community Hub): https://techcommunity.microsoft.com/blog/microsoftdefenderforoffice365blog/strengthening-email-ecosystem-outlook%E2%80%99s-new-requirements-for-high%E2%80%90volume-senders/4399730
- Resend, Gmail and Yahoo bulk sending requirements: https://resend.com/blog/gmail-and-yahoo-bulk-sending-requirements-for-2024
- Mailgun, Yahoogle bulk senders / Microsoft sender requirements: https://www.mailgun.com/state-of-email-deliverability/chapter/yahoogle-bulk-senders/ , https://www.mailgun.com/blog/deliverability/microsoft-sender-requirements/
- PowerDMARC, Bulk email sender rules: https://powerdmarc.com/bulk-email-sender-requirements/
- dmarcian / dmarcwise, Gmail·Outlook DMARC 요건: https://dmarcian.com/yahoo-and-google-dmarc-required/ , https://dmarcwise.io/blog/outlook-new-requirements-2025
- Smartlead, Secondary domains: https://www.smartlead.ai/blog/secondary-domains
- UnifyGTM, Cold email domain setup & deliverability: https://www.unifygtm.com/explore/cold-email-2026-domain-setup-deliverability-sequences
- DitLead, Secondary domains / SMTP servers: https://ditlead.com/blog/secondary-domains-for-cold-email
- Mailforge, SPF/DKIM/DMARC DNS basics · TLD impact · content mistakes: https://www.mailforge.ai/blog/spf-dkim-dmarc-dns-basics-for-cold-email
- MailReach, 웜업·도메인·리스트 위생·배치 테스트: https://www.mailreach.co/blog/gmail-warmup , https://www.mailreach.co/blog/email-list-hygiene-best-practices , https://www.mailreach.co/blog/inbox-placement-testing
- Topo.io, Safe cold email sending limits: https://www.topo.io/blog/safe-sending-limits-cold-email
- MailReach, How many cold emails per day: https://www.mailreach.co/blog/how-many-cold-emails-to-send-per-day
- Overloop, Email warmup / Spam traps: https://overloop.com/blog/email-warmup , https://overloop.com/blog/spam-traps
- lemlist, Email warmup: https://www.lemlist.com/blog/warm-up-email-account
- Folderly / Moosend / Twilio, Google Postmaster Tools v2: https://folderly.com/blog/google-postmaster-tools-v2-migration-guide-2025 , https://moosend.com/blog/google-postmaster-tools-update/ , https://www.twilio.com/en-us/blog/insights/gmail-postmaster-tools-changes
- SenderReputation.org / Mailflow Authority, 블랙리스트 해제: https://senderreputation.org/blog/how-to-remove-domain-ip-from-email-blacklists , https://mailflowauthority.com/email-deliverability/email-blacklists-guide
- Woodpecker / Litemail / Warmforge, 콜드 메일 옵트아웃·CAN-SPAM: https://woodpecker.co/blog/cold-email-opt-out/ , https://litemail.ai/blog/can-spam-compliance-guide-for-cold-email-2026
- Validity, Spam traps: https://www.validity.com/blog/what-is-a-spam-trap/
- verified.email, Bounce rate benchmark: https://verified.email/blog/email-deliverability/email-bounce-rate-benchmark
- Instantly / Belkins 계열, 콜드 이메일 벤치마크: https://instantly.ai/blog/cold-email-reply-rate-benchmarks/
- TrulyInbox, 메일박스 제공자 비교·인박스 배치 도구: https://www.trulyinbox.com/blog/email-providers-for-cold-email-deliverability/
- Thundermail 블로그, 네이버 대량메일 발송 가이드(KISA RBL·화이트도메인): https://blog.thundermail.co.kr/9

주의: 위 수치 중 상당수는 공식 정책(Google/Yahoo/Microsoft 요건, CAN-SPAM)을 제외하면 업계 실무자 데이터에 기반한 통설이다. 정책 수치(스팸 신고율 0.3%, 5,000통 기준 등)는 공식 문서 기준이며, 발송 한도·웜업 기간 등은 보수적 범위를 채택했다.
