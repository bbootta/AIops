# PLGD 산식 모수를 시뮬레이션으로 결정한 기록

[별표 3] 185.바 후단의 "회수기간동안 발생할 수 있는 예상외 손실 가능성"을
산출하려면 자료가 주지 않는 모수 넷을 정해야 했다. 넷 중 둘은 회수이력으로
갈렸고, 하나는 조문 문언으로 좁혔으며, 하나는 시뮬레이션이 정해 주지 못했다.
이 문서는 무엇을 어떤 수치로 정했고 무엇이 남았는지를 적는다.

구현: `risk_lib/models/estimation/plgd.py`
시험: `tests/test_plgd.py`
연결: `risk_lib/models/estimation/lgd_est.py`의 `build_defaulted_lgd(plgd=...)`

---

## 0. 재현

아래를 그대로 실행하면 이 문서의 모든 표가 다시 나온다. 난수는 관측이력
생성에만 쓰이고 `(asof, seed)`가 고정이라 결과는 바이트 동일하다.

```bash
cd /home/user/AIops && python - <<'PY'
import warnings; warnings.simplefilter('ignore')
import pandas as pd
from risk_lib.models.estimation.history import build_history_ledgers
from risk_lib.models.estimation.params import (
    build_estimation_param_ledgers, approve_discount_rate)
from risk_lib.models.estimation import plgd as P

A, SEED = '2026-06-30', 42
R = build_history_ledgers(asof=A, seed=SEED, years=8)['crm_recovery_history']

def rates(d):
    r = build_estimation_param_ledgers(A)['crm_lgd_discount_rate']
    for s in ('corporate', 'retail_other', 'residential_mortgage'):
        r = approve_discount_rate(r, asof=A, segment=s, recovery_scope='전체',
                                  rate=d, basis='자기자본비용',
                                  approved_by='시험', approval_date='2026-01-01')
    return r

# 표 1. 분모 두 후보의 단조성을 할인율을 바꿔 가며 본다
for d in (0.0, 0.04, 0.11, 0.20):
    c = P.build_crm_beel_curve(R, asof=A, rates=rates(d))
    g = c.groupby(['beel_denominator', 'segment'])['monotonicity_rho'].first()
    print(f'd={d}', ' | '.join(f'{k[0][:4]}/{k[1][:4]}={v:+.3f}'
                               for k, v in g.items()))

c = P.build_crm_beel_curve(R, asof=A, rates=rates(0.11), confidence_q=0.95)
print(P.decide_beel_denominator(c)['rationale'])

# 표 3. DSF 반영형태
for q in (0.75, 0.90, 0.95, 0.99):
    cc = P.build_crm_beel_curve(R, asof=A, rates=rates(0.11), confidence_q=q)
    f = P.decide_dsf_form(cc, confidence_q=q, denominator='부도시익스포저')
    for seg, dd in sorted(f['detail'].items()):
        print(f'q={q} {seg:22s} CV승산={dd["cv_승산_전구간"]:.4f} '
              f'CV가산={dd["cv_가산_전구간"]:.4f} 포화={dd["n_saturated"]}')

# 표 4. 신뢰수준 민감도
pd.set_option('display.width', 250)
s = P.build_crm_plgd_sensitivity(R, asof=A, rates=rates(0.11),
                                 denominator='부도시익스포저')
print(s[['segment', 'confidence_q', 'elbe', 'plgd', 'capital_requirement_k',
         'rwa', 'provision_requirement', 'min_tail_observations']].to_string())

# 표 6. PLGD 원장
L = P.build_plgd_ledgers(R, asof=A, rates=rates(0.11), confidence_q=0.95,
                         approved_by='시험 모형위원회', approval_date='2026-03-01')
print(L['crm_plgd'][['segment', 'elbe', 'plgd', 'dsf', 'dsf_form',
                     'capital_requirement_k', 'status']].to_string())
PY
```

시험으로도 같은 판정을 확인한다.

```bash
cd /home/user/AIops && python -m pytest tests/test_plgd.py -q
```

---

## 1. 출발점

교안 원문(`5강) (LGD) 교안.ppt` 슬라이드 "6. PL(G)D 추정")은 다음 한 문장이
전부다.

