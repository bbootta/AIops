"""기후리스크 업무요건(CLR 72건) 대비 이 하네스 구현의 추적.

req_trace.py 와 같은 계약이다. 증빙 kind 도 같고(module · table · screen ·
test), 실재 검증은 tests/test_req_trace_clr.py 가 한다.

현재 상태를 있는 그대로 적는다. 이 하네스의 기후 모듈은 부문 계수로 ECL 을
올리는 개요 수준(risk_lib.climate)과 NGFS 탄소가격 경로로 CET1 경로를 그리는
자본 통합(risk_lib.stress.climate_capital) 둘뿐이다. 상세설계가 정한 표준
원장 clr_* 36장은 카탈로그에 한 장도 없고, 차주·자산 단위 전이, 공간매핑,
공시, 인터페이스 계약은 없다. 그러므로 '반영'은 0건이고 '부분'만 몇 건이다.
"""

from __future__ import annotations

from risk_lib.regulatory.requirements_clr import (
    CHAPTERS, REQUIREMENTS, SOURCE, SOURCE_SHA256, SOURCES, TABLES,
)

# 상태: 반영 · 부분 · 미반영 (매핑에 없으면 미반영)
# 형식: id → (상태, ((kind, ref), …), note)
TRACE: dict[str, tuple[str, tuple[tuple[str, str], ...], str]] = {
    "CLR-02-01": ("부분", (("table", "gov_approval"),),
                  "4-Eyes 승인 기록 원장은 있으나 기후 업무의 역할별 권한 매트릭스는 없다"),
    "CLR-02-02": ("부분", (("module", "risk_lib.icaap.risk_inventory"),),
                  "ICAAP 리스크 인벤토리가 기후리스크(R-CLM)를 Pillar 2 정량모형으로 "
                  "등재한다. 포트폴리오별 중요/비중요/미평가 구분은 없다"),
    "CLR-06-01": ("부분", (("module", "risk_lib.scenario_library"),),
                  "시나리오 라이브러리에 climate 계열 3종(30년 시계)이 있다. "
                  "승인 상태·버전·출처 등급은 없다"),
    "CLR-07-01": ("부분", (("module", "risk_lib.climate"),),
                  "물리적 위험은 부문별 LGD 상승 계수로만 잡는다. 재해별 손상함수와 "
                  "자산 단위 damage_ratio 는 없다"),
    "CLR-08-01": ("부분", (("module", "risk_lib.stress.climate_capital"),
                          ("module", "risk_lib.climate")),
                  "NGFS 탄소가격 경로가 부문 PD 를 올린다. 차주별 배출량 기반 "
                  "carbon_cost_base/stress/delta 산출은 없다"),
    "CLR-10-01": ("부분", (("module", "risk_lib.climate"),),
                  "시나리오별 ECL 상승분을 낸다. 가중 ECL 과 Stage 판정 사유는 없다"),
    "CLR-10-03": ("부분", (("module", "risk_lib.stress.climate_capital"),),
                  "시나리오별 연도 CET1 비율 경로는 있다. 자본변동표와 거시·산업·직접 "
                  "충격 중복제거는 없다"),
    "CLR-14-01": ("부분", (("module", "risk_lib.validation.independent"),),
                  "3선 독립검증 요청·게이트는 있으나 기후 수치는 재계산 범위"
                  "(RECALC_SCOPE)에 없다"),
    "CLR-16-04": ("부분", (("module", "risk_lib.ops_pages.capital_stress"),),
                  "운영 보고서 50번(기후 자본 경로)이 있다. 감독 제출본과 실무 보고서, "
                  "세 보고서 간 대사는 없다"),
    "CLR-18-01": ("부분", (("screen", "요건 추적"),
                          ("module", "risk_lib.ui_studio.req_trace_clr")),
                  "요건 72건이 레지스터로 들어와 상태·증빙이 화면에 뜬다. "
                  "인수시험(AT) 결과와 보류 목록은 없다"),
}

