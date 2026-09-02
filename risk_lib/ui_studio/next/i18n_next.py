"""차세대 UI 셸 카탈로그와 병합 (설계 사양 7장).

기존 `risk_lib.ui_studio.i18n` 은 그대로 두고 옆에 선다. 셸(머리말·게이트
스트립·배지 행·드로어·팔레트·비상정지·꼬리말)이 쓰는 문자열과 모든 화면
모듈이 함께 쓰는 공용 어휘(ng_frag)는 여기 있고, 화면별 문자열은
`risk_lib/ui_studio/next/i18n/ng_<slug>.py` 가 각자 `MESSAGES` 로 가진다.
그래서 병렬로 작업하는 사람이 같은 파일을 건드리지 않는다.

형식은 i18n.py 와 같다. `'한국어||English'` 를 `_t(section, ...)` 로 등록하고
키는 `섹션_일련번호` 다. 조회는 한국어 원문으로 하므로 키 자체는 중복만
피하면 된다.

화면 모듈 파일은 자기 사전을 이렇게 만든다.

    from risk_lib.ui_studio.next.i18n_next import _t
    MESSAGES: dict[str, dict[str, str]] = {}
    _t("ng_reports",
       '...||...',
       into=MESSAGES)

**원장에서 오는 값은 번역하지 않는다.** 원장 값·프레임 라벨·물리 컬럼명·
조문 인용·실행 ID·지문·요청 ID·검증명·수치 ID·테이블명·서식 코드는 이
카탈로그에 넣지 않는다. 3선 판정 어휘(적합·조건부·부적합·응답대기·요청됨)와
결재 어휘(대기·승인·반려)도 원장 값이므로 그대로 둔다.

수치가 섞이는 문장은 `{name}` 자리표시자를 둔 조각으로 등록하고 화면이
`TF(key, vars)` 로 채운다. 키를 이어 붙여 문장을 만들지 않는다.

임포트 시점 가드: 두 언어가 모두 있고, 어느 쪽에도 긴 대시(U+2014·U+2013)가
없고, 영문 자리가 한국어만으로 남지 않고, 금지한 경구 문구가 없다.
"""

from __future__ import annotations

import importlib
import pkgutil
import re

from risk_lib.ui_studio import i18n as _base

MESSAGES_NEXT: dict[str, dict[str, str]] = {}

# 화면 모듈 카탈로그 패키지. 비어 있어도 된다.
_PKG = "risk_lib.ui_studio.next.i18n"
_MODULE_PREFIX = "ng_"

_DASHES = ("\u2014", "\u2013")
_HANGUL = re.compile(r"[가-힣]")
_LATIN = re.compile(r"[A-Za-z]")

# tests/test_ui_screens.py 의 금지 경구 문구와 같은 목록 (대조 수사·단정 경구).
BANNED_PHRASES = (
    "서식만 다르고",
    "사람의 적은",
    "없는 것만 못하다",
    "제일 나쁘다",
    "제일 위험하다",
    "데인 유형",
    "경보가 죽는다",
    "거짓이 된다",
    "화면의 정체",
    "부문이 이긴다",
    "사실은 하나다",
    "조건부는 적합이 아니다",
    "아무에게도 안 읽힌다",
)


def _check_entry(key: str, ko: str, en: str) -> None:
    """항목 하나의 가드. 실패하면 임포트가 멈춘다."""
    if not ko.strip():
        raise ValueError(f"i18n 항목 {key} 의 한국어가 비었다")
    if not en.strip():
        raise ValueError(f"i18n 항목 {key} 에 영문이 없다: {ko!r}")
    for side, text in (("ko", ko), ("en", en)):
        for c in _DASHES:
            if c in text:
                raise ValueError(
                    f"i18n 항목 {key} 의 {side} 에 긴 대시 U+{ord(c):04X} 가 있다: {text!r}")
        for phrase in BANNED_PHRASES:
            if phrase in text:
                raise ValueError(
                    f"i18n 항목 {key} 의 {side} 에 금지 문구 {phrase!r} 가 있다")
    if _HANGUL.search(en) and not _LATIN.search(en):
        raise ValueError(f"i18n 항목 {key} 의 영문이 한국어만이다: {en!r}")


