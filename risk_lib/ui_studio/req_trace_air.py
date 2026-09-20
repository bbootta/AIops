"""AI 리스크관리 업무요건(BR 76건) 대비 이 하네스 구현의 추적.

req_trace.py 와 같은 계약이다. 증빙 kind 도 같고(module · table · screen ·
test), 실재 검증은 tests/test_req_trace_air.py 가 한다.

현재 상태를 있는 그대로 적는다. 이 하네스는 언어모형을 호출하지 않는 결정론적
산출 라이브러리라, AI 거버넌스 쪽은 에이전트 레지스트리·활동 원장·추적 사슬·
마스킹 규칙·범위형 비상정지·4-Eyes 승인·변경통제·모형 수명주기·감사 해시체인
까지 있다(v9.6.0 AIG 요건과 겹치는 부분). 반면 생성형 AI 평가·레드티밍·RAG
접근통제·위임체인·공급자 계약·고객 이의제기·사고 분류처럼 언어모형 운영을
전제한 요건은 없다. 해설서의 엔티티 테이블 43장은 카탈로그에 한 장도 없다.
"""

from __future__ import annotations

from risk_lib.regulatory.requirements_air import (
    CHAPTER_OF, CHAPTERS, REQUIREMENTS, SOURCE, SOURCE_SHA256, SOURCES, TABLES,
)

