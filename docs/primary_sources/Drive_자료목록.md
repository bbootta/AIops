# 사용자 Google Drive 자료 목록 (조사용 색인)

egress 프록시가 bis.org·law.go.kr·fss.or.kr을 차단한다. 규정·교육·검증 자료는
**사용자 Drive에서 받아야 한다.** 이 문서는 조사·구현 에이전트가 파일을 다시
찾아 헤매지 않도록 만든 색인이다.

## 사용법

ToolSearch로 Google Drive 도구를 부른다.

```
mcp__Google_Drive__search_files        query: "parentId = '<폴더ID>'"
mcp__Google_Drive__read_file_content   fileId: <파일ID>       자연어 표현
mcp__Google_Drive__download_file_content fileId: <파일ID>     base64 원본
```

결과가 커서 파일로 저장되면 그 경로를 직접 읽는다. 형식별 파싱은 아래와 같다.

| 형식 | 방법 |
|---|---|
| HWP | `docs/primary_sources/hwp2txt.py` (OLE `BodyText` zlib 해제 후 `HWPTAG_PARA_TEXT`) |
| PDF | `pypdf`. 단 `cryptography` rust 바인딩이 임포트 시 패닉을 낸다. `sys.modules`에 `cryptography` 계열을 `None`으로 미리 넣어 막으면 통과한다. `hwp2txt.py` 하단에 절차가 있다 |
| PPTX | `python-pptx`. 없으면 zip으로 풀어 `ppt/slides/slide*.xml`의 `<a:t>` 텍스트를 긁는다 |
| PPT (구형) | 텍스트 추출이 어렵다. `read_file_content`의 자연어 표현을 먼저 시도한다 |
| XLSX/XLSM | `openpyxl`·`pandas`. xlsm은 VBA가 들어 있어 시트 값만 읽는다 |
| ZIP | 내려받아 풀고 내부 파일을 위 규칙대로 |

**스캔 PDF는 OCR 품질이 낮고 표 본문이 통째로 누락될 수 있다.** 표를 못 건지면
"표 추출 실패"라고 적어라. 본문에서 읽은 것만 인용한다.

---

## A. 규정·기준 (`교육자료/리스크` 하위 주제 폴더)

폴더 `리스크` = `1BH25e6S8W1Ca_JxAlHrxugh2KSHgj9qO`

| 폴더 | ID | 비고 |
|---|---|---|
| 0.공통 | `1_gzMGASQAnuptsKuUS7friz5FnDtlQFD` | |
| 0.업무관련법규 | `1jiPIg-SDO2tj25OJDcnF1v6pR6ytUTpJ` | |
| 1.시장리스크 | `1qXfQI-41d2nncJhCzdwr4qDU6i7Qo_8i` | |
| **2.신용리스크** | `1HJ7X_bx4tXdvBIKWPz-MM7zUvbf0rKhe` | PD·LGD·CCF 조사 우선 |
| 3.운영리스크 | `1jzaEw6UyZEODHIBdKCWi0QMkKiDKV5x6` | |
| **4.금리리스크** | `1jvh3SfmBtH1fgMpAnSmaft3OHESdz0gf` | BCBS d368 PDF가 여기 있었다 |
| **5.유동성리스크** | `1_jv4v86fbzxlJhgYX0B-xeIZyK2__icA` | |
| 6.기후리스크 | `10EA4BsOcEobOw1T99qbyIooopi9_74_K` | |
| **7.거액익스포져** | `1LgC_k04wGh7MZPqkLjq7myUqCHEX0ayB` | 거액익스포저 담당은 여기부터 |
| 8.통합위기상황분석 | `1_0td0ovvKm3cVDgACCBRdydSwymzFKlL` | |
| 9.교육자료 | `1_cbVcB1Ceqkej-MymL2axYwRdZdacnoO` | 아래 §B |
| 10.금리산정 | `1fyDcs3U6E-MokhjrsjLwJ7evHC3MkCEw` | 전가율·예금금리 조사에 볼 것 |

### 감독규정 원문 폴더

`은행업감독업무시행세칙(별첨)` = `1lsuaVn6_UFlHXxp4Zs2jeo_LLxhdzQxw`
`은행업감독업무시행세칙_20181113` = `1k-2zezrTS8aa2egwpvBBDPkl0bxxAMAy`

여기에 [별표 1]·[별표 3]·[별표 3의6]·[별표 3의9]·[별표 7]·[별표 9]·[별표 9의1]·
[별표 9의2]·[별표 18]·[별표 19] 등이 HWP로 있다. **전부 2018년 이전 판본이다.**

---

## B. 교육자료 — 2016 3기 FRME 교안 (금융리스크관리전문가 과정)

폴더 `2016 3기 FRME 교안자료` = `1y0eOG8YRTVYkvVb6Fa5gTrt5d7z1xqGG`

**추정 방법론 조사에 가장 직접적인 자료다.** 강의별로 파일이 하나씩 있다.

