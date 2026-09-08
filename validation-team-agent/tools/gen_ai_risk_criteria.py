"""AI 리스크관리 업무요건 → 적합성검증 기준 항목 생성기.

근거 원문은 `AI 리스크관리 업무요건 문서 세트`(v1.0 · 2026-09-08: 개요, 실무진
해설서, 구조화 요건 원장 requirements.json, 문서 manifest) 이며 `harness/reference/`
에 지문과 함께 보관한다. 요건 76건(BR-NNN)·인수조건·챕터·근거원장(G·K·CASE)은
원문에서 **파싱**한다. 검증 기준 문장·자동화 상태·근거 파일만 이 파일이 정한다.

근거(evidence)는 하니스에 실재하는 파일만 선언한다. `automated` 는 일반 통제가
그 요건에도 적용된다는 뜻이며, 덮는 범위는 note 에 적는다
(tools.ai_risk_criteria verify 가 강제).

사용:
    python -m tools.gen_ai_risk_criteria --out harness/ai_risk_requirement_criteria.json
"""

from __future__ import annotations

import argparse
import hashlib
import html as _html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SOURCES = {
    "register": {
        "title": "AI 리스크관리 업무요건 구조화 원장 (requirements.json)",
        "path": "harness/reference/ai_risk_requirements_20260908.json",
        "version": "1.0", "date": "2026-09-08",
        "role": "요건 76건·샘플 인수조건·책임·인수시험 ID 의 정본",
    },
    "manual": {
        "title": "AI 리스크관리 실무진 해설서 · v1.0",
        "path": "harness/reference/ai_risk_practitioner_manual_20260908.html",
        "version": "1.0", "date": "2026-09-08",
        "role": "23개 챕터·근거원장(G·K·CASE)·필드사전·API 계약의 원문",
    },
    "overview": {
        "title": "AI 리스크관리 업무요건정의서 · 개요 · v1.0",
        "path": "harness/reference/ai_risk_requirements_overview_20260908.html",
        "version": "1.0", "date": "2026-09-08",
        "role": "경영진·승인자용 개요",
    },
    "manifest": {
        "title": "문서 manifest (document_manifest.json)",
        "path": "harness/reference/ai_risk_document_manifest_20260908.json",
        "version": "1.0", "date": "2026-09-08",
        "role": "문서 세트 자체의 지문·검증 상태 (browser_visual_review·database_runtime 등 NOT_RUN 포함)",
    },
}

SECTIONS = {
    "01": "RDM·BIS비율", "02": "신용리스크·RWA", "03": "IFRS 9 ECL", "04": "시장리스크",
    "05": "ALM·IRRBB·유동성", "06": "운영리스크", "07": "통합위기상황분석",
    "08": "리스크 적합성검증", "09": "기후리스크", "10": "AI리스크",
}
LENSES = ("데이터", "산식", "방법론", "내부통제", "문서화")

# 챕터 → 닿는 기존 부문
RELATED = {
    "01": ("08",), "03": ("08",), "04": ("08",), "05": ("01",), "06": ("02",),
    "07": ("08",), "08": ("08",), "09": ("08",), "10": ("08",), "11": ("08",),
    "12": ("08",), "13": ("06",), "14": ("06",), "15": ("08",), "16": ("07", "01", "02"),
    "17": ("08",), "19": ("08",),
}

# 국내 구속 근거만 binding. 가이드라인·안내서·제재 사례·컨퍼런스는 아니다.
BINDING_NORMS = {"K02": "인공지능기본법", "K03": "인공지능기본법 시행령",
                 "K04": "개인정보 보호법", "K05": "신용정보법"}

AUTOMATION = {
    "automated": "하니스에 실행 가능한 통제가 존재하고 근거 파일이 실재함 (evidence 1건 이상 필수). 덮는 범위는 note 에 적는다",
    "manual": "하니스에 통제가 없어 사람 검토로 남김 (note 필수, evidence 0건)",
    "out_of_scope": "시스템 구현·인프라·인수시험 영역이라 산출값 적합성검증 범위 밖 (note 필수, evidence 0건)",
}

_MANIFEST = ("harness/change_manifest.json", "tools/manifest.py")
_SOD = ("middleware/sod_guard.py", "harness/sod_policy.json")
_PERM = ("middleware/permission_guard.py", "harness/permission_matrix.json")

