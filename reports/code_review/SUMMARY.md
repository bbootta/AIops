# 저장소 전체 코드 리뷰 종합 (2026-08-25)

**대상:** `risk_lib/` (Basel III/FSS 리스크 라이브러리, ~189k LoC, Python 647 파일), `tools/`, `validation-team-agent/`, `examples/`.
**방식:** 도메인별 10개 병렬 리뷰 에이전트가 파일을 실제로 읽어 correctness/regulatory/security/CLAUDE.md 위반을 산출. 도메인별 상세는 `by-domain/`.

---

## 요약, 결재를 막아야 할 findings

### 🔴 BLOCKER (5건)

| # | 파일:행 | 문제 | 영향 |
|---|---|---|---|
| B1 | `risk_lib/models/rating.py:49` | `pd_to_rating`가 `bisect_left` 사용, `pd_upper` exclusive 계약 위반 | 16개 등급 경계 전부 하위 등급으로 오매핑. 하류 midpoint 재보정·리포트 오염 |
| B2 | `risk_lib/ui_studio/studio.py:230~237` | `cross_form_checks` 결과가 `BuiltForm.checks`에 병합 안 됨 → 결재 게이트 무력화 | 초과 오차 cross-form이 있어도 `approved` 상신, F-701 재발 |
| B3 | `risk_lib/regulatory/cross_form.py:54~58` | `INVARIANTS "보통주자본비율"`가 현행 CET1이 아닌 stress trough CET1과 비교 | 시나리오 순서 바뀌면 상시 FAIL(그러나 B2로 결재는 통과) |
| B4 | `risk_lib/provisioning/ecl.py:155~177` | SICR 트리거에서 forbearance/notch_drop/abs_pd 4개 무시 | 채무재조정 차주가 Stage 1 잔류, 충당금 과소 |
| B5 | `risk_lib/monitoring/vintage_deep.py:117~121` | `vintage_drift`의 신·구 cohort 선택이 반대 방향 | 최근 vintage 악화가 개선으로, 반대도 마찬가지 → RED/GREEN 판정 역전 |

### 🟠 HIGH (18건, 주요)

**자본·RWA (`risk_lib/capital/`)**
- H1. `capital/rwa_sa.py:44`, 기업 SA 등급 `"B"` RW 100% (정답 150%, CRE20.44). 1tn B 기업대출 자본 40bn 부족.
- H2. `capital/crm.py` 전 모듈, CRE22.35~36 만기 불일치 할인, CRE22.55~58 최소 보유기간 haircut scaling 미구현. 5y 대출·2y 담보에서 RWA ~62bn 과소.
- H3. `capital_simulation.py:217~219`, AT1 트리거 시 대수적으로 `tier1 = tier1_old - conversion`. 트리거마다 Tier1 30bp 과소.

**RWA 하류 (IFRS9·Stage3)**
- H4. `provisioning/ecl.py:56~62, 175~177`, Stage 3 UTP 트리거 부재 (dpd≥90만).

**CCR·시장**
- H5. `ccr.py:60~76`, `saccr_ead`가 자산군 add-on, 헤징세트, 초과담보 승수 미반영. +100/-100 IR 스왑 헤지가 EAD 2배.
- H6. `sensitivities.py:82~95`, `dv01` 중복 할인. 스왑·본드 dV01이 `1/(1+y)`만큼 과소.
- H7. `sensitivities.py:57`, 만기 put delta 항상 0 (정답 -1.0). 헤지 손실.
- H8. `sensitivities.py:106~109`, `cs01`이 spread=0에서 ZeroDivisionError → 트레이딩북 빌드 중단.

**한도·집중**
- H9. `limits/large_exposure.py:883~885`, CDS 예외 로직이 AND (규정·docstring은 OR). CDS 안전장치 무력화.
- H10. `limits/limits_deep.py:8` vs `:149~155`, docstring 표방과 달리 동일인 20% 한도 미등록. Tier1 21~24% 개인 차주 침묵 통과.
- H11. 은행법 §35① 분모(자기자본)를 코드가 Tier1로 씀 (`limits_deep.py`, `limits_master.py`, `concentration_deep.py`). 규정상 정상 차주가 BREACH.

**규제 forms 코디네이션**
- H12. `regulatory/cross_form.py:65~68`, 레버리지비율 invariant가 해외 전용 vs 전행 비교 (`BF605` vs `B5101`). 항등식 트릭.
- H13. `regulatory/requirements_v960.py:6~7`, `SOURCE_SHA256` 계약이 강제 미실행. 명예 규정.
- H14. `cross_form` registry 테스트 커버리지 0.
- H15. `fss_master.py` `2026-07-15` vs `form_ids.py` `2025-09-05` 조사기준일 불일치.

**스트레스·기후**
- H16. `stress/ccar.py:224~226`, `recovery_summary`와 `paths_df.cbr_breach`가 다른 dsib 버퍼로 CET1 요구를 계산. 같은 결과에서 "no breach" ↔ "not recovered" 모순.
- H17. `stress/ccar.py:163`, `cum_ecl_uplift`가 실제 누적 아님 (`max()`).
- H18. `climate.py:109, 141`, 포트폴리오 PD·LGD 무시, 하드코딩. `climate_capital`와 두 개의 서로 다른 결과.