# 상태: 반영 · 부분 · 미반영 (매핑에 없으면 미반영)
# 형식: id → (상태, ((kind, ref), …), note)
TRACE: dict[str, tuple[str, tuple[tuple[str, str], ...], str]] = {
    # ---- 01 범위·기준선 ---------------------------------------------------
    "BR-001": ("부분", (("table", "agent_registry"),
                        ("test", "test_no_agent_has_operational_write_permission")),
                "에이전트마다 owner·domain·tools 가 레지스트리에 있고 운영 반영 권한은 전건 "
                "거짓이다. 미등록 호출을 잡는 발견 원장(discovery_item)은 없다"),
    "BR-002": ("부분", (("table", "aig_agent_trace"), ("table", "agent_activity"),
                        ("module", "risk_lib.aig.trace")),
                "도구호출·출력 두 구간을 phase 로 나눠 기록하고 산출은 전부 결정론 엔진이다. "
                "AI 생성 수치에 calculation_id 를 붙여 승격을 막는 검사는 없다"),
    "BR-004": ("부분", (("table", "gov_change_policy"), ("table", "gov_change_gate"),
                        ("screen", "변경통제")),
                "변경 등급·위험 등급별 필수 통제 단계와 게이트 판정은 있다. "
                "사용범위 확대·외부 실행 추가를 변경평가 재시작 조건으로 잡는 규칙은 없다"),
    # ---- 03 거버넌스 -------------------------------------------------------
    "BR-005": ("부분", (("table", "gov_role_permission"), ("table", "gov_sod_conflict"),
                        ("module", "risk_lib.governance.rbac")),
                "역할·권한 원장과 직무분리 충돌표가 있고 겸직 충돌을 검사한다. "
                "AI 서비스별 책임자·기술운영자·독립검증자·준법·최종승인자 지정은 없다"),
    "BR-008": ("부분", (("screen", "검증 일정"), ("module", "risk_lib.model_inventory")),
                "모형별 검증 주기·경과·다음 기한은 있다. 만료 평가·미지정 오너·퇴사 승인자로 "
                "재배포를 차단하는 게이트는 없다"),
    # ---- 04 인벤토리·위험분류 ----------------------------------------------
    "BR-009": ("부분", (("table", "agent_registry"),
                        ("screen", "에이전트 레지스트리 · 최소 권한")),
                "등록 필드는 이름·모드·위험등급·도구·범위·쓰기권한·오너·도메인이다. "
                "목적·고객영향·법인·모델버전·데이터등급·배포환경·종료계획은 없다"),
    "BR-010": ("부분", (("table", "agent_registry"), ("test", "test_agent_registry_has_risk_tiers")),
                "위험등급 상·중·하를 규칙으로 매긴다(규제 산출=상). 5개 요소 최대값 1~4 체계와 "
                "금지행위 REJECTED 는 없고 법적 분류도 따로 두지 않는다"),
    # ---- 05 데이터 ---------------------------------------------------------
    "BR-014": ("부분", (("table", "rdm_dq_rule"), ("table", "rdm_dq_result"),
                        ("module", "risk_lib.datamodel.decompose")),
                "수집 원장마다 건수·키·결측·중복·참조정합성 DQ 규칙과 판정이 있다. "
                "실패 자료를 배포 인덱스·모형에 투입하지 않는 차단은 없다"),
    "BR-015": ("부분", (("module", "risk_lib.ui_studio.nl_query"), ("table", "ui_view"),
                        ("test", "test_masked_field_condition_is_blocked_on_screen")),
                "조회는 승인 View·필드정책·집계최소단위를 통과해야 실행된다. "
                "벡터 인덱스·캐시·내보내기·인용 링크에 같은 통제를 거는 층은 없다"),
    "BR-017": ("부분", (("table", "gov_evidence_node"), ("table", "gov_evidence_edge"),
                        ("module", "risk_lib.archive")),
                "증빙 계보 7단계의 부모·자식 관계는 있다. 신뢰·기밀 레이블 보존은 없다"),
    "BR-020": ("부분", (("table", "aig_redaction_rule"), ("module", "risk_lib.aig.trace"),
                        ("test", "test_blocking_rule_reports_that_the_payload_must_not_be_sent")),
                "전송 전 마스킹·차단 규칙 원장이 있고 차단된 페이로드는 저장하지 않는다. "
                "텍스트만 다루며 이미지·음성·첨부와 목적지 정책 검사는 없다"),
    # ---- 06 전통적 모형 ----------------------------------------------------
    "BR-021": ("부분", (("table", "crm_model_governance"), ("table", "crm_dev_sample"),
                        ("screen", "모형 인벤토리")),
                "모형 인벤토리·승인·개발표본(관측기간·부도정의) 원장은 있다. "
                "변수변환·제외기준·계수·사용제한을 담은 모델카드 원장은 없다"),
    "BR-022": ("부분", (("table", "crm_backtest_result"), ("table", "crm_dev_sample")),
                "표본외(out_of_sample) 백테스트와 관측기간 원장은 있다. 자료누출 검사와 "
                "회수정보 시점 검사는 없다"),
    "BR-023": ("부분", (("table", "crm_performance"), ("table", "crm_pd_calibration"),
                        ("table", "crm_backtest_criteria")),
                "변별력·보정·안정성·백테스트 기준을 분리해 둔다. 공정성·보수성 분리와 "
                "경제적 해석 기록은 없다"),
    "BR-024": ("부분", (("table", "aig_adjustment"), ("screen", "오버레이")),
                "수작업 조정은 이전값·변경값·요청자·승인자·만료를 갖는다. 승인된 모델·파라미터 "
                "버전과 운영 산출의 대사는 없다"),
    # ---- 07 생성형 AI 평가 -------------------------------------------------
    "BR-026": ("부분", (("table", "aig_agent_trace"),),
                "실행마다 행위자·도구·페이로드 지문·마스킹 규칙을 기록한다. 프롬프트 본문·"
                "검색집합·샘플링 설정은 없다(이 저장소는 언어모형을 호출하지 않는다)"),
    # ---- 09 승인과 실행 ----------------------------------------------------
    "BR-034": ("부분", (("table", "gov_approval"), ("table", "val_independent_request")),
                "승인은 대상 종류·대상 ID·증빙 참조에 묶이고 독립검증 요청은 대상 수치 지문을 "
                "갖는다. 금액·통화·도구버전·정규화 인수까지 담은 승인 지문과 실행 직전 재비교는 없다"),
    "BR-035": ("부분", (("table", "gov_approval"), ("table", "gov_sod_conflict")),
                "검토자와 승인자를 나누고 직무분리 여부를 기록한다(4-Eyes). "
                "승인 재사용 금지와 무응답·읽음을 승인으로 치지 않는 규칙은 명시되지 않았다"),
    "BR-036": ("부분", (("table", "agent_killswitch"),
                        ("test", "test_kill_switch_stops_new_queries_without_any_dialog")),
                "정지 상태이면 신규 도구 호출이 차단된다. 버전·역할·정책·자격증명 회수를 "
                "원자적으로 검사하는 재인가 단계는 없다"),
    # ---- 10 런타임 정책 ----------------------------------------------------
    "BR-037": ("부분", (("table", "gov_access_decision"), ("table", "ui_field_policy"),
                        ("module", "risk_lib.ui_studio.nl_query")),
                "접근 판정과 필드 마스킹 의무가 있고 미통과 조건은 실행되지 않는다. "
                "ALLOW/BLOCK/DEFER 와 의무 목록을 분리한 정책 평가 원장은 없다"),
    "BR-040": ("부분", (("module", "risk_lib.ui_studio.nl_query"),
                        ("module", "risk_lib.validation.independent")),
                "정책 통과 없이는 조회가 되지 않고 독립검증 게이트는 응답이 없으면 결재 불가다"
                "(fail-closed). 검사 엔진 장애 시 읽기전용 축소모드는 없다"),
    # ---- 11 생애주기·변경 --------------------------------------------------
    "BR-041": ("부분", (("table", "gov_model_stage"), ("table", "gov_model_transition"),
                        ("screen", "모형 수명주기")),
                "단계·필수 산출물·승인 역할·전이 원장이 있다. 반려를 새 버전 재제출로 "
                "강제하는 규칙과 배포·폐기 단계 실행은 없다"),
    "BR-042": ("부분", (("module", "risk_lib.repro"),
                        ("test", "test_engine_js_is_inlined_by_the_renderer")),
                "실행 지문·코드 리비전과 브라우저 엔진 패리티 검사는 있다. "
                "배포번들 서명과 공급자 실제 버전 확인은 없다"),
    "BR-043": ("부분", (("table", "gov_change_request"), ("table", "gov_change_impact"),
                        ("screen", "변경통제")),
                "변경 요청·영향 항목·회귀 필요 여부는 있다. 보안·공정성·비용·지연·복구를 "
                "포함한 평가 항목과 긴급 변경의 기한부 승인은 없다"),
    "BR-044": ("부분", (("table", "gov_change_gate"),
                        ("test", "test_approve_then_rollback_round_trip")),
                "게이트 판정과 화면 레이아웃 롤백은 있다. 단계적 배포와 검증된 이전 버전으로의 "
                "운영 복구는 없다"),
    # ---- 12 모니터링 -------------------------------------------------------
    "BR-046": ("부분", (("table", "gov_alert_policy"),),
                "경보 유형·발동 규칙·조치·SLA·제출 차단 여부를 정책 원장으로 둔다. "
                "최소표본·지속조건·변동성 설정과 실행위반 즉시 경보는 없다"),
    "BR-047": ("부분", (("table", "gov_exception_action"), ("table", "gov_alert_policy")),
                "예외·조치 큐에 담당·기한이 붙는다. 사건별 경보 묶기와 부재 시 대체자 배정은 없다"),
    "BR-048": ("부분", (("module", "risk_lib.macro_monitor"), ("table", "crm_backtest_result")),
                "지표는 근거(파생·실측)를 수치와 함께 보고하고 판정 불가면 판정 컬럼을 비운다. "
                "DATA_GAP/NOT_EVALUATED 상태값과 수집지연 탐지는 없다"),
    # ---- 13 사고·중단 ------------------------------------------------------
    "BR-049": ("부분", (("table", "gov_run_issue"),),
                "실행 통제 이슈 원장(단계·종류·상세)은 있다. 7종 사고분류와 영향·탐지시각·"
                "보고의무 검토 기록은 없다"),
    "BR-050": ("부분", (("table", "agent_killswitch"), ("screen", "Kill Switch")),
                "범위형 정지(scope_type·scope_ref)와 중요 범위의 2차 확인은 있다. "
                "자식 전파와 회수 세대번호 검사는 없다"),
    "BR-052": ("부분", (("table", "agent_killswitch"), ("test", "test_kill_switch_can_be_cancelled")),
                "정지 해제는 별도 행위로 기록된다. 원인제거·무결성검사·회귀시험·재개 승인 "
                "절차와 중단권한·재개승인 분리는 없다"),
    # ---- 16 리스크관리 연결 -------------------------------------------------
    "BR-058": ("부분", (("module", "risk_lib.repro"), ("table", "gov_unified_run")),
                "실행마다 기준일·시드·코드 리비전·지문이 고정된다. 개별 고객 결정 단위의 "
                "주요요인·사람 관여 고정은 없다"),
    "BR-061": ("반영", (("module", "risk_lib.repro"), ("table", "gov_unified_run"),
                        ("table", "val_audit_ledger")),
                "기준일·시드·코드 리비전·실행 지문을 고정하고 동일 입력 재산출을 대사한다. "
                "산출 근거 원장이 수치마다 모듈·함수·인용을 잇는다"),
    "BR-062": ("반영", (("module", "risk_lib.regulatory.cross_form"),
                        ("table", "rdm_reconciliation"), ("table", "reg_form_check")),
                "원천·산출 대사와 서식 간 교차 대사 9종, 서식 라인 검증이 있다"),
    "BR-064": ("반영", (("table", "reg_submission"), ("table", "gov_approval"),
                        ("module", "risk_lib.validation.independent")),
                "제출본은 작성·검토·승인자와 지문·검증 실패 수를 갖고, 독립검증 게이트는 "
                "응답 없이는 결재 불가다. 자동 제출 경로가 없다"),
    # ---- 17 증빙·감사 ------------------------------------------------------
    "BR-065": ("부분", (("table", "gov_unified_run"), ("table", "gov_run_domain"),
                        ("table", "gov_evidence_edge")),
                "run_id 로 도메인·원장·증빙 노드가 이어진다. action_id·decision_id·approval_id "
                "체계와 링크 누락 시 미완료 처리는 없다"),
    "BR-066": ("부분", (("table", "gov_audit_chain"), ("module", "risk_lib.governance.audit_chain"),
                        ("test", "test_chain_detects_a_modified_row")),
                "추가기록 해시체인이 수정·삭제를 잡는다. 서명과 서버시각·원천시각 분리는 없다"),
    "BR-068": ("부분", (("module", "risk_lib.archive"), ("table", "ui_field_policy")),
                "보고서 묶음은 판별 보관되고 필드 마스킹 정책이 있다. "
                "보고서 버전과 재다운로드 동일성·열람 이력은 없다"),
    # ---- 19 개발·인수 ------------------------------------------------------
    "BR-073": ("부분", (("module", "risk_lib.validation.consistency"),
                        ("test", "test_kill_switch_stops_new_queries_without_any_dialog")),
                "회귀 스위트와 권한·비상정지 시험은 있다. 장애·복구·동시성 시험은 없다"),
}

