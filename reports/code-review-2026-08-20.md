# 코드 리뷰 결과 — 2026-08-20

리뷰 범위: `risk_lib/` (111,546 LoC), `validation-team-agent/`, 관련 도구.
5개 병렬 리뷰어가 독립적으로 스캔하여 총 90건의 결함 후보를 보고. 아래는
심각도(HIGH) 기준으로 정리한 액션 가능 항목이다.

각 항목은 `파일:라인 - 결함 - 실패 시나리오` 형식.

## 1. 규제 수치가 조용히 틀리는 결함 (HIGH)

### 1.1 결측값이 0으로 대체되어 규제 수치 왜곡

- `risk_lib/datamodel/materialize.py:246-247` - `pd_pit`, `lgd`가
  `np.nan_to_num`으로 0으로 치환. PD가 결측인 익스포저가 IFRS9 원장에 PD=0,
  LGD=0으로 실제 EAD와 함께 기록됨.
- `risk_lib/datamodel/materialize.py:190-203` - `expected_loss`는
  `nan_to_num(pd) * nan_to_num(lgd) * ead`를 쓰지만 같은 행의 pd/lgd 열은
  NaN 유지. 한 행 안에서 pd/lgd는 NaN인데 EL은 실제 KRW 수치가 되거나, EL=0
  인데 참 PD는 미상인 상태로 규제 EL이 조용히 0이 됨.
- `risk_lib/cecl.py:52-53` - `df["pd"].fillna(0.01).clip(1e-4, 0.99)` 와
  `lgd.clip(0.05, 0.95)`가 부도 익스포저(PD=1.0, LGD=1.0)를 0.99/0.95의
  performing으로 조용히 재분류. Stage-3 대출의 잔존기간 ECL이 과소 계상.
- `risk_lib/regulatory/forms_base.py:112` - `_val()`이 `float(ln.value or 0.0)`
  로 `None`을 0으로 취급. `_sum_check` / `_ratio_check`가 성분 라인이
  `value=None`(미계산/누락)일 때 조용히 통과.
- `risk_lib/regulatory/forms_fss_indicator.py:184,758,863` -
  `rr["expected_loss"].fillna(0.0).sum()`이 규제 신고 "예상손실 (EL)"
  (B2901)에서 NaN EL을 0으로 마스킹.
- `risk_lib/monitoring/deep.py:43-44,106` - DPD가 NaN인 대출이 "Current"로
  버킷팅되고 `df[dpd_col] >= threshold`가 False로 판정 - NPL 비율이 규제에
  과소 신고됨.
- `risk_lib/limits/limits_deep.py:230,242,431` - `sum()`이 기본
  `skipna=True`. NaN EAD 행이 한도 소진율에서 조용히 빠져 실제 BREACH가
  CRO 대시보드에 OK로 표시.

### 1.2 스트레스 시나리오가 조용히 무력화

- `risk_lib/stress/scenario.py:31-41` - `stress_pd`가
  `np.maximum(pd_base, pd_sat)`로 클램프. `pd_multiplier == 1`인 benign 시나리오
  ("GDP 회복")가 unshocked PD를 반환하여 기준선과 동일한 RWA/ECL을 산출.
- `risk_lib/stress/multi_axis.py:39,127-133` - `RATING_LADDER`가 `"CCC"`를
  쓰지만 `rwa_sa`의 `_RW_*` 테이블은 `"CCC-"`로 키. 심하게 다운그레이드된
  익스포저가 UNRATED(100% RW)로 폴백 - 최악 버킷의 스트레스 RWA 과소 계상.
- `risk_lib/stress/ccar.py:224-228` - 회복 임계값이 DSIB=1%를 하드코딩하고
  `sum(buffers)`가 공급된 키만 계산 - "회복 안됨" 태깅이 breach 산출에
  쓰인 임계값과 다른 임계값으로 이뤄짐.

### 1.3 XVA / FRTB

- `risk_lib/frtb.py:114-135` - `rfet_test`가 `price_history.columns`를
  순회하여 `"date"` 열까지 리스크 팩터로 스코어링, NMRF 카운트와 자본 add-on
  (`n_nmrf * 1e9`) 부풀림.