**신용모형**
- H19. `models/pd_model.py:98~103`, `gini()` 동점 미처리, `auc_roc()`와 결과 불일치.
- H20. `models/pd_model.py:112~113`, `ks_statistic`가 전 부도/전 정상에서 침묵 0.
- H21. `models/pd_model.py:117~128`, `psi()`가 mass point 변수에서 중복 경계로 0 근접, 드리프트 미검.
- H22. `models/estimation/pd_est.py:214~216, 234`, NaN이 MoC/floor/`final_applied`에 침묵 전파, `check_pd_floor`가 NaN 드롭.

**모니터링**
- H23. `monitoring/delinquency.py:28~32`, `deep.py:42~49`, 음수 DPD가 침묵으로 `"90+"`/`"180+"` 오분류.

**리포트/알림 XSS (4건, HIGH)**
- H24. `report_chrome.py:159`, `_table()`이 `<` 포함 문자열 escape 스킵. 모든 리포트 표면(exec, printable, board_pack, ops_pages)에 stored XSS.
- H25. `notifications.py:160~167`, 이메일 페이로드 unescape. 웹훅 릴레이 stored/relayed XSS.
- H26. `board_pack.py:128~134`, exec summary 카드 unescape. 12페이지 dossier 유입.
- H27. `work_report.py:198, 214, 216`, 마크다운→HTML 변환 unescape. json 유래 requirement gap이 페이지 파괴/실행.

**거버넌스**
- H28. `governance/rbac.py:290~338`, RBAC `decide_access`가 실경계에서 미호출. 결정 원장만 만들고 실제 액션 통제 안 함.
- H29. `governance/audit_chain.py:118, 150`, `verify_chain`/`chain_head`가 테스트 외 미호출. 아카이브 사후 편집 방어 없음.

**ALM**
- H30. `alm/contracts.py:189~190`, 재설정 창 0.25y 하드코딩, `params._PRODUCTS`의 `reset_freq_months=6` 무시. 소매·mortgage 변동 대출 repricing ladder 오슬롯.
- H31. `alm/nsfr.py:170~174` + `balance_sheet.py:172~174`, 은행 대출 ≥1y가 85% RSF 매핑 (정답 100% RSF, NSF30.14). NSFR 과대.

### 🟡 MEDIUM · 저장소 광역

**CLAUDE.md §5 (장dash 금지) 위반이 저장소 전 범위에서 수천 건.** 특히 감독규정 forms에서만 1,502건. 일부는 DataFrame 값·이메일·CSV·Excel으로 유출되어 산출물 계약을 깬다 (예: `ncr.py:144`의 `","`가 리포트로, `limits/limits_deep.py:268~274`가 CRO 대시보드로).

**침묵 실패·NaN 전파 패턴:** 여러 모듈에서 `groupby(dropna=True)`, `except: pass`, `assert`(python -O에서 사라짐), NaN→침묵 반환이 발견됨.

**CSV/JSON injection:** `deliverables.py:38~46`의 `to_csv`가 `=`, `+`, `-`, `@` prefix sanitisation 없음.

---

## 두 층 검증 표기 (CLAUDE.md §6)

```
자체검증 (2선)      해당 없음 (본 리뷰는 리스크 재산출이 아니라 코드 리뷰)
상시 독립검증 (3선)  해당 없음 (동)
```

이 리뷰가 지목한 correctness 결함(B1, H1, H2, H3, H6, H31 등)이 실제로 대시보드·상신 수치를 흔든다면, 수치 재산출 시 두 층 검증 절차가 강제된다.

---

## 우선순위 제안

1. **오늘 안**, BLOCKER 5건 수정. 특히 B2(cross-form 게이트 미병합)와 B1(rating bisect 방향)은 결재 페이지에 즉시 영향.
2. **이번 주**, HIGH 중 자본·CCR·XVA·한도 correctness (H1~H3, H5~H11) 재산출·재검증.
3. **이번 주**, 리포트 XSS (H24~H27), 4곳 모두 `_esc()` 도입.
4. **다음 스프린트**, 거버넌스 실경계 통합 (H28, H29), 스트레스 시나리오 정합성 (H16~H18), IFRS9 SICR (B4·H4).
5. **정리 스프린트**, CLAUDE.md §5 저장소 광역 스윕, NaN·CSV injection 방어.

---

**세부 파일:**
- `01-alm.md` · `02-capital-rwa-basel.md` · `03-credit-rating-pd-lgd.md` · `04-cecl-ifrs9-monitoring.md` · `05-regulatory-forms.md` · `06-stress-scenarios-climate.md` · `07-limits-concentration.md` · `08-ccr-xva-margin-ipv.md` · `09-governance-validation-audit.md` · `10-reporting-pipeline-tools.md`
