# 08. CCR·XVA·마진·IPV·민감도 코드 리뷰

**리뷰 범위:** `risk_lib/crm/`, `risk_lib/ccr.py`, `risk_lib/xva.py`, `risk_lib/margin.py`, `risk_lib/ipv.py`, `risk_lib/sensitivities.py`, `risk_lib/sensitivity.py`, `risk_lib/intraday.py`, `risk_lib/funding.py`, `risk_lib/market_data.py`, `risk_lib/market_portfolio.py`.

## BLOCKER

### 1. `risk_lib/sensitivities.py:57`, 만기 옵션 put delta 오류
- `delta=1.0 if (call and spot>strike) else 0.0`. Deep-ITM 만기 put은 -1.0이 되어야 함. 항상 0으로 반환.
- 실패 시나리오: 만기 도달 put이 배치에 포함되면 `desk_aggregate` 순델타 과소, `intraday.py:118` 헤지비 오적용.

## HIGH

### 2. `risk_lib/ccr.py:60~76`, `saccr_ead` 자산군·헤징세트·초과담보 미반영
- PFE가 `Σ SF·notional·MF` 단순합. 자산군별 add-on, 헤징세트, 초과담보 승수(CRE52.30~79) 없음. `RC=max(V-C,0)`는 margined/unmargined 분기 없음(NICA·TH+MTA). `MF = sqrt(min(M,1))`은 10 영업일 하한 누락.
- 실패 시나리오: +100/-100 IR 스왑 헤지 페어 (notional 1bn씩) → SA-CCR EAD ≈ 진정 헤지의 2배.

### 3. `risk_lib/sensitivities.py:82~95`, `dv01` 중복 할인
- `macaulay = (1-(1+y)^-n)/y` 이미 par bond의 **수정** 듀레이션. 라인 94에서 다시 `(1+y)`로 나눔. 모든 스왑·본드 dV01이 `1/(1+y)` 만큼 과소(y=3.5% 기준 ~3.4%, y=10% 기준 ~10%). VaR, intraday IR P&L(`intraday.py:119, 147`)로 전파.

### 4. `risk_lib/sensitivities.py:106~109`, `cs01` 0 spread 미방어
- `(1 - exp(-s/(1-R)·M)) / (s/(1-R))`가 s==0에서 ZeroDivisionError. 트레이딩북 빌드 중단.

### 5. CLAUDE.md §5 위반
- market_data.py 29, ipv.py 18, sensitivities.py 9, xva.py 6, sensitivity.py 4, ccr.py 3, market_portfolio.py 2, intraday.py 1. docstring뿐 아니라 `ipv.py:16`, `sensitivities.py:1~8`, `market_data.py:4~30`가 최다.

## MEDIUM

### 6. `risk_lib/ipv.py:155~158`, 스왑·CDS는 IPV 구조적 미검출
- `fo_price = np.where(unit_price!=0, unit_price*notional/100, notional*0.01)`. `synthesise_trading_book`이 모든 스왑·CDS `price=0.0`을 씀(`sensitivities.py:156~158, 167`). 결과: 비옵션은 늘 notional의 1%가 FO price, 벤치마크도 그 값 ± 작은 노이즈 → 스왑·CDS 가격 오류 구조적으로 감지 불가.

### 7. `risk_lib/xva.py:118~130`, `mva`가 `t.max()`로 나눔
- `len(t)==0`은 방어하나 `t=[0.0]` 미방어. 또 `dt = np.diff(t, prepend=0)`가 dt[0]=t[0]로 첫 구간을 이중 계상. cva/dva/fva/colva/mva 모두 영향.

### 8. `risk_lib/sensitivity.py:59, 62, 177`, LGD 하드코딩 0.45
- LGD 쇼크 스케일에 `base_lgd = 0.45` 고정. 실현 LGD가 다르면 선형 오스케일(LGD=0.60이면 ~33% 과대). `result.lgd_avg` 참조로 교체.

### 9. `risk_lib/xva.py:78~81`, `_hazard_curve` `lgd<=0` 미검
- `s = cds_bps/1e4 / max(lgd, 1e-6)`. `lgd=0`이면 λ ≈ 10^6, PD ≈ 1, CVA = LGD·EPE·1·DF = 0. 아주 작은 양의 LGD이면 거의 전액 손실 CVA. 명시 거부 필요.

## LOW
- `risk_lib/funding.py:246`, `ladder[ladder["bucket"]=="익일"]["share"].iloc[0]` label 삭제 시 IndexError, 방어 lookup 없음.

## 클린
`risk_lib/crm/allocation.py`, `crm/consistency.py`, `crm/link.py`, `crm/params.py`, `margin.py`, `market_portfolio.py`, `funding.py`(LOW 제외).