> BEEL 분포의 일정 신뢰수준에 해당하는 극단값에 해당하는 PLGD(Potential LGD)는
> 부도 후 경과시점에 따른 BEEL 분포의 불안정성을 감안하여 BEEL 추정치에
> Downturn Scaling Factor를 반영하거나 BEEL 분포로부터 직접 추정합니다.

규정 대응은 [별표 3] 185.바의 두 문장이다.

| 조문 | 값 |
|---|---|
| "예상손실의 최적 추정치를 산출하여야 하며" | ELBE (교안 표기 BEEL) |
| "회수기간동안 발생할 수 있는 예상외 손실 가능성을 추가적으로 반영하여야 한다" | PLGD |

미확정 넷: (가) DSF 반영이 승산인가 가산인가, (나) 신뢰수준 q, (다) BEEL
경과월 산식의 분모, (라) PLGD와 LGD in-default의 대응.

관측 데이터는 `risk_lib/models/estimation/history.py`의 회수이력 원장이다.
기준일 2026-06-30, seed 42, 관측 8년, 부도건 3,361건(회수 미종결 110건),
회수 현금흐름 6,671행이다. **합성 이력이며 실계 자료가 아니다.** 아래 판정은
이 생성 과정이 만든 회수 타이밍 분포 위에서 나온 것이고, 실계 데이터를 붙이면
같은 절차를 다시 돌려 판정을 갱신해야 한다.

---

## 2. (다) 분모: 부도시 익스포저로 정했다

### 검정 방법

경과월 `k`에 아직 부도상태이고 회수가 종결된 건을 코호트로 잡고, 두 분모로 각각
BEEL 곡선을 그린 뒤 경과월과 BEEL 평균의 스피어만 순위상관을 본다.

```
BEEL_i(k) = 1 − PV_k(k 이후 회수 − 비용) / 분모_i(k)
(가) 잔여익스포저   분모 = 부도시 익스포저 − (k까지 받은 회수)
(나) 부도시익스포저 분모 = 부도시 익스포저
```

판정 기준은 **상관계수의 부호**다. 임계값을 세우면 그 임계가 규정처럼 보이므로
두지 않았고, 코호트 최소 건수 필터도 걸지 않았다. 필터를 1건에서 100건까지
바꿔도 판정이 뒤집히지 않는 것을 확인했다.

근거는 신한 카드론 LGD 개선 종료보고(2022)가 "BEEL 그래프가 우상향의 일반
조건을 만족한다"고 적는 데 있다. 실무는 BEEL이 부도 경과월에 대해 단조증가할
것을 기대하고, 곡선이 꺾이면 회수데이터 누락을 의심한다.

### 표 1. 할인율별 스피어만 상관

| 할인율 | 분모 | corporate | residential_mortgage | retail_other |
|---|---|---|---|---|
| 0.00 | 부도시익스포저 | +1.000 | +1.000 | +0.998 |
| 0.00 | 잔여익스포저 | +0.997 | +0.943 | +0.993 |
| 0.04 | 부도시익스포저 | +0.998 | +0.998 | +0.996 |
| 0.04 | 잔여익스포저 | +0.991 | **+0.579** | +0.990 |
| 0.11 | 부도시익스포저 | +0.996 | +0.996 | +0.991 |
| 0.11 | 잔여익스포저 | +0.979 | **−0.684** | +0.976 |
| 0.20 | 부도시익스포저 | +0.992 | +0.992 | +0.986 |
| 0.20 | 잔여익스포저 | +0.735 | **−0.924** | +0.951 |

할인율 0.11(교안이 참조하는 자기자본비용 수준의 타행 실측치)에서 p값은
부도시익스포저 쪽 6.5e-31 · 6.5e-31 · 4.5e-26, 잔여익스포저 쪽 8.8e-21 ·
3.1e-05 · 4.5e-20이다.

**판정: 부도시익스포저.** 3개 세그먼트 전부에서 우상향하고, 잔여익스포저는
2개에서만 우상향한다.

### 표 2. 곡선 양끝값 (할인율 0.11)

