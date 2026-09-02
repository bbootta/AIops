"""(참고) 그룹 화면 카탈로그 (screens/reference.js).

상업성 화면 하나가 쓰는 문자열이다. 원장에서 오는 값(패키지 이름·편익 설명·
프레임 라벨·단계 정의)과 요건 코드(COM-001~008)는 여기 없다. 표 제목처럼
코드가 문장에 섞이는 경우에는 코드를 두 언어에 그대로 둔다.
"""

from __future__ import annotations

from risk_lib.ui_studio.next.i18n_next import _t

MESSAGES: dict[str, dict[str, str]] = {}

_t("ng_reference",
   # 경계 문단 아래 줄. 첫 문단(사업성 산출...)은 i18n.py commercial 절에 이미 있다.
   '이 화면의 수치에는 수치 ID가 없다. 계보 드로어와 3선 재계산 범위(RECALC_SCOPE) 배지는 규제 산출물에만 붙는다.'
   '||The figures on this screen carry no figure id. Lineage drawers and third-line recalculation scope (RECALC_SCOPE) badges attach to regulatory outputs only.',
   # COM-007 이중계상 판정
   'ROI 이중계상 검증 통과. 편익 항목마다 출처 가정이 하나씩이다 (COM-007)'
   '||ROI double counting check passed. Each benefit item cites exactly one source assumption (COM-007)',
   'ROI 이중계상 발견 (COM-007)||ROI double counting found (COM-007)',
   # 견적·편익 차트
   '회수기간 최단 {name} {years}년||Shortest payback: {name}, {years} years',
   '패키지별 1년차 대가 구성||First-year fee composition by package',
   '가정 원장에서 계산으로만 나온 금액이며 승인·제출값이 아니다'
   '||Amounts computed from the assumption ledger only, not approved or submitted figures',
   'ROI 연 편익 (편익 항목별)||Annual ROI benefit by benefit item',
   '연 편익은 가정 원장의 값을 항목별로 한 번만 계상한 결과다'
   '||The annual benefit counts each assumption ledger value once per item',
   # 표 제목 네 개는 i18n.py commercial 절에 이미 있다. 다시 등록하지 않는다.
   into=MESSAGES)