def _t(section: str, *pairs: str, into: dict[str, dict[str, str]] | None = None) -> None:
    """`'한국어||English'` 를 순서대로 등록한다. 키는 `섹션_일련번호` 다.

    `into` 를 주면 그 사전에, 없으면 셸 카탈로그 MESSAGES_NEXT 에 넣는다.
    화면 모듈 파일은 자기 `MESSAGES` 를 `into` 로 넘긴다.
    """
    target = MESSAGES_NEXT if into is None else into
    for i, val in enumerate(pairs):
        ko, sep, en = val.partition("||")
        key = f"{section}_{i:03d}"
        if not sep:
            raise ValueError(f"i18n 항목 {key} 에 영문이 없다: {ko!r}")
        _check_entry(key, ko, en)
        if key in target:
            raise ValueError(f"i18n 키 중복: {key}")
        target[key] = {"ko": ko, "en": en}


# ════════════════════════════════════════════════════════════════════════
# 1. 셸: 머리말·네비게이션·팔레트·꼬리말·오류 경계 (사양 3.1, 3.3, 3.6~3.8)
# ════════════════════════════════════════════════════════════════════════

_t("ng_shell",
   '게이트하우스||Gatehouse',
   'Read-only · 조건·출력 마스킹||Read-only · condition and output masking',
   '마스킹은 조회 조건에는 엔진이, 출력 컬럼에는 화면만 적용한다. 화면 밖 데이터는 이 가드가 지키지 않는다.||Masking is applied to query conditions by the engine and to output columns by the screen only. Data outside this screen is not protected by this guard.',
   'Kill Switch (화면 가드)||Kill Switch (screen guard)',
   '2차 확인자 (필수)||Second confirmer (required)',
   '화면 전용 가드다. 이 페이지 안의 조회·제안 실행만 막고 운영 런타임에는 영향이 없으며 agent_killswitch 원장에는 쓰지 않는다.||A screen-only guard. It blocks only query and proposal execution inside this page, has no effect on the operating runtime and writes nothing to the agent_killswitch ledger.',
   '에이전트는 신용등급·여신승인, 가격·거래, PD·LGD·EAD 등 핵심 위험파라미터, ECL·충당금·회계전표, RWA·NCR·BIS 비율, 감독제출·공시, 경영조치, 운영코드·모형 배포를 자동확정하지 않는다.||Agents never finalise credit grades or loan approvals, pricing or trades, key risk parameters (PD, LGD, EAD), ECL, loan loss allowance or accounting entries, RWA, NCR or BIS ratios, regulatory submissions and disclosures, management actions, or production code and model deployments.',
   '운영 반영 권한(write_allowed)은 전 에이전트가 거짓이다:||Operational write permission (write_allowed) is false for every agent:',
   '상세||Details',
   '명령 팔레트||Command palette',
   '화면 필터||Filter screens',
   '화면 이름·영문명·단축키로 걸러낸다||Filter by Korean name, English name or chord',
   '화면·테이블·검증·수치·서식 검색||Search screens, tables, checks, figures and forms',
   '결과 없음||No matches',
   '화면||Screens',
   '검증 항목||Checks',
   '수치 ID||Figure ids',
   '서식||Forms',
   '명령||Commands',
   '기준일 전환||Switch as-of date',
   '기관 전환||Switch institution',
   '단축키||Shortcuts',
   '단축키 안내||Shortcut sheet',
   '그룹 접기||Collapse group',
   '그룹 펼치기||Expand group',
   '건전성||Prudential',
   '카탈로그·코드||Catalogue and codes',
   '통제||Controls',
   '한도·거액||Limits and large exposures',
   '접기||Collapse',
   '펼치기||Expand',
   '열기||Open',
   '이동||Go',
   '알 수 없는 화면 주소다. 종합보고서로 이동했다.||Unknown screen address. Moved to the executive report.',
   '화면 오류||Screen error',
   '이 화면을 그리는 중 오류가 났다. 다른 화면은 영향이 없다.||An error occurred while drawing this screen. Other screens are unaffected.',
   '요약||Summary',
   '원장 표||Ledger tables',
   '원장 표 펼치기||Show ledger tables',
   '원장 표 접기||Hide ledger tables',
   '이 화면의 원자료 원장이다. 값은 원문 그대로다.||The raw ledgers behind this screen. Values are shown as recorded.',
   '단위 범례||Unit legend',
   '금액은 억원, 비율은 %, 변동은 %p 로 적는다||Amounts in KRW 100m, ratios in %, changes in %p',
   '경로||Route',
   '현재 화면||Current screen',
   '팔레트 열기 / 또는 Ctrl+K · 게이트 스트립 Alt+G · 단축키 안내 ?||Open the palette with / or Ctrl+K · gate strip Alt+G · shortcut sheet ?',
   '그룹 안 이동 [ 와 ]||Step within the group with [ and ]',
   '두 글자 단축키: 그룹 글자 다음 화면 글자||Two-key chord: group key, then screen key',
   '방향키로 이동, Enter 로 열기, Escape 로 닫기||Arrow keys move, Enter opens, Escape closes',
   '드로어 닫기||Close drawer',
   '팔레트 닫기||Close palette',
   '화면 밝기 전환||Toggle theme',
   '언어 전환||Switch language',
   '보고서 인쇄||Print report',
   '인쇄||Print',
   '없음||None',
   '해당 없음||Not applicable',
   '더 보기||More',
   '{n}건 더 보기||{n} more',
   '{n}건||{n} items',
   '화면 {n}개||{n} screens',
   '테이블 {n}장 · {rows}행||{n} tables · {rows} rows',
   '실린 실행 사이 전환만 한다. 새 산출은 하지 않는다.||Switches between embedded runs only. Nothing is recalculated.',
   '합성 기관||Synthetic institution',
)