| 분모 | 세그먼트 | BEEL(k=0) | BEEL(k=29) | 코호트 건수 k=0 | k=29 |
|---|---|---|---|---|---|
| 부도시익스포저 | corporate | 0.4613 | 0.6614 | 2,266 | 77 |
| 부도시익스포저 | residential_mortgage | 0.2389 | 0.6381 | 148 | 9 |
| 부도시익스포저 | retail_other | 0.5903 | 0.7513 | 837 | 44 |
| 잔여익스포저 | corporate | 0.4613 | 0.5079 | 2,266 | 77 |
| 잔여익스포저 | residential_mortgage | 0.2389 | **0.2250** | 148 | 9 |
| 잔여익스포저 | retail_other | 0.5903 | 0.6776 | 837 | 44 |

`k=0`에서 두 분모의 값이 같은 것은 정의상 당연하다. 아직 받은 회수가 없어
잔여 익스포저가 부도시 익스포저와 같다.

### 왜 갈리는가

잔여익스포저 분모에서는 두 힘이 반대로 작용한다. 경과월이 커지면 남은 회수가
줄어 분자가 작아지고(BEEL을 올린다), 동시에 이미 받은 회수만큼 분모가 깎여
비율이 커진다(역시 BEEL을 올린다). 그런데 평가시점을 `k`로 옮기면 남은 회수의
할인 기간이 짧아져 현재가치가 커진다(BEEL을 내린다). 손실률이 낮은 세그먼트일
수록 회수액이 크므로 이 되감기 항이 커지고, 주거용주택담보(생성 LGD 0.22)에서는
되감기가 이겨 곡선이 우하향으로 돌아선다. 표 1에서 할인율이 0일 때 두 분모가
모두 우상향하고 할인율이 오를수록 잔여익스포저 쪽만 무너지는 것이 그 증거다.
부도시익스포저 분모는 분모가 고정이라 되감기 항 하나만 남고, 그 크기가 남은
회수의 감소보다 작아 곡선이 무너지지 않는다.

`tests/test_plgd.py::test_denominator_undecided_without_discounting`이 이
메커니즘을 시험으로 고정한다. 할인율을 0으로 두면 두 분모 모두 우상향해
판정이 갈리지 않고, 코드는 한쪽으로 밀지 않고 `판정불가`를 낸다.

### 앞선 조사문서의 추론을 정정한다

`docs/primary_sources/BEEL_PLGD_조사결과.md`의 "분모가 무엇인가" 절은 교안
예시표의 24개월 값이 정확히 100.00%로 찍히는 것을 근거로 잔여익스포저 쪽을
추론했다. **그 근거는 두 후보를 가르지 못한다.** 회수관찰기간 종료시점에는 남은
회수가 없으므로 분자가 0이고, 분모가 무엇이든 `1 − 0/분모 = 100%`가 된다.
두 후보 모두 그 지점에서 정확히 100%를 만든다.

### 남은 불확실성

1. **판정이 할인율에 기댄다.** 할인율은 [별표 3] 184.가 값을 주지 않는
   내부기준이고 아직 승인 전이다. 승인된 할인율이 0에 가까우면 이 판정은
   `판정불가`로 되돌아간다. 곡선 원장이 두 분모를 모두 들고 있고
   `is_applied_denominator` 한 칸만 다르므로 재판정이 가능하다.
2. **금액 기준이 달라진다.** 부도시익스포저 분모의 BEEL에 부도시 익스포저를
   곱한 금액은 이미 받은 회수까지 손실로 세는 값이다. 잔여익스포저 기준으로
   바꾸면 corporate 153.5억이 133.0억, residential_mortgage 6.92억이 3.67억,
   retail_other 62.7억이 58.7억이 된다(표 6). 185.바 후단의 충당금 비교가 이
   금액 위에서 이루어지므로 분모 선택이 입증책임 판정을 뒤집을 수 있다.
   `crm_plgd.elbe_amount_alt_denominator`가 그 차이를 들고 있다.
3. **[별표 3] 193.가는 난내 익스포저의 EAD를 현재 인출액으로 본다.** 부도자산에
   적용하는 LGD를 현재 잔액에 곱하는 구조라면 잔여익스포저 기준이 자연스럽다는
   반대 논거가 성립한다. 이 문서는 단조성 기준으로 판정했고, 조문 정합 기준으로
   보면 결론이 달라질 수 있다. 두 기준 중 무엇을 우선할지는 판정하지 않았다.
