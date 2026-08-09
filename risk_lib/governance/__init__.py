"""거버넌스·통제 원장 (GOV·NFR·PLT·DAT 계열).

이 패키지는 산출값을 만들지 않는다. 산출을 **누가 볼 수 있고, 무엇이 언제
바뀌었으며, 어떤 실행이 어떤 원장을 만들었고, 그 원장을 언제까지 보관하는가**를
원장으로 남긴다. 통제는 데이터로 남아야 감사에서 재현된다.

  rbac             NFR-003 역할·권한·직무분리, 화면 접근 판정 (fail-closed)
  audit_chain      NFR-004 감사기록 append-only 해시체인, 변조 탐지
  retention        DAT-008·PLT-002 보존기간 정책, Data Mart 적재·판 정리
  unified_run      PLT-014 한 실행이 전 도메인을 관통하는 run_id
  model_lifecycle  GOV-004 모형 승인 생애주기 상태기계

각 모듈은 자기 TableSpec을 `SPECS`로 들고 있고 `build_*`가 원장을 만든다.
규제표·정책값은 build_* 안에만 두고 판정 함수는 원장을 인자로 받는다.
"""

from __future__ import annotations