# ════════════════════════════════════════════════════════════════════════
# 2. 게이트 스트립·배지 행·게이트 드로어 (사양 3.2, 3.4, 6.2)
#
# 판정 값(적합·조건부·부적합·응답대기·요청됨·대기·승인·반려)은 원장 값이라
# 여기 없다. 화면은 그 값을 원문 그대로 찍는다.
# ════════════════════════════════════════════════════════════════════════

_t("ng_gate",
   '자체검증 (2선)||Self-validation (2nd line)',
   '상시 독립검증 (3선)||Standing independent validation (3rd line)',
   '결재||Approval',
   '조건부 승인||Conditional approval',
   'PASS {pass} · WARN {warn} · FAIL {fail} · 규제미달 {blocks} · 미실행 {not_run} (항등식 {identity} 제외)||PASS {pass} · WARN {warn} · FAIL {fail} · regulatory shortfall {blocks} · not run {not_run} ({identity} identities excluded)',
   '{status} ({request_id}) · {kind} · {dispatch}||{status} ({request_id}) · {kind} · {dispatch}',
   '결재 대기 {pending} · 승인 {approved} · 반려 {returned} · 보류 사유 {kinds}종 · 제출 {reviewed}/{total}||Approvals pending {pending} · approved {approved} · returned {returned} · hold reasons {kinds} kinds · submissions {reviewed}/{total}',
   '조건부 승인 기록 필요: ConditionalApproval 필드를 담는 카탈로그 원장이 없고, 스튜디오는 파일 기록을 읽지 않는다||Conditional approval record required: no catalog ledger stores the ConditionalApproval fields, and the studio does not read file records',
   '3선 게이트 미확인||Third-line gate unconfirmed',
   '3선 게이트||Third-line gate',
   '3선 원장 행 없음||No third-line ledger row',
   '게이트 객체 없음||No gate object',
   '발신||dispatched',
   '미발신||not dispatched',
   '발신 미확인||dispatch unconfirmed',
   '종류||Kind',
   '게이트 상태||Gate status',
   '전체 판정||Overall status',
   '결재 차단||Blocks approval',
   '결재 차단 아님||Does not block approval',
   '규제미달||Regulatory shortfall',
   '미실행||Not run',
   '항등식 제외||Identities excluded',
   '○ 미실행||○ not run',
   '이 화면의 2선 검증||Second-line checks on this screen',
   '이 화면의 3선 재계산 대상||Third-line recalculation targets on this screen',
   '이 화면의 수치 {n}건이 RECALC_SCOPE 에 있고 {m}건은 재계산 대상 아님||{n} figures on this screen are in RECALC_SCOPE and {m} are not recalculation targets',
   '이 화면에 연결된 2선 검증이 없다||No second-line check is linked to this screen',
   '이 화면에 3선 재계산 대상이 없다||No third-line recalculation target is on this screen',
   '일치||matched',
   '불일치||mismatched',
   '이전 요청 응답||response to an earlier request',
   '범위밖||out of scope',
   '재계산 대상||Recalculation target',
   '재계산 대상 아님||not a recalculation target',
   '재계산 커버리지||Recalculation coverage',
   '보고값||Reported',
   '재계산값||Recomputed',
   '요청 ID||Request id',
   '요청 대상||Requested to',
   '브랜치||Branch',
   '헤드라인 지문||Headline digest',
   '재계산 대상 수||Recalculation targets',
   '자체검증 FAIL 수||Self-validation FAIL count',
   '자체검증 WARN 수||Self-validation WARN count',
   '응답||Response',
   '응답 없음||No response',
   '응답 요청 ID||Response request id',
   '검증자||Validated by',
   '검증 시각||Validated at',
   '발신 디렉터리||Dispatch directory',
   '보류 사유||Hold reasons',
   '보류 목록||Hold list',
   '차단 검증||Blocking checks',
   '차단 검증 없음||No blocking checks',
   '해소 조치||Unblocking action',
   '담당 미확인, 일치하는 gov_alert_policy 행 없음||owner unknown, no gov_alert_policy row matches',
   '직무분리 위반||Segregation of duties violations',
   '결정 분포||Decision distribution',
   '대상 유형별||By subject type',
   '제출 현황||Submission status',
   '서식별||By form',
   '서식검증 실패||Form check failures',
   '게이트는 fail-closed 다. 응답이 없으면 응답대기이며 결재할 수 없다.||The gate is fail-closed. Without a response it stays pending and nothing can be approved.',
   '3선이 응답대기 또는 부적합이면 초록으로 표시하지 않는다||Never shown green while the third line is pending or non-conforming',
   '게이트 드로어 열기||Open gate drawer',
   '관련 화면||Related screens',
   '2선 검증 {n}건 · FAIL {fail} · WARN {warn}||{n} second-line checks · FAIL {fail} · WARN {warn}',
   '3선 대상 {n}건 · 일치 {matched} · 불일치 {mismatched} · 미보고 {unreported}||{n} third-line targets · matched {matched} · mismatched {mismatched} · not reported {unreported}',
)

