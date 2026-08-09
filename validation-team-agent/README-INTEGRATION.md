# 적합성검증 기준 항목 — 국내 감독규정 + 도메인 업무요건

두 층으로 구성된다.

| 층 | SSoT | 근거 | 항목 수 |
|---|---|---|---|
| **국내 감독규정** | `harness/domestic_rule_criteria.json` | 은행업감독**규정** [시행 2026. 4. 1.] + 시행**세칙** [시행 2026. 6. 30.] — 원문 2종을 저장소에 보관 | 검증 항목 53건 (자동 31 · 수동 22) + 계량 임계 10건 |
| 도메인 업무요건 | `harness/domain_requirement_criteria.json` | RYNTA BRD Level 1 v9.6.0 | 131건 (자동 69 · 수동 12 · 범위밖 50) |

국내 층이 **법적 근거**, 도메인 층이 **업무 요건**이다. 국내 층이 상위다 —
업무요건이 국내 기준을 덮지 못하면 그것이 곧 공백이다.

---

# 1. 국내 감독규정 검증 항목

## 인용을 원문과 대조한다

근거가 두 층이다. **규정**이 경영지도비율 등 임계값을, **세칙**이 그 산정기준을
정하므로 한쪽만으로는 국내 기준을 덮지 못한다.

| 근거 | 원문 | 지문 | 수록 |
|---|---|---|---|
| 규정 | `harness/reference/bank_supervision_regulation_20260401.md` | `c8bc6abb18ba355c…` | 조문 heading 148 · 별표 23 |
| 세칙 | `harness/reference/bank_supervision_rules_20260630.md` | `66ac0b4d292b8440…` | 조문 heading 145 · 별표 45 |

각 검증 항목의 조문·별표 인용은 **생성 시점과 검증 시점 양쪽에서 해당 원문을
찾아 해석**되며, 라인 번호는 손으로 적지 않고 파생한다.

이월 `CO-004`("규정 텍스트가 저장소에 없다 — 인용 474종의 원문 정합성 미보증")가
열려 있던 이유가 원문 부재였다. 시행세칙 범위에서는 이제 대조가 가능하다.

```bash
python -m tools.domestic_criteria cite-check "별표 3의7"
#  해석됨 — L23178: [별표 3의7] 원화예대율 산출 기준
python -m tools.domestic_criteria cite-check "별표 99의9"
#  해석 실패 — 원문에서 찾을 수 없다 (exit 1)
```

## 규정 임계 vs 하니스 임계 — 기계 대조

규정이 정한 계량 임계 10건을 하니스 임계 파일과 대조한다. 하니스가 규정보다
느슨하면 `looser`로 드러나며 `verify`가 위반으로 판정한다 — 규제 미달을 통과시키기
때문이다. 더 엄격하면 `stricter`로 통과시키되 보고한다.

```
$ python -m vta domestic thresholds
[일치] 보통주자본비율 최소      규정 0.045 이상 | 하니스 0.045 | [규정] 제26조
[일치] 총자본비율 최소         규정 0.08  이상 | 하니스 0.08  | [규정] 제26조
[일치] 거액익스포져비율 한도     규정 0.25  이하 | 하니스 0.25  | [규정] 제26조
...
10건 · 일치 10 · 엄격 0 · 느슨 0 · 없음 0
```

현재 10건 전부 일치한다. 각 임계는 원문 발췌(예: `"보통주자본비율 : 100분의 4.5"`)를
함께 보관하며, 그 문장이 원문에 없으면 위반이다 — 지어낸 근거를 막는다.

## verify가 강제하는 것

① 근거 원문 2종의 지문 일치(원문이 바뀌면 카탈로그가 낡았다는 사실이 드러난다)
② 인용의 원문 해석과 기록 라인·표제 일치
③ 계량 임계의 원문 발췌 실재 + 하니스 임계가 규정보다 느슨하지 않을 것
④ `automated` 항목의 하니스 근거 파일 실재

## 부문별

```
총 53건 · 자동 31 · 수동 22      (규정 13건 · 세칙 40건)

01 RDM·BIS비율       14건 (자동 10)   05 ALM·IRRBB·유동성  11건 (자동 4)
02 신용리스크·RWA       8건 (자동  4)   06 운영리스크          2건 (자동 1)
03 IFRS 9 ECL         2건 (자동  2)   07 통합위기상황분석      6건 (자동 5)
04 시장리스크           2건 (자동  2)   08 리스크 적합성검증     8건 (자동 3)
```

## 드러난 통제 공백 22건 중 눈여겨볼 것

- **`KR-002` 산정 시점 (제17조제2항)** — 자기자본비중·단순기본자본비율·NSFR·
  거액익스포져비율은 가결산일·결산일 **현재** 기준, LCR·원화예대율은 **매월 평잔**
  기준이다. 하니스는 LCR을 시점값 하나로 받으므로 시점값을 평잔으로 보고해도
  잡지 못한다.
- **`KR-019` 원화예대율 (별표 3의7)** — 월평잔 기준이며 양도성예금증서는 원화예수금의
  1/100, 커버드본드는 만기 구간별로 1/100·합산 2/100 한도가 있다. 하니스의 ALM
  예대율은 잔액 기준 관리지표라 이 기준과 다르다.