# 아직 판정하지 않은 요건, id → 사유. 사유는 요건별로 쓴다.
UNASSESSED: dict[str, str] = {
    "CLR-01-01": "실행 목적 코드와 범위 manifest 가 없다. 제외 EAD 를 사유와 함께 남기는 자리도 없다",
    "CLR-01-02": "규범원장(법규·감독요구·국제원칙·정책계획·사례·내부설계 6구분)이 없다",
    "CLR-01-03": "엔진 카탈로그와 SAMPLE_ONLY/PARTIAL 가용성 상태가 없다",
    "CLR-01-04": "실행 프로파일(기본 정책 묶음)을 승인·동결하는 절차가 없다",
    "CLR-02-03": "기후 집중한도 규칙과 사용률·초과 사건 원장(clr_limit_rule·clr_limit_event)이 없다",
    "CLR-02-04": "정책 유효기간과 변경이력 원장(clr_policy)이 없다",
    "CLR-03-01": "실행 상태기계와 승인 게이트의 원자적 전이 이력(clr_run)이 없다",
    "CLR-03-02": "작업 의존성 그래프와 작업별 처리행수·시간 기록(clr_job)이 없다",
    "CLR-03-03": "기후 실행의 불변 manifest 와 재실행 대사가 없다",
    "CLR-03-04": "취소·정정·재제출 상태와 전후 대사가 없다",
    "CLR-04-01": "차주·여신·자산·담보의 canonical 식별자와 참조 무결성 검사가 없다",
    "CLR-04-02": "기준일과 인지시점을 나눈 이력 스냅샷(clr_snapshot)이 없다",
    "CLR-04-03": "원천금액·환산금액·표시단위를 나눠 저장하는 원장이 없다",
    "CLR-04-04": "기후 필드의 필수·조건부·미측정 구분과 미측정 익스포저 집계가 없다",
    "CLR-05-01": "원천 파일 수신·전수 대사·quarantine(clr_source_file)이 없다",
    "CLR-05-02": "좌표 정합성 검사와 위험지도 공간 조인이 없다",
    "CLR-05-03": "대체값 이력과 품질등급별 coverage 가 없다",
    "CLR-05-04": "기후 데이터 품질 게이트(READY/FAILED)와 조건부 승인이 없다",
    "CLR-06-02": "시나리오 변수 변환·보간·범위 검사와 변환로그(clr_scenario_value)가 없다",
    "CLR-06-03": "목적별 시나리오 가중치·확률 검사가 없다",
    "CLR-06-04": "출처 경고와 모델 불확실성에 따른 사용제한·대체경로가 없다",
    "CLR-07-02": "영업중단·복구·공급망 손실(lost_revenue·interruption_margin_loss)이 없다",
    "CLR-07-03": "보험 회수와 적응효과 배분(clr_insurance·clr_adaptation)이 없다",
    "CLR-07-04": "복합·반복재해 중복제거와 집중손실 산출이 없다",
    "CLR-08-02": "에너지·매출·투자 경로의 손익·현금·재무상태 증분이 없다",
    "CLR-08-03": "전환계획 신뢰성 평가와 미이행 사건(clr_transition_plan)이 없다",
    "CLR-08-04": "거시·산업·직접 충격의 gross/overlap/residual 분해가 없다",
    "CLR-09-01": "차주 재무 삼표 스트레스와 상환능력 비율(clr_financial·clr_cashflow)이 없다",
    "CLR-09-02": "차주 단위 조건부 PD 기간구조와 등급 override 가 없다. 부문 계수 상승뿐이다",
    "CLR-09-03": "목적별 LGD 와 담보 recovery waterfall 이 없다",
    "CLR-09-04": "기후 시나리오 하의 EAD·한도인출 추정이 없다",
    "CLR-10-02": "기후 충격 후 규제 RWA 엔진 재호출과 floor 영향 표시가 없다",
    "CLR-10-04": "기후 시나리오의 NII/EVE·시장손익·LCR/NSFR·운영손실 연계가 없다",
    "CLR-11-01": "Top-down·Bottom-up 차이 bridge 와 미설명 잔차가 없다",
    "CLR-11-02": "정적·동적 대차대조표 전환과 관리조치 전후 비교가 없다",
    "CLR-11-03": "기후 임계충격 탐색과 역위기상황분석이 없다",
    "CLR-11-04": "공식 시나리오 수령과 제출파일·접수증 관리가 없다",
    "CLR-12-01": "여신심사 기후 검토의견·조건·근거 기록이 없다",
    "CLR-12-02": "기후 약정 이행원장과 기한경과 사건이 없다",
    "CLR-12-03": "기후 조기경보 규칙과 재평가 배정·종결 증빙이 없다",
    "CLR-12-04": "use-test 증빙과 미이행 항목 목록이 없다",
    "CLR-13-01": "공시 적용대상 판정과 기준버전·공시 캘린더가 없다",
    "CLR-13-02": "금융배출량(financed_emissions) 산정과 coverage(clr_emission)가 없다",
    "CLR-13-03": "공시 사실값의 근거 추적과 증빙묶음(clr_disclosure)이 없다",
    "CLR-13-04": "회계와 공시의 미래재무영향 차이 설명표가 없다",
    "CLR-14-02": "기후 사건 귀속 백테스트와 표본 한계 보고가 없다",
    "CLR-14-03": "기후 모형 성능·안정성 표와 챌린저 대체결과가 없다",
    "CLR-14-04": "기후 검증의견 발급과 조치 종결 로그(clr_finding)가 없다",
    "CLR-15-01": "수신 파일·엔진 계약 검증과 행별 오류 반환이 없다",
    "CLR-15-02": "멱등 run_id 와 재전송 응답 규약(clr_api_request)이 없다",
    "CLR-15-03": "오류·재시도·시간초과의 공통 envelope 이 없다",
    "CLR-15-04": "내보내기 파일의 셀 대사와 receipt(clr_export)가 없다",
    "CLR-16-01": "기후 작업함·실행·취소 화면이 없다",
    "CLR-16-02": "차주 진단·위험지도·원천 계보 화면이 없다",
    "CLR-16-03": "기후 검증·승인/반려 화면(clr_object_approval)이 없다",
    "CLR-17-01": "기후 데이터의 접근결정·마스킹·외부 서비스 감사 이벤트가 없다",
    "CLR-17-02": "처리량·지연·자원·실패율의 비기능 기준과 측정이 없다",
    "CLR-17-03": "장애 복구대사·훈련증빙·장애보고 절차가 없다",
    "CLR-17-04": "불변 증빙·파기·접근로그 보존(clr_audit_event)이 없다",
    "CLR-18-02": "공통 합성자료 세트와 독립 재계산 차이 로그가 없다",
    "CLR-18-03": "단계별 출구조건·전환 승인·되돌림 계획이 없다",
    "CLR-18-04": "운영 전 확정 결정(DEC-01~20) 목록과 확정 설정 기록이 없다",
}