4. **합성 이력의 회수 타이밍이 결과를 좌우한다.** 생성기는 회수 시점을
   0.25~2.5년 균등분포로 뽑고 금액을 균등 배분한다. 실계 회수는 담보 처분
   일정에 몰려 있으므로 되감기 항의 크기가 다르다.

---

## 3. (가) DSF 반영형태: 승산으로 정했다

### 검정 방법

경과월마다 BEEL 분포의 q분위수와 평균을 구한 뒤

```
승산 가설  quantile(k) / mean(k) 이 경과월에 걸쳐 안정적인가
가산 가설  quantile(k) − mean(k) 이 경과월에 걸쳐 안정적인가
```

를 변동계수(표준편차 / 평균)로 비교하고 작은 쪽을 택한다. 교안이 "반영"이라고만
적어 두 형태가 모두 읽히므로 문언으로는 갈리지 않는다.

### 표 3. 변동계수 (분모 부도시익스포저, 할인율 0.11)

| q | 세그먼트 | CV(승산) | CV(가산) | 포화 구간 |
|---|---|---|---|---|
| 0.75 | corporate | **0.0347** | 0.2218 | 0/30 |
| 0.75 | residential_mortgage | **0.0896** | 0.3634 | 0/30 |
| 0.75 | retail_other | **0.0198** | 0.1625 | 0/30 |
| 0.90 | corporate | **0.0564** | 0.1704 | 0/30 |
| 0.90 | residential_mortgage | **0.1529** | 0.2970 | 0/30 |
| 0.90 | retail_other | **0.0344** | 0.1280 | 0/30 |
| 0.95 | corporate | **0.0696** | 0.1619 | 0/30 |
| 0.95 | residential_mortgage | **0.1760** | 0.2687 | 0/30 |
| 0.95 | retail_other | **0.0457** | 0.1383 | 0/30 |
| 0.99 | corporate | **0.0892** | 0.1578 | 0/30 |
| 0.99 | residential_mortgage | **0.2283** | 0.2683 | 0/30 |
| 0.99 | retail_other | **0.0620** | 0.1619 | 0/30 |

**판정: 승산.** 12개 (세그먼트 × q) 칸 전부에서 승산 쪽 변동계수가 작다.
차이는 q가 낮을수록 크고(최대 8배) q=0.99에서 가장 좁혀지지만 뒤집히지 않는다.

조사문서가 경고한 상한 절단(분위수가 100%에 붙어 변별력이 사라지는 구간)은 이
표본에서 한 칸도 나오지 않았다. 포화 구간이 생기면 두 지표가 모두 퇴화하므로
`decide_dsf_form`은 포화 구간을 뺀 변동계수도 함께 돌려준다.

### 남은 불확실성

1. **DSF의 크기는 이 판정에 포함되지 않는다.** 형태만 정했다. 세그먼트별 DSF
   값(표 6에서 1.30~1.81)은 q가 정해져야 나오는 파생값이고 별도 승인 대상이다.
2. **DSF는 181.의 MoC와 다른 항목이다.** 한 컬럼에 합치면 안 되고, 이 구현은
   `crm_plgd.dsf`와 `crm_lgd_estimate.moc_amount`를 따로 둔다.
3. **경기침체기 정의가 DSF에 들어가지 않았다.** 교안의 DSF는 이름 그대로
   downturn 배수인데, 여기서 계산한 배수는 전기간 BEEL 분포의 분위수 대 평균
   비율이다. 침체기 대 전기간 비율로 정의하면 값이 달라진다. 침체기 정의는
   `crm_estimation_param.downturn_year_quantile`이 들고 있고 승인 전이다.

---

## 4. (나) 신뢰수준 q: 시뮬레이션이 정하지 못했다

q는 관측이 정해 주는 값이 아니라 정책 선택이다. 교안은 "일정 신뢰수준"이라고만
적고 [별표 3]에는 이 자리에 해당하는 수치가 없다. 그래서 원장에는 NULL로 두고
`build_crm_plgd(confidence_q=..., approved_by=..., approval_date=...)` 승인
경로로만 들어가게 했다. 승인자 없이 값만 넣으면 `ValueError`다.

