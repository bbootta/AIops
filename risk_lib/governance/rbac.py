"""역할기반 접근통제와 직무분리 (NFR-003).

이 저장소에는 4-Eyes 결재(gov_approval)와 필드 마스킹(ui_field_policy)이
이미 있었다. 없던 것은 그 앞단이다. **누가 어느 화면·원장을 열 수 있는가**를
정하는 권한 원장이 없으면, 마스킹은 이미 접근한 사람에게만 걸리고 결재는
이미 값을 본 사람 사이에서만 갈린다.

원장 네 장과 판정 한 개로 구성한다.

  gov_role             역할 정의와 방어선(1선·2선·3선)
  gov_role_permission  역할 x 자원 x 행위 권한 부여
  gov_user_role        사용자 x 역할 배정과 유효기간
  gov_sod_conflict     같은 사람이 함께 가지면 안 되는 역할 쌍
  gov_access_decision  판정 결과 원장

판정은 fail-closed다. 권한 행이 없으면 거부하고 사유를 남긴다. 유효기간이
지난 배정도 거부한다. 판정 함수는 원장을 인자로 받고 자체 기본값을 갖지 않는다.

이 모듈의 TableSpec은 아직 datamodel.catalog에 등재하지 않았다. 등재는 실체화
검증과 문서 수치 일치를 함께 만족해야 하므로 배선 단계에서 `SPECS`를 넘긴다.
스펙 품질 기준(입도·기본키·float 단위·FK 대상 존재)은 지금부터 지킨다.

참조: RYNTA BRD NFR-003(RBAC·직무분리) · PLT-013(미승인 필드 차단),
전자금융감독규정 제13조(전산자료 접근통제), BCBS 239 원칙 3.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from risk_lib.datamodel.spec import ColumnSpec as C, ForeignKey as FK, TableSpec
from risk_lib.page_registry import PAGES

LINES = ("1선", "2선", "3선", "운영")
ACTIONS = ("read", "write", "approve")
RESOURCE_KINDS = ("page", "ledger", "function")
DECISIONS = ("허용", "거부")


# ---------------------------------------------------------------- 스펙

ROLE = TableSpec(
    name="gov_role", korean="역할 원장", product="PRD-UIX",
    grain="역할 1개당 1행",
    columns=(
        C("role_id", "string", "역할 식별자", nullable=False),
        C("role_name", "text", "역할명", nullable=False),
        C("line_of_defence", "string", "방어선", nullable=False, allowed=LINES),
        C("org_unit", "text", "소속 조직", nullable=False),
        C("description", "text", "역할 설명"),
    ),
    primary_key=("role_id",),
    note="방어선을 컬럼으로 둔다. 직무분리 판정이 방어선 교차를 근거로 하기 때문이다.",
)

ROLE_PERMISSION = TableSpec(
    name="gov_role_permission", korean="역할 권한 원장", product="PRD-UIX",
    grain="역할 x 자원 x 행위 1건당 1행",
    columns=(
        C("role_id", "string", "역할 식별자", nullable=False),
        C("resource_kind", "string", "자원 종류", nullable=False,
          allowed=RESOURCE_KINDS),
        C("resource_id", "text", "자원 식별자", nullable=False),
        C("action", "string", "행위", nullable=False, allowed=ACTIONS),
        C("granted", "bool", "부여 여부", nullable=False),
        C("citation", "text", "근거"),
    ),
    primary_key=("role_id", "resource_kind", "resource_id", "action"),
    foreign_keys=(FK(("role_id",), "gov_role", ("role_id",)),),
    note="granted=False 행은 명시적 거부다. 행이 없는 경우(묵시적 거부)와 구분해 기록한다.",
)

USER_ROLE = TableSpec(
    name="gov_user_role", korean="사용자 역할 배정", product="PRD-UIX",
    grain="사용자 x 역할 x 유효구간 1건당 1행",
    columns=(
        C("user_id", "string", "사용자 식별자", nullable=False),
        C("user_name", "text", "성명 표기", nullable=False),
        C("role_id", "string", "역할 식별자", nullable=False),
        C("valid_from", "date", "유효 시작일", nullable=False),
        C("valid_to", "date", "유효 종료일", nullable=False),
        C("granted_by", "text", "부여자", nullable=False),
    ),
    primary_key=("user_id", "role_id", "valid_from"),
    foreign_keys=(FK(("role_id",), "gov_role", ("role_id",)),),
    note="유효기간을 필수로 둔다. 기간 없는 배정은 회수 절차가 없는 배정이다.",
)

SOD_CONFLICT = TableSpec(
    name="gov_sod_conflict", korean="직무분리 상충 역할", product="PRD-UIX",
    grain="상충 역할 쌍 1건당 1행",
    columns=(
        C("conflict_id", "string", "상충 식별자", nullable=False),
        C("role_a", "string", "역할 A", nullable=False),
        C("role_b", "string", "역할 B", nullable=False),
        C("reason", "text", "상충 사유", nullable=False),
        C("severity", "string", "심각도", nullable=False, allowed=("중대", "경미")),
    ),
    primary_key=("conflict_id",),
    foreign_keys=(FK(("role_a",), "gov_role", ("role_id",)),
                  FK(("role_b",), "gov_role", ("role_id",))),
)

ACCESS_DECISION = TableSpec(
    name="gov_access_decision", korean="접근 판정 원장", product="PRD-UIX",
    grain="사용자 x 자원 x 행위 판정 1건당 1행",
    columns=(
        C("decision_id", "string", "판정 식별자", nullable=False),
        C("asof", "date", "판정 기준일", nullable=False),
        C("user_id", "string", "사용자 식별자", nullable=False),
        C("resource_kind", "string", "자원 종류", nullable=False,
          allowed=RESOURCE_KINDS),
        C("resource_id", "text", "자원 식별자", nullable=False),
        C("action", "string", "행위", nullable=False, allowed=ACTIONS),
        C("decision", "string", "판정", nullable=False, allowed=DECISIONS),
        C("matched_role", "string", "판정 근거 역할", nullable=True),
        C("reason", "text", "판정 사유", nullable=False),
    ),
    primary_key=("decision_id",),
    note="거부 사유를 문장으로 남긴다. 거부만 기록하면 허용 근거를 사후에 재현할 수 없다.",
)

SPECS: tuple[TableSpec, ...] = (ROLE, ROLE_PERMISSION, USER_ROLE,
                                SOD_CONFLICT, ACCESS_DECISION)


# ---------------------------------------------------------------- 원장 빌더
#
# 아래 세 상수가 이 모듈의 유일한 데이터 적재 지점이다. 판정 함수는 이 값을
# 참조하지 않고 인자로 받은 DataFrame만 본다.

_ROLES = (
    # (role_id, role_name, 방어선, 조직, 설명)
    ("R-CRO", "최고리스크책임자", "2선", "리스크관리본부",
     "전 부문 조회와 결재. 산출 원장 직접 수정 권한은 없다"),
    ("R-CRD", "신용리스크관리자", "2선", "신용리스크부",
     "신용 부문 조회와 산출 실행"),
    ("R-MKT", "시장리스크관리자", "2선", "시장리스크부",
     "시장·CCR·평가 부문 조회와 산출 실행"),
    ("R-ALM", "자금·ALM담당", "1선", "자금부",
     "유동성·금리리스크 원장 조회와 조달 실행"),
    ("R-OPR", "운영리스크관리자", "2선", "운영리스크부",
     "운영손실·RCSA·KRI 조회와 등록"),
    ("R-DAT", "리스크데이터관리자", "2선", "리스크데이터팀",
     "원천·품질·계보 원장 조회와 정정 요청"),
    ("R-VAL", "적합성검증담당", "3선", "적합성검증팀",
     "전 부문 조회. 산출·승인 권한 없음"),
    ("R-AUD", "내부감사", "3선", "감사부",
     "전 부문 조회와 감사기록 열람. 산출·승인 권한 없음"),
    ("R-FO", "영업·트레이딩", "1선", "영업본부",
     "자기 부문 성과·가격 조회에 한정"),
    ("R-OPS", "시스템운영", "운영", "IT운영팀",
     "적재·배치 실행. 리스크 수치 조회 권한 없음"),
)

# 화면 자원은 page_registry의 builder 모듈로 업무영역을 가른다. 화면 목록을
# 손으로 복사하면 화면이 늘 때마다 권한 원장이 조용히 뒤처진다.
_MODULE_DOMAIN = {
    "risk_lib.ops_pages.core_overview": "요약",
    "risk_lib.ops_pages.core_credit": "신용",
    "risk_lib.ops_pages.core_capital_alm": "자본·ALM",
    "risk_lib.ops_pages.credit": "신용",
    "risk_lib.ops_pages.capital_stress": "자본·ALM",
    "risk_lib.ops_pages.market_trading": "시장",
    "risk_lib.ops_pages.concentration_limits": "신용",
    "risk_lib.ops_pages.performance": "성과",
    "risk_lib.ops_pages.nonfinancial": "비재무",
    "risk_lib.ops_pages.governance": "거버넌스",
}

# 역할 x 업무영역 조회 권한. 여기 없는 조합은 행 자체가 생기지 않으므로
# 판정에서 묵시적 거부가 된다.
_DOMAIN_GRANTS = {
    "R-CRO": ("요약", "신용", "자본·ALM", "시장", "성과", "비재무", "거버넌스"),
    "R-CRD": ("요약", "신용", "거버넌스"),
    "R-MKT": ("요약", "시장", "거버넌스"),
    "R-ALM": ("요약", "자본·ALM"),
    "R-OPR": ("요약", "비재무", "거버넌스"),
    "R-DAT": ("요약", "거버넌스"),
    "R-VAL": ("요약", "신용", "자본·ALM", "시장", "성과", "비재무", "거버넌스"),
    "R-AUD": ("요약", "신용", "자본·ALM", "시장", "성과", "비재무", "거버넌스"),
    "R-FO": ("성과",),
}

# 행위 권한. 조회 외의 행위는 자원을 명시해 부여한다.
_FUNCTION_GRANTS = (
    # (role_id, 자원종류, 자원, 행위, 부여, 근거)
    ("R-CRO", "function", "결재 상신", "approve", True, "AIMS_POLICY §2-1 인적 감독"),
    ("R-CRO", "function", "수동조정 승인", "approve", True, "BRD DAT-006"),
    ("R-CRD", "function", "신용 산출 실행", "write", True, "BRD BNK-CRE"),
    ("R-MKT", "function", "시장 산출 실행", "write", True, "BRD SEC-MKT"),
    ("R-ALM", "function", "조달 등록", "write", True, "BRD SEC-LIQ-001"),
    ("R-OPR", "function", "운영손실 등록", "write", True, "BRD SEC-OAI-001"),
    ("R-DAT", "function", "원천 스냅샷 등록", "write", True, "BRD DAT-004"),
    ("R-OPS", "function", "Data Mart 적재", "write", True, "BRD PLT-002"),
    # 명시적 거부. 3선이 산출을 실행하면 독립성이 사라진다.
    ("R-VAL", "function", "신용 산출 실행", "write", False,
     "별표 9-1 제16항 라 독립 부서 요건"),
    ("R-VAL", "function", "결재 상신", "approve", False,
     "별표 9-1 제16항 라 독립 부서 요건"),
    ("R-AUD", "function", "결재 상신", "approve", False, "내부감사 독립성"),
    ("R-OPS", "function", "결재 상신", "approve", False, "직무분리"),
)

_SOD_CONFLICTS = (
    ("SOD-01", "R-FO", "R-MKT", "포지션을 만드는 자와 그 포지션을 평가하는 자는 분리한다", "중대"),
    ("SOD-02", "R-CRD", "R-VAL", "산출 실행자와 독립검증자를 겸하면 3선이 성립하지 않는다", "중대"),
    ("SOD-03", "R-MKT", "R-VAL", "산출 실행자와 독립검증자를 겸하면 3선이 성립하지 않는다", "중대"),
    ("SOD-04", "R-CRO", "R-AUD", "결재자와 감사자를 겸하면 자기 결재를 자기가 점검한다", "중대"),
    ("SOD-05", "R-OPS", "R-CRO", "적재 권한과 결재 권한을 겸하면 값과 승인을 함께 바꿀 수 있다", "중대"),
    ("SOD-06", "R-FO", "R-OPR", "손실사건 당사자가 손실 등록을 겸하면 누락 유인이 생긴다", "경미"),
)


def build_roles() -> pd.DataFrame:
    return pd.DataFrame([{
        "role_id": r[0], "role_name": r[1], "line_of_defence": r[2],
        "org_unit": r[3], "description": r[4],
    } for r in _ROLES])


def build_role_permissions(pages=PAGES) -> pd.DataFrame:
    """화면 권한은 page_registry에서 유도하고, 행위 권한은 명시 목록에서 만든다."""
    rows = []
    for role_id, domains in _DOMAIN_GRANTS.items():
        for p in pages:
            domain = _MODULE_DOMAIN.get(p.module)
            if domain is None or domain not in domains:
                continue
            rows.append({
                "role_id": role_id, "resource_kind": "page",
                "resource_id": p.filename, "action": "read", "granted": True,
                "citation": f"업무영역 {domain}",
            })
    for role_id, kind, res, action, granted, cite in _FUNCTION_GRANTS:
        rows.append({"role_id": role_id, "resource_kind": kind,
                     "resource_id": res, "action": action,
                     "granted": bool(granted), "citation": cite})
    return pd.DataFrame(rows)


def build_user_roles(*, asof: str) -> pd.DataFrame:
    """시연용 사용자 배정 6건. 만료 1건과 상충 1건을 일부러 포함한다.

    통제가 실제로 발동하는 것을 보이려면 위반 사례가 원장에 있어야 한다.
    """
    y = int(asof[:4])
    users = (
        ("U-001", "리스크관리본부 CRO", "R-CRO", f"{y - 2}-01-01", f"{y + 1}-12-31", "이사회"),
        ("U-002", "신용리스크부 담당", "R-CRD", f"{y - 1}-03-01", f"{y + 1}-12-31", "리스크관리본부"),
        ("U-003", "시장리스크부 담당", "R-MKT", f"{y - 1}-03-01", f"{y + 1}-12-31", "리스크관리본부"),
        ("U-004", "적합성검증팀 담당", "R-VAL", f"{y - 1}-07-01", f"{y + 1}-12-31", "감사위원회"),
        # 만료된 배정. 판정에서 거부돼야 한다.
        ("U-005", "전출자", "R-DAT", f"{y - 3}-01-01", f"{y - 1}-06-30", "리스크관리본부"),
        # 상충 배정. SOD-03에 걸린다.
        ("U-006", "겸직자", "R-MKT", f"{y - 1}-01-01", f"{y + 1}-12-31", "리스크관리본부"),
        ("U-006", "겸직자", "R-VAL", f"{y - 1}-01-01", f"{y + 1}-12-31", "감사위원회"),
    )
    return pd.DataFrame([{
        "user_id": u[0], "user_name": u[1], "role_id": u[2],
        "valid_from": u[3], "valid_to": u[4], "granted_by": u[5],
    } for u in users])


def build_sod_conflicts() -> pd.DataFrame:
    return pd.DataFrame([{
        "conflict_id": c[0], "role_a": c[1], "role_b": c[2],
        "reason": c[3], "severity": c[4],
    } for c in _SOD_CONFLICTS])


# ---------------------------------------------------------------- 판정 엔진

def active_roles(user_roles: pd.DataFrame, user_id: str, asof: str) -> list[str]:
    """기준일에 유효한 역할만 돌려준다. 날짜는 ISO date로 파싱해 비교한다."""
    a = date.fromisoformat(asof)
    out = []
    for _, r in user_roles[user_roles["user_id"] == user_id].iterrows():
        try:
            f, t = date.fromisoformat(str(r["valid_from"])), date.fromisoformat(str(r["valid_to"]))
        except ValueError:
            continue                      # 날짜를 못 읽으면 유효하지 않은 배정이다
        if f <= a <= t:
            out.append(str(r["role_id"]))
    return sorted(set(out))


def decide_access(role_permissions: pd.DataFrame, user_roles: pd.DataFrame, *,
                  user_id: str, resource_kind: str, resource_id: str,
                  action: str, asof: str) -> tuple[str, str, str]:
    """(판정, 근거역할, 사유)를 돌려준다. 권한 근거가 없으면 거부한다.

    명시적 거부가 부여보다 앞선다. 한 역할이 거부하고 다른 역할이 허용하면
    거부가 이긴다. 겸직으로 통제를 우회하는 경로를 막기 위함이다.
    """
    roles = active_roles(user_roles, user_id, asof)
    if not roles:
        return "거부", "", f"{asof} 기준 유효한 역할 배정이 없다"

    sel = role_permissions[
        (role_permissions["role_id"].isin(roles))
        & (role_permissions["resource_kind"] == resource_kind)
        & (role_permissions["resource_id"] == resource_id)
        & (role_permissions["action"] == action)]

    denied = sel[sel["granted"] == False]        # noqa: E712
    if len(denied):
        r = denied.iloc[0]
        return "거부", str(r["role_id"]), f"명시적 거부 ({r['citation']})"
    allowed = sel[sel["granted"] == True]        # noqa: E712
    if len(allowed):
        r = allowed.iloc[0]
        return "허용", str(r["role_id"]), f"{r['role_id']} 권한 ({r['citation']})"
    return "거부", "", (f"보유 역할 {'·'.join(roles)}에 {resource_kind} "
                       f"{resource_id} {action} 권한 행이 없다")


def build_access_decisions(role_permissions: pd.DataFrame,
                           user_roles: pd.DataFrame, requests, *,
                           asof: str) -> pd.DataFrame:
    """요청 목록을 판정해 원장으로 만든다.

    requests는 (user_id, resource_kind, resource_id, action) 튜플의 열거다.
    """
    rows = []
    for i, (uid, kind, rid, action) in enumerate(requests, start=1):
        decision, role, reason = decide_access(
            role_permissions, user_roles, user_id=uid, resource_kind=kind,
            resource_id=rid, action=action, asof=asof)
        rows.append({
            "decision_id": f"AC-{asof.replace('-', '')}-{i:04d}",
            "asof": asof, "user_id": uid, "resource_kind": kind,
            "resource_id": rid, "action": action, "decision": decision,
            "matched_role": role or None, "reason": reason,
        })
    return pd.DataFrame(rows, columns=[c.name for c in ACCESS_DECISION.columns])


def sod_violations(user_roles: pd.DataFrame, conflicts: pd.DataFrame, *,
                   asof: str) -> pd.DataFrame:
    """기준일에 유효한 배정만으로 상충을 판정한다.

    만료된 배정까지 세면 이미 회수된 겸직이 영구히 위반으로 남는다.
    """
    rows = []
    for uid in sorted(set(user_roles["user_id"])):
        held = set(active_roles(user_roles, uid, asof))
        name = str(user_roles[user_roles["user_id"] == uid].iloc[0]["user_name"])
        for _, c in conflicts.iterrows():
            if {str(c["role_a"]), str(c["role_b"])} <= held:
                rows.append({
                    "user_id": uid, "user_name": name,
                    "conflict_id": str(c["conflict_id"]),
                    "role_a": str(c["role_a"]), "role_b": str(c["role_b"]),
                    "severity": str(c["severity"]), "reason": str(c["reason"]),
                })
    return pd.DataFrame(rows, columns=["user_id", "user_name", "conflict_id",
                                       "role_a", "role_b", "severity", "reason"])


# ---------------------------------------------------------------- 조립

def _demo_requests(pages=PAGES) -> tuple[tuple[str, str, str, str], ...]:
    """판정 시연 요청. 허용·묵시적거부·명시적거부·만료를 모두 포함한다."""
    market_page = next(p.filename for p in pages
                       if _MODULE_DOMAIN.get(p.module) == "시장")
    credit_page = next(p.filename for p in pages
                       if _MODULE_DOMAIN.get(p.module) == "신용")
    return (
        ("U-002", "page", credit_page, "read"),      # 허용
        ("U-002", "page", market_page, "read"),      # 묵시적 거부
        ("U-004", "page", credit_page, "read"),      # 3선 조회 허용
        ("U-004", "function", "신용 산출 실행", "write"),   # 명시적 거부
        ("U-005", "page", credit_page, "read"),      # 배정 만료
        ("U-001", "function", "결재 상신", "approve"),      # 허용
    )


def build_rbac(*, asof: str, pages=PAGES) -> dict[str, pd.DataFrame]:
    """RBAC 원장 5장을 만든다."""
    roles = build_roles()
    perms = build_role_permissions(pages)
    users = build_user_roles(asof=asof)
    conflicts = build_sod_conflicts()
    decisions = build_access_decisions(perms, users, _demo_requests(pages),
                                       asof=asof)
    return {
        "gov_role": roles,
        "gov_role_permission": perms,
        "gov_user_role": users,
        "gov_sod_conflict": conflicts,
        "gov_access_decision": decisions,
    }
