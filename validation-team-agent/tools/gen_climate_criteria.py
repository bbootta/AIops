"""기후리스크 관리 업무요건 → 적합성검증 기준 항목 생성기.

근거 원문은 `기후리스크 관리 업무요건정의서`(개요 + 실무진 해설서·상세설계,
설계 버전 1.0.0 · 2026.09.06) 두 HTML 이며 `harness/reference/` 에 지문과 함께
보관한다. 요건 72건(CLR-NN-MM)·인수시험 72건(AT)·운영 전 결정 20건(DEC)·근거
자료 13건(S01~S13)은 손으로 옮겨 적지 않고 **원문에서 파싱**한다. 검증 기준
문장·자동화 상태·근거 파일만 이 파일이 정한다.

근거(evidence)는 하니스에 실재하는 파일만 선언한다. 실재하지 않으면
`automated` 로 주장할 수 없다 (tools.climate_criteria verify 가 강제).
`automated` 가 요건 전체를 덮는다는 뜻은 아니며, 덮는 범위는 note 에 적는다.

사용:
    python -m tools.gen_climate_criteria --out harness/climate_requirement_criteria.json
"""

from __future__ import annotations

import argparse
import hashlib
import html as _html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFDIR = ROOT / "harness" / "reference"

SOURCES = {
    "detail": {
        "title": "기후리스크 관리 실무진 해설서 · 상세설계",
        "path": "harness/reference/climate_risk_requirements_20260906.html",
        "design_version": "1.0.0",
        "date": "2026-09-06",
        "role": "요건 72건·인수시험 72건·근거 자료·참조계산기의 원문",
    },
    "overview": {
        "title": "기후리스크 관리 업무요건정의서 · 개요",
        "path": "harness/reference/climate_risk_overview_20260906.html",
        "design_version": "1.0.0",
        "date": "2026-09-06",
        "role": "운영 전 확정할 결정 20건(DEC)의 원문",
    },
}

# 요건정의 마스터 8부문(CLAUDE.md §2) + 기후리스크. 기후 요건은 모두 09 에 두고
# 어느 기존 부문의 산출에 닿는지를 related_sections 로 적는다.
SECTIONS = {
    "01": "RDM·BIS비율", "02": "신용리스크·RWA", "03": "IFRS 9 ECL", "04": "시장리스크",
    "05": "ALM·IRRBB·유동성", "06": "운영리스크", "07": "통합위기상황분석",
    "08": "리스크 적합성검증", "09": "기후리스크",
}
LENSES = ("데이터", "산식", "방법론", "내부통제", "문서화")

RELATED = {
    "01": ("08",), "02": ("08",), "03": ("08",), "04": ("01",), "05": ("01",),
    "06": ("07",), "07": ("02",), "08": ("02",), "09": ("02",), "10": ("03", "01", "05"),
    "11": ("07",), "12": ("02",), "13": ("01",), "14": ("08",), "15": ("08",),
    "16": ("08",), "17": ("08",), "18": ("08",),
}

AUTOMATION = {
    "automated": "하니스에 실행 가능한 통제가 존재하고 근거 파일이 실재함 (evidence 1건 이상 필수). 덮는 범위는 note 에 적는다",
    "manual": "하니스에 통제가 없어 사람 검토로 남김 (note 필수, evidence 0건)",
    "out_of_scope": "시스템 구현·인수시험 영역이라 산출값 적합성검증 범위 밖 (note 필수, evidence 0건)",
}

_RECALC = "tools/climate_recalc.py"