- `risk_lib/frtb.py:171-183` - `backtest_var`가 VaR을 양의 손실 크기로
  가정. 호출자가 부호 있는 음의 손실로 넘기면 매일 예외로 카운트되어
  자동 RED / IMA 취소.
- `risk_lib/xva.py:118-130` - MVA가 `im_t = im_initial * (1 - t/t.max())`.
  IM이 시점 0에서 사후 값이 아니라 감쇠된 값에서 시작하여 MVA가 체계적
  과소계상.

### 1.4 재현성 (reproducibility) 파괴

- `risk_lib/cli.py:375-380` - `_cmd_reproduce`가 재실행 시 `asof`를 누락,
  `run_pipeline`이 `date.today()`를 재읽음. 원본 asof가 벽시계였던 매니페스트
  는 데이터·시드가 같아도 재현 실패.
- `risk_lib/cli.py:373` - `_cmd_reproduce`가 `saved.portfolio` fingerprint
  없이 시드로부터 포트폴리오를 재생성. 원본이 `--data book.csv`를 썼던
  매니페스트가 합성 데이터로 재실행되고 잘못된 원인을 가리키는 "재현 실패"
  가 보고됨.
- `risk_lib/report.py:43` - `_sec_header`가 `result.meta['asof']` 대신
  `date.today().isoformat()`을 표지에 기록. 동일 입력이 매일 다른 바이트를
  생산.
- `risk_lib/board_pack.py:87,417-418` - 표지와 `meeting_date`가 벽시계.
  12쪽의 "재현성 인증"이 매일 다른 표지에 스테이플됨.
- `risk_lib/pipeline.py:1501-1503` - `run_pipeline`이 `asof=None`을 받아
  `date.today()`로 조용히 치환. 호출자가 `--asof`를 잊으면 모든 다운스트림
  수치가 벽시계에 앵커됨.

### 1.5 로깅 / 경고 억제

- `risk_lib/pipeline.py:1033-1037,1044-1047` - `warnings_mod.simplefilter("ignore")`
  가 `build_lgd_ead_backtest_ledgers` 와 `build_irb_estimation_ledgers` 전체에
  걸쳐 모든 경고를 억제. 정당한 데이터 품질 / 외삽 경고가 CRO 원장에
  표면화되지 않음.

## 2. 3선 (독립검증) 게이트의 fail-open 결함 (HIGH)

VTA의 여러 검증 핸들러가 **입력이 없을 때 조용히 PASS**를 반환. 3선의
핵심 계약이 뒤집힘.

- `validation-team-agent/src/vta/handlers/registry.py:653` - `schema_check_handler`
  가 df 없을 때 status="ok" 반환. 부재한 데이터가 PASS.
- `registry.py:679` - `safety_check_handler` (PII 가드) df=None 이면 ok.
- `registry.py:696` - `leakage_check_handler` feature_names 비면 ok.
  타깃/결과 열이 모델에 남아있어도 leakage 체크가 통과.
- `registry.py:714` - `date_coverage_handler` date_col 없으면 ok. 호출자가
  "gaps 없음"과 "미검사"를 구별할 수 없음.
- `registry.py:734` - `duplicates_check_handler` key_cols 비면 ok.
  프라이머리 키 중복을 은닉.
- `registry.py:208-211` - `capital_handler`가 Tier1/Total 비율 미제공 시
  CET1 값으로 디폴트. CET1만 제출한 은행이 Tier1과 Total 자본 적정성 게이트
  를 자동 통과.
- `tools/independent_recalc.py:210-229` - `inputs_validation`이 None일 때
  "독립" 재계산이 `inputs_operational`을 재사용. 3선 게이트가 운영 전용
  입력에서 통과, `hitl_note`의 자유 텍스트로만 경고.
- `middleware/permission_guard.py:73-79` - `load_patterns`가
  `harness/permission_matrix.json`이 malformed일 때 `_FALLBACK_PATTERNS`로
  조용히 폴백. SSoT에 추가된 커스텀 리스크 패턴이 JSON 오타 이후 소멸.
