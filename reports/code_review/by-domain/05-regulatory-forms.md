# 05. 감독규정 업무보고서 코드 리뷰

**리뷰 범위:** `risk_lib/regulatory/*.py` (35 파일), `risk_lib/ui_studio/studio.py`(cross_form 호출부), 관련 tests (`test_regulatory.py`, `test_form_structure.py`, `test_citations.py`) 및 baseline.

## BLOCKER

### 1. `risk_lib/ui_studio/studio.py:230–237` — cross-form 실패가 결재 게이트를 통과함
- `cross_form_checks` 결과가 `doc_checks`(IV 요청용)에만 붙고 `BuiltForm.checks`에는 병합되지 않음. 따라서 `n_failed`(`forms_base.py:83–85`)에 반영 안 되고, `reg_submission.status`(`forms.py:956–958`, `"draft" if b.n_failed else "approved"`)에 영향 없고, Excel 검증 sheet(`excel.py:198–222`)에 안 나타나고, 제출 digest도 안 움직임.
- 실패 시나리오: 허용 오차 초과 cross-form이 있어도 `approved` 상신, 초록 digest. 모듈이 방지하려 했던 F-701 재발.

### 2. `risk_lib/regulatory/cross_form.py:54–58` — `INVARIANTS "보통주자본비율"` 의미 오류
- BR-14/2100 진입점 `_br14`(`forms.py:637–643`)가 첫번째 시나리오의 `trough_cet1`(스트레스 최악 분기)을 2100 라인에 쓴다. tolerance `1e-9`.
- 오늘은 `DEFAULT_STRESS_PATHS`에 `baseline`이 먼저라 baseline trough ≈ current여서 우연히 PASS. path 순서 바뀌거나 baseline 제거되면 상시 FAIL(그러나 위 블로커 때문에 결재는 그대로 통과).

## HIGH

### 3. `risk_lib/regulatory/cross_form.py:65–68` — 레버리지비율 invariant 대상 오설정
- `BF605`(해외점포 단순기본자본비율)와 `B5101`(연결기준 지표)를 `1e-9`로 비교. 전행 vs 해외전용 비교로 무효. `forms_fss_capital.py:31–33` "연결 = 단독" 프록시 덕에 오늘만 통과. 실제 해외 원장 도착 시 상시 FAIL.

### 4. `cross_form.py:60–63, 76–79` — LCR·총자본비율 invariant는 항등식
- `BR-31/1110`(CAMEL 자본), `BR-31/1510`(CAMEL 유동성)이 `result.bis.total_ratio` / `result.alm["lcr"].lcr` 그대로에서 왔음(`prudential/camel.py:64, 94`). BR-01, BR-08과 같은 소스. 검증이 아니라 항등식(F-602/F-703 tautology). 삭제하거나 독립 계산과 비교로 교체.

### 5. `risk_lib/regulatory/requirements_v960.py:6–7` — SOURCE_SHA256 강제 없음
- `SOURCE`/`SOURCE_SHA256`가 단순 문자열. `risk_lib/`나 `tests/`에서 `RYNTA_Business_Requirements_v9.6.0.html`를 재해시하는 코드가 없음. "손으로 고치지 않는다" 계약이 명예 규정.

### 6. cross_form registry 테스트 커버리지 0
- `tests/` 하위에서 `cross_form` grep 무결과. 블로커 #1이 안 잡히는 근본 원인.

### 7. `fss_master.py:7` vs `form_ids.py:55` — 조사기준일 상이
- `fss_master.py`는 `2026-07-15`, `form_ids.py`는 `FSS_SOURCE = "…(조사기준일 2025-09-05)"`. 모든 `FormId.source`에 10개월 낡은 provenance가 찍힘.

## MEDIUM

### 8. `structure.py:60–63` — `structure.coverage()`의 침묵 열화
- baseline 파일 없으면 `{"n_baseline_keys": 0, "key_gap": 0}` 반환, 관련 테스트는 skip(`test_form_structure.py:53`). 신규 체크아웃이 "0 baseline, 0 gap"의 겉만 초록인 리포트 산출.

### 9. `excel.py:170–186` — 단위 값 없음(None) 셀 처리
- `unit == "ratio"`, `value is None`일 때 `0.0000%` 포맷 적용. text 단위에서 `text_value=None`이면 D열 공백만 남음.

### 10. `forms.py:468–472` — `_br10` 나눗셈 우선순위 버그
```python
float(...) / float(t["balance"].sum()) if float(t["balance"].sum()) else 0.0
```
- 파이썬 파싱상 `X / (Y if Y else 0.0)` → Y=0일 때 `X/0` 여전히 실행. 합성 포트폴리오에서 sum이 정확히 0이 아니라서 지금은 안 터짐. `(X / Y) if Y else 0.0`으로 괄호.

### 11. citation 커버리지 임계 80%는 계약과 상충
- `tests/test_citations.py:61–74` + `citations.py:38–49`. 폼 docstring들(예: `excel.py:1–6`, `forms.py:10–12`)은 "라인마다 산식·규정근거·산출 모듈을 함께 남긴다"라 하나 테스트는 ≥80%만 통과. 최대 ~1,050 라인이 인용 없이 합법 통과.

## LOW
- `forms_ext.py:350–352` — `sum(next(...) for ...)`가 PEP 479로 RuntimeError. `_val(L, c)`로 통일.
- `forms.py:140–150` — `_capital_detail_lines`가 `row['sign']`을 검증 없이 문자열에 임베드.

## CLAUDE.md §5 위반 (저장소 광역)
`grep`으로 regulatory 하위 35 파일에 em/en dash 총 1,502건. docstring뿐 아니라 `text_value`, formula 문자열에도 있어 Excel 산출물로 유출. 파일별 개별 수정보다는 저장소 광역 스윕 필요.

## 클린
`forms_fss_*` 패턴은 자산·자본·소매·해외B 샘플 검사 결과 일관·정상. 문제는 조정 계층(cross_form, submission 게이트, 버전 스탬프)에 집중.
