# 인물 특정 인덱스 (Lessie식 검색의 컴플라이언스 준수 실행)

> 기준일: 2026-09-14 · 작성: sales-lead 종합 (원본: 본 디렉터리 6개 배치 파일)
> 방법: 자연어 타깃 묘사 기반 인물 검색(Lessie.ai 방식)을 공개 출처 한정으로 실행.
> 기관 공식 리더십 페이지, 보도자료, 뉴스, 규제기관 공표, 공개 LinkedIn만 사용했고
> 전 인물에 출처 URL + 확인일을 남겼다. 비공개 정보 수집 없음.

## 0. 절대 규칙 (전 파일 공통)

- **이메일 주소는 이 디렉터리 어디에도 없다.** email 필드는 전 레코드 `[PO/도구]`이며
  PO가 검증 도구(US=ZoomInfo, UK=Cognism 권고)로 채운다 (list-build-spec.md §1.2).
- 이 문서들은 인물 특정 산출물이며 **발송 판단이 아니다.** 발송 큐 진입은 G9 필수
  필드 충족과 PO 보류 해제 이후에만 가능하다 [G1][G4][G9].
- 적합도: 강 = 1차·복수 출처로 현직 확인 / 중 = 2차 출처 중심, 발송 전 재확인 권고 /
  후보 = 재검증 전 발송 불가.

## 1. 배치별 결과

| 파일 | 대상 | 특정 인물 | 미확인 직책 | 비고 |
|---|---|---|---|---|
| us-banks-1.md | US 은행 1~10 (Citizens~Zions) | 15 (강 8, 중 6, 후보 등급 표기 포함) | 12 | KeyCorp·Zions 0명 (검색 한도로 미수행, 차기 최우선). IBKR Group CRO 공석 |
| us-banks-2.md | US 은행 11~19 (Truist~First Horizon) | 22 (강 17, 중 4, 후보 1) | 11 | 9곳 전부 기관당 2명 이상 충족. Edward Jones CRO 공석 |
| uk.md | UK 16곳 | 22 (강 13, 중 7, 후보 2) | 16 | Leeds 신임 CRO Katherine Tong 확정. Investec Group CRO는 근무지 관할 밖으로 회피 태깅(G2 이관) |
| us-insurance-am.md | US 보험·자산운용 8곳 | 21 (강 13, 중 6, 후보 2) | 8 | 8곳 전부 기관당 2~3명 충족. 우선 지시 4건(Prudential·Lincoln·T. Rowe·AB) 전건 완료 |
| us-brokers.md | US 증권사·은행 추가 6곳 | 16 (강 10, 중 5, 후보 1) | 9 | Raymond James CRO 교체 반영(현직 Krauss). Robinhood CTO 공석 |
| sg-au.md | SG/AU 8곳 | 17 (강 11, 중 5, 후보 1) | 9 | GXS·Trust Bank 기관당 1명 미달(임원 이직으로 후임 미보도) |
| **합계** | **57곳** | **113명 (표 기재 기준)** | **65건** | 수신자 전망 114~177명(prospect-list-summary.md)의 하한에 근접 |

## 2. 구 데이터로는 틀렸을 사실 (이번 재확인의 성과)

8월 리서치 이후 한 달 사이 실제로 바뀐 것들이다. 옛 리스트를 그대로 썼다면
은퇴자·이직자에게 보낼 뻔했다.

| 기관 | 확인 사실 |
|---|---|
| Raymond James | 전 CRO Catanese 은퇴, 현직은 David Krauss |
| Moomoo SG | 전 CEO Gavin Chia 2026-05 Longbridge 이직, 현직 CEO는 Jeyson Ng |
| GXS Bank | CDO Geraldine Wong 2026-02 말 퇴사, 후임 미보도 |
| Trust Bank | 창립 CRO Lalit Lohia는 Mashreq 이직 (디렉토리에 잔존 표기 주의) |
| Prudential | Chief Actuary Candace Woods 은퇴, 후임 미공표 (구 출처 재직 표기 잔존) |
| Edward Jones | CRO 공석 (전임 2024-06 은퇴, 후임 공개 발표 미발견) |
| Interactive Brokers | Group CRO Farrell 2026-01 HKEX 이직, 후임 공식 발표 추적 필요 |
| Robinhood | CTO Pinner 2026-05-07 퇴사(8-K), 후임 미발표 |

## 3. 공백과 미달 (정직 기록)

- KeyCorp·Zions: 이번 회차 웹 확인 자체가 미수행 (세션 검색 한도). 차기 회차 최우선.
- Head of Model Risk 계열 champion은 대부분 기관에서 공개 출처로 특정 불가였다.
  전건 "미확인"으로 남기고 PO용 Sales Navigator 쿼리를 파일마다 기재했다.
  이 직책은 보도가 잘 안 되는 자리라 도구(ZoomInfo/Cognism/SalesNav) 단계에서
  채워지는 것이 정상 경로다.
- 기관 공식 도메인 다수가 이 환경의 프록시에 차단되어 일부 인물은 2차 출처
  기반이다. 해당 건은 각 파일에 "재확인 필요"로 명시했다.

## 4. 다음 단계

1. **시그널 재확인 (긴급)**: 8월 조사 시그널의 30일 유효기간(G4)이 2026-09-17~18에
   만료된다. 발송이 그 이후면 시그널 재조사 없이는 보류가 유지된다.
2. PO: 검증 도구 가입 후 이 리스트의 인물들로 이메일 주소 추출·검증
   (list-build-spec.md §2, §5). 인물이 특정되어 있어 도구 검색이 빨라진다.
3. PO: 신임 임원 유효창 임박 건 우선 처리 (First Citizens CRO Eklund 부임 105일째).
4. sales-compliance-officer: UK LIA 공급, IBKR Colin Clarke 관할 판정.
5. 미달 기관(KeyCorp, Zions, GXS, Trust Bank, Pinnacle, Ameriprise) 후속 탐색.