| 강 | 파일 | fileId | 크기 |
|---|---|---|---|
| 1-1 | 김근식강사님.pptx | `1j_fMlBR1i-F_DBY9xFLMMUBcVadCJNVb` | 5.6MB |
| 1-2 | 이문수 금융리스크관리전문가과정 교재(2016년)_최종.pptx | `1sgYCrQ6bcbN7MFawpmSYHHqUkzR7M_r8` | 2.6MB |
| **2** | **정혜욱 기업신용평가모형_교육자료.pptx** | `1foktJdD0MlagVKFJdHTbQmm5hmo5AqZC` | 2.7MB |
| 3 | 김영익 경기판단(금융리스크).ppt | `11J6XcVFGEj3Z_tolY_S-XQF9UXZkh3oD` | 17.6MB |
| **4** | **지연주 개인신용평가모형교육자료_발표본_20161012.pdf** | `1pGr1RwgmMqhjJBzr1VbQiJznJHiwT2Y7` | 4.2MB |
| **5** | **(LGD) 교안.ppt** | `1CFYSYXKiBV1Lui_Bn0rgleUEIiD_iPCk` | 4.0MB |
| **6** | **EAD추정_20161019_V0.9.pptx** | `1bxFad-l-mU5A4uXjRAB3a5WPQQkpjQol` | 1.5MB |
| 7 | 바젤1 바젤2(SA) RWA산출_이진욱.pptx | `1eC5nEPZkdqkDjLyOIjTYs8Ux9BQQHZg3` | 0.6MB |
| 8 | 바젤 RWA산출_서동진.pptx | `1FIEfpJrBEZ9h-Cfaka__92lFgvrK17xJ` | 0.6MB |
| 9 | 2016 시장리스크와 금융시장의 이해.pptx | `1QIQIOOKIptifN_gtD0PaY1fR1enNeVQd` | 0.5MB |
| 10 | 시장리스크 개편안에 대한 이해.pptx | `1TspMxwfiwDV7-ofRkVbhHtb_012Zjs-3` | 0.9MB |
| 11 | 거래상대방_강의자료_161107.pdf | `1AYbFRE20oYvT-aP9Rk1JjjJ6KnGSa10J` | 1.6MB |
| 12 | 자산유동화증권_강유석.pptx | `16UXU05-ZyE65JiefbvfRCBzb6bVN5LyN` | 5.4MB |
| 13 | 장외 파생상품 프라이싱 강의노트.pdf | `1jpGB5fkBIXJNUzSUbwHxJMShVVLdNUbn` | 1.2MB |
| 14 | FRME_운영리스크_교육자료_ver1.0.pptx | `1VGk3OWrF2f2MGfuuAutzjTfoKzWOYFtH` | 1.3MB |
| **15-1** | **신용편중리스크_20161121.ppt** | `1R5sl9-hMXD36YQcXcX_gCw1atcYyOElb` | 1.3MB |
| 15-2 | 외환결제리스크 관리_서동진.pptx | `1qrOrkKnzFDfAUaPFZ5ZxFyqVE-G6DKRJ` | 0.6MB |
| **16·17** | **유동성 and 금리리스크_2016.pdf** | `1TwYE8wRECd-9TSILV2IyZx3SX7tS-O0o` | 1.2MB |
| **18-1** | **통합위기상황분석_frme.pptx** | `1NdwtaZq16awSqu3G2FPegfFqsQdwr-AS` | 1.2MB |
| 18-2 | FRME_포트폴리오 1.5H_황인환.pdf | `18oumzkybZd9CR0nKwJ-jYnxU6MamntWv` | 1.6MB |

**2016년 자료다.** 바젤Ⅲ 최종안 이전이고 별표 9의1도 2019년 개정 이전이다.
**방법론과 개념은 유효하나 수치·조문은 현행이 아니다.** 인용할 때 그 사실을
반드시 적어라. 이 자료의 수치를 `evidence_status='원문확인'`으로 올리지 마라.
`'교육자료(2016)'` 로 표시한다.

## B-2. 신용평가모형 폴더

`교육자료/신용평가모형` = `1pdfSGCo20pwDY22Zo01mi3rUpftMVbIj` (2024-04-21)
하위 `머신러닝` = `1pf1FBEKSDnOinGeVJUiytzl2X6b5LhOQ`

2024년 자료이므로 FRME 교안보다 최신이다. PD 모형·변별력 조사에 먼저 볼 것.

---

## C. 실무 프로젝트 산출물