STATUSES = ("반영", "부분", "미반영")


def build_trace() -> list[dict]:
    """레지스터 72건 전부에 상태를 붙인다. TRACE 에 없으면 미반영이고 사유는
    UNASSESSED 에서 따라붙는다."""
    out = []
    for rid, title, sector, priority, n_ac in REQUIREMENTS:
        status, evidence, note = TRACE.get(
            rid, ("미반영", (), UNASSESSED.get(rid, "")))
        out.append({
            "id": rid, "title": title, "sector": sector,
            "priority": priority, "n_ac": n_ac,
            "status": status,
            "evidence": [{"kind": k, "ref": r} for k, r in evidence],
            "note": note,
        })
    return out


def coverage() -> dict:
    rows = build_trace()
    by = {s: sum(1 for r in rows if r["status"] == s) for s in STATUSES}
    return {
        "source": SOURCE, "source_sha256": SOURCE_SHA256,
        "sources": [{"role": r, "title": t, "sha256": h} for r, t, h in SOURCES],
        "n": len(rows), **by,
        "n_evidence": sum(len(r["evidence"]) for r in rows),
        "chapters": [{"no": no, "title": t} for no, t in CHAPTERS],
        "n_tables": len(TABLES), "n_tables_registered": n_tables_registered(),
    }


def n_tables_registered() -> int:
    """상세설계 표준 원장 clr_* 가운데 이 하네스 카탈로그에 등재된 장수.
    화면이 이 수를 보여 주므로 고정값이 아니라 카탈로그에서 센다."""
    from risk_lib.datamodel import catalog as cat
    names = {sp.name for sp in cat.ALL_TABLES}
    return sum(1 for name, _ in TABLES if name in names)
