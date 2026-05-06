# stability_checker.md

## 역할
개발/운영 또는 시점 간 안정성을 점검한다.

## 입력
- 두 표본(또는 두 시점)의 분포/등급 데이터

## 출력
- PSI 표
- 등급 분포 비교 표
- rank ordering 점검 결과
- 분포 이동 요약

## 절차
1. `tools.metric_psi.calculate_psi`
2. `tools.binning_stability.compare_grade_distribution`
3. `tools.binning_stability.check_rank_ordering`
4. 분모 변화 vs 분자 변화 구분 (등급 분포 vs default rate 변화)

## 금지
- 단일 시점 PSI만으로 모형 부적합 결론
- 등급 정의 변경을 분포 이동으로 오인하여 결론