# req_id → (관점, 검증 기준, 자동화, 근거, 비고)
CRITERIA: dict[str, tuple] = {
    "BR-001": (("내부통제", "데이터"), "모든 AI 업무가 system_id 와 업무오너를 갖고 미등록 호출은 발견 원장에 기록된 뒤 운영 연결이 거부되는가",
        "automated", ("harness/model_materiality.json", "tools/validation_scope.py"),
        "하니스는 모형을 중요도 등급과 함께 등록하고 등급별 최소 심도를 강제한다. 미등록 호출의 발견·거부는 은행 게이트"),
    "BR-002": (("데이터", "내부통제"), "결정론 계산·AI 설명·사람의 판단·외부 실행이 별도 유형으로 기록되고 AI 가 만든 숫자는 승인된 계산결과 참조(calculation_id) 없이는 공식 수치로 승격되지 않는가",
        "automated", ("tools/provenance.py", "tools/independent_recalc.py"),
        "산출 근거 분류(실측·파생·서술)와 독립 재계산이 수치의 출처를 요구한다. 생성문 안의 숫자 탐지는 사람"),
    "BR-003": (("문서화", "내부통제"), "제안 값에 POLICY_PROPOSAL 표시가 있고 법규·내규·계약·시험값의 출처 유형과 효력시점이 분리 저장되며 충돌 시 더 넓은 권한이 부여되지 않는가",
        "automated", ("harness/regulatory_rule_catalog.json", "tools/reg_rules.py", "harness/pd_design_thresholds.json"),
        "규제 원장이 근거수준·유효일자를 분리하고 임계 파일 notes 가 내부 판정값을 규제 인용과 구분한다"),
    "BR-004": (("내부통제",), "사용범위 확대·외부 실행 추가·중요 데이터 추가가 변경평가를 다시 시작하고 이름 변경만으로 중복 등록되지 않는가",
        "automated", _MANIFEST, "변경은 매니페스트에 영향·검증·롤백과 함께 남는다. 재평가 범위 판정은 사람"),
    "BR-005": (("내부통제",), "서비스별 책임자·기술운영자·독립검증자·준법·최종 승인자가 지정되고 겸직 충돌이 시스템에서 검사되는가",
        "automated", _SOD, ""),
    "BR-006": (("내부통제", "문서화"), "법적 적용성이 KR 고영향·EU 고위험·개인정보 자동화결정·신용정보 자동화평가·내부 위험등급으로 각각 판단되고 UNKNOWN 이 NO 로 읽히지 않는가",
        "manual", (), "법령 적용성 판정은 준법 확인 사항. 하니스는 법률 유권해석을 하지 않는다 (CLAUDE.md §2)"),
    "BR-007": (("내부통제",), "예외가 허용된 통제항목에만 사유·보완통제·범위·만료·재검토와 함께 기록되고 법령 금지·승인자 분리·무권한 실행은 예외 불가인가",
        "automated", ("tools/conditional_approval.py",), "조건부 승인이 잔여위험·후속조건·이행기한·배포 범위를 요구한다. 예외 불가 항목 목록은 은행 정책"),
    "BR-008": (("내부통제",), "신규·정기·중요변경·사고 후 재평가가 예약되고 만료 평가·미지정 오너·퇴사 승인자가 재배포를 차단하는가",
        "automated", ("tools/validation_trigger.py", "harness/validation_triggers.json", "tools/validation_scope.py"),
        "트리거·주기 강제가 있다. 인사 연계(퇴사 승인자)는 은행 시스템"),
    "BR-009": (("데이터", "문서화"), "등록 필수값(목적·고객영향·법인·오너·모델버전·데이터등급·도구·실행권한·배포환경·종료계획)이 누락되면 제출이 불가한가",
        "manual", (), "하니스에 AI 자산명세 원장이 없다"),
    "BR-010": (("방법론",), "내부 등급이 5개 요소의 최대값(1~4)이고 금지행위는 점수와 무관하게 REJECTED 이며 법적 분류와 별도 저장되는가",
        "manual", (), "하니스 중요도 등급은 모형 단위 점수이며 AI 시스템 5요소 최대값 규칙·금지행위 목록이 아니다"),
    "BR-011": (("방법론", "데이터"), "미확인 데이터·권한·공급자는 해당 요소가 4 로 잠정 설정되어 검토 전 운영이 금지되고 통제 적용 후에도 고유위험 등급이 보존되는가",
        "manual", (), "미확인을 최고 등급으로 두는 규칙은 은행 등급 체계의 것"),
    "BR-012": (("내부통제",), "승인된 위험평가의 버전·증빙·정책 변경이 재평가를 트리거하고 미등록 자식 에이전트·도구는 실행되지 않는가",
        "automated", ("tools/golden_regression.py", "tools/validation_trigger.py"),
        "범위 밖 변경은 회귀검증이 배포를 차단하고 트리거가 재검증을 연다. 자식 에이전트 등록은 은행 플랫폼"),
    "BR-013": (("데이터", "내부통제"), "원천별 수집근거·이용목적·보유기간·개인정보/신용정보 분류·국외이전이 등록되고 목적 외 재학습이 적법근거·목적 적합성·승인 없이는 금지되는가",
        "manual", (), "적법성 판단은 개인정보·준법 확인 사항. 내부승인이 적법근거를 대체하지 않는다"),
    "BR-014": (("데이터",), "수집마다 건수·고유키·기준일·단위·결측·이상치·중복·참조정합성이 검사되고 실패 자료가 인덱스·모형에 투입되지 않는가",
        "automated", ("middleware/schema_guard.py", "tools/data_adapter.py", "tools/data_profile.py"),
        "스키마·결측·중복 프로파일이 있다. 참조정합성(외래키)은 사람"),
    "BR-015": (("내부통제",), "사용자 권한으로 검색 전에 문서·행 접근이 제한되고 인용 링크·벡터 인덱스·캐시·내보내기에도 같은 통제가 적용되는가",
        "manual", (), "하니스에 검색증강생성 경로가 없다"),
    "BR-016": (("데이터", "내부통제"), "정정·삭제·동의철회 시 원본·파생문서·임베딩·캐시·로그가 원문별로 추적 처리되고 법정보관은 근거와 접근제한을 남기는가",
        "manual", (), "하니스에 파생자료 삭제 추적이 없다"),
    "BR-017": (("데이터",), "모든 변환 결과가 부모 출처와 신뢰·기밀 레이블을 보존하고 비신뢰 자료의 요약이 자동으로 신뢰자료가 되지 않는가",
        "automated", ("tools/provenance.py", "middleware/run_logger.py"),
        "산출 근거 계보와 실행 로그가 출처를 잇는다. 신뢰·기밀 레이블 필드는 없다"),
    "BR-018": (("문서화", "내부통제"), "만료·미승인 규정이 공식 근거로 쓰이지 않고 문서 충돌 시 최신이라는 이유만으로 자동 선택되지 않으며 효력기간·적용조직이 대조되는가",
        "automated", ("harness/regulatory_rule_catalog.json", "tools/reg_rules.py", "harness/regulatory_criteria.json"),
        "규제 원장이 RETIRED 규칙을 차단하고 유효일자를 분리하며 근거 원문은 지문으로 고정된다"),
    "BR-019": (("데이터",), "보안 맥락의 자산·계정·접근관계에 source_at·expires_at 이 있고 기한 초과 관계가 중요 조치의 단독 근거로 쓰이지 않는가",
        "manual", (), "하니스에 보안 맥락 원장이 없다"),
    "BR-020": (("내부통제", "데이터"), "텍스트·이미지·음성·첨부가 외부 전송 전에 민감정보·목적지 정책 검사를 거치고 검사불가·시간초과 시 반출이 보류되는가",
        "automated", ("middleware/data_safety_guard.py", "tools/data_adapter.py"),
        "민감정보 가드가 텍스트 PII 를 차단한다. 이미지·음성 채널 검사와 목적지 정책은 없다"),
    "BR-021": (("문서화", "방법론"), "모델카드에 개발목적·모집단·표본기간·부도 정의·변수변환·제외기준·분할·계수·한계·사용제한이 등록되는가",
        "automated", ("harness/policies/credit_scoring.md", "harness/policies/pd_lgd_ead.md", "tools/model_notes.py"),
        "검증 정책이 모델 문서 요건을 정하고 모형별 노트 원장이 있다. 모델카드 서식 자체는 은행"),
    "BR-022": (("방법론", "데이터"), "시간외·표본외 검증과 자료누출 검사가 수행되고 검증기간 후에 알려진 정보가 변수에 들어가면 개발이 재수행되는가",
        "automated", ("middleware/leakage_guard.py", "tools/run_validation.py"), ""),
    "BR-023": (("방법론", "산식"), "변별력·보정·안정성·공정성·보수성·민감도·백테스트가 분리 점검되고 벤치마크·경제적 해석이 기록되며 비선형 모형에 계수 유의성이 억지 적용되지 않는가",
        "automated", ("tools/metric_ks_auc.py", "tools/binomial_calibration.py", "tools/metric_psi.py", "tools/pd_cyclicality.py"),
        "변별·보정·안정성·경기 민감도 도구가 있다. 공정성 지표는 없다 (BR-028 참조)"),
    "BR-024": (("산식", "내부통제"), "승인된 모델·파라미터·피처 버전과 운영 산출이 대사되고 수작업 조정이 사유·이전값·변경값·전결자와 함께 기록되는가",
        "automated", ("tools/independent_recalc.py", "tools/pack_verify.py"),
        "독립 재계산과 팩 재현성 검증이 운영 산출을 대사한다. 수작업 조정 원장은 없다 (도메인 요건 DAT-006 수동)"),
    "BR-025": (("방법론", "데이터"), "생성형 시험셋 버전이 고정되고 정상·공격·경계·부정확 질문이 분리되며 시험별 정답·허용·금지 행동·근거가 사전 지정되는가",
        "manual", (), "하니스 Golden Case 는 수치 산출 회귀용이며 생성형 시험셋이 없다"),
    "BR-026": (("데이터", "문서화"), "평가 실행마다 모델·프롬프트·검색집합·도구·정책·샘플링·반복번호·판정자가 기록되고 비결정성은 실행환경 재현과 결과분포 재평가로 구분되는가",
        "manual", (), "하니스는 LLM 을 호출하지 않는다. 자기 실행 로그는 있으나 프롬프트·샘플링 기록 대상이 없다"),
    "BR-027": (("방법론",), "모델 판정자가 사람 라벨과의 일치도로 검증되고 불일치·중대피해 사례는 사람이 판정하며 같은 모델의 자기검증만으로 PASS 되지 않는가",
        "manual", (), "LLM 판정자 일치도 검증 경로가 없다. 자기검증 불인정 원칙은 2선·3선 분리(CLAUDE.md §6)와 같다"),
    "BR-028": (("방법론",), "집단별 정확성·거절·불이익·오차단과 불확실성이 보고되고 민감속성은 적법근거·필요성·권한 없이 수집되지 않는가",
        "manual", (), "하니스에 공정성 지표가 없다"),
    "BR-029": (("내부통제",), "사용자 지시·외부문서·도구응답·메모리·멀티모달의 신뢰경계가 위협모델에 표시되고 시스템 권한변경이 모델 출력만으로 불가한가",
        "automated", _PERM, "권한은 정책 파일이 정하고 산출로 바뀌지 않는다. 위협모델 문서는 사람"),
    "BR-030": (("방법론",), "직접·간접·저장형·다중회차·다중에이전트·도구 설명 오염·멀티모달 공격 경로가 시험되고 공격성공 정의가 실제 금지효과·정책우회인가",
        "manual", (), "하니스에 프롬프트 주입 시험 경로가 없다. 적대적 검증(ADV 25)은 산출값 반증용이다"),
    "BR-031": (("방법론",), "계좌·수취인·금액·통화·매수/매도·상품·처리순서·승인상태 변경이 별도 중대 시험항목인가",
        "manual", (), "금융 무결성 시험은 거래 시스템의 것"),
    "BR-032": (("내부통제",), "중대취약점이 재현·영향·통제·담당·기한·재시험과 연결되고 재시험 미완료 티켓은 종결되지 않는가",
        "automated", ("tools/validation_finding.py",), "Finding 원장이 재검증 없는 종결을 차단한다"),
    "BR-033": (("내부통제",), "사용자·서비스·에이전트·자식의 신원이 분리되고 위임 원천·최대권한이 기록되며 자식이 부모보다 권한·수명·예산을 확대하지 못하는가",
        "automated", _PERM, "권한 매트릭스가 역할별 허용 작업을 고정한다. 에이전트 위임체인 기록은 은행 플랫폼"),
    "BR-034": (("내부통제", "데이터"), "중요행위가 대상·금액·버전·정책·데이터등급·유효기간의 승인 지문에 묶이고 실행 직전 다시 비교되는가",
        "automated", ("tools/ivr_response.py", "tools/pack_verify.py"),
        "독립검증 응답은 요청 지문(request_id)과 일치해야 하고 팩은 입력·정책·코드 지문으로 재검증된다"),
    "BR-035": (("내부통제",), "승인이 명시적 행위로만 생성되고 무응답·모델의 '승인됨' 문장·읽음·자동 시작은 승인이 아니며 자기승인·재사용이 금지되는가",
        "automated", ("middleware/sod_guard.py", "tools/conditional_approval.py"),
        "직무분리와 인간 결재 기록 필수(조건부 승인)가 있다. 게이트는 fail-closed 로 무응답을 승인으로 보지 않는다"),
    "BR-036": (("내부통제",), "실행 전에 버전·역할·정책·자격증명 회수·중단상태가 원자적으로 검사되고 승인 후 권한 회수·인수 변경이면 거부되는가",
        "manual", (), "집행게이트는 은행 플랫폼의 것"),
    "BR-037": (("내부통제",), "정책 판정이 ALLOW/BLOCK/DEFER 와 의무 목록으로 분리되고 금지 우선·미확인 보류·의무 합집합·마스킹→재평가→승인→집행 순서가 지켜지는가",
        "automated", ("middleware/permission_guard.py", "middleware/data_safety_guard.py"),
        "가드는 위반 시 차단(fail-closed)한다. 의무 합집합·순서 규칙은 은행 정책 엔진"),
    "BR-038": (("내부통제", "데이터"), "비신뢰 원문이 제어영역에 재주입되지 않고 필요한 값만 명시된 반출규칙으로 타입·출처·목적 검증을 거쳐 전달되는가",
        "manual", (), "하니스에 정보흐름 경계 시험이 없다"),
    "BR-039": (("내부통제",), "도구 네트워크가 프록시·집행게이트를 통과하고 직접 외부연결·임의 코드실행·미등록 플러그인이 차단되는가",
        "out_of_scope", (), "인프라 구성: 산출값 검증 대상이 아니다"),
    "BR-040": (("내부통제",), "정책·민감정보 검사 장애 시 거래·반출·쓰기가 보류·차단되고 승인된 읽기전용 축소모드만 허용되며 로그 누락 상태로 중요 실행이 금지되는가",
        "manual", (), "하니스 가드는 위반 시 차단하나 가드 자체 장애 시의 축소모드 정책은 없다"),
    "BR-041": (("내부통제",), "등록→평가→검증→승인→배포→운영→폐기 상태전이가 정해진 역할·산출물을 요구하고 반려는 새 버전으로 재제출되는가",
        "automated", ("tools/validation_finding.py", "harness/change_manifest.json"),
        "Finding 계보와 매니페스트 상태(proposed·applied·validated·rolled_back)가 있다. AI 시스템 생애주기 상태기계는 은행"),
    "BR-042": (("내부통제", "데이터"), "모델·정책·프롬프트·검색·도구·설정 지문이 배포번들과 일치하고 공급자 별칭이 아닌 실제 버전이 확인되는가",
        "automated", ("tools/pack_verify.py", "tools/golden_regression.py"), ""),
    "BR-043": (("내부통제", "문서화"), "변경영향평가가 보안·성능·공정성·데이터·비용·지연·복구를 포함하고 긴급 변경도 최소 시험·기한부 승인·사후 독립검토를 남기는가",
        "automated", _MANIFEST, "매니페스트가 예상 회귀 위험·검증 방법·롤백 기준을 요구한다"),
    "BR-044": (("내부통제",), "단계적 배포가 관측→제한범위→확대 순서이고 회귀 실패·중대사건 시 검증된 이전버전이나 수동업무로 복구되는가",
        "automated", ("tools/conditional_approval.py", "harness/change_manifest.json"),
        "제한 배포 범위와 롤백 기준이 기록된다. 실제 배포 파이프라인은 은행"),
    "BR-045": (("문서화", "산식"), "지표마다 분자·분모·모집단·기간·시간대·제외규칙·소유자·임계값 버전이 등록되고 원자료로 재계산 가능한가",
        "automated", ("harness/metric_policy.md", "tools/policy_lint.py", "harness/report_glossary.json"), ""),
    "BR-046": (("내부통제", "방법론"), "중대 실행위반·승인불일치·대량반출·중단실패는 1건도 경보하고 통계 지표는 최소표본·지속조건·변동성·정상시간대를 갖는가",
        "automated", ("tools/validation_trigger.py", "harness/validation_triggers.json", "middleware/sample_size_guard.py"),
        "트리거 임계와 표본 하한이 있다. 실행위반 경보는 은행 게이트"),
    "BR-047": (("내부통제",), "동일 사건 경보가 원본을 보존한 채 묶이고 업무영향·노출·복구난이도로 우선순위가 정해지며 담당자 부재 시 대체자에게 배정되는가",
        "manual", (), "경보 운영은 은행 운영 절차"),
    "BR-048": (("데이터",), "데이터 누락·시계오차·표본부족이면 DATA_GAP 또는 NOT_EVALUATED 로 표시되고 수집지연이 탐지되어 품질상태가 수치와 함께 보고되는가",
        "automated", ("middleware/sample_size_guard.py", "middleware/schema_guard.py"),
        "표본 부족은 판정 보류로, 스키마 결함은 차단으로 처리된다. 수집지연 탐지는 없다"),
    "BR-049": (("내부통제", "문서화"), "사고가 데이터유출·권한위반·모형오류·공정성·가용성·공급망·증빙손상으로 분류되고 영향·탐지시각·범위·잠정손실·보고의무 검토가 기록되는가",
        "automated", ("tools/classify_error.py", "tools/validation_finding.py"),
        "실패 원인 6분류와 Finding 원장이 있다. 사고 분류 7종·보고의무는 은행 사고 원장"),
    "BR-050": (("내부통제",), "중단 명령이 서비스·테넌트·에이전트·도구·키 단위로 전파되고 회수 세대번호를 실행게이트가 검사하는가",
        "manual", (), "Kill switch 는 은행 플랫폼의 것"),
    "BR-051": (("내부통제",), "외부효과 불명이 UNKNOWN 으로 보존되고 자동 재시도가 금지되며 대사·수동판정 후 해소되고 보정행위도 새 승인 대상인가",
        "manual", (), "외부 실행 대사는 은행 시스템"),
    "BR-052": (("내부통제",), "복구가 원인제거·무결성검사·회귀시험·재개 승인·사용자 안내·재발방지를 요구하고 중단권한과 재개승인이 분리되는가",
        "manual", (), "복구 훈련은 은행 운영"),
    "BR-053": (("문서화", "내부통제"), "공급자별 서비스·모델·리전·하위처리자·학습이용·보관·삭제·감사권·사고통지 조건이 계약버전으로 등록되고 불명이 허용으로 간주되지 않는가",
        "manual", (), "공급자 계약 원장은 구매·법무"),
    "BR-054": (("데이터", "내부통제"), "데이터 유입→외부연결→추론→저장→로그→백업→지원자 접근이 경로별로 심사되고 처리변경이 재승인을 트리거하는가",
        "manual", (), "데이터 흐름 심사는 개인정보·설계 부서"),
    "BR-055": (("방법론",), "공급자 장애·가격·모델종료·정책변경·공통모델 실패 시나리오가 검증되고 대체 공급자도 사전 검증·승인 범위만 사용되는가",
        "manual", (), "집중위험 탈출 훈련은 은행 운영"),
    "BR-056": (("문서화", "내부통제"), "기능·안전성·인증·성능 주장이 출처·시험조건·승인범위·유효기한을 가진 주장원장으로 관리되고 영업자료에도 적용되는가",
        "automated", ("tools/val_coverage.py", "tools/domain_criteria.py"),
        "하니스는 자동 통제라는 주장에 근거 파일 실재를 요구한다. 영업자료 주장은 준법"),
    "BR-057": (("문서화", "내부통제"), "AI 활용 사전고지와 생성 결과물 표시가 별도 필드·시험으로 관리되고 중요결정 설명·출처·사람 연결·이의신청이 채널별로 제공되는가",
        "automated", ("middleware/draft_watermark_guard.py", "tools/report_pdf.py"),
        "생성 초안은 DRAFT 워터마크가 강제된다. 고객 고지·이의신청 채널은 은행"),
    "BR-058": (("데이터", "문서화"), "결정 당시 데이터·모델·규칙·주요요인·사람 관여가 고정되고 설명자료가 당시 결과와 일치하는가",
        "automated", ("tools/pack_verify.py", "middleware/run_logger.py", "tools/explainability.py"), ""),
    "BR-059": (("내부통제",), "이의제기 접수→신원확인→적용성판단→설명/정정/재평가→인적검토→통지→종결이 기록되고 개인정보법상 30일 기한이 재기산 없이 관리되는가",
        "manual", (), "고객 요청 처리 기한은 소비자보호·준법 관리 사항"),
    "BR-060": (("내부통제",), "인적 재검토가 수정 권한을 가진 담당자에 의해 수행되고 원판정을 무조건 추인하지 않으며 이의신청에 따른 불이익이 없는가",
        "manual", (), "인적 재검토는 은행 전결자"),
    "BR-061": (("산식", "데이터"), "계산에 기준일·시나리오·포트폴리오·통화·단위·파라미터·엔진버전·입력해시가 고정되고 동일입력 재산출이 대사되는가",
        "automated", ("tools/pack_verify.py", "tools/independent_recalc.py", "tools/golden_regression.py"), ""),
    "BR-062": (("산식",), "PD/LGD/EAD→손실→손익→자본→비율과 RWA 변화가 추적되고 템플릿별 합계·부호·반올림·버전이 대사되는가",
        "automated", ("tools/independent_recalc.py", "tools/climate_recalc.py", "src/vta/domains/capital.py"),
        "합계형·비율형 재계산과 기후 사례 전이 재계산이 있다. 서식별 부호 규약 대조는 요청서 대상별"),
    "BR-063": (("문서화",), "여신감리 초안이 차주·여신구조·담보·상환재원·현금흐름·산업·등급·한도·조기경보·충당금·위반·승인조건을 근거와 연결하는가",
        "manual", (), "여신감리는 은행 업무"),
    "BR-064": (("내부통제", "문서화"), "감독 제출·결재 산출물이 원장 스냅샷·수치대사·검증의견·승인·제출본 지문으로 묶이고 생성 초안은 DRAFT 표기되며 승인 전 자동 제출되지 않는가",
        "automated", ("tools/ivr_response.py", "tools/pack_verify.py", "middleware/draft_watermark_guard.py"),
        "대외 제출은 인간 권한 (CLAUDE.md §5)"),
    "BR-065": (("데이터", "내부통제"), "system_id·version_id·run_id·action_id·decision_id·approval_id·event_id 가 입력출처부터 외부효과까지 연결되고 핵심 링크 누락은 미완료 처리되는가",
        "automated", ("middleware/run_logger.py", "tools/run_audit.py", "tools/ivr_response.py"),
        "실행 로그·plan 대 실행 감사·요청/응답 ID 대조가 있다"),
    "BR-066": (("데이터", "내부통제"), "증빙이 추가기록 방식으로 서버시각·원천시각·행위자·전후값·사유·지문·서명을 갖고 지문만으로 진정성이 증명되지 않음이 인식되는가",
        "automated", ("harness/change_manifest.json", "middleware/run_logger.py", "tools/audit_retention.py"), ""),
    "BR-067": (("문서화", "내부통제"), "보관기간이 증빙유형·법적근거·목적·기산점·소송보존·삭제방법으로 설정되고 고영향 책무 문서의 법정 5년과 AI 원문로그 보관이 혼동되지 않는가",
        "automated", ("tools/audit_retention.py", "tools/feedback_retention.py"),
        "감사 로그·학습 시그널 보존 도구가 있다. 유형별 법적 기간은 준법"),
    "BR-068": (("문서화", "내부통제"), "보고서 생성이 기준시점 스냅샷·출처를 고정하고 마스킹·승인·내보내기 권한을 적용하며 재다운로드가 동일 버전인가",
        "automated", ("tools/pack_archive.py", "tools/report_pack.py", "middleware/permission_guard.py"), ""),
    "BR-069": (("내부통제",), "UI-01~12 의 필수필드·역할·상태검사가 서버와 화면에서 동일 적용되는가",
        "out_of_scope", (), "화면 구현 계약: 인수시험 영역"),
    "BR-070": (("데이터",), "데이터형·키·열거값·외래키·보관·테넌트격리 계약이 준수되는가",
        "out_of_scope", (), "스키마 구현 계약: 인수시험 영역"),
    "BR-071": (("내부통제",), "동시요청·재전송·순서역전·외부결과불명·회수경합이 처리되는가",
        "out_of_scope", (), "동시성 구현 계약: 인수시험 영역"),
    "BR-072": (("데이터",), "이행 데이터의 건수·고유키·필수값·승인근거·고아관계·버전이 대사되는가",
        "manual", (), "이행 대사는 구축 시점의 일"),
    "BR-073": (("방법론",), "핵심 시나리오 전건과 부정·경계·장애·권한·복구 시험이 수행되는가",
        "automated", ("harness/golden_cases.json", "harness/adversarial_protocol.json", "tools/golden_regression.py"),
        "하니스 자체의 Golden Case·적대적 프로토콜이 있다. 은행 시스템 시험은 구축 시"),
    "BR-074": (("내부통제",), "성능·가용성·백업·보안목표가 측정환경·시간·분모·제외조건과 함께 고정되는가",
        "out_of_scope", (), "비기능 요건: 인수시험 영역"),
    "BR-075": (("문서화",), "운영 매뉴얼·당직·교육·재처리·모니터링·고객전환·공급자지원·감사추적이 인계되는가",
        "manual", (), "운영 인계는 프로젝트 관리 사항"),
    "BR-076": (("내부통제",), "개발완료·기술시험완료·은행운영승인·규제적용확인이 별도 상태로 관리되는가",
        "automated", ("harness/change_manifest.json", "tools/conditional_approval.py"),
        "매니페스트 상태와 인간 승인 필수 플래그가 있다. 규제적용확인은 준법"),
}