# ════════════════════════════════════════════════════════════════════════
# 3. 의사결정 큐 어휘 (x_queue). 예외 심각도·상태 값은 원장 값이라 없다.
# ════════════════════════════════════════════════════════════════════════

_t("ng_queue",
   '보류||Holds',
   '보류 종류||Hold kind',
   '자체검증 실패||Self-validation failure',
   '규제 미달||Regulatory shortfall hold',
   '서식검증 실패 보류||Form check failure hold',
   '예외||Exceptions',
   '예외 스트림||Exception stream',
   '기한||Due',
   '기한 (일)||Due (days)',
   '기한 (영업일)||Due (business days)',
   '담당 역할||Owner role',
   '담당 미확인||Owner unknown',
   '출처 원장||Source ledger',
   '출처 키||Source key',
   '발견 사항||Finding',
   '조치||Action',
   '경보 유형||Alert type',
   '연동 조치||Bound action',
   'SLA (일)||SLA (days)',
   '제출 차단||Blocks submission',
   'DQ 실패 (규칙별)||DQ failures by rule',
   '대사 실패||Reconciliation failures',
   '대사 통과||Reconciliation passed',
   '계약 미통과||Contracts not passed',
   '표준 매핑 미완||Canonical mapping incomplete',
   '마감 차단 요인||Close blockers',
   '대상 유형||Subject types',
   '심각도별||By severity',
   '기한별||By due date',
   '출처별||By source ledger',
   '심각도·톤 매핑||Severity to tone mapping',
   '출처 어휘||Source vocabulary',
   '톤||Tone',
   '표시 기호||Glyph',
   '큐가 비어 있다||The queue is empty',
   '건수는 서버 집계이고 아래 표본 행은 확인용이다||Counts are server-side aggregates; the sample rows below are for inspection',
)

