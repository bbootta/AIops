"""Basel III/IV 리스크 부문별 검증 점검 모듈.

각 부문은 다음 패턴을 따른다.
- 임계 SSoT 는 ``harness/<bucket>_thresholds.json``
- 점검 함수는 결정론적·부작용 없는 순수 함수
- 산정 모형 자체는 트레이딩/리스크 시스템에서 수행, 본 모듈은 점검만

`tools.risk_checks.market`, `.operational`, `.liquidity`, `.irrbb`, `.cva`, `.ccr`.
"""