def source_path(key: str) -> Path:
    return ROOT / SOURCES[key]["path"]


def _clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", "", s)
    return _html.unescape(re.sub(r"\s+", " ", s)).strip()


def parse_register(raw: str) -> list[dict]:
    rows = json.loads(raw)
    out = []
    for r in rows:
        out.append({
            "req_id": r["requirement_id"], "priority": r["priority"],
            "chapter": r["chapter"][:2], "chapter_title": r["chapter"],
            "rule": r["rule"], "sample_acceptance": r["sample_acceptance"],
            "owner_evidence": r["owner_evidence"], "test_id": r["test_id"],
        })
    return out


def parse_chapters(raw: str) -> dict[str, str]:
    return {m.group(1): _clean(m.group(2))
            for m in re.finditer(r'<section class="chapter" id="ch-(\d\d)"[^>]*>.*?<h2>(.*?)</h2>', raw, flags=re.S)}


def parse_norms(raw: str) -> list[dict]:
    out = []
    for m in re.finditer(r'<article class="source-card" id="source-([^"]+)">(.*?)</article>', raw, flags=re.S):
        sid, b = m.group(1), m.group(2)
        tag = _clean((re.search(r'<div class="tag">(.*?)</div>', b, flags=re.S) or [None, ""])[1])
        title = _clean((re.search(r"<h3>(.*?)</h3>", b, flags=re.S) or [None, ""])[1])
        url = (re.search(r'href="([^"]+)"', b) or [None, ""])[1]
        facts = _clean((re.search(r"확인한 사실:</b>(.*?)</p>", b, flags=re.S) or [None, ""])[1])
        nature = _clean((re.search(r"성격·적용성:</b>(.*?)</p>", b, flags=re.S) or [None, ""])[1])
        out.append({"source_id": sid, "tag": tag, "title": title, "url": _html.unescape(url),
                    "facts": facts, "applicability": nature, "binding": sid in BINDING_NORMS})
    return out