# ════════════════════════════════════════════════════════════════════════
# 4. 마감 워크플로 어휘 (x_close). 과업·게이트 판정 값은 원장 값이라 없다.
# ════════════════════════════════════════════════════════════════════════

_t("ng_close",
   '마감 워크플로||Close workflow',
   '마감 보드||Close board',
   '과업||Task',
   '과업명||Task name',
   '순서||Sequence',
   '단계 레인||Phase lane',
   '데이터||Data',
   '산출||Calculation',
   '선행 과업||Predecessors',
   '승인 필요||Requires approval',
   '증빙 테이블||Evidence table',
   '증빙 행수||Evidence rows',
   '증빙 유형||Evidence kind',
   '행수형||row count',
   '게이트형||gate',
   '승인형||approval',
   '제출형||submission',
   '게이트 판정||Gate decision',
   '차단 요인||Blocked by',
   '마감 단계 이슈||Close-stage issues',
   '제출 건수||Submitted count',
   'CL-12 는 합성 파이프라인에서 구조적으로 미완이다. reg_submission.status 가 submitted 에 이르지 않는다.||CL-12 is structurally incomplete in the synthetic pipeline: reg_submission.status never reaches submitted.',
   '조건부는 CL-10 을 완료하지만 CL-11 은 ConditionalApproval 기록이 있어야 풀린다. 어느 원장에도 그 기록은 없다.||A conditional verdict completes CL-10, but CL-11 stays blocked until a ConditionalApproval record exists, and none is stored in any ledger.',
   '구조적 미완||Structurally incomplete',
   '비대칭 규칙||Asymmetric rule',
)

# ════════════════════════════════════════════════════════════════════════
# 5. 헤드라인 추이 어휘 (x_trend)
# ════════════════════════════════════════════════════════════════════════

_t("ng_trend",
   '헤드라인 추이||Headline trend',
   '추이 원장 경로||Trend ledger path',
   '원장 경로 없음||no ledger path given',
   '기간 수||Periods',
   '현재 요청의 헤드라인 지문이 최신 스냅샷 지문과 같다||The current request headline digest equals the latest snapshot digest',
   '현재 요청의 헤드라인 지문이 최신 스냅샷 지문과 다르다||The current request headline digest differs from the latest snapshot digest',
   '비교 불가||not comparable',
   '원장은 validation_summary 건수를 담지만 게이트 이력은 없어 게이트 전이는 표시할 수 없다||The ledger carries validation_summary counts but no gate history, so gate transitions are unavailable',
   '게이트 전이 없음 (이력 미보존)||Gate transitions unavailable (no history kept)',
   '단일 기간, 추이 없음||one period, no trend drawn',
   '전기 대비||QoQ',
   '전년 대비||YoY',
   '최신||Latest',
   '방향||Direction',
   '추이 상태||Trend state',
   '연속 위반||Consecutive breaches',
   '기간||Period',
   '스냅샷||Snapshot',
   '기간별 검증 요약||Validation summary per period',
   '변화 (기간 대비)||Changed since',
   '변동 없음||No change',
   '악화||Adverse',
   '개선||Improving',
   '하한선||Floor line',
   '한 기관만 싣는다||One institution only',
   '합성 이력은 싣지 않는다||No synthetic history is shipped',
)

# ════════════════════════════════════════════════════════════════════════
# 6. 자본 판정 어휘 (x_capital). 계층 라벨(CET1 · Tier1 (누적) · Total (누적))은
#    payload 값이라 그대로 찍는다.
# ════════════════════════════════════════════════════════════════════════

_t("ng_capital",
   '자본 판정||Capital verdict',
   '구속 계층||Binding tier',
   '자본 계층||Capital tiers',
   '소요||Required',
   '잉여||Surplus',
   '부족||Shortfall',
   '버퍼||Buffers',
   '자본보전||Capital conservation',
   '경기대응||Countercyclical',
   '시스템적 중요 은행||Domestic systemically important bank',
   'MDA 구간||MDA zone',
   'MDA 구간 진입||In the MDA zone',
   '최저 기준||Minimums',
   '레버리지||Leverage',
   '익스포저 측정치||Exposure measure',
   '스트레스 경로||Stress path',
   '분기||Quarter',
   '구속||Binding',
   '미통과 분기||Failing quarters',
   '미통과 분기 {n}건||{n} failing quarters',
   '자본 목표||Capital targets',
   'CET1 등급 (KRI)||CET1 KRI grade',
   '소요 자본 선||Requirement line',
   '소요 대비||Against requirement',
)

