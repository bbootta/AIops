# 계정 리서치: PNC Financial Services Group

> 저장 경로: `docs/sales/campaigns/20260818-usuk-rynta-aigov/research/us-b11-pnc.md`
> Tier 1~2 레코드는 이 산출물(30일 이내 작성분) 없이 시퀀스에 투입할 수 없다 [G4].

| 항목 | 내용 |
|---|---|
| 계정 / 티어 | PNC Financial Services Group (US-B11) / Tier 2 (S1 근접 주의) |
| 캠페인ID | 20260818-usuk-rynta-aigov |
| 작성 에이전트 | prospect-researcher |
| 검토 | sales-lead (대기) |
| 승인 | PO (앵글 선택 §7, 보류 해제 §1에 한함) 미서명 |
| 기준일 | 2026-08-19 (유효기간: 2026-09-18까지) |

## 1. 판정 요약

- **투입 판정: 발송 보류 (G4 해제 상신 권고, 중간 강도. S1 근접 조건부)**
- [G4] "왜 이 사람, 왜 지금" 한 문장: 2026-06-22 FirstBank($26.4bn) 고객 전환을 완료한 직후로, 전환 후 분기는 흡수된 포트폴리오의 모델·데이터가 본체 모델 인벤토리에 편입되며 재검증 백로그가 표면화되는 시점이기 때문이다.
- FirstBank 관련 검증 결과(과제 지시): "인수 보도(2025 [검증 필요])" 해소. **법적 완료 2026-01-05, 고객 전환 완료 2026-06-22 확정.**
- 조건부 사유: PNC는 ~$560bn 규모로 icp-draft §6.2 S1(대형 사내 플랫폼) 근접. 전사 정면 접근이 아니라 모델검증·MRM 기능 단위의 좁은 진입을 전제로만 상신한다. 이 전제 판단 자체가 PO 결정 사항이다.
- **보류 해제는 PO만 할 수 있다 [G1].** 해제 기록: 없음.

## 2. 시그널 (강제 필드)

| 종류 | 내용 | 일자 | 출처 (URL) |
|---|---|---|---|
| 인수 완료 | FirstBank Holding Company 인수 법적 완료. 인수 시점 FirstBank 자산 $26.4bn, 대출 $16.0bn, 예금 $23.1bn. 콜로라도·애리조나 확장 | 2026-01-05 | https://pnc.mediaroom.com/2026-01-05-PNC-Completes-Acquisition-of-FirstBank |
| 시스템·고객 전환 완료 | FirstBank 고객의 PNC Bank 전환 완료(별도 은행 자회사 체제 종료) | 2026-06-22 | https://pnc.mediaroom.com/2026-06-22-PNC-Completes-FirstBank-Customer-Conversion |

- 유효기간 판정(KB03 §5.2): 전환 완료(2026-06-22)는 발생 후 약 8주로 기술·통합 이벤트 유효창(1~6개월) 내.
- 정직 표기: PNC의 AI 거버넌스 조직·채용, 신임 리스크 임원, 어닝콜 AI 발언은 이번 조사 범위에서 확인하지 않았다(합병 검증에 집중). 발송 전 보강 여지가 있다 [검증 필요].

## 3. 가설

전환 완료 직후는 흡수 은행의 신용·예금 모델과 데이터 계보가 본체 MRM 체계로 편입되는 시기이고, $560bn 규모 은행의 검증 조직은 이 편입 백로그를 상시 인력만으로 소화하기 어렵다는 가설. 다만 PNC급은 사내 플랫폼·벤더 체계가 이미 갖춰져 있을 개연이 높아, 전사 제안이 아닌 "통합 국면의 독립 재검증 보완"이라는 좁은 쐐기만 성립한다고 본다. 단정하지 않는다: PNC MRM의 실제 백로그·외주 의존도는 미확인이다 [검증 필요].

## 4. 타깃 인물

실명·이메일은 기재하지 않는다(PO 도구, list-build-spec §1.2).

| 이름 | 직함(타깃 수준) | jurisdiction | 이메일 출처 / 수집일 | 직무 관련성 근거 |
|---|---|---|---|---|
| (PO 특정) | Head of Model Risk Management / Model Validation | US | 미수집 (PO 도구) | 전환 후 재검증 백로그의 실무 소유자. 챔피언 1순위 |
| (PO 특정) | Model Risk 산하 통합 담당 임원(있을 경우) | US | 미수집 (PO 도구) | FirstBank 모델 편입 접점 |

- [ ] [G9] 인물 레코드 0건 상태. 수집 출처·수집일은 PO(도구) 공급 후 충족. US 수신 근거: CAN-SPAM 옵트아웃 기준. 충족 전 발송 큐 진입 불가.
- [x] [G2] 회피 등급 관할 인물 없음 (계정 관할 US 확정)

## 5. 훅 1문장

- 국문 메모: 가장 강한 시그널 1개: 2026-06-22 FirstBank 고객 전환 완료(전환 후 재검증 국면).
- 영문 초안: `PNC finished converting FirstBank customers in June, and the quarters right after a conversion are when the absorbed portfolio's models hit the validation queue.`

## 6. Anti-ICP 배제 확인

- [x] H1~H4 해당 없음: 연방 감독 대상 은행, MRM 실재 개연, 관할 US
- [x] H5 해당 없음: 경쟁사 아님
- [ ] S1 근접: ~$560bn, 대형 사내 기술 조직 개연. 메가뱅크 금지 목록(§1.4)에는 미포함이나 좁은 기능 단위 접근 전제. **전제 승인은 PO 판정란**
- [x] Anti-ICP 제외 규칙 icp-draft.md §6 (PO 확정 2026-08-18) 대조 완료
- [ ] [G2] suppression 리스트 대조: 미완 (전역 suppression 리스트 미구축, list-build-spec 대기)

## 7. 공략 앵글 후보 (선택은 PO)

| # | 앵글 | 근거 시그널 | 예상 채널 |
|---|---|---|---|
| 1 | 전환 후 독립 재검증 보완: FirstBank 편입 모델의 결정론 재계산·감사 원장 (PRD-VAL, 좁은 쐐기) | 전환 완료 2026-06-22 | 이메일 |
| 2 | 통합 국면 데이터·모델 계보 어슈어런스: 이질적 계보의 감사 가능성 (PRD-AIG 접점) | 인수 완료 2026-01-05 | 이메일 / LinkedIn |

- **앵글 선택은 PO 전속 결정이다 [G1].** 선택 기록: 미선택 / PO 서명 없음 / 날짜 없음