def build() -> dict:
    raw = {k: source_path(k).read_text(encoding="utf-8") for k in SOURCES}
    digests = {k: hashlib.sha256(source_path(k).read_bytes()).hexdigest() for k in SOURCES}
    manifest = json.loads(raw["manifest"])
    # 문서 세트 manifest 의 지문과 보관본이 같아야 한다.
    by_name = {f["file"]: f["sha256"] for f in manifest["files"]}
    for key, name in (("manual", "AI_Risk_Practitioner_Manual.html"),
                      ("overview", "AI_Risk_Requirements_Overview.html"),
                      ("register", "requirements.json")):
        if by_name.get(name) != digests[key]:
            raise SystemExit(f"{key}: 보관본 지문이 문서 manifest 와 다르다 ({name})")

    reqs = parse_register(raw["register"])
    chapters = parse_chapters(raw["manual"])
    norms = parse_norms(raw["manual"])
    ids = {r["req_id"] for r in reqs}
    if set(CRITERIA) != ids:
        raise SystemExit(f"원문과 기준 매핑 불일치: 원문에 없음 {sorted(set(CRITERIA) - ids)} · 기준 없음 {sorted(ids - set(CRITERIA))}")
    for r in reqs:
        if r["chapter"] not in chapters:
            raise SystemExit(f"{r['req_id']}: 챕터 {r['chapter']} 가 해설서에 없다")
    for sid in BINDING_NORMS:
        if sid not in {n["source_id"] for n in norms}:
            raise SystemExit(f"구속 근거 {sid} 가 해설서 근거원장에 없다")

    criteria = []
    for r in reqs:
        lenses, criterion, automation, evidence, note = CRITERIA[r["req_id"]]
        criteria.append({**r, "section": "10", "section_name": SECTIONS["10"],
                         "related_sections": list(RELATED[r["chapter"]]),
                         "lens": list(lenses), "criterion": criterion, "automation": automation,
                         "evidence": list(evidence), "note": note})
    return {
        "schema_version": "1.0", "policy_version": "1.0",
        "sources": {k: {**v, "sha256": digests[k]} for k, v in SOURCES.items()},
        "document_verification": manifest.get("verification", {}),
        "description": (
            "AI 리스크관리 업무요건 문서 세트(v1.0 · 2026-09-08)의 요건 76건(BR)을 적합성검증 기준 "
            "항목으로 전개한 것. 요건·인수조건·챕터·근거원장은 원문에서 파싱하고 검증 기준 문장·"
            "자동화 상태·근거 파일만 생성기가 정한다. automated 는 하니스 통제가 그 요건에도 "
            "적용된다는 뜻이며 근거 파일이 실재해야 주장할 수 있다 (tools.ai_risk_criteria verify). "
            "문서 세트 자체가 밝힌 미수행 검증(브라우저 시각 검수·DB 실행·OpenAPI 메타스키마·은행 "
            "운영 인수)은 document_verification 에 그대로 싣는다."
        ),
        "automation_definition": AUTOMATION, "sections": SECTIONS, "lenses": list(LENSES),
        "chapters": {no: {"title": t, "related_sections": list(RELATED.get(no, ()))} for no, t in chapters.items()},
        "norms": norms, "criteria": criteria,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI 리스크 업무요건 → 적합성검증 기준 항목 생성")
    parser.add_argument("--out", default=str(ROOT / "harness" / "ai_risk_requirement_criteria.json"))
    args = parser.parse_args(argv)
    data = build()
    Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    from collections import Counter
    c = Counter(x["automation"] for x in data["criteria"])
    print(f"{args.out}: 요건 {len(data['criteria'])}건 (자동 {c['automated']} · 수동 {c['manual']} · "
          f"범위밖 {c['out_of_scope']}) · 챕터 {len(data['chapters'])} · 근거원장 {len(data['norms'])}"
          f" (구속 {sum(1 for n in data['norms'] if n['binding'])})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