# 아직 판정하지 않은 요건, id → 사유. 사유는 요건별로 쓴다.
UNASSESSED: dict[str, str] = {
    "BR-003": "제안값 POLICY_PROPOSAL 표시와 출처 유형·효력시점 원장(regulatory_rule)이 없다",
    "BR-006": "KR 고영향·EU 고위험·자동화결정 적용성 판정(applicability_assessment)이 없다",
    "BR-007": "통제 예외 원장(control_exception, 보완통제·만료·재검토)이 없다",
    "BR-011": "미확인 데이터·권한·공급자를 4등급으로 잠정 설정하는 미확인 원장이 없다",
    "BR-012": "위험평가 의존관계 변경 이벤트와 미등록 자식 에이전트 실행 차단이 없다",
    "BR-013": "원천별 수집근거·이용목적·보유기간·국외이전 적법성 원장이 없다",
    "BR-016": "정정·삭제·동의철회의 파생자료(임베딩·캐시) 삭제 추적(deletion_request)이 없다",
    "BR-018": "만료·미승인 규정 배제와 효력기간·적용조직 대조 규칙이 없다",
    "BR-019": "보안 맥락 관계의 source_at·expires_at 부여가 없다",
    "BR-025": "고정 test_set 버전과 정상·공격·경계 질문 골든셋이 없다",
    "BR-027": "모델 판정자와 사람 라벨의 일치도 검증이 없다",
    "BR-028": "집단별 정확성·거절·불이익 공정성 보고가 없다",
    "BR-029": "신뢰경계를 표시한 위협모델·데이터흐름도가 없다",
    "BR-030": "직접·간접·저장형·다중에이전트 주입 공격 시험이 없다",
    "BR-031": "계좌·수취인·금액·승인상태 변경의 금융 무결성 시험이 없다",
    "BR-032": "중대취약점 재현·재시험 연결 티켓이 없다",
    "BR-033": "사용자·서비스·에이전트·자식 신원 분리와 위임체인 원장이 없다",
    "BR-038": "비신뢰 원문의 제어영역 재주입 금지와 반출규칙 경계 시험이 없다",
    "BR-039": "도구 네트워크 프록시·집행게이트와 미등록 플러그인 차단이 없다",
    "BR-045": "분자·분모·모집단·임계값 버전을 가진 AI 지표 사전(metric_definition)이 없다",
    "BR-051": "외부효과 불명 UNKNOWN 보존과 자동 재시도 금지 규약이 없다",
    "BR-053": "공급자 계약 조건 원장(provider_contract)이 없다",
    "BR-054": "데이터 유입·추론·저장·백업 경로별 심사(processing_route)가 없다",
    "BR-055": "공급자 장애·모델종료·집중위험 시나리오 검증이 없다",
    "BR-056": "기능·안전성·성능 주장 원장이 없다",
    "BR-057": "AI 활용 사전고지·생성물 표시 필드와 채널별 이의신청 제공이 없다",
    "BR-059": "고객 요청 접수·적용성·인적검토·통지 원장(rights_request)과 30일 시계가 없다",
    "BR-060": "수정 권한을 가진 담당자의 인적 재검토와 불이익 금지 규칙이 없다",
    "BR-063": "여신감리 초안의 차주별 근거 연결이 없다",
    "BR-067": "증빙 유형별 보관기간·법적근거·삭제방법 원장(retention_policy)이 없다",
    "BR-069": "UI-01~12 화면의 필수필드·역할·상태검사 서버·화면 동일 적용이 없다",
    "BR-070": "해설서 데이터 계약(데이터형·키·열거값·테넌트 격리) 준수 검증이 없다",
    "BR-071": "동시요청·재전송·순서역전·회수경합 처리(idempotency_record)가 없다",
    "BR-072": "이행 데이터 건수·고유키·고아관계·버전 대사가 없다",
    "BR-074": "성능·가용성·백업·보안 목표의 측정환경·분모 고정이 없다",
    "BR-075": "운영 매뉴얼·당직·교육·재처리·공급자지원 인계 절차가 없다",
    "BR-076": "개발완료·기술시험완료·운영승인·규제적용확인 상태 분리가 없다",
}