### 표 4. 후보 q별 민감도 (분모 부도시익스포저, 할인율 0.11, 단위 억원)

| 세그먼트 | q | 부도상태 건수 | 부도상태 익스포저 | ELBE | PLGD | 추가분 | K | RWA | 충당금 | 꼬리 표본 |
|---|---|---|---|---|---|---|---|---|---|---|
| corporate | 0.75 | 76 | 274.2 | 0.5598 | 0.7086 | 0.1488 | 0.1488 | 510.0 | 153.5 | 199 |
| corporate | 0.90 | 76 | 274.2 | 0.5598 | 0.7891 | 0.2293 | 0.2293 | 785.9 | 153.5 | 79 |
| corporate | 0.95 | 76 | 274.2 | 0.5598 | 0.8231 | 0.2633 | 0.2633 | 902.5 | 153.5 | 39 |
| corporate | 0.99 | 76 | 274.2 | 0.5598 | 0.8679 | 0.3081 | 0.3081 | 1,055.9 | 153.5 | 7 |
| residential_mortgage | 0.75 | 5 | 17.9 | 0.3864 | 0.5710 | 0.1846 | 0.1846 | 41.3 | 6.9 | 15 |
| residential_mortgage | 0.90 | 5 | 17.9 | 0.3864 | 0.6589 | 0.2725 | 0.2725 | 60.9 | 6.9 | 6 |
| residential_mortgage | 0.95 | 5 | 17.9 | 0.3864 | 0.6983 | 0.3118 | 0.3118 | 69.8 | 6.9 | 3 |
| residential_mortgage | 0.99 | 5 | 17.9 | 0.3864 | 0.7447 | 0.3583 | 0.3583 | 80.1 | 6.9 | **0** |
| retail_other | 0.75 | 29 | 92.8 | 0.6759 | 0.7935 | 0.1176 | 0.1176 | 136.4 | 62.7 | 76 |
| retail_other | 0.90 | 29 | 92.8 | 0.6759 | 0.8516 | 0.1758 | 0.1758 | 203.9 | 62.7 | 30 |
| retail_other | 0.95 | 29 | 92.8 | 0.6759 | 0.8784 | 0.2025 | 0.2025 | 234.9 | 62.7 | 15 |
| retail_other | 0.99 | 29 | 92.8 | 0.6759 | 0.9114 | 0.2356 | 0.2356 | 273.2 | 62.7 | 3 |

합계 기준으로는 이렇게 움직인다.

| q | 부도자산 RWA (억원) | 충당금 소요 (억원) |
|---|---|---|
| 0.75 | 687.6 | 223.1 |
| 0.90 | 1,050.7 | 223.1 |
| 0.95 | 1,207.1 | 223.1 |
| 0.99 | 1,409.3 | 223.1 |

**q는 자본만 움직이고 충당금은 움직이지 않는다.** q를 0.75에서 0.99로 올리면
부도자산 RWA가 2.05배가 되지만 충당금 소요는 223.1억으로 고정이다. 근거는
[별표 3] 120.가(2) 주4)다. PD가 100%인 경우 EL을 185.바의 부도자산 예상손실로
정하므로 EL은 ELBE 그대로이고, 움직이는 것은

```
K = max(0, LGD_in_default − EL_default) = max(0, PLGD − ELBE)
```

의 첫 항뿐이다. 주2)가 PD 100%에서 N{x}를 1로 두고 주1)이 0 미만을 0으로
자른다. RWA는 여기에 12.5와 익스포저를 곱한 값이다.

유효만기 조정은 곱하지 않았다. 원장에 유효만기 자료가 없다.
`crm_plgd.maturity_adjustment_applied = False`가 그 사실을 들고 있고, 기업
익스포저는 120.가(4)의 조정이 걸리므로 위 표의 corporate RWA는 그만큼 과소다.

### 권고값과 그 근거

**권고: q = 0.95.** 근거 둘이다.