# req_id → (관점, 검증 기준, 자동화, 근거, 비고)
CRITERIA: dict[str, tuple] = {
    "CLR-01-01": (("내부통제", "데이터"),
        "실행마다 목적 코드(SUPERVISORY_CST·INTERNAL_CST·ACCOUNTING_ECL·DISCLOSURE·CREDIT_REVIEW) 하나와 동결된 범위가 있고 포함+제외 합계가 원장 전체와 대사되는가",
        "manual", (), "하니스에 기후 실행 범위 manifest 를 받는 경로가 없다. 제외 금액·비중 표시는 사람 확인"),
    "CLR-01-02": (("문서화", "내부통제"),
        "규범원장이 법규·감독요구·국제원칙·정책계획·현장사례·내부설계를 구분하고 시행일·공표일·근거조항을 갖는가: 컨퍼런스 발표나 추진계획(PLAN)이 법적 의무(MANDATORY)로 승격되지 않는가",
        "automated", ("harness/regulatory_criteria.json", "harness/regulatory_rule_catalog.json", "tools/reg_rules.py"),
        "하니스 규제 원장은 근거수준(국내구속·국제권고·내부권고)·시행일·지문을 관리한다. 기후 고유 규범(S03~S13)의 효력 구분은 이 카탈로그의 norms 에 원문 상태 그대로 싣는다"),
    "CLR-01-03": (("내부통제",),
        "승인된 회계·규제자본·시장·유동성 엔진이 없을 때 결과가 SAMPLE_ONLY 로만 표시되고 OFFICIAL 보고서로 나가지 않는가",
        "automated", ("middleware/draft_watermark_guard.py", "tools/report_pdf.py", _RECALC),
        "재계산기는 SAMPLE_ONLY 분류가 아닌 fixture 를 거부하고 보고서는 DRAFT 워터마크가 강제된다"),
    "CLR-01-04": (("데이터", "문서화"),
        "금액 원·비율 소수·ISO 날짜·UTC 저장 규약이 지켜지고 DEMO 프로파일의 계수(beta 2 등)가 PRODUCTION 에서 참조되지 않는가",
        "manual", (), "DEMO/PRODUCTION 프로파일은 은행 설정 원장의 것이다. 하니스 재계산기는 합성 사례만 다룬다"),
    "CLR-02-01": (("내부통제",),
        "작성자·모형 개발자·독립검증자·업무 승인자·제출자가 분리되고 역할 이름이 달라도 동일인 식별자면 자기승인이 차단되는가",
        "automated", ("middleware/sod_guard.py", "harness/sod_policy.json"), ""),
    "CLR-02-02": (("방법론", "데이터"),
        "기후 중요성이 위험유형×업종×지역×상품×기간으로 평가되고 UNKNOWN 이 0점 저위험으로 치환되지 않으며 비중요 결론에도 사유·불확실성·재평가일이 남는가",
        "manual", (), "하니스의 중요도 등급은 모형 단위(model_materiality)이며 기후 익스포저 중요성 평가 경로가 없다"),
    "CLR-02-03": (("산식", "내부통제"),
        "KRI 의 분모·기준일·중복제거가 정의되고 분모 변경이 버전 없이 비교되지 않으며 한도 초과가 자동 여신 회수가 아닌 심사·상향보고로 이어지는가",
        "manual", (), "하니스에 기후 KRI·집중한도 원장이 없다"),
    "CLR-02-04": (("내부통제", "문서화"),
        "정책·한도·시나리오·모형 변경이 영향분석→검증→승인→유효일 순서로 기록되고 과거 결과를 덮어쓰지 않으며 입력 해시가 바뀐 결과에 이전 승인이 재사용되지 않는가",
        "automated", ("harness/change_manifest.json", "harness/change_manifest.schema.json", "tools/manifest.py"),
        "하니스 변경은 매니페스트에 근거·검증·롤백과 함께 남는다. 기후 모듈 자체의 버전 원장은 은행 몫"),
    "CLR-03-01": (("내부통제",),
        "검증 미완료 상태에서 APPROVED 전이가 불가하고 미해결 finding 수가 표시되며 허용되지 않은 전이가 거부되는가",
        "manual", (), "실행 상태기계는 기후 모듈의 것이다. 하니스는 자기 finding 원장에서만 미종결 차단을 한다"),
    "CLR-03-02": (("내부통제",),
        "처리 순서(입력확정→품질검사→위험매핑→기후손실→차주재무→PD/LGD/EAD→엔진→집계→대사→검토)가 고정되고 필수 파티션 누락 시 전행 총계가 승인되지 않는가",
        "manual", (), "배치 의존성은 기후 모듈 구현 사항. 부분 결과로 총계를 승인하지 않는지는 사람 확인"),
    "CLR-03-03": (("데이터", "내부통제"),
        "원천·정규화·시나리오·모형·파라미터·코드 버전·환율·반올림 정책의 해시가 manifest 로 동결되고 같은 manifest 의 두 실행이 원단위까지 같은가; seed 만 같고 라이브러리 버전이 다르면 재현으로 보지 않는가",
        "automated", ("tools/pack_verify.py", "tools/golden_regression.py", _RECALC),
        "재현성 자체검증(입력해시·정책·코드·페이지)과 Golden Case 회귀가 있다. 재계산기는 같은 fixture 의 결과 동일성을 시험한다"),
    "CLR-03-04": (("내부통제",),
        "완료 마커가 전 파티션 검증 후 원자적으로 발행되고 정정은 correction_of 로 원본에 연결되어 새 승인·새 접수증을 남기는가",
        "manual", (), "정정·재제출 상태는 기후 모듈 구현 사항"),
    "CLR-04-01": (("데이터",),
        "기관·차주·계약·실물자산·위치·보험계약이 별도 식별되고 시설별 배분회수액 합이 가용 담보회수액을 넘지 않는가",
        "manual", (), "하니스에 기후 실물자산·보험계약 원장이 없다"),
    "CLR-04-02": (("데이터", "방법론"),
        "as_of·effective·recorded_at 이 구분되고 과거시점 검증에 당시 인지 가능 정보만 쓰는가: 미래 재해지도·사후확정 보험금으로 과거 예측을 평가하지 않는가",
        "automated", ("middleware/leakage_guard.py", "harness/data_definition.md"),
        "누수 가드는 목표변수·미래정보 누수를 막는다. 재해지도 버전의 시점 정합은 사람 확인"),
    "CLR-04-03": (("데이터", "산식"),
        "금액이 원통화·환율버전과 함께 보관되고 최종 금액만 ROUND_HALF_UP 원단위이며 중간값을 반올림하지 않는가",
        "automated", (_RECALC,), "재계산기는 유리수 산술로 중간값을 정확히 유지하고 최종 금액만 반올림한다"),
    "CLR-04-04": (("데이터",),
        "결측이 0 과 구분되고 좌표·배출량·보험 결측에 reason_code 와 proxy/측정불가 상태가 있으며 공백을 0 으로 자동 변환하지 않는가",
        "manual", (), "하니스 스키마 가드는 필수 컬럼·자료형을 보되 결측 사유코드·대체 상태 필드를 요구하지 않는다"),
    "CLR-05-01": (("데이터",),
        "정상·격리·중복 행수 합이 원천 행수와 같고 금액합계·체크섬이 대사되며 같은 기본키에 금액이 다른 두 행이 차단되는가",
        "manual", (), "하니스 데이터 로더는 스키마·PII 를 보되 원천 행수·합계·체크섬 전수 대사를 하지 않는다"),
    "CLR-05-02": (("데이터",),
        "좌표가 원좌표 보존과 함께 WGS84 로 표준화되고 경계 tie-break 규칙이 기록되며 범위 밖·해상점이 자동 정상화되지 않는가",
        "manual", (), "하니스에 공간 조인 경로가 없다"),
    "CLR-05-03": (("데이터", "방법론"),
        "좌표·배출량 대체값에 품질등급·우선순위·버전이 있고 상·하방 민감도가 보고되며 근거 없는 대체 대신 UNKNOWN 이 유지되는가",
        "manual", (), "대체값 민감도 보고는 기후 모듈 산출물. 업종평균 0 을 저위험으로 읽지 않는지는 사람 확인"),
    "CLR-05-04": (("내부통제", "데이터"),
        "BLOCK 이 공식 실행을 막고 WARN 은 영향금액·유효기간·승인권자 확인 후만 통과하며 면제 기한 경과 후 자동 승계되지 않는가",
        "automated", ("tools/conditional_approval.py",),
        "조건부 승인 도구가 잔여위험·후속조건·이행기한을 추적한다. 품질 규칙별 BLOCK/WARN 분류는 은행 몫"),
    "CLR-06-01": (("문서화", "방법론"),
        "시나리오 set 이 공급기관·발행일·수령일·기간·법적 상태를 갖고 장기(2100년) 결과가 단기(2030년) 자본손실로 앞당겨지지 않는가",
        "manual", (), "하니스 시나리오 정책은 거시 심도·순서를 다루고 기후 시나리오 set 의 법적 상태·분석시계는 다루지 않는다"),
    "CLR-06-02": (("데이터", "산식"),
        "변수마다 형식(LEVEL·ABS_DELTA·REL_DELTA·GROWTH_RATE)·단위·통화·빈도가 지정되고 외삽이 기본 차단되며 통화가 다른 값이 환율 없이 합쳐지지 않는가",
        "manual", (), "하니스에 기후 변수사전이 없다"),
    "CLR-06-03": (("산식", "방법론"),
        "CST 목적에서 스트레스 경로를 임의 가중평균하지 않고 회계 목적 가중치는 합 1·음수 불가이며 재해 연초과확률과 사건 조건부 확률이 별도 필드인가",
        "automated", ("tools/scenario_weights.py", _RECALC),
        "재계산기는 가중치 합 0.99·음수를 거부한다(WEIGHT_SUM). CST 목적의 가중평균 금지는 사람 확인"),
    "CLR-06-04": (("데이터", "문서화"),
        "NGFS Phase V 영향 변수가 UNDER_REVIEW 로 표시되고 영향분석·대체모형 비교·명시 승인 없이 운영 사용되지 않으며 단기 자료가 같은 사유로 일괄 제외되지 않는가",
        "manual", (), "출처 경고는 시나리오 원장의 필드. 하니스에 해당 원장이 없다"),
    "CLR-07-01": (("산식", "방법론"),
        "피해율 함수가 재해별 단위(수심·폭염일수·풍속)를 쓰고 0~1 범위와 단조성을 만족하며 조건부 손실과 연평균손실이 분리되는가",
        "automated", (_RECALC,), "재계산기는 피해율의 [0,1] 범위만 강제한다. 함수 단조성·재해 단위·자산평가 기준일은 함수 버전별 사람 검토"),
    "CLR-07-02": (("산식",),
        "영업중단 손실이 매출×중단일/가동일×공헌이익률로 계산되고 매출손실 전액과 공헌이익손실이 함께 EBITDA 에서 차감되지 않으며 다중 사업장 배분 합이 1 인가",
        "automated", (_RECALC,), "재계산기는 공헌이익 기준 이익영향만 EBITDA 에 반영한다. 사업장 배분 합·공급망 중복은 사람 확인"),
    "CLR-07-03": (("산식", "데이터"),
        "가동이 확인된 적응조치만 피해율을 조정하고 보험회수가 면책·자기부담·한도·지급가능성을 거쳐 계약별 순차 배분되며 만료·비보장 계약은 회수 0 인가",
        "automated", (_RECALC,), "재계산기가 한도·자기부담·지급가능성·무효 계약(INS-CAP·INS-DEDUCTIBLE·INS-EXPIRED)을 시험한다. 복수 계약 순차 배분은 사람 확인"),
    "CLR-07-04": (("산식",),
        "같은 자산·같은 사건의 손상이 단순 합산되지 않고 V×[1−∏(1−d)] 순차 생존가치로 계산되며 유역·산업단지 집중이 추가 집계되는가",
        "automated", (_RECALC,), "재계산기의 compound_damage 가 순차 생존가치를 계산한다(LOSS-COMPOUND-28). 집중 집계는 사람 확인"),
    "CLR-08-01": (("산식",),
        "탄소 순비용이 (배출−무상할당−보유배출권)⁺×가격×(1−전가율)의 기준·충격 차이로 계산되고 Scope 2 배출이 전력가격 상승과 이중부과되지 않는가",
        "automated", (_RECALC,), "재계산기가 순증 비용(CARBON-DELTA·CARBON-EXCESS-ALLOWANCE)을 시험한다. Scope 2 이중부과 제거는 사람 확인"),
    "CLR-08-02": (("산식", "방법론"),
        "에너지·수요·CAPEX·보조금·차입이 별도 연도에 반영되고 기준사업계획에 이미 포함된 투자·가격변화는 증분만 반영되는가",
        "manual", (), "하니스에 전환 경로 모형이 없다"),
    "CLR-08-03": (("방법론", "문서화"),
        "전환계획 점수가 항목별 판단과 증빙을 갖고 높은 점수만으로 신용등급을 자동 우대하지 않으며 배출사업 매각을 경제 전체 감축으로 읽지 않는가",
        "manual", (), "하니스에 전환계획 평가 경로가 없다"),
    "CLR-08-04": (("방법론",),
        "거시 시나리오에 포함된 정책·재해 효과가 component ledger 로 표시되고 DIRECT_REPLACEMENT/RESIDUAL 방식이 구분되며 알 수 없으면 분리 감도로 보고되는가",
        "manual", (), "거시·직접 충격 중복 제거는 시나리오 설계 사항"),
    "CLR-09-01": (("산식", "데이터"),
        "손익·현금흐름·재무상태가 연결되고 자산손실이 대출손실로 직결되지 않으며 EBITDA·유동현금·DSCR·레버리지가 산출되는가",
        "automated", (_RECALC,), "재계산기는 EBITDA 경로(중단·탄소·비용화 피해)만 다룬다. 삼표 항등식·DSCR 은 사람 확인"),
    "CLR-09-02": (("방법론", "산식"),
        "회계 PIT·규제 장기평균(TTC)·감독 스트레스 PD 가 목적별로 분리되고 예제 로짓 보정이 경계 PD(0·1)를 거부하며 PIT 값이 규제 IRB 에 자동 복사되지 않는가",
        "automated", ("tools/pd_cyclicality.py", "harness/pd_design_thresholds.json", _RECALC),
        "PD 설계 판정 도구가 TTC·PIT 를 자료로 구분하고 재계산기는 PD-001(기부도 자산 로짓)을 거부한다"),
    "CLR-09-03": (("산식", "방법론"),
        "LGD 가 회수현금흐름 할인·회수비용·선순위·보증을 반영하고 보험 복구로 회복한 담보가치에 같은 보험금이 다시 더해지지 않으며 downturn LGD 와 회계 LGD 가 분리 저장되는가",
        "manual", (), "하니스에 담보 회수 배분 경로가 없다. 규제·회계 LGD 분리는 문서 확인"),
    "CLR-09-04": (("산식",),
        "EAD 가 잔액+CCF×적격 미사용한도이고 현금흐름 엔진이 인출액을 계산한 실행에서 CCF 가 중복 가산되지 않는가",
        "automated", (_RECALC,), "재계산기가 EAD 계약(EAD-BASE·EAD-STRESS·EAD-ZERO-UNDRAWN)을 시험한다. CCF 중복 가산 여부는 실행별 사람 확인"),
    "CLR-10-01": (("산식", "방법론"),
        "ECL 이 생존확률×조건부 PD×LGD×EAD×할인계수의 시나리오 가중합이고 Stage 1 은 12개월·Stage 2 는 잔존기간·Stage 3 은 별도 엔진이며 기후 고위험 태그만으로 Stage 2 가 자동 부여되지 않는가",
        "automated", (_RECALC, "harness/policies/ifrs9.md", "tools/run_ifrs9_validation.py"),
        "재계산기가 기간구조 ECL(SURVIVAL-28·STAGE1-10·STAGE3-REJECT)을 시험한다. SICR 판정 정책은 IFRS 9 정책 문서와 runner 가 본다"),
    "CLR-10-02": (("산식", "내부통제"),
        "IRB 파라미터·하한·output floor 가 기존 엔진에서 처리되고 기후등급에 임의 위험가중치 가산이 없으며 회계 PIT PD 가 IRB 입력에 자동 복사되지 않는가",
        "automated", ("tools/independent_recalc.py", "tools/pd_cyclicality.py"),
        "독립 재계산기가 RWA 합계와 산출하한을 다시 계산하고 PD 설계 판정 도구가 PIT·TTC 혼용을 잡는다. 기후등급 가산 금지는 사람 확인"),
    "CLR-10-03": (("산식",),
        "자본이 기초자본+세후손익−배당±기타조정으로 전개되고 충당금 비용이 승인 회계흐름으로 연결되며 누적 ECL 전체가 매년 자본에서 차감되지 않는가",
        "automated", (_RECALC, "src/vta/domains/capital.py"),
        "재계산기의 capital_bridge 가 충당금 비용을 별도 입력으로 받는다(GOLDEN-CET1). 규제 EL 부족액·세금·필터 대사는 사람 확인"),
    "CLR-10-04": (("산식", "방법론"),
        "금리·스프레드·예금유출·한도인출·HQLA haircut 이 기존 엔진에 전달되고 LCR/NSFR 의 적격성·유입상한이 해당 엔진에서 처리되며 단순 합계로 대체되지 않는가",
        "automated", ("src/vta/domains/liquidity.py", "src/vta/domains/irrbb.py", "src/vta/domains/market.py"),
        "기존 엔진 산출값 점검은 있다. 기후 충격의 전달 경로(예금유출률 적용 대상 등)는 사람 확인"),
    "CLR-11-01": (("방법론", "산식"),
        "하향식·상향식이 동일 기준일·범위·시나리오·통화·기간·손실정의를 맞춘 뒤 차이가 단계적 치환으로 분해되고 치환 순서가 표시되는가",
        "automated", ("tools/independent_recalc.py",),
        "독립 재계산의 decompose 가 단계적 치환으로 기여도를 분리하고 합계 대사를 확인한다. 기후 특유의 치환 순서(포트폴리오→손상함수→보험→재무→신용→조치)는 보고에 적는다"),
    "CLR-11-02": (("방법론",),
        "정적/동적 여부와 재투자·신규영업·매각·보험 갱신·자본조달 가정이 명시되고 관리조치는 승인·실행가능성·시간·비용·시장용량을 갖춘 경우만 순효과에 반영되며 현재 적응시설과 미래 조치가 분리되는가",
        "manual", (), "관리조치 실행가능성은 경영 판단 사항 (DEC-18)"),
    "CLR-11-03": (("방법론", "산식"),
        "역위기가 자본비율/유동성 임계치를 처음 위반하는 충격조합을 찾고 단조성 확인 시에만 이분탐색을 쓰며 단일 최악값을 확률 손실로 표현하지 않는가",
        "manual", (), "하니스 시나리오 통제는 거시 심도 순서까지다. 기후 역위기 탐색은 사람 검토"),
    "CLR-11-04": (("내부통제", "문서화"),
        "공식 배포파일·공문·템플릿이 수령 원장에 등록되고 파일 생성과 실제 제출이 별도 상태이며 접수증을 합성하지 않는가",
        "manual", (), "대외 제출은 인간 권한 (CLAUDE.md §5). 하니스는 제출 상태를 만들지 않는다"),
    "CLR-12-01": (("내부통제", "문서화"),
        "여신심사에 사업장·보험·전환계획 최신성·현금흐름·담보·한도·기후민감도가 제시되고 기후점수만으로 거절이 자동 확정되지 않는가",
        "manual", (), "여신 승인·거절·가격은 은행 심사권자의 결정"),
    "CLR-12-02": (("내부통제",),
        "약정이 이행항목·측정방법·증빙·마감·미이행조치·책임자를 갖고 금리·한도 변경이 권한자 승인 후 반영되며 그린워싱 우려만으로 약정 밖 제재가 자동 실행되지 않는가",
        "manual", (), "여신 약정 관리는 은행 시스템의 것"),
    "CLR-12-03": (("내부통제", "데이터"),
        "재해 발생·보험 해지·이전·전환투자 지연·배출규제 변경이 trigger 로 등록되어 발생일·인지일·영향 대상이 매칭되고 기존 심사·PD·담보 재평가가 요청되며 뉴스 키워드만으로 피해가 확정되지 않는가",
        "automated", ("tools/validation_trigger.py", "harness/validation_triggers.json"),
        "상시 모니터링 트리거가 검증 사례·검토 큐를 만든다. 기후 트리거 유형의 등록은 은행 몫"),
    "CLR-12-04": (("문서화", "내부통제"),
        "위원회 보고에 결정사항·담당부서·완료일·기대효과·재평가조건이 남고 문서 열람만으로 활용완료 처리되지 않는가",
        "manual", (), "경영 활용 확인은 위원회 기록 검토 사항"),
    "CLR-13-01": (("문서화", "내부통제"),
        "공시 적용대상이 상장 여부·연결자산·보고연도·경과조치·관할·채택기준 판정표로 관리되고 정책 로드맵이 법적 의무와 구분되며 FY 와 공시연도가 혼동되지 않는가",
        "manual", (), "공시 적용 판정은 준법 확인 사항 (DEC-13)"),
    "CLR-13-02": (("산식", "데이터"),
        "금융배출량이 PCAF 버전·자산군별 귀속계수·분모·차주 배출경계와 함께 저장되고 Scope 1·2·3 이 분리 보존되며 모든 자산군에 EVIC 이나 EAD 분자를 일률 적용하지 않는가",
        "manual", (), "하니스에 금융배출량 산정 경로가 없다. 금융배출량은 신용손실과 다른 척도다"),
    "CLR-13-03": (("데이터", "문서화"),
        "각 disclosure_fact 가 기준·항목·기관·연도·단위·원천 산출키·수정사유·승인자를 갖고 보고표와 공시표가 자동 대사되며 수동 변경에 기초 사실값·근거가 남는가",
        "manual", (), "하니스는 공시 산출물을 만들지 않는다: 대외 확정은 인간 권한"),
    "CLR-13-04": (("방법론", "문서화"),
        "시나리오 기간·확률·회계 경계·할인·관리조치의 차이가 설명되고 장기 CST 누적손실이 당기 충당금으로 전환되지 않으며 공시 위험이 회계 추정에 미반영이면 사유·금액영향·불확실성이 문서화되는가",
        "manual", (), "회계·공시 차이 설명은 재무 문서 검토 사항"),
    "CLR-14-01": (("내부통제", "방법론"),
        "검증자가 개발자와 별도 구현·표본으로 목적·사용범위·데이터 계보·표본·계수 부호·변별·정확·안정·보수성·운영을 확인하고 개발자 자기점검이 독립검증으로 표시되지 않는가",
        "automated", ("tools/independent_recalc.py", "tools/adversarial_review.py", "middleware/sod_guard.py", "harness/sod_policy.json"),
        "독립 재계산·적대적 검증·직무분리가 있다. 검증 표본의 별도 선정(침수 미노출·만료 보험·기부도·복수담보)은 사람"),
    "CLR-14-02": (("방법론", "데이터"),
        "재해 전 기준일 자료로 예측하고 이후 실제 피해·보험·부도·회수를 관찰하며 비피해 비교집단·관측창·검열을 명시하는가: 부도 기업만 표본으로 뽑거나 비교집단을 누락하지 않는가",
        "manual", (), "하니스 백테스트는 PD 실현 부도율 대조(pd_cyclicality·binomial_calibration)이며 재해 사건 귀속·비교집단 설계는 사람"),
    "CLR-14-03": (("방법론", "산식"),
        "PD 의 AUC/KS·캘리브레이션·관측부도율 CI, LGD/EAD·피해모형의 편향·MAE, 시점·업종·지역별 PSI 가 점검되고 동일 재해가 학습·검증에 섞이지 않으며 AUC 만으로 총손실 과소추정을 수용하지 않는가",
        "automated", ("tools/metric_ks_auc.py", "tools/binomial_calibration.py", "tools/metric_psi.py", "harness/policies/pd_lgd_ead.md"),
        "변별·캘리브레이션·안정성 지표가 있다. leave-one-event-out 과 피해모형 MAE 는 사람"),
    "CLR-14-04": (("내부통제", "문서화"),
        "PASS·CONDITIONAL·REJECT 가 사용범위와 함께 기록되고 CRITICAL/HIGH 미해결 시 승인이 차단되며 조건부는 기간·한도·완화조치·승인근거를 갖고 종결은 수정자와 다른 검증자의 재현 증거로 확인되는가",
        "automated", ("tools/validation_finding.py", "tools/conditional_approval.py", "tools/ivr_response.py"),
        "Finding 계보(발견·원인·보완·재검증·종결)·조건부 승인 기록·응답 판정 파생이 있다"),
    "CLR-15-01": (("데이터",),
        "수신 파일이 UTF-8·schema_version·행수·합계·체크섬을 갖고 엔진 응답이 행별 결과/오류·처리수·무결성 해시를 포함하며 누락행 없이 성공건수만 반환하지 않는가",
        "out_of_scope", (), "인터페이스 구현 계약: 인수시험 AT-15-01 영역이며 산출값 검증 대상이 아니다"),
    "CLR-15-02": (("내부통제",),
        "쓰기 요청이 Idempotency-Key 와 body hash 로 중복 판정되고 상태 변경이 expected_version 의 compare-and-swap 으로 수행되는가",
        "out_of_scope", (), "멱등성·동시성 구현 계약: 인수시험 AT-15-02 영역"),
    "CLR-15-03": (("내부통제",),
        "오류 코드가 구분되고 자동 재시도는 429/503/전송단절만 지수 backoff 로 하며 timeout 을 실패로 단정해 다른 키로 중복 실행하지 않는가",
        "out_of_scope", (), "오류·재시도 구현 계약: 인수시험 AT-15-03 영역"),
    "CLR-15-04": (("내부통제",),
        "APPROVED 상태만 제출용 export 가 허용되고 CALCULATED 결과는 SAMPLE/DRAFT 워터마크만 허용되며 조회·다운로드에도 범위권한·로그가 적용되는가",
        "automated", ("middleware/draft_watermark_guard.py", "tools/report_pdf.py", "middleware/permission_guard.py"),
        "DRAFT 워터마크 강제와 권한 가드가 있다. 외부송신 별도 승인은 인간 권한"),
    "CLR-16-01": (("내부통제",),
        "실행 버튼이 READY 와 권한 충족 시만 활성화되고 진행률 100% 가 승인완료로 표시되지 않는가",
        "out_of_scope", (), "화면 명세: 인수시험 AT-16-01 영역"),
    "CLR-16-02": (("데이터", "내부통제"),
        "차주별 화면이 수치마다 단위·기준일·버전·대체값 여부·근거 링크를 표시하고 정밀좌표가 권한 없는 사용자에게 전송되지 않는가",
        "out_of_scope", (), "화면 명세: 인수시험 AT-16-02 영역. 좌표 최소 제공 원칙은 CLR-17-01 에서 본다"),
    "CLR-16-03": (("내부통제",),
        "승인 화면이 미해결 이슈·차이·가정·관리조치·결과버전을 보여주고 자기승인·검증미완료가 서버에서도 차단되는가",
        "out_of_scope", (), "화면 명세: 인수시험 AT-16-03 영역. 서버 측 자기승인 차단은 CLR-02-01 에서 본다"),
    "CLR-16-04": (("문서화",),
        "경영진·감독·실무 보고의 모든 표에 기준일·단위·범위·미측정 비중·조치 전후·버전이 있고 미측정이 분모에서 빠지지 않는가",
        "automated", ("middleware/output_completeness_guard.py", "tools/report_pack.py"),
        "산출물 완결성 통제와 계층형 보고서 팩이 있다. 미측정 비중의 분모 포함 여부는 사람 확인"),
    "CLR-17-01": (("내부통제",),
        "SSO 사용자와 서비스 계정이 분리되고 RBAC+기관/포트폴리오 범위가 서버에서 적용되며 상세좌표·차주식별자가 최소 제공·암호화되는가",
        "automated", ("middleware/permission_guard.py", "middleware/data_safety_guard.py", "harness/permission_matrix.json"),
        "권한 매트릭스와 민감정보 가드가 있다. 암호화·키관리·외부 서비스 보안 검토는 은행 인프라"),
    "CLR-17-02": (("내부통제",),
        "성능 목표(조회 p95·접수·야간처리)가 참조 인프라·외부엔진 조건과 함께 성능시험서에 고정되는가",
        "out_of_scope", (), "비기능 요건: 인수시험 AT-17-02 영역"),
    "CLR-17-03": (("내부통제",),
        "RTO·RPO 가 은행 승인 후 확정되고 승인·제출 기록이 응답 이전에 내구 저장되며 재처리가 멱등한가",
        "out_of_scope", (), "장애·복구 운영: 인수시험 AT-17-03 영역"),
    "CLR-17-04": (("내부통제", "문서화"),
        "실행·오류·사용자·변경·승인·다운로드 로그가 correlation_id 로 연결되고 보존기간이 유형별 승인값이며 자격증명·민감 본문이 로그에 남지 않는가",
        "automated", ("middleware/run_logger.py", "tools/audit_retention.py", "middleware/data_safety_guard.py"),
        "실행 로그·감사 보존·민감정보 차단이 있다. 유형별 보존기간 승인값은 은행 몫 (DEC-15)"),
    "CLR-18-01": (("문서화", "내부통제"),
        "모든 CLR 요건이 구현항목·테스트·담당·근거와 연결되고 P0 전건 통과·CRITICAL/HIGH 미해결 0 이 운영 출구조건이며 예시를 실행하지 않고 PASS 로 표시하지 않는가",
        "automated", ("harness/climate_requirement_criteria.json", "tools/climate_criteria.py"),
        "이 카탈로그가 요건 72건·인수시험 72건을 원문에서 파싱해 추적표로 싣고 근거 실재성을 강제한다. 실제 인수시험 수행은 구축 시점의 일"),
    "CLR-18-02": (("산식", "방법론"),
        "합성 fixture·기대값으로 손실·PD·EAD·ECL·RWA·비율을 단계별 대사하고 결과에 SAMPLE_ONLY 를 강제하며 문서 계산기와 엔진이 같은 모듈을 공유한 결과를 독립검증으로 치지 않는가",
        "automated", (_RECALC,),
        "재계산기는 문서 참조계산기와 코드를 공유하지 않는 별도 구현으로 공표값 21건과 대조한다"),
    "CLR-18-03": (("내부통제",),
        "구축이 원장·품질·시나리오·권한 → 전이·엔진·CST → 공시·심사·운영 전환 순서로 진행되고 병행산출·기존 결과 대사·기간 제한 사용을 거쳐 정식 전환되는가",
        "manual", (), "이행 단계는 프로젝트 관리 사항. 병행기간 2회는 제안값"),
    "CLR-18-04": (("내부통제", "문서화"),
        "운영 전 결정 20건(DEC-01~20)이 승인·유효기간과 함께 결정 원장에 등록되고 미승인 설정이 운영 시작·공식 export 를 차단하며 TBD 가 코드 상수로 남지 않는가",
        "automated", ("harness/climate_requirement_criteria.json", "tools/climate_criteria.py"),
        "결정 20건을 원문에서 파싱해 이 카탈로그의 decisions 에 싣고 각 결정이 차단하는 산출을 함께 적는다. 승인·유효기간 등록은 은행 몫"),
}


