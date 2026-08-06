# 적합성검증 기준 항목 — 도메인 업무요건 전개

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
python -m pytest -q                                      # 1375 passed / 4 skipped
python -m vta criteria verify
python -m vta criteria report
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