| 자료 | fileId | 크기 | 내용 |
|---|---|---|---|
| **신한_카드론_부도_및_LGD_개선_종료보고_v1.0_20220630** | `1gUrijNiyJ7sdPKHR5c9HGaAP0ompqL3D` | 1.45MB | 실측 LGD 개선 프로젝트. **BEEL 추이·청산부도손실율·정상화(cure) 요건·검증 판정 어휘**가 실물로 들어 있다 |
| **적합성검증 시스템 전산요건 정의서** | `1AA-vRUIf-H5XFRPjxW3HlE_YiihtFvo1` | 3.6MB | 검증 시스템 전산요건 |
| **K_검증파일_VBA.xlsm** | `1RuLSp0G1FDfjPSWKazzb15NiNNqHQkvY` | 516KB | 검증 계산 파일 |
| **K_검증파일_VBA.xlsx** | `1GnHCQ2tf8a6cd3XpzK5mIbeygjlipaXO` | 172KB | 위의 값 전용본 |
| **JB금융지주-바젤III 최종안 신용리스크 요건정의서(3)** | `1MUi01hRJ_I3nGjKVeb7dnA8S6V-VNSmm` | 20.4MB | 바젤Ⅲ 최종안 국내 구현 요건. 스캔본이라 표 추출 실패. 본문은 읽힌다 |
| 신용리스크프로젝트_교육자료_1주차_현대해상.zip | `15kYVYDwgrUhP8bPTE0WR17zN7Ufyhob3` | 1.9MB | 보험사 프로젝트 교육 |
| 교육자료_규제자본_RC관련.pptx | `112VgxYno323gCTCCOyxh7Ev8LOPfZ6Ou` | 1.0MB | 규제자본 |

### 신한 LGD 보고서에서 이미 확인한 것

읽어서 확인한 사실이므로 다시 파싱하지 않아도 된다. 다만 세부는 원문을 봐야 한다.

- 산출 계보에 `월BEEL추이(MSBAD0026)`, `월누적회수율추이(MSBAD0025)`,
  `월LGD구간별분포(MSBAD0028)`, `월LGD비용추이(MSBAD0027)`,
  `월대환계좌회수율추이(MSBAD0030)`, `월LGD추정(MSBAD0023)` 이 있다
- BEEL을 **부도 경과월(1~48개월) 축**으로 그리고 "BEEL 그래프가 하방 이동하고
  **우상향의 일반 조건**을 만족하게 되었다"고 적는다
- **청산부도손실율**과 **부도손실율**을 구분해 그린다
- **정상화(cure) 요건**: 부도 시작 1년 후부터 회수관찰기간 내 부도가 해제된
  고객 중 해제 이전까지 원금회수가 부도시익스포저보다 작으면 회복 고객으로 보고,
  부도해제월에 `(부도시익스포저 − 원금회수누계)` 만큼 추가회수를 인식한다.
  주석에 "정상화된 고객의 이자만 회수로 인정하면 지나치게 보수적"이라고 적혀 있다
- 검증 판정이 **적용값·실측값·상한값 삼자 비교**다.
  `실측PD ≥ 상한PD → 우수`, `적용PD ≤ 실측PD < 상한PD → 양호`,
  `실측PD < 적용PD → 낮음`. LGD도 같은 구조이고 "규제 상한 77.61%"를 쓴다
- PD 세그먼트 구조: 연체/무연체, 무연체는 경과기간·BS등급으로 세분.
  카드론·할부금융·법인카드·개인사업자 등 상품축이 먼저 온다
- LGD 개선이 IFRS 9 충당금에 미친 영향을 PD 효과와 LGD 효과로 분해해 제시한다

---

## D. 이미 저장소에 옮긴 것 (다시 받지 마라)

| 저장소 파일 | 원본 |
|---|---|
| `별표9의1_2026-01-29_추출본문.txt` | 사용자 업로드 PDF (현행) |
| `d578_추출본문.txt` | 사용자 업로드 PDF (현행) |
| `별표9의1_2014판_추출본문_폐지.txt` | Drive HWP (폐지된 판본) |
| `d368_Annex2_발췌.txt` | Drive PDF |
| `별표3_내부등급법_추정검증_발췌.txt` | Drive HWP (**바젤Ⅲ 최종안 이전 판본**) |
| `IRRBB_원문발췌.md` | 위 원문들의 정리 |
| `IRB_최소요건_원문발췌.md` | 위 원문들의 정리 + 최종안 변경 |
| `2차자료_금리리스크_조사_20260809.md` | 사용자 제공 조사문서 |

---

## E. 아직 확보하지 못한 것

| 자료 | 왜 필요한가 |
|---|---|
| **[별표 3] 바젤Ⅲ 최종안 반영본** | IRB 적용범위 제한·리스크 추정치 하한·183·187·193 개정 내용 |
| BCBS d424 (Basel III finalisation) | 위의 국제기준 대조 |
| [별표 19] 위기상황분석 실시 기준 (현행) | 별표 9-1 제19항이 참조한다. Drive에 2017년 BMP 이미지가 있다 |
| [별표 3의9] 내부자본적정성 (현행) | 별표 9-1 제18항이 참조한다 |
| [별표 23] 공시 (현행) | 별표 9-1 제22항 라가 참조한다 |
| 은행법 제35조·감독규정 제30조 | 거액익스포저 한도 |

Drive 보관본은 대부분 2018년 이전이다. 사용자에게 업로드를 요청해야 한다.