# ════════════════════════════════════════════════════════════════════════
# 7. 결재 패키지 어휘 (인쇄 우선)
# ════════════════════════════════════════════════════════════════════════

_t("ng_pack",
   '결재 패키지||Approval pack',
   '실행 식별||Run identity',
   'IV 문서 실행 ID (meta.run_id 와 다름)||IV document run id (differs from meta.run_id)',
   '보류 사유 (중복 제거)||Hold reasons (deduplicated)',
   '조건부 승인 기록||Conditional approval record',
   '승인자 (approver)||Approver (approver)',
   '잔여위험 (residual_risk)||Residual risk (residual_risk)',
   '후속조건 (conditions)||Follow-up conditions (conditions)',
   '이행기한 (due_date)||Due date (due_date)',
   '배포 범위 (scope)||Deployment scope (scope)',
   '수용한 지적 (findings_accepted)||Findings accepted (findings_accepted)',
   '서명란 (미서명)||Signature block (unsigned)',
   '미서명||unsigned',
   '작성자||Prepared by',
   '검토자||Reviewed by',
   '내보내기는 인쇄만 가능하다. 샌드박스가 다운로드를 막는다.||Export is print only because the sandbox blocks downloads.',
   'AIMS §8-2 자동확정 금지 목록||AIMS §8-2 list of items never auto-finalised',
   '3선이 응답대기 또는 부적합이면 이 패키지는 결재에 올릴 수 없다||While the third line is pending or non-conforming this pack cannot be submitted for sign-off',
   '결재 상신 가능||Ready for sign-off',
   '결재 상신 불가||Not ready for sign-off',
   '결재 책임자가 잔여위험·후속조건·이행기한·배포 범위를 기록해야 통과한다||Passes only when the approving officer records residual risk, follow-up conditions, due date and deployment scope',
)

# ════════════════════════════════════════════════════════════════════════
# 8. 비상정지 (화면 가드). 기존 i18n 의 범위·사유·정지·취소·해제 라벨은 재사용.
# ════════════════════════════════════════════════════════════════════════

_t("ng_kill",
   '비상정지 (실행 차단)||Emergency stop (execution blocked)',
   '비상정지 발동 · 범위 {scope}||Emergency stop engaged · scope {scope}',
   '범위: {scope}||Scope: {scope}',
   '해제 모드||Release mode',
   '해제 사유 (필수)||Reason for release (required)',
   '해제||Release',
   '사유와 2차 확인자를 모두 채워야 정지할 수 있다||Both the reason and the second confirmer are required before stopping',
   '사유와 2차 확인자를 모두 채워야 해제할 수 있다||Both the reason and the second confirmer are required before releasing',
   '이 실행에서만 유지되며 원장에 기록되지 않는다||Held for this run only and never written to a ledger',
   '화면 전용 범위다 (AIG-009). 운영 킬스위치 원장 agent_killswitch 와는 별개다.||Screen-only scope (AIG-009). Separate from the operational agent_killswitch ledger.',
   'Kill Switch가 걸려 있어 실행할 수 없다||The Kill Switch is engaged, so this cannot run',
   'Kill Switch가 걸려 있어 승인 적용을 할 수 없다||The Kill Switch is engaged, so approval cannot be applied',
   '이 도메인은 비상정지 범위 안이다||This domain is inside the emergency stop scope',
   '2차 확인자||Second confirmer',
   '발동 사유||Engage reason',
   '해제 사유||Release reason',
)

# ════════════════════════════════════════════════════════════════════════
# 9. 드로어·표 조작 (계보·행·게이트·단축키 드로어, 표 카드 조작)
# ════════════════════════════════════════════════════════════════════════