STATUSES = ("반영", "부분", "미반영")


def build_trace() -> list[dict]:
    """레지스터 76건 전부에 상태를 붙인다. TRACE 에 없으면 미반영이고 사유는
    UNASSESSED 에서 따라붙는다. 요건 ID 에 장이 없으므로 area 를 따로 준다."""
    out = []
    for rid, title, sector, priority, n_ac in REQUIREMENTS:
        status, evidence, note = TRACE.get(
            rid, ("미반영", (), UNASSESSED.get(rid, "")))
        out.append({
            "id": rid, "title": title, "sector": sector,
            "priority": priority, "n_ac": n_ac, "area": CHAPTER_OF[rid],
            "status": status,
            "evidence": [{"kind": k, "ref": r} for k, r in evidence],
            "note": note,
        })
    return out


def n_tables_registered() -> int:
    """해설서 엔티티 테이블 가운데 이 하네스 카탈로그에 등재된 장수. 고정값이
    아니라 카탈로그에서 센다."""
    from risk_lib.datamodel import catalog as cat
    names = {sp.name for sp in cat.ALL_TABLES}
    return sum(1 for name, _ in TABLES if name in names)


def coverage() -> dict:
    rows = build_trace()
    by = {s: sum(1 for r in rows if r["status"] == s) for s in STATUSES}
    return {
        "source": SOURCE, "source_sha256": SOURCE_SHA256,
        "sources": [{"role": r, "title": t, "sha256": h} for r, t, h in SOURCES],
        "generator": "tools/gen_ai_risk_requirements.py",
        "tables_label": "해설서 엔티티 테이블",
        "n": len(rows), **by,
        "n_evidence": sum(len(r["evidence"]) for r in rows),
        "chapters": [{"no": no, "title": t} for no, t in CHAPTERS],
        "n_tables": len(TABLES), "n_tables_registered": n_tables_registered(),
    }