1. **표본이 받치는 상한이 거기까지다.** 표 4의 "꼬리 표본"은 부도상태 건이
   실제로 올라타는 경과월 칸에서 분위수 위쪽에 남는 관측 수의 최소값이다.
   q=0.99에서 residential_mortgage는 0이 된다. 분위수가 표본 밖 순서통계량이
   되어 관측이 뒷받침하지 않는 값이 자본으로 흘러간다. q=0.95에서는 가장 얇은
   세그먼트에도 3건이 남는다.
2. **같은 신뢰수준이 국내 검증 실무 두 곳에서 확인된다.** 신한 카드론 보고서의
   PD 상한검정이 q=0.95이고, JB금융지주 적합성검증 시스템 전산요건 정의서의
   소매 PD 데이터흐름 컬럼에도 `적용PD / 95% 상한 / 95% 하한`이 있다
   (`BEEL_PLGD_조사결과.md` §5). **다만 그것은 사후검증 상한의 신뢰수준이고
   PLGD 분위수와 목적이 다르다.** 같은 값을 쓸 근거가 아니라 국내 실무가
   이 수준을 쓴다는 방증으로만 읽어야 한다.

이것은 권고이지 승인이 아니다. 원장의 `confidence_q`는 비어 있고
`confidence_q_status = '미승인'`이며, 그 상태에서 `crm_plgd.plgd`는 NULL이고
`crm_defaulted_lgd.addon_status`는 `'미산출(신뢰수준미승인)'`이다.

### 남은 불확실성

1. **꼬리 표본 기준선 자체가 내부기준이다.** "0이면 안 된다"는 자명하지만
   "3건이면 되는가"는 규정도 자료도 답하지 않는다. 이 문서는 기준선을 세우지
   않고 각 q의 꼬리 표본 수를 사실로 적었다.
2. **표본 크기가 실계에서 달라진다.** 이 판정은 부도상태 건 110건(corporate 76,
   retail_other 29, residential_mortgage 5) 위에서 나왔다. 실계 포트폴리오가
   더 크면 q=0.99도 표본이 받칠 수 있다.
3. **q를 세그먼트별로 다르게 둘 것인가를 판정하지 않았다.** 표본이 세그먼트마다
   크게 다르므로 단일 q가 얇은 세그먼트에서만 표본 밖으로 나간다. 원장 구조는
   세그먼트별 q를 허용하지 않는다(`crm_plgd.confidence_q`가 행마다 있으나
   빌더가 하나만 받는다).

---

## 5. (라) PLGD와 LGD in-default의 대응: 조문으로 좁혔다

185.바가 요구하는 것은 ELBE에 "예상외 손실 가능성을 추가적으로 반영"한 값이고,
그것이 부도자산에 적용되는 LGD다. 120.가(5)도 "부도자산의 LGD는 회수기간동안
발생할 수 있는 예상외 손실 가능성을 추가적으로 반영하여야 한다"고 적어 같은
문장을 LGD 자리에 다시 놓는다. 그래서

```
LGD in-default = ELBE + 예상외손실 추가분 = PLGD
```

로 읽었다. **이 대응을 명시한 문장은 어느 자료에도 없다.** 조문 구조와 교안
문장의 대응으로 세운 추론이므로 `crm_plgd.evidence_status = '추론'`이고
`lgd_in_default_basis` 컬럼이 그 사실을 문장으로 들고 있다.

### 이 해석이 틀렸다면 무엇이 달라지는가

대안 해석은 "LGD in-default는 별도 추정치이고 PLGD는 그 상한 또는 참고값"이다.
그 경우 세 가지가 달라진다.

1. **소요자기자본이 달라진다.** `K = max(0, LGD_in_default − ELBE)`의 첫 항이
   PLGD가 아니게 되므로 표 4의 RWA가 전부 바뀐다. PLGD가 상한이라면 현재 값은
   상한을 적용한 보수적 산출이 되고, 실제 자본은 그보다 작아진다.
2. **q의 성격이 바뀐다.** 적용치의 신뢰수준이 아니라 상한의 신뢰수준이 되므로,
   사후검증 상한(신한·JB의 95%)과 같은 자리에 놓인다. 그러면 §4의 근거 2가
   방증이 아니라 직접 근거가 된다.