_t("ng_drawer",
   '원장 행||Ledger row',
   '2선||2nd line',
   '3선||3rd line',
   '추이||Trend',
   '계보||Lineage',
   '닫기||Close',
   '참조 행 열기||Open referenced row',
   '외래키 이동||Foreign key hops',
   '참조 테이블||Referenced table',
   '참조 컬럼||Referenced column',
   '참조 행 없음||Referenced row not found',
   '코드 모듈||Code module',
   '코드 함수||Code function',
   '수치 라벨||Figure label',
   '연결 검증 없음||No checks linked',
   '감사 원장 행 없음||No audit ledger row',
   '3선 대상 아님||Not a third-line target',
   '계보 없음||No lineage',
   '행 상세||Row details',
   '열 선택||Choose columns',
   '열 필터||Filter column',
   '정렬||Sort',
   '오름차순||Ascending',
   '내림차순||Descending',
   '정렬 해제||Clear sort',
   '표시 열||Visible columns',
   '표 보기||Show table',
   '차트 보기||Show chart',
   '행 클릭으로 상세를 연다||Click a row to open its details',
   '물리 컬럼명||Physical column name',
   '원장 값은 원문 그대로다||Ledger values are shown as recorded',
)

# ════════════════════════════════════════════════════════════════════════
# 10. 공용 어휘 (모든 화면 모듈이 함께 쓴다). 화면별 문자열은 ng_<slug>.py 에.
#
# 이미 i18n.py 에 있는 조각(표본 · 기준값의 출처 · 원장 · 단위 · 억원 · 지표 ·
# 상태 · 심각도 · 정상 · 주의 · 경보 · 위반 · 통과 · 미통과)은 다시 넣지 않는다.
# ════════════════════════════════════════════════════════════════════════

_t("ng_frag",
   '연결 원장||Linked ledgers',
   '전량||Full',
   '원장 전량||full ledger',
   '서버 집계||server-side aggregate',
   '전량 {N} (서버 집계)||full {N} (server-side aggregate)',
   '소관 미확인||Ownership unresolved',
   '소관 (UI 가정)||Ownership (UI assumption)',
   'DOMAIN_ROLE_MAP 상수로 연결했다. 도메인과 역할을 잇는 원장 컬럼은 없다.||Joined through the DOMAIN_ROLE_MAP constant. No ledger column joins a domain to a role.',
   '카탈로그 외 · 엔진 산출||outside catalog · engine output',
   '미확인||unconfirmed',
   '미산출||not computed',
   '미보고||not reported',
   '기록 없음||no record',
   '설명용 산술 · 승인·제출값 아님||explanatory arithmetic · not an approved or submitted value',
   '결정론적 규칙 출력 · 같은 데이터면 같은 문장 · LLM 호출 없음||deterministic rule output · the same data gives the same sentence · no LLM call',
   '한도 정의||Limit definition',
   '항등식 (통제 아님)||Identities (not controls)',
   '미리보기 {n}행 / 전체 {N}행||preview {n} rows / total {N} rows',
   '표본 {n}/{N}||sample {n}/{N}',
   '표본 {n}/{N}행||sample {n}/{N} rows',
   '전량 {N}||full {N}',
   '전량 {N}행||full {N} rows',
   '단일 기간||single period',
   '추이 원장에 기간이 하나뿐이다||the trend ledger holds one period, no delta shown',
   '양호||Good',
   '불량||Bad',
   '차단||Blocked',
   '합성||Synthetic',
   '중립||Neutral',
   '설명용||Explanatory',
   '합성데이터 · 합성 포트폴리오||Synthetic data · synthetic portfolio',
   '시드 {seed}||seed {seed}',
   '합성 포트폴리오 · 시드 {seed}||synthetic portfolio · seed {seed}',
   '이 화면의 값은 합성 포트폴리오에서 산출한 것이며 실제 기관 수치가 아니다||Figures on this screen come from a synthetic portfolio and are not actual institution figures',
   '표본 프레임이라 차트를 그리지 않는다||Not drawn because the frame is a sample',
   '차트는 전량 프레임에서만 그린다||Charts are drawn from full frames only',
   '원장에 없다||not in the ledger',
   '원장 행 없음||No ledger row',
   '값 없음||no value',
   '집계 기준||Aggregation basis',
   '출처: {table}||Source: {table}',
   '{shown}/{total}행||{shown}/{total} rows',
   '{n}행||{n} rows',
   '{n}종||{n} kinds',
   '{n}개||{n} items',
   '판정 근거||Basis for the determination',
   '연결 원장 없음||No linked ledger',
   '제품 코드||Product code',
   '그레인||Grain',
   '표시 단계에서 마스킹 컬럼 {n}개를 제외했다. engine.execute 는 전체 컬럼을 반환한다.||{n} masked columns withheld at display; engine.execute returns all columns.',
)