# ---------------------------------------------------------------- 원문 파싱

def source_path(key: str) -> Path:
    return ROOT / SOURCES[key]["path"]


def _clean(s: str) -> str:
    s = re.sub(r'<span class="expansion">.*?</span>', "", s, flags=re.S)
    s = re.sub(r"<[^>]+>", "", s)
    return _html.unescape(re.sub(r"\s+", " ", s)).strip()


def _text_lines(raw: str) -> list[str]:
    body = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", raw, flags=re.S)
    body = re.sub(r"</(h[1-6]|p|li|tr|div|section|article|caption)>", "\n", body)
    body = re.sub(r"</(td|th)>", " | ", body)
    body = re.sub(r"<br\s*/?>", "\n", body)
    txt = _html.unescape(re.sub(r"<[^>]+>", "", body))
    txt = re.sub(r"[ \t]+", " ", txt)
    return [l.strip() for l in txt.splitlines() if l.strip()]


def parse_requirements(raw: str) -> list[dict]:
    out = []
    for m in re.finditer(r'<article class="requirement" id="(CLR-\d\d-\d\d)"(.*?)</article>', raw, flags=re.S):
        rid, b = m.group(1), m.group(2)

        def g(p: str) -> str:
            mm = re.search(p, b, flags=re.S)
            return _clean(mm.group(1)) if mm else ""

        out.append({
            "req_id": rid,
            "chapter": rid[4:6],
            "priority": g(r'<span class="badge">(.*?)</span>'),
            "acceptance_test": g(r"인수시험 (.*?)</span>").replace(" ", ""),
            "title": g(r"<h3>(.*?)</h3>"),
            "body": g(r"</h3>\s*<p>(.*?)</p>"),
            "error_case": g(r'<div class="case negative"><b>오류·경계 사례 / 예상 처리</b><p>(.*?)</p>'),
            "owner": g(r"책임: (.*?)<br>"),
            "sources": re.findall(r'href="#(S\d\d)"', b),
        })
    return out