3. **185.바 후단 비교 대상이 갈린다.** 조문은 "예상손실의 최적추정치"를
   충당금+상각과 비교하라고 하므로 비교 대상은 어느 해석에서나 ELBE다. 이
   부분은 바뀌지 않는다. 구현도 `shortfall`을 `elbe_amount`로만 계산한다.

---

## 6. 185.바 후단 검사와 관측중단

### 충당금 비교

`crm_plgd`가 `elbe_amount` · `specific_provision` · `partial_writeoff` ·
`shortfall = 충당금 + 상각 − ELBE금액` · `justification_required` ·
`justification_ref`를 들고 있고, `check_plgd_provision_justification`이
`justification_required = True`인데 입증 문서가 비어 있으면 FAIL을 낸다.
비대칭 규칙이라 반대 방향(ELBE가 더 큼)에는 입증책임이 없고 검사도 걸지 않는다.
충당금 자료가 없는 세그먼트는 False가 아니라 NULL로 남는다. False로 두면
"입증이 필요 없음을 확인했다"가 되어 판정하지 않은 것과 구분되지 않는다.

`check_plgd_not_below_elbe`는 `PLGD < ELBE`인 행을 FAIL로 잡는다. 조문이
"추가적으로" 반영하라고 요구하므로 추가분이 음수인 상태는 조문 위반이다.

`check_beel_monotonicity`는 적용 분모 곡선이 우상향하지 않는 세그먼트를 WARN으로
낸다. FAIL이 아닌 이유는 신한 프로젝트에서 우상향이 깨진 원인이 상각 부도·연체
정보 누락이었기 때문이다. 이 검사는 데이터 품질 신호이며, 곡선을 강제로
단조화하라는 뜻이 아니다.

### 표 5. 관측중단 (분모 부도시익스포저, 할인율 0.11)

| 세그먼트 | 관측중단이 있는 경과월 칸 | 관측중단 건수 합 | 포함 평균과 제외 평균의 차이 (평균) | 최대 |
|---|---|---|---|---|
| corporate | 24 / 30 | 1,091 | +0.0082 | +0.0135 |
| residential_mortgage | 23 / 30 | 69 | +0.0105 | +0.0163 |
| retail_other | 24 / 30 | 444 | +0.0072 | +0.0108 |

곡선 평균은 회수가 종결된 건만 쓰고, 미종결 건은 `observation_censored`에
건수로만 남긴다. 미종결 건의 미래 회수는 관측되지 않았으므로 관측분만으로
BEEL을 계산하면 회수를 0으로 본 값이 되어 위로 치우친다. 그 값을 넣은 평균을
`beel_mean_incl_censored`에, 두 값의 차이를 `censoring_impact`에 둔다. 차이는
전부 양수 방향이고, 즉 미종결 건을 빼는 처리가 낙관적이다.

경과월이 짧은 구간에 관측중단이 몰린다. 미종결 건의 부도후 경과가 6~24개월이라
그 구간의 코호트에만 들어가기 때문이다. 곡선의 왼쪽 끝을 읽을 때 이 편의를
같이 봐야 한다.

---

## 7. 표 6. 결과 원장 (q = 0.95를 승인했다고 가정)

| 세그먼트 | 부도상태 건수 | ELBE | PLGD | 추가분 | DSF | 형태 | K | ELBE금액(억) | 대체분모 금액(억) | 상태 |
|---|---|---|---|---|---|---|---|---|---|---|
| corporate | 76 | 0.5598 | 0.8231 | 0.2633 | 1.4704 | 승산 | 0.2633 | 153.5 | 133.0 | 산출완료 |
| residential_mortgage | 5 | 0.3864 | 0.6983 | 0.3118 | 1.8069 | 승산 | 0.3118 | 6.9 | 3.7 | 산출완료(표본부족) |
| retail_other | 29 | 0.6759 | 0.8784 | 0.2025 | 1.2996 | 승산 | 0.2025 | 62.7 | 58.7 | 산출완료(표본부족) |

`insufficient_sample`은 부도상태 건이 30건 미만인 세그먼트에 붙는다.
residential_mortgage 5건은 분위수 추정에 쓰기에 너무 얇고, 그 사실이 상태
컬럼과 `note`에 남는다.

