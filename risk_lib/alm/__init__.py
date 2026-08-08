"""ALM (자산부채관리) — IRRBB / LCR / NSFR and the synthetic balance sheet.

카탈로그를 먼저 세운다. `datamodel.catalog`가 이 패키지의 TableSpec을 가져다
`ALL_TABLES`에 등재하는데(스펙은 그것을 채우는 코드와 같은 파일에 둔다),
`datamodel.spec`을 import하면 `datamodel` 패키지 __init__이 catalog를 부르므로
ALM 하위모듈이 먼저 실행되면 서로를 반쯤 초기화된 상태로 만난다. 여기서
카탈로그를 완결시켜 두면 하위모듈 본문은 항상 완성된 catalog 위에서 돈다.
"""
from risk_lib.datamodel import catalog as _catalog  # noqa: F401
