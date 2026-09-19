# 07. 한도·집중 리스크 코드 리뷰

**리뷰 범위:** `risk_lib/limits/`, `risk_lib/limits_master.py`, `risk_lib/concentration_deep.py`, `risk_lib/institutions.py`, `risk_lib/aig/`.

## HIGH

### 1. `risk_lib/limits/large_exposure.py:883~885`, CDS 예외 논리 AND 오류
- 별표 3-12 34., BCBS 283 §34, 그리고 자체 docstring(라인 830) 모두 **OR** ("보장제공자 **또는** 준거기업이 금융기관이 아니면") 조건인데 코드가 AND로 구현되어 있음.
```python
cds_exc = (ptype == "신용부도스왑"
           and not bool(q["provider_is_financial"])
           and not bool(q["reference_is_financial"]))
```
- 실패 시나리오: 기업이 은행 준거로 CDS를 매도한 경우(provider 비금융·reference 금융) 예외가 발동하지 않아 전체 `substituted_amount`(=covered notional)를 provider LEX 익스포저로 잡음. SA-CCR CCR EAD로 다뤄야 하는데 그렇지 않음.
- 영향: 규정이 요구하는 안전장치가 무력화되고, provider 익스포저 과대 계상.

### 2. `risk_lib/limits/limits_deep.py:8` vs `:149~155`, 동일인 20% 한도 미등록
- 모듈 docstring(라인 8)은 "동일인 한도(Tier1의 20%), 아래 기본 세트에 반영"이라고 하지만 `build_default_limit_set`은 `동일차주_Tier1_25pct`(obligor_id)와 `그룹차주_Tier1_30pct`만 등록.
- 실패 시나리오: 이 기본 세트에서 `LimitEngine`을 구성한 CRO는 20% 동일인 체크를 아예 못 받음. Tier1의 21~24% 개인 차주가 조용히 통과.

### 3. 은행법 §35① "자기자본" vs 코드의 `tier1` 사용 불일치
- 파일: `risk_lib/limits/limits_deep.py:151~152`, `risk_lib/limits_master.py:140~142`, `risk_lib/concentration_deep.py:53~89`.
- 은행법 §35①의 동일차주 25% cap 분모는 자기자본(own_funds). 세 모듈은 Tier1을 씀. docstring에도 명시되어 있으나 수치가 그대로 대시보드/조치로 흐름.
- 실패 시나리오: Tier1 < 자기자본(일반적)일 때 규정보다 엄격 → 규정상 정상인 차주가 BREACH로 표시되어 실제 영업이 왜곡됨.

## MEDIUM

### 4. `risk_lib/limits/large_exposure.py:1405~1407` vs `:1478`, 임계 비교 연산자 불일치
- `reportable = ratio >= rep_thr`이 모든 프레임워크에 적용되지만 은행법 §35④는 "초과"(strict `>`), 감독규정 §26/별표 3-12 2.라는 "이상"(`>=`). `compute_aggregate:1478`은 aggregate에 `>`를 사용해서 은행법 계정에서 경계값(ratio == threshold) 포지션이 reportable로는 잡히지만 aggregate 합에서는 빠짐. 두 뷰가 경계에서 불일치.

### 5. `risk_lib/limits/limit_engine.py:90` 외, groupby dropna=True 침묵 드롭
- `portfolio.groupby(lim.dimension)[exposure_col].sum()`이 팬더스 기본 `dropna=True`. NaN sector/country/obligor 익스포저가 침묵 소실.
- 실패 시나리오: `sector` NaN인 단일 차주 breach가 sector 집계에서 안 잡힘. 동일 패턴이 `concentration.concentration_report:43`, `concentration_deep.hierarchical_hhi:174`, `limits_deep.limit_dashboard:241`에도 있음.

## CLAUDE.md §5 위반 (장dash)
- `risk_lib/limits/limits_deep.py`, 20건. 특히 268~274, 303~321행은 CRO 대시보드로 흘러가는 문자열 안에 있어 최종 산출물로 유출됨.
- `risk_lib/limits/large_exposure.py`, 17건 (639, 653, 666, 672, 685, 707, 734, 854, 870, 1050, 1128, 1249, 1578, 1971, 1983, 2035, 2095)
- `risk_lib/limits/limit_engine.py`, 2건 (8, 73)
- `risk_lib/concentration_deep.py`, 4건 (1, 107, 143, 315)

## LOW
- `risk_lib/institutions.py:394~397`, `check_shared_reference_agreement`가 로드 실패 테이블을 `continue`로 조용히 건너뜀. Violation이 안 나지만 후속 merge에서 PK 충돌.
- `risk_lib/concentration_deep.py:35~36`, `agg(el=(...) if "el" in work.columns else ("ead", lambda s: 0), ...)`이 pd/lgd 결측 시 el·risk_score를 0으로 만듦. 경고 없이 정렬 순서만 무의미해짐.
- `risk_lib/limits/large_exposure.py:1352~1356, 1476`, 향후 리팩터 시 empty-partition에서 iloc[0] 위험 (현재는 외부 루프가 방어).

## 클린 판정
`risk_lib/limits/concentration.py`, `risk_lib/limits/__init__.py`, `risk_lib/limits_master.py`, `risk_lib/aig/__init__.py`, `risk_lib/aig/trace.py`.