이 표의 ELBE는 `crm_lgd_estimate.longrun_default_weighted_lgd`와 다른 값이다.
후자는 신규 부도를 대상으로 한 장기 부도가중평균이고, 여기의 ELBE는 이미 부도난
건의 현재 경과월을 조건으로 한 최적추정치다. `build_defaulted_lgd`에
`crm_plgd`를 넘기면 `elbe` 컬럼도 곡선 기준으로 바뀐다. 바꾸지 않으면 한 행
안에서 `lgd_in_default − elbe`가 `unexpected_loss_addon`과 어긋난다.

---

## 8. 원장에 값을 넣지 않은 것

| 항목 | 원장 자리 | 상태 |
|---|---|---|
| 신뢰수준 q | `crm_plgd.confidence_q` | NULL. `confidence_q_status='미승인'` |
| DSF 값 | `crm_plgd.dsf` | q 승인 후에 나오는 파생값 |
| 회수 할인율 | `crm_lgd_discount_rate.discount_rate` | NULL. 승인 전이라 곡선 자체가 `산출불가(할인율미승인)` |
| 유효만기 | 없음 | 원장에 자료가 없어 만기조정을 적용하지 않았다 |
| 회수관찰기간 T | 없음 | 규정 미제시. 이 구현은 관측된 마지막 회수월까지를 코호트로 잡는다 |
| 정상화(cure) 규칙 | 없음 | 자료 두 종이 어긋난다. 이 구현은 cure 처리를 하지 않는다 |

승인 전 기본 산출물에서 `crm_plgd.plgd`는 전건 NULL이고
`crm_defaulted_lgd.addon_status`는 `'미산출(신뢰수준미승인)'`이다. 할인율까지
승인 전이면 곡선이 만들어지지 않아 분모 판정이 `판정불가`가 되고
`crm_plgd`·`crm_plgd_sensitivity`는 빈 원장으로 나온다. 그 사유는
`crm_beel_curve.status`가 들고 있다.

---

## 9. 배선이 남은 것

1. `risk_lib/models/estimation/run.py`의 `build_irb_estimation_ledgers`가
   PLGD 원장 석 장을 만들지 않는다. `build_plgd_ledgers`를 부르고
   `build_defaulted_lgd(plgd=...)`로 넘기면 연결된다.
2. `risk_lib/models/estimation/checks.py`의 `run_irb_estimation_checks`가
   `run_plgd_checks`를 부르지 않는다.
3. `risk_lib/models/estimation/__init__.py`의 `ALL_TABLES`에 세 스펙이 없다.
   **이것 때문에 `tests/test_req_wiring.py::test_every_new_ledger_spec_is_registered_or_excluded_with_a_reason`이
   실패한다.** `ALL_TABLES`에 `crm_beel_curve`(24컬럼)·`crm_plgd`(32컬럼)·
   `crm_plgd_sensitivity`(18컬럼)를 넣으면 `catalog.py`가 그 dict를 그대로
   읽어가므로(2630행) 카탈로그 등재까지 한 번에 끝난다. 등재하면 카탈로그가
   261테이블/2708컬럼에서 264테이블/2782컬럼이 되므로 `ARCHITECTURE.md`의
   "N테이블/M컬럼" 주장도 같이 고쳐야 한다
   (`tests/test_architecture.py::test_architecture_doc_table_and_column_counts_match_the_catalog`).
4. `risk_lib/ui_studio/app.py`와 `i18n.py`의 PLGD 문구가 "청산부도손실율(PLGD)의
   정의와 산식을 1차자료에서 확인하지 못했다"로 남아 있다. PLGD는 Potential LGD
   이고 정의는 확인됐다. 화면 문구와 `elbe_method` 표시가 갱신 대상이다.
5. `crm_estimation_param.PARAM_CODES`에 `beel_denominator`·`plgd_confidence_q`
   ·`dsf_form` 세 모수 코드가 없다. 현재는 빌더 인자로 받는다. 모수 원장에
   올리면 승인 기록이 `approve_estimation_param` 경로로 통일된다.