# ════════════════════════════════════════════════════════════════════════
# 병합
# ════════════════════════════════════════════════════════════════════════

def _module_names() -> list[str]:
    """`i18n/ng_*.py` 모듈 이름을 정렬해 돌려준다. 패키지가 비어 있으면 빈 목록."""
    pkg = importlib.import_module(_PKG)
    names = [m.name for m in pkgutil.iter_modules(pkg.__path__)
             if m.name.startswith(_MODULE_PREFIX) and not m.ispkg]
    return sorted(names)


def module_messages() -> dict[str, dict[str, dict[str, str]]]:
    """모듈 이름 → MESSAGES. 각 항목은 셸과 같은 가드를 다시 지난다."""
    out: dict[str, dict[str, dict[str, str]]] = {}
    for name in _module_names():
        mod = importlib.import_module(f"{_PKG}.{name}")
        msgs = getattr(mod, "MESSAGES", None)
        if not isinstance(msgs, dict):
            raise ValueError(f"{_PKG}.{name} 에 MESSAGES 사전이 없다")
        for key, v in msgs.items():
            if set(v) != {"ko", "en"}:
                raise ValueError(f"{name}:{key} 에 ko·en 이 아닌 키가 있다")
            _check_entry(f"{name}:{key}", v["ko"], v["en"])
        out[name] = msgs
    return out


def duplicate_keys_across_modules() -> dict[str, list[str]]:
    """둘 이상의 `ng_*.py` 가 정의한 한국어 키 → 파일 이름 목록.

    영문이 같아도 잡는다. 같은 문구를 두 모듈이 각자 들고 있으면 한쪽만 고쳐질
    때 갈라지므로, 고치는 길은 그 키를 ng_frag 로 옮기는 것이다.
    """
    where: dict[str, list[str]] = {}
    for name, msgs in module_messages().items():
        for v in msgs.values():
            lst = where.setdefault(v["ko"], [])
            if name not in lst:
                lst.append(name)
    return {ko: names for ko, names in where.items() if len(names) > 1}


def _merge(out: dict[str, str], seen: dict[str, str],
           source: str, msgs: dict[str, dict[str, str]]) -> None:
    for key, v in msgs.items():
        ko, en = v["ko"], v["en"]
        if ko in out and out[ko] != en:
            raise ValueError(
                f"같은 한국어 '{ko}' 에 영문이 둘이다: "
                f"{seen[ko]}={out[ko]!r} / {source}:{key}={en!r}")
        if ko not in out:
            out[ko] = en
            seen[ko] = f"{source}:{key}"


def ko_to_en_next() -> dict[str, str]:
    """셸 카탈로그와 모든 `ng_*.py` MESSAGES 를 합친 조회 사전. 충돌이면 실패."""
    out: dict[str, str] = {}
    seen: dict[str, str] = {}
    _merge(out, seen, "i18n_next", MESSAGES_NEXT)
    for name, msgs in module_messages().items():
        _merge(out, seen, name, msgs)
    return out


def merged_map() -> dict[str, str]:
    """i18n.ko_to_en() 위에 차세대 카탈로그를 얹는다. 어디서든 충돌이면 실패."""
    out = _base.ko_to_en()
    seen = {ko: "i18n" for ko in out}
    _merge(out, seen, "i18n_next", MESSAGES_NEXT)
    for name, msgs in module_messages().items():
        _merge(out, seen, name, msgs)
    return out


def payload(debug: bool = False) -> dict:
    """화면에 인라인할 i18n 페이로드. map 만 병합본으로 바꾼다."""
    p = _base.payload(debug)
    p["map"] = merged_map()
    return p


# 임포트 시점에 셸 카탈로그가 기존 카탈로그와 충돌하지 않는지 확인한다.
# 모듈 파일은 병합 시점에 본다 (병렬 작성 중 비어 있을 수 있다).
_base_map = _base.ko_to_en()
_merge(_base_map, {ko: "i18n" for ko in _base_map}, "i18n_next", MESSAGES_NEXT)
del _base_map