def parse_chapters(raw: str) -> dict[str, dict]:
    ch = {}
    for m in re.finditer(r'<section class="chapter" id="ch(\d\d)"[^>]*>.*?<h2>(.*?)</h2>\s*<p class="purpose">(.*?)</p>', raw, flags=re.S):
        ch[m.group(1)] = {"title": _clean(m.group(2)), "purpose": _clean(m.group(3)),
                          "related_sections": list(RELATED[m.group(1)])}
    return ch


def parse_acceptance_tests(raw: str) -> list[dict]:
    rows = []
    for l in _text_lines(raw):
        m = re.match(r"(AT-\d\d-\d\d) \| (.+?) \| (.+?) \| (.+?) \|$", l)
        if m:
            rows.append({"at_id": m.group(1), "req_id": "CLR" + m.group(1)[2:], "owner": m.group(2),
                         "expected_ok": m.group(3), "expected_error": m.group(4)})
    return rows


def parse_decisions(raw: str) -> list[dict]:
    rows = []
    for l in _text_lines(raw):
        m = re.match(r"(DEC-\d\d) (.+?) \| (.+?) \| (.+?) \|$", l)
        if m:
            rows.append({"dec_id": m.group(1), "title": m.group(2), "bank_must_fix": m.group(3),
                         "gate": m.group(4)})
    return rows


