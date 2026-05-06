# model_type_mapping.md

모형 유형별 필수 / 권장 지표 매핑.

| 모형 유형 | 필수 지표 | 권장 지표 |
|---|---|---|
| 신용평가모형 / 스코어링 | KS, AUROC, AR, PSI, 등급별 bad rate, rank ordering | decile lift, calibration |
| PD | calibration table, Brier, CDR, SDR, backtest | 시계열 PSI, 장기평균 PD 비교 |
| LGD | MAE, RMSE, bias, segment 오차 | downturn LGD, 담보유형 오차 |
| EAD/CCF | MAE, RMSE, bias, CCF 오차 | 한도사용률 구간별 오차 |
| PD multiplier / 회귀 | R², adj R², p-value, VIF, condition index, scenario order | challenger 비교, 잔차 진단 |
| 운영 모니터링 | PSI, default rate 추이 | calibration 추이, segment 분포 안정성 |
| 챌린저 비교 | KS/AUC/AR 비교, calibration 비교 | 안정성, 회귀진단 |