- **외환건전성 4건** (`KR-023`~`KR-026`, 별표 14·14의1·15의1·제39조) — 외화유동성비율·
  외화안전자산 산출 경로가 없다.

---

# 2. 도메인 업무요건 전개

`claude/validation-team-agent-Pw9F5` 하니스에 얹을 컴포넌트다. 본 브랜치
(`claude/compliance-team-agent-call-midnvi`)는 하니스 본체를 담고 있지 않으므로
여기서는 신규 파일과 기존 파일 패치를 분리해 둔다.

## 무엇인가

RYNTA BRD Level 1 도메인 업무요건 **131건 전부**를 적합성검증 기준 항목으로
전개했다. 기존 `harness/val_requirement_coverage.json`(PRD-VAL 18건 · 검증
업무요건)과 층이 다르다 — 저쪽은 "검증 체계가 갖춰야 할 것", 이쪽은 "각 도메인
업무요건을 무엇으로 검증할 것인가"다.

항목마다 부문(8부문)·검증관점(데이터·산식·방법론·내부통제·문서화)·검증 기준
문장·자동화 상태를 갖는다.

- `automated` — 하니스에 통제가 실재. **근거 파일이 실재해야만 주장 가능**
- `manual` — 통제가 없어 사람 검토로 남김. 사유 필수
- `out_of_scope` — 은행 8부문 검증 범위 밖. 사유 필수

`automated`가 요건을 다 덮는다는 뜻은 아니고, `out_of_scope`가 요건이
불필요하다는 뜻도 아니다.

## 현재 집계 (v9.6.0 레지스터 기준)

```
총 131건 · 자동 69 · 수동 12 · 범위밖 50

01 RDM·BIS비율        18건 (자동 14 · 수동  4)
02 신용리스크·RWA       13건 (자동  9 · 수동  4)
03 IFRS 9 ECL          3건 (자동  3)
04 시장리스크            2건 (자동  2)
05 ALM·IRRBB·유동성     1건 (자동  1)
06 운영리스크            1건 (자동  1)
07 통합위기상황분석        8건 (자동  6 · 수동  2)
08 리스크 적합성검증      34건 (자동 33 · 수동  1)
-- 부문 미귀속          51건 (범위밖 50 · 수동 1)   플랫폼·상업·연계·증권 업권
```

자동 69건이 선언한 근거 **124개 파일이 전부 실재**함을 `verify`가 확인한다.

## 파일

| 파일 | 성격 |
|---|---|
| `harness/reference/bank_supervision_regulation_20260401.md` | 국내 근거 원문 — 은행업감독규정 전문 (지문 고정) |
| `harness/reference/bank_supervision_rules_20260630.md` | 국내 근거 원문 — 시행세칙 전문 (지문 고정) |
| `harness/domestic_rule_criteria.json` | SSoT — 국내 검증 항목 53건 + 계량 임계 10건 (생성물) |
| `tools/gen_domestic_criteria.py` | 국내 항목 생성기 — 인용을 원문에서 해석 |
| `tools/domestic_criteria.py` | `list` / `report` / `thresholds` / `cite-check` / `verify` |
| `tests/test_domestic_criteria.py` | 16건 — 인용 해석·임계 대조 + 음성 통제 6건 |
| `harness/domain_requirement_criteria.json` | SSoT — 기준 항목 131건 (생성물) |
| `tools/gen_domain_criteria.py` | 생성기 — 원문 레지스터가 바뀌면 재실행 |
| `tools/domain_criteria.py` | `list` / `report` / `verify` |
| `tests/test_domain_criteria.py` | 10건 — 근거 실재성 + 음성 통제 3건 |
| `INTEGRATION.patch` | 기존 파일 4종 패치 (CLAUDE.md · README.md · cli_index · vta dispatch) |

## 적용

```bash
git checkout claude/validation-team-agent-Pw9F5
cp -r validation-team-agent/{harness,tools,tests} .      # 신규 4파일
git apply INTEGRATION.patch                              # 기존 4파일
python -m pytest -q                                      # 1391 passed / 4 skipped
python -m vta criteria verify
python -m vta criteria report
python -m vta domestic verify
python -m vta domestic report
python -m vta domestic thresholds
```

## 알려진 한계

- **원문은 v9.6.0이다.** 요청받은 `RYNTA_RiskOps_Vol1_v9.6.1_한국어_정리본`은
  Slack 업로드본이 50.7MB로 파일 읽기 한도(10MB)를 넘어 받지 못했다. v9.6.1에서
  요건이 추가·변경됐다면 이 원장은 그만큼 낡았다. 원문을 확보하면 레지스터를
  갱신하고 `gen_domain_criteria`를 다시 돌리면 된다 — 손으로 고치지 않는다.
- 원문 지문 `e1a8daa2907c445e…`(v9.6.0 BRD HTML)를 SSoT에 박아 두었으므로,
  레지스터가 다른 원문에서 생성되면 그 사실이 드러난다.
- 검증 기준 문장은 요건 **제목**에서 전개한 것이다. v9.6.0 레지스터는 수용기준
  본문을 담고 있지 않아(수용기준 수만 보유) 항목별 수용기준 대조는 하지 못했다.
  원문 확보 시 보강 대상이다.