def parse_norms(raw: str) -> list[dict]:
    out = []
    for m in re.finditer(r'<div class="source-item" id="(S\d\d)">(.*?)</div></div>', raw, flags=re.S):
        b = m.group(2)
        status = _clean((re.search(r'<span class="source-status">(.*?)</span>', b, flags=re.S) or [None, ""])[1])
        title = _clean((re.search(r"<h3>(.*?)</h3>", b, flags=re.S) or [None, ""])[1])
        url = (re.search(r'href="([^"]+)"', b) or [None, ""])[1]
        desc = _clean((re.search(r"</h3>\s*<p>(.*?)</p>", b, flags=re.S) or [None, ""])[1])
        parts = [p.strip() for p in status.split("·")]
        out.append({"source_id": m.group(1), "status": status, "kind": parts[1] if len(parts) > 1 else "",
                    "title": title, "url": _html.unescape(url), "description": desc,
                    "binding": parts[1] in ("국내 규정", "국내 세칙") if len(parts) > 1 else False})
    return out


# ---------------------------------------------------------------- 생성

def build() -> dict:
    raw = {k: source_path(k).read_text(encoding="utf-8") for k in SOURCES}
    digests = {k: hashlib.sha256(source_path(k).read_bytes()).hexdigest() for k in SOURCES}

    reqs = parse_requirements(raw["detail"])
    chapters = parse_chapters(raw["detail"])
    ats = parse_acceptance_tests(raw["detail"])
    decisions = parse_decisions(raw["overview"])
    norms = parse_norms(raw["detail"])

    ids = {r["req_id"] for r in reqs}
    missing = sorted(set(CRITERIA) - ids)
    extra = sorted(ids - set(CRITERIA))
    if missing or extra:
        raise SystemExit(f"원문과 기준 매핑 불일치: 원문에 없음 {missing} · 기준 없음 {extra}")
    at_by_req = {a["req_id"]: a for a in ats}

    criteria = []
    for r in reqs:
        lenses, criterion, automation, evidence, note = CRITERIA[r["req_id"]]
        at = at_by_req.get(r["req_id"])
        criteria.append({
            **r,
            "section": "09",
            "section_name": SECTIONS["09"],
            "related_sections": list(RELATED[r["chapter"]]),
            "lens": list(lenses),
            "criterion": criterion,
            "automation": automation,
            "evidence": list(evidence),
            "note": note,
            "acceptance_expected_ok": at["expected_ok"] if at else "",
            "acceptance_expected_error": at["expected_error"] if at else "",
        })

    return {
        "schema_version": "1.0",
        "policy_version": "1.0",
        "sources": {k: {**v, "sha256": digests[k]} for k, v in SOURCES.items()},
        "description": (
            "기후리스크 관리 업무요건정의서(설계 버전 1.0.0 · 2026.09.06)의 요건 72건을 "
            "적합성검증 기준 항목으로 전개한 것. 요건·인수시험·결정·근거 자료는 원문에서 "
            "파싱하고 검증 기준 문장·자동화 상태·근거 파일만 생성기가 정한다. "
            "automated 는 하니스에 통제가 실재함을 뜻하며 근거 파일이 실재해야 주장할 수 "
            "있다 (tools.climate_criteria verify 가 강제). 덮는 범위는 note 에 적는다. "
            "문서가 SAMPLE_ONLY 로 못박은 합성 사례의 재계산은 모형 적합성 승인이 아니다 (DEC-20)."
        ),
        "automation_definition": AUTOMATION,
        "sections": SECTIONS,
        "lenses": list(LENSES),
        "chapters": chapters,
        "norms": norms,
        "criteria": criteria,
        "acceptance_tests": ats,
        "decisions": decisions,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="기후리스크 업무요건 → 적합성검증 기준 항목 생성")
    parser.add_argument("--out", default=str(ROOT / "harness" / "climate_requirement_criteria.json"))
    args = parser.parse_args(argv)
    data = build()
    Path(args.out).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    from collections import Counter
    c = Counter(x["automation"] for x in data["criteria"])
    print(f"{args.out}: 요건 {len(data['criteria'])}건 (자동 {c['automated']} · 수동 {c['manual']} · "
          f"범위밖 {c['out_of_scope']}) · 인수시험 {len(data['acceptance_tests'])} · "
          f"결정 {len(data['decisions'])} · 근거 자료 {len(data['norms'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