- `registry.py:427-437` - `cva_handler`가 잘못된 CVA 입력(scva 결측/비Mapping
  /음수) 시 skipped 반환(fail 아님). BA-CVA의 지배적 항이 실패 신호 없이
  누락.
- `registry.py:150-151` - `credit_calibration_handler`가 모든 등급이
  reject되어도 status가 warning일 뿐 fail이 되지 않음. `on_fail_activate`
  에스컬레이션과 MRMC 알림이 트리거되지 않음.
- `registry.py:657` - 필수 열 누락이 fail이 아닌 warning으로 다운그레이드.

## 3. 검증 로직 자체가 vacuous (HIGH)

`risk_lib/validation` 과 `risk_lib/regulatory/cross_form`의 여러 검사가
**항상 통과하는 형태**로 작성되어 있음.

- `risk_lib/validation/cross_domain.py:84-92` - `_check_pd_rwa`가 gaps
  존재 여부와 무관하게 두 분기 모두 status="PASS". PD segment-mean
  reconciliation이 절대 실패할 수 없음.
- `risk_lib/validation/cross_domain.py:76-82` - 같은 루틴이 평균 PD를
  `m.get("auprc", obs)`와 비교. auprc는 판별력 지표이지 중심 경향이 아님 -
  "reconciliation"이 무의미.
- `risk_lib/regulatory/forms.py:266-267` - BR-05 체크
  `float(t["capital"].sum()) == sum(float(x) for x in t["capital"])`가 시리즈를
  자신과 비교. vacuous PASS.
- `risk_lib/regulatory/forms_ext.py:157-159` - "MRF + NMRF = 위험요소 총수"
  체크가 `n_true + n_false = n_total` - 항상 참(또는 NaN에서 에러).

## 4. MEDIUM / LOW 결함

원본 리뷰에 총 52건의 MEDIUM/LOW 결함이 추가로 보고됨. 대표적:

- `risk_lib/capital/rwa_sa.py:56` - `past_due`가 자산군 무관 150% RW로
  단락. Basel III CRE20.94는 past-due 주거용 담보 대출을 100% RW로 규정.
- `risk_lib/capital/leverage.py:33-41` - Direct credit substitute에 100% CCF
  대신 단일 `off_balance_ccf` 적용 (LEV30.11 위반).
- `risk_lib/capital/bis_deep.py:216-240` - 15% CET1 결합 임계값이 각 10%
  개별 한도 절단 이후에만 적용 - CRE40.10과 다른 결과.
- `risk_lib/repro.py:75-82,104-107,133-137` - bare `except`, 비원자적 파일
  쓰기 - 감사 원장 무결성 취약.
- `risk_lib/audit_trail.py:62-67,73-81` - 감사 원장이 락 없이 리스트 append
  + 원자성 없는 쓰기. 동시 실행 시 항목이 인터리브.
- `risk_lib/regulatory/cross_form.py:56,61,77` - "총자본비율", "보통주자본
  비율", "유동성커버리지비율" 불변 조건이 잘못된 라인 코드를 참조 -
  실제로 검증되지 않음.

전체 목록은 `reports/code-review-details-2026-08-20.jsonl` 참조.

## 권고

1. **1.1과 1.2를 우선 처리** - 규제 수치가 조용히 틀리는 결함은 결재
   가능성 자체를 무너뜨림. 특히 NaN → 0 치환과 stress scenario의 `maximum`
   클램프.
2. **2번 (VTA 게이트)의 fail-open 결함은 CLAUDE.md §6의 fail-closed 계약과
   정면 충돌**. registry.py의 handler들이 입력 부재를 "skipped" (별도 상태)
   로 구분하도록 리팩터.
3. **3번 (vacuous check)은 각 파일 단독 수정으로 처리 가능**하지만, 지금
   존재하는 "PASS" 이력은 신뢰할 수 없으므로 재실행 후 결과를 다시 봐야
   함.
4. **1.4 (재현성)**은 결재 라인의 신뢰 계약이므로 `asof`와 표지 날짜를
   즉시 `meta`에서 읽도록 수정.

리뷰어별 원본 findings는 세션 로그 참조. 이 리뷰는 **정적 스캔**이므로
런타임 검증(테스트 실행, 골든 비교)이 별도로 필요.
