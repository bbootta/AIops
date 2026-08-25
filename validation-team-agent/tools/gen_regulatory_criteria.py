"""규제 기준 → 적합성검증 항목 생성기 (국내 + 국제).

근거 원문을 저장소에 두고, 각 검증 항목의 인용이 **원문에서 실제로 해석되는지**
생성 시점에 확인한다. 해석되지 않는 인용은 카탈로그에 실리지 않는다: 인용이
원문과 맞는지 검증하지 못하던 상태(이월 CO-004)를 닫기 위한 것이다.

기준 스택은 세 층이다.

    규정(국내구속) → 세칙(국내구속) → 바젤(국제권고)

**국내 기준이 우선한다.** 국내가 그 주제를 정하지 않으면 바젤을 따르고, 국내
기준이 있으나 해석이 모호하면 바젤 원문으로 보충 해석한다. 국내가 바젤보다
느슨해도 국내가 적용되나 그 차이는 산출물에 표기한다 (PRECEDENCE 참조).

라인 번호는 손으로 적지 않는다. 인용 문자열에서 원문을 찾아 파생한다.

바젤 근거는 BIS 이용조건상 원문 전문을 복제하지 않은 **Chapter 단위 source
map**이다. 따라서 Chapter 실재·시행일·공식 URL 까지만 대조되며, paragraph
단위 문구 대조는 이 소스북으로 할 수 없다.

사용:
    python -m tools.gen_regulatory_criteria --out harness/regulatory_criteria.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REFDIR = ROOT / "harness" / "reference"

# 근거 원문: 상위 규정과 하위 세칙을 함께 둔다. 임계값은 규정에, 산정기준은
# 세칙에 있으므로 둘 중 하나만으로는 국내 기준을 덮지 못한다.
SOURCES = {
    "규정": {
        "title": "은행업감독규정",
        "effective": "2026-04-01",
        "promulgation": "금융위원회고시 제2026-10호, 2026. 3. 18., 일부개정",
        "url": "https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq=2100000276094",
        "path": "harness/reference/bank_supervision_regulation_20260401.md",
        "role": "경영지도비율 등 임계값의 근거",
    },
    "세칙": {
        "title": "은행업감독업무시행세칙",
        "effective": "2026-06-30",
        "promulgation": "금융감독원세칙 제9999호, 2026. 6. 26., 일부개정",
        "url": "https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq=2200000108789",
        "path": "harness/reference/bank_supervision_rules_20260630.md",
        "role": "산정기준·별표의 근거",
    },
    "바젤": {
        "title": "Basel Framework 공식 원문 소스북",
        "effective": "2026-08-09",
        "promulgation": "BIS/BCBS 통합 Basel Framework · Standard 14종",
        "url": "https://www.bis.org/basel_framework/",
        "path": "harness/reference/basel_framework_sourcebook_20260809.md",
        "role": "국제 기준: 국내 기준이 없거나 해석이 모호할 때의 보충 근거",
    },
}
BASIS_LEVEL = {"규정": "국내구속", "세칙": "국내구속", "바젤": "국제권고"}

# 기준 스택: 어느 기준이 지배하는가. 손으로 판단하지 않도록 정책으로 고정한다.
PRECEDENCE = {
    "order": ["규정", "세칙", "바젤"],
    "rules": [
        "① 국내 구속 기준(규정 → 세칙)이 그 주제를 정하면 국내 기준이 적용된다.",
        "② 국내 기준이 그 주제를 정하지 않으면 바젤 원문을 따른다.",
        "③ 국내 기준이 있으나 해석이 모호하면 바젤 원문으로 보충 해석한다. "
        "다만 국내가 명시적으로 정한 값·범위는 바젤과 달라도 국내가 적용된다.",
        "④ 국내가 바젤보다 느슨한 경우에도 국내가 적용되나, 그 차이를 산출물에 "
        "표기한다: 국내 준수가 국제 기준 충족을 뜻하지 않는다.",
    ],
    "governing_values": {
        "국내": "국내 기준이 지배한다 (규칙 ①)",
        "바젤": "국내 기준이 없어 바젤이 지배한다 (규칙 ②)",
        "국내+바젤보충": "국내가 지배하되 모호한 부분을 바젤로 보충한다 (규칙 ③)",
    },
}

SECTIONS = {
    "01": "RDM·BIS비율",
    "02": "신용리스크·RWA",
    "03": "IFRS 9 ECL",
    "04": "시장리스크",
    "05": "ALM·IRRBB·유동성",
    "06": "운영리스크",
    "07": "통합위기상황분석",
    "08": "리스크 적합성검증",
}
LENSES = ("데이터", "산식", "방법론", "내부통제", "문서화")


# ---------------------------------------------------------------- 원문 해석

def source_path(key: str) -> Path:
    return ROOT / SOURCES[key]["path"]


def _lines(key: str) -> list[str]:
    return source_path(key).read_text(encoding="utf-8").splitlines()


def resolve(citation: str, lines: list[str]) -> int | None:
    """인용 문자열 → 원문 라인 번호 (1-based). 해석 불가면 None."""
    m = re.fullmatch(r"별표 ([0-9]+(?:의[0-9]+)?)", citation)
    if m:
        want = f"## [별표 {m.group(1)}]"
        for i, l in enumerate(lines, 1):
            if l.startswith(want):
                return i
        return None
    m = re.fullmatch(r"(제[0-9]+조(?:의[0-9]+)?)", citation)
    if m:
        pat = re.compile(rf"^##### {re.escape(m.group(1))}[(（]")
        for i, l in enumerate(lines, 1):
            if pat.match(l):
                return i
        return None
    # 바젤 Chapter: paragraph 접미사(CRE20.1)는 Chapter 로 절단해 해석한다.
    # 소스북이 Chapter 단위 색인이므로 paragraph 문구는 대조할 수 없다.
    m = re.fullmatch(r"([A-Z]{3})([0-9]+)(?:\.[0-9.]+)?", citation)
    if m:
        want = f"| {m.group(1)}{m.group(2)} |"
        for i, l in enumerate(lines, 1):
            if l.startswith(want):
                return i
        return None
    return None



def count_current_chapters(lines: list[str]) -> int:
    """'2. 현행 Chapter 전수 색인' 구간의 Chapter 행만 센다.

    파일 전체에서 세면 장래 시행 예정(3장)과 전체 원장(4장)의 행까지 들어와
    '현행'이라는 이름과 어긋난다: 세는 범위를 이름과 맞춘다.
    """
    start = end = None
    for i, l in enumerate(lines):
        if l.startswith("## 2. "):
            start = i
        elif start is not None and l.startswith("## 3. "):
            end = i
            break
    if start is None:
        return 0
    body = lines[start:end if end is not None else len(lines)]
    return sum(1 for l in body if re.match(r"^\| [A-Z]{3}[0-9]+ \|", l))

def basel_chapter(citation: str) -> str | None:
    m = re.fullmatch(r"([A-Z]{3}[0-9]+)(?:\.[0-9.]+)?", citation)
    return m.group(1) if m else None


def heading_of(line_no: int, lines: list[str]) -> str:
    return lines[line_no - 1].lstrip("#").strip()


# ---------------------------------------------------------------- 검증 항목
#
# (인용, 부문, 검증관점, 검증 기준, 자동화, 하니스 근거, 비고)
#
# 자동화는 하니스에 통제가 실재할 때만 'automated' 다. 기준을 덮지 못하면
# 'manual' 로 두고 무엇이 없는지 적는다: 인용이 있다는 것과 통제가 있다는 것은
# 다르다.
CRITERIA: tuple[tuple, ...] = (
    # ---- 부문 01 RDM·BIS비율
    ("세칙", "제17조", "01", ("내부통제", "산식"),
     "경영지도비율의 산정기준이 세칙이 지정한 별표(3·3의2·3의3·3의4·3의5·3의6·3의7·3의8·3의10·3의12)를 따르는가",
     "automated", ("harness/capital_adequacy_thresholds.json", "harness/policies/capital_adequacy.md"),
     ""),
    ("세칙", "제17조", "01", ("데이터", "내부통제"),
     "산정 시점이 지표별로 구분되는가: 자기자본비중·단순기본자본비율·NSFR·거액익스포져비율은 가결산일·결산일 현재, LCR·원화예대율은 매월 평잔 (제17조제2항)",
     "manual", (),
     "하니스는 LCR·원화예대율을 시점값 하나로 받는다. 월평잔 여부를 판별할 입력이 없어 사람 확인 항목으로 남긴다: 시점값을 평잔으로 보고하면 잡지 못한다"),
    ("세칙", "제17조", "01", ("내부통제",),
     "완충자본 포함 자본비율 미달이 예상될 때 배당·자사주매입·성과연동상여 제한과 자본계획 승인 절차로 연결되는가 (제17조제3항)",
     "automated", ("harness/capital_adequacy_thresholds.json", "src/vta/domains/capital.py"),
     ""),
    ("세칙", "별표 3", "01", ("산식",),
     "신용·운영리스크 위험가중자산과 자기자본비율 산출이 바젤Ⅲ 국내 기준에 따라 재계산되는가",
     "automated", ("harness/basel_risk_taxonomy.json", "src/vta/domains/capital.py"), ""),
    ("세칙", "별표 3의2", "04", ("산식",),
     "시장리스크를 포함한 위험가중자산 산출기준이 적용되는가",
     "automated", ("harness/market_risk_thresholds.json", "src/vta/domains/market.py"), ""),
    ("세칙", "별표 3의8", "01", ("산식",),
     "단순기본자본비율(레버리지비율)이 국내 산출기준으로 재계산되는가",
     "automated", ("harness/capital_adequacy_thresholds.json", "src/vta/domains/capital.py"), ""),
    ("세칙", "별표 3의12", "02", ("산식",),
     "거액익스포져비율(LEX)이 산출기준에 따라 산정되고 한도 저촉이 판정되는가",
     "automated", ("harness/concentration_thresholds.json", "src/vta/domains/concentration.py"), ""),
    ("세칙", "별표 7", "01", ("데이터", "산식"),
     "경영실태평가 계량지표가 정해진 산정기준으로 산출되는가",
     "manual", (),
     "하니스에 경영실태평가 계량지표 산출 경로가 없다"),
    ("세칙", "별표 11", "01", ("데이터",),
     "자산·부채 항목별 평가·산정이 세부기준을 따르는가",
     "manual", (), "하니스에 항목별 평가기준 대조가 없다"),
    ("세칙", "별표 20", "01", ("내부통제",),
     "시스템적 중요도 산정과 추가자본 부과가 세부기준에 따라 반영되는가",
     "automated", ("harness/capital_adequacy_thresholds.json",), ""),
    ("세칙", "별표 21", "01", ("내부통제",),
     "경기대응완충자본이 세부기준에 따라 자본요구에 반영되는가",
     "automated", ("harness/capital_adequacy_thresholds.json",), ""),

    # ---- 부문 02 신용리스크·RWA
    ("세칙", "제18조", "02", ("문서화", "내부통제"),
     "자산건전성 분류기준·대손충당금 적립 기준과 그 결과 보고가 매분기 종료 후 20일 이내에 이루어지는가",
     "manual", (),
     "보고 기한 준수는 운영 사실: 하니스는 산출값만 검증하며 제출 시점 데이터를 갖지 않는다"),
    ("세칙", "별표 12", "02", ("데이터", "산식"),
     "무수익여신 산정이 기준에 따라 이루어지는가",
     "manual", (), "하니스에 무수익여신 산정 검증이 없다"),
    ("세칙", "별표 18", "02", ("방법론",),
     "주택관련 담보대출의 LTV·DTI 등 리스크관리 세부기준이 적용되는가",
     "manual", (), "하니스에 주담대 규제비율 점검이 없다"),
    ("세칙", "별표 24", "02", ("내부통제",),
     "조기경보제도와 여신감리제도가 기준에 따라 운영되는가",
     "automated", ("harness/validation_triggers.json", "tools/validation_trigger.py"),
     ""),
    ("세칙", "별표 15", "04", ("내부통제",),
     "국가별·거액신용·시장리스크 관리기준이 한도 체계로 운영되는가",
     "automated", ("harness/concentration_thresholds.json", "src/vta/domains/concentration.py"), ""),

    # ---- 부문 03 IFRS 9 ECL
    ("세칙", "별표 4", "03", ("방법론", "문서화"),
     "회계처리 기준이 충당금·손상 인식에 일관되게 적용되는가",
     "automated", ("harness/policies/ifrs9.md",), ""),

    # ---- 부문 05 ALM·IRRBB·유동성
    ("세칙", "별표 3의6", "05", ("산식",),
     "유동성커버리지비율이 국내 산출기준(HQLA 계층·유출입 인정률·유입 한도)으로 재계산되는가",
     "automated", ("harness/liquidity_risk_thresholds.json", "src/vta/domains/liquidity.py"), ""),
    ("세칙", "별표 3의7", "05", ("산식", "데이터"),
     "원화예대율이 월평잔 기준으로 산출되고 양도성예금증서·커버드본드 산입 한도(원화예수금의 1/100·합산 2/100)가 적용되는가",
     "manual", (),
     "하니스에 원화예대율 산출·한도 적용이 없다. ALM 도메인의 예대율은 잔액 기준 관리지표이며 이 기준과 다르다"),
    ("세칙", "별표 3의10", "05", ("산식",),
     "순안정자금조달비율이 국내 산출기준(ASF·RSF 계수)으로 재계산되는가",
     "automated", ("harness/liquidity_risk_thresholds.json", "src/vta/domains/liquidity.py"), ""),
    ("세칙", "별표 9의1", "05", ("산식", "방법론"),
     "금리리스크가 연결재무제표 기준 비트레이딩 포지션(은행계정)에 대해 산출되고 은행계정·신탁계정·자회사가 구분 관리되는가",
     "automated", ("harness/irrbb_thresholds.json", "src/vta/domains/irrbb.py"),
     ""),
    ("세칙", "별표 9의2", "05", ("내부통제",),
     "유동성리스크 관리기준(한도·비상조달계획 등)이 운영되는가",
     "automated", ("harness/policies/liquidity_risk.md", "harness/liquidity_risk_thresholds.json"), ""),
    ("세칙", "별표 14", "05", ("산식",),
     "외화유동성비율 등이 산정방법에 따라 산출되는가",
     "manual", (), "하니스에 외화유동성비율 산출이 없다"),
    ("세칙", "별표 14의1", "05", ("산식",),
     "외화안전자산 보유규모가 산출방법에 따라 산정되는가",
     "manual", (), "하니스에 외화안전자산 산출이 없다"),
    ("세칙", "별표 15의1", "05", ("내부통제",),
     "외화 유동성 리스크 관리기준이 운영되는가",
     "manual", (), "하니스에 외화 유동성 전용 통제가 없다"),
    ("세칙", "제39조", "05", ("산식", "문서화"),
     "외화유동성비율 등의 산정방법이 세칙이 정한 바를 따르는가",
     "manual", (), "하니스에 외환건전성 지표 산출이 없다"),
    ("세칙", "제40조", "05", ("내부통제",),
     "외화유동성비율 등 위반 시 달성계획 제출 절차가 작동하는가",
     "manual", (), "제출 절차는 운영 사실: 하니스 범위 밖"),

    # ---- 부문 06 운영리스크
    ("세칙", "별표 3의11", "06", ("내부통제",),
     "건전한 운영리스크 관리 원칙이 손실자료 수집·경계 설정에 반영되는가",
     "automated", ("harness/operational_risk_thresholds.json", "harness/policies/operational_risk.md"), ""),
    ("세칙", "별표 8의2", "06", ("내부통제",),
     "내부통제평가 부문별 평가항목과 등급 정의가 적용되는가",
     "manual", (), "하니스에 내부통제평가 등급 산정이 없다"),

    # ---- 부문 07 통합위기상황분석
    ("세칙", "제29조의3", "07", ("방법론",),
     "위기상황분석이 세칙이 정한 운용 기준에 따라 실시되는가",
     "automated", ("harness/scenario_floors.json", "harness/policies/macro_scenario.md"), ""),
    ("세칙", "별표 19", "07", ("방법론", "내부통제"),
     "위기상황분석 실시 기준의 목적·적용대상·활용(위험 식별·제어, 타 방법론 보완)이 충족되는가",
     "automated", ("skills/stress_test_validation.md", "harness/scenario_floors.json"), ""),
    ("세칙", "제29조의2", "07", ("내부통제",),
     "내부자본적정성 평가·관리체제가 별표 3의9 기준으로 구축되는가",
     "automated", ("harness/icaap_thresholds.json", "src/vta/domains/icaap.py"), ""),
    ("세칙", "별표 3의9", "07", ("방법론", "내부통제"),
     "내부자본적정성 평가·관리체제의 구축·운용 및 점검이 기준을 충족하는가",
     "automated", ("harness/icaap_thresholds.json", "src/vta/domains/icaap.py"), ""),

    # ---- 부문 08 리스크 적합성검증 (검증 체계 자체)
    ("세칙", "제29조", "08", ("내부통제",),
     "리스크관리실태 평가가 본점·자회사에 대해 연 1회 이상 실시되는가 (제29조제1항)",
     "automated", ("tools/validation_scope.py", "harness/model_materiality.json"),
     ""),
    ("세칙", "별표 9", "08", ("방법론", "내부통제"),
     "리스크평가 기준의 평가 항목·주기·조치 부과기준이 검증 계획에 반영되는가",
     "automated", ("harness/validation_policy.md", "tools/validation_scope.py"), ""),
    ("세칙", "별표 8", "08", ("문서화",),
     "평가등급별 정의가 검증 의견 등급 체계와 정합하는가",
     "automated", ("harness/regulatory_rule_catalog.json",), ""),
    ("세칙", "별표 23", "08", ("문서화",),
     "경영공시 운영기준이 산출물 공시 범위와 정합하는가",
     "manual", (), "하니스는 공시 산출물을 만들지 않는다: 대외 확정은 인간 권한 (CLAUDE.md §5)"),
    ("세칙", "별표 13", "08", ("방법론",),
     "자회사 경영실태평가 기준이 적용되는가",
     "manual", (), "하니스에 자회사 평가 경로가 없다"),
    ("세칙", "제27조", "08", ("내부통제",),
     "경영실태평가 실시 체계가 검증 대상 범위와 연결되는가",
     "manual", (), "경영실태평가는 감독당국 절차: 하니스는 산출값 검증만 한다"),
    ("세칙", "제28조", "08", ("방법론",),
     "경영실태 평가방법·등급 산정이 기준을 따르는가",
     "manual", (), "하니스에 경영실태 등급 산정이 없다"),
)

# 상위 규정(은행업감독규정) 근거 항목: 임계값과 적용 대상이 여기 있다.
CRITERIA_REG: tuple[tuple, ...] = (
    ("규정", "제26조", "01", ("산식", "내부통제"),
     "경영지도비율(자본비율·LCR·원화예대율·NSFR·단순기본자본비율·거액익스포져비율)이 규정이 정한 최소·최대 수준을 충족하는가",
     "automated", ("harness/capital_adequacy_thresholds.json", "harness/liquidity_risk_thresholds.json",
                   "harness/concentration_thresholds.json"), ""),
    ("규정", "제26조", "05", ("내부통제",),
     "원화예대율이 적용 제외 대상인지 판정되는가: 직전분기말월 원화대출금 4조원 미만 은행은 적용하지 않는다 (제26조제1항 단서)",
     "manual", (), "하니스에 원화예대율 자체가 없어 적용 대상 판정도 없다"),
    ("규정", "제26조의2", "01", ("내부통제",),
     "금융체계상 중요한 은행 추가자본이 자본요구에 반영되고, 선정 외은지점의 LCR 100% 유지 의무가 구분되는가",
     "automated", ("harness/capital_adequacy_thresholds.json",), ""),
    ("규정", "제26조의3", "01", ("내부통제",),
     "경기대응완충자본이 위험가중자산의 0~2.5% 범위에서 반영되고 해외 차주는 해당국 수준을 감안하는가",
     "automated", ("harness/capital_adequacy_thresholds.json",), ""),
    ("규정", "별표 2의10", "01", ("산식",),
     "완충자본을 포함한 자본비율 요구(2019.1.1. 이후 CET1 7.0+K · T1 8.5+K · 총자본 10.5+K, K=D-SIB 추가자본+경기대응완충자본)가 적용되는가",
     "automated", ("harness/capital_adequacy_thresholds.json", "src/vta/domains/capital.py"), ""),
    ("규정", "별표 2의11", "01", ("내부통제",),
     "완충자본 미달 구간별 이익 배당 등의 최저 내부유보비율이 적용되는가",
     "manual", (), "하니스는 미달 사실만 표시하고 구간별 내부유보비율을 산정하지 않는다"),
    ("규정", "제26조의4", "07", ("내부통제",),
     "자체정상화계획이 작성기준(별표 9)에 따라 수립되는가",
     "manual", (), "하니스에 자체정상화계획 검증 경로가 없다"),
    ("규정", "제27조", "02", ("데이터", "방법론"),
     "자산건전성 분류가 별표 3 분류기준에 따라 이루어지는가",
     "automated", ("harness/policies/credit_scoring.md",), ""),
    ("규정", "제29조", "03", ("산식",),
     "대손충당금등 적립기준이 충족되는가: 최저적립액 대비 충당금은 합계 기준으로 대비한다",
     "automated", ("harness/policies/ifrs9.md",), ""),
    ("규정", "제30조", "07", ("내부통제",),
     "리스크관리체제와 내부자본적정성 평가·관리체제가 규정이 요구하는 수준으로 구축·운용되는가",
     "automated", ("harness/icaap_thresholds.json", "src/vta/domains/icaap.py"), ""),
    ("규정", "별표 3", "02", ("데이터",),
     "자산건전성 분류기준(정상·요주의·고정·회수의문·추정손실)이 적용되는가",
     "automated", ("harness/policies/credit_scoring.md",), ""),
    ("규정", "별표 5", "08", ("방법론",),
     "경영실태평가 부문별 평가항목이 검증 범위와 대응되는가",
     "manual", (), "하니스에 경영실태평가 항목 산정이 없다"),
    ("규정", "별표 6", "02", ("방법론",),
     "주택 관련 담보대출 리스크관리기준이 적용되는가",
     "manual", (), "하니스에 주담대 규제비율 점검이 없다"),
)


# PD 설계 구분(TTC·PIT) 검증 항목. 근거는 세칙 별표 3 이 명시하므로 국내가 지배한다.
CRITERIA_PD: tuple[tuple, ...] = (
    ("세칙", "별표 3", "02", ("데이터", "방법론"),
     "PD 추정 관측기간이 5년 이상이고 경기순환주기를 반영하며 과거 1년 부도율의 평균을 기초로 산출되는가",
     "automated", ("harness/pd_design_thresholds.json", "tools/pd_cyclicality.py",
                   "harness/policies/pd_lgd_ead.md"), ""),
    ("세칙", "별표 3", "02", ("방법론",),
     "TTC 를 주장하는 PD 가 실제로 경기에 둔감한가: 등급별 PD 변동계수와 평균 PD 변동의 등급 이동분 비중으로 판정한다",
     "automated", ("tools/pd_cyclicality.py", "harness/pd_design_thresholds.json"), ""),
    ("세칙", "별표 3", "02", ("방법론", "데이터"),
     "등급별 PD 가 거시변수와 유의하게 상관되지 않는가: 상관되면 TTC 라는 주장과 자료가 어긋난다",
     "automated", ("tools/pd_cyclicality.py",), ""),
    ("규정", "제29조", "03", ("방법론",),
     "PIT 를 주장하는 PD 가 실현 1년 부도율 시계열을 추종하는가: 상관·평균절대편차·방향 일치율로 판정한다",
     "automated", ("tools/pd_cyclicality.py", "harness/pd_design_thresholds.json"), ""),
    ("세칙", "별표 3", "02", ("산식",),
     "TTC 와 PIT 의 단일요인 변환이 왕복에서 복원되고 국면 부호가 뒤집히지 않는가 (호황 PIT<TTC · 침체 PIT>TTC)",
     "automated", ("tools/pd_cyclicality.py",), ""),
    ("세칙", "별표 3", "02", ("방법론", "문서화"),
     "같은 등급체계를 IRB 자본(TTC)과 IFRS 9 ECL(PIT)에 함께 쓸 때 두 산출물의 PD 가 변환 관계로 설명되는가",
     "manual", (),
     "하니스는 두 산출물을 한 실행에서 받지 않는다. 변환 도구는 있으나 자본용·ECL용 PD 를 동시에 입력받는 경로가 없어 사람 대조로 남긴다"),
)


# 계량 임계: 규정 값과 하니스 임계 파일을 기계가 대조한다.
#
# (근거, 인용, 키, 한글명, 규정값, 방향, 원문 발췌, 하니스 파일, JSON 경로)
#
# 방향 'min' 은 은행이 그 값 **이상**을 유지해야 한다는 뜻이다. 하니스 임계가
# 규정보다 낮으면 규제를 통과시켜 버리므로 위반이고, 높으면 더 엄격한 내부
# 기준이므로 통과시키되 보고한다. 'max' 는 반대다.
THRESHOLDS: tuple[tuple, ...] = (
    ("규정", "제26조", "cet1_min", "보통주자본비율 최소", 0.045, "min",
     "보통주자본비율 : 100분의 4.5",
     "harness/capital_adequacy_thresholds.json", ("minimum_ratios", "cet1_min")),
    ("규정", "제26조", "tier1_min", "기본자본비율 최소", 0.06, "min",
     "기본자본비율 : 100분의 6",
     "harness/capital_adequacy_thresholds.json", ("minimum_ratios", "tier1_min")),
    ("규정", "제26조", "total_capital_min", "총자본비율 최소", 0.08, "min",
     "총자본비율 : 100분의 8",
     "harness/capital_adequacy_thresholds.json", ("minimum_ratios", "total_capital_min")),
    ("규정", "제26조", "lcr_min", "유동성커버리지비율 최소", 1.00, "min",
     "유동성커버리지비율\"이라 한다) : 100분의 100 이상",
     "harness/liquidity_risk_thresholds.json", ("lcr_min",)),
    ("규정", "제26조", "nsfr_min", "순안정자금조달비율 최소", 1.00, "min",
     "순안정자금조달비율\"이라 한다) : 100분의 100 이상",
     "harness/liquidity_risk_thresholds.json", ("nsfr_min",)),
    ("규정", "제26조", "leverage_ratio_min", "단순기본자본비율 최소", 0.03, "min",
     "단순기본자본비율\"이라 한다) : 100분의 3 이상",
     "harness/capital_adequacy_thresholds.json", ("leverage_ratio_min",)),
    ("규정", "제26조", "single_counterparty_limit", "거액익스포져비율 한도", 0.25, "max",
     "거액익스포져비율\"이라 한다) : 100분의 25 이하",
     "harness/concentration_thresholds.json", ("single_counterparty_limit_pct_tier1",)),
    ("규정", "제26조의2", "gsib_interbank_limit", "글로벌 중요 은행 간 거액익스포져 한도", 0.15, "max",
     "다른 글로벌 금융체계상 중요한 은행에 대한 거액익스포져비율을 100분의 15 이하",
     "harness/concentration_thresholds.json", ("gsib_interbank_limit_pct_tier1",)),
    ("규정", "제26조의3", "countercyclical_buffer_max", "경기대응완충자본 상한", 0.025, "max",
     "100분의 0부터 2.5까지",
     "harness/capital_adequacy_thresholds.json", ("buffers", "countercyclical_buffer_max")),
    ("규정", "별표 2의10", "conservation_buffer", "자본보전완충자본", 0.025, "min",
     "7.0 + K",
     "harness/capital_adequacy_thresholds.json", ("buffers", "conservation_buffer")),
    ("세칙", "별표 3", "pd_min_observation_years", "PD 추정 최소 관측기간(년)", 5, "min",
     "은행은 PD 추정시 5년 이상의 관측기간에 걸친 외부 데이터, 내부 데이터 또는 금융기관간 공유 데이터 중 하나 이상을 이용하여야 한다",
     "harness/pd_design_thresholds.json", ("ttc", "min_observation_years")),
)


def dig(obj, path):
    for k in path:
        if not isinstance(obj, dict) or k not in obj:
            return None
        obj = obj[k]
    return obj


def compare(regulated: float, harness: float | None, direction: str) -> str:
    """하니스 임계가 규정을 통과시키는가. 'ok' · 'stricter' · 'looser' · 'missing'."""
    if harness is None:
        return "missing"
    if regulated == harness:
        return "ok"
    if direction == "min":
        return "stricter" if harness > regulated else "looser"
    return "stricter" if harness < regulated else "looser"


# 같은 조문·별표를 인용해도 대응 바젤 Chapter 가 다를 수 있다. 검증 기준 문장으로
# 지정하며 BASEL_MAP 보다 우선한다.
BASEL_MAP_BY_CRITERION: dict[str, tuple[str, bool]] = {
    "PD 추정 관측기간이 5년 이상이고 경기순환주기를 반영하며 과거 1년 부도율의 평균을 기초로 산출되는가":
        ("CRE36", False),
    "TTC 를 주장하는 PD 가 실제로 경기에 둔감한가: 등급별 PD 변동계수와 평균 PD 변동의 등급 이동분 비중으로 판정한다":
        ("CRE36", False),
    "등급별 PD 가 거시변수와 유의하게 상관되지 않는가: 상관되면 TTC 라는 주장과 자료가 어긋난다":
        ("CRE36", False),
    "TTC 와 PIT 의 단일요인 변환이 왕복에서 복원되고 국면 부호가 뒤집히지 않는가 (호황 PIT<TTC · 침체 PIT>TTC)":
        ("CRE32", True),
    "같은 등급체계를 IRB 자본(TTC)과 IFRS 9 ECL(PIT)에 함께 쓸 때 두 산출물의 PD 가 변환 관계로 설명되는가":
        ("CRE35", True),
}


# 국내 항목 → 대응 바젤 Chapter. 대응이 없으면 국내 고유 기준이다.
# 세 번째 값 True 는 국내 해석이 모호해 바젤로 보충한다는 뜻이다 (규칙 ③).
BASEL_MAP: dict[tuple[str, str], tuple[str, bool]] = {
    ("규정", "제26조"): ("RBC20", False),
    ("규정", "제26조의2"): ("RBC40", False),
    ("규정", "제26조의3"): ("RBC30", False),
    ("규정", "별표 2의10"): ("RBC30", False),
    ("규정", "별표 2의11"): ("DIS26", True),
    ("규정", "제26조의4"): ("SRP30", True),
    ("규정", "제29조"): ("CRE35", True),
    ("규정", "제30조"): ("SRP30", False),
    ("세칙", "별표 3"): ("CRE20", False),
    ("세칙", "별표 3의2"): ("MAR20", False),
    ("세칙", "별표 3의6"): ("LCR20", False),
    ("세칙", "별표 3의8"): ("LEV20", False),
    ("세칙", "별표 3의9"): ("SRP30", False),
    ("세칙", "별표 3의10"): ("NSF30", False),
    ("세칙", "별표 3의11"): ("OPE10", True),
    ("세칙", "별표 3의12"): ("LEX20", False),
    ("세칙", "별표 9의1"): ("SRP31", False),
    ("세칙", "별표 9의2"): ("SRP50", True),
    ("세칙", "별표 19"): ("SRP30", True),
    ("세칙", "제29조의2"): ("SRP20", False),
    ("세칙", "제29조의3"): ("SRP30", True),
    ("세칙", "별표 15"): ("LEX30", True),
}

# 국내 기준이 정하지 않아 바젤이 지배하는 주제 (규칙 ②).
# (인용, 부문, 관점, 기준, 자동화, 근거, 비고)
CRITERIA_BASEL: tuple[tuple, ...] = (
    ("바젤", "CRE52", "02", ("산식",),
     "거래상대방 신용리스크 익스포저가 SA-CCR(RC + α·PFE, α=1.4)로 산출되는가",
     "automated", ("harness/ccr_thresholds.json", "src/vta/domains/ccr.py"),
     "국내 세칙은 CCR 산출을 별표 3 체계 안에서 다루며 SA-CCR 전용 기준을 따로 두지 않는다"),
    ("바젤", "MAR50", "04", ("산식",),
     "CVA 리스크 자본이 BA-CVA/SA-CVA 체계로 산출되고 소요자본과 RWA의 차원(12.5배)이 구분되는가",
     "automated", ("harness/cva_thresholds.json", "src/vta/domains/cva.py"),
     "국내 기준에 CVA 전용 산출 체계가 별도로 없다"),
    ("바젤", "CRE60", "02", ("산식",),
     "집합투자증권 익스포저가 LTA·MBA·fallback 계층으로 산출되는가",
     "automated", ("harness/basel_risk_taxonomy.json",),
     "국내 기준에 펀드 익스포저 전용 산출 계층이 별도로 없다"),
    ("바젤", "CRE40", "02", ("산식",),
     "유동화 익스포저가 SEC-IRBA→SEC-ERBA→SEC-SA 계층 순서로 산출되는가",
     "automated", ("harness/basel_risk_taxonomy.json",),
     "국내 기준에 유동화 접근법 계층 전용 규정이 별도로 없다"),
    ("바젤", "MAR32", "04", ("방법론",),
     "내부모형 접근법의 백테스팅과 손익귀속검정(PLA)이 수행되는가",
     "automated", ("harness/market_risk_thresholds.json", "src/vta/domains/market.py"),
     "국내는 표준·간편법 중심이라 IMA 백테스팅 기준을 별도로 두지 않는다"),
    ("바젤", "CRE35", "03", ("산식",),
     "IRB 기대손실과 적격충당금의 대비가 자본에서 처리되고 EAD 차감과 이중계상되지 않는가",
     "automated", ("harness/policies/ifrs9.md",), ""),
    ("바젤", "DIS20", "08", ("문서화",),
     "위험관리 개요·핵심 건전성 지표·RWA 공시 서식이 산출물 구조와 대응되는가",
     "manual", (), "하니스는 공시 서식을 만들지 않는다: 대외 확정은 인간 권한"),
    ("바젤", "SCO60", "02", ("데이터", "방법론"),
     "가상자산 익스포저의 분류·자본 처리 기준이 적용되는가",
     "manual", (), "하니스에 가상자산 익스포저 경로가 없다. 국내 기준에도 대응 조항이 없어 바젤이 지배한다"),
    ("바젤", "MGN20", "04", ("내부통제",),
     "비청산 파생상품의 증거금 요건이 적용되는가",
     "manual", (), "하니스에 증거금 요건 검증이 없다"),
    ("바젤", "SRP36", "01", ("데이터", "내부통제"),
     "리스크 데이터 집계와 리스크 보고 원칙(RDARR)이 충족되는가",
     "automated", ("harness/data_definition.md", "middleware/schema_guard.py"),
     "국내 기준에 RDARR 대응 조항이 별도로 없다"),
)


def governing_of(source_key: str, ambiguous: bool) -> str:
    """기준 스택 규칙 적용: 손으로 판단하지 않는다."""
    if source_key == "바젤":
        return "바젤"
    return "국내+바젤보충" if ambiguous else "국내"



def build() -> dict:
    lines = {k: _lines(k) for k in SOURCES}
    digests = {k: hashlib.sha256(source_path(k).read_bytes()).hexdigest() for k in SOURCES}

    items, unresolved = [], []
    for idx, row in enumerate(CRITERIA + CRITERIA_REG + CRITERIA_PD + CRITERIA_BASEL, 1):
        src, cite, section, lenses, criterion, automation, evidence, note = row
        ln = resolve(cite, lines[src])
        if ln is None:
            unresolved.append(f"{src} {cite}")
            continue
        ref, ambiguous = BASEL_MAP_BY_CRITERION.get(
            criterion, BASEL_MAP.get((src, cite), (None, False)))
        if src == "바젤":
            ref, ambiguous = basel_chapter(cite), False
        if ref is not None and resolve(ref, lines["바젤"]) is None:
            unresolved.append(f"바젤 {ref} (대응 Chapter)")
            continue
        items.append({
            "rule_id": f"KR-{idx:03d}" if src != "바젤" else f"BIS-{idx:03d}",
            "source_key": src,
            "basis_level": BASIS_LEVEL[src],
            "citation": cite,
            "source_heading": heading_of(ln, lines[src]),
            "source_line": ln,
            "basel_ref": ref,
            "ambiguous_domestic": ambiguous,
            "governing": governing_of(src, ambiguous),
            "section": section,
            "section_name": SECTIONS[section],
            "lens": list(lenses),
            "criterion": criterion,
            "automation": automation,
            "evidence": list(evidence),
            "note": note,
        })

    thresholds = []
    for src, cite, key, korean, value, direction, quote, hfile, jpath in THRESHOLDS:
        ln = resolve(cite, lines[src])
        if ln is None:
            unresolved.append(f"{src} {cite}")
            continue
        if not any(quote in l for l in lines[src]):
            unresolved.append(f"{src} {cite} 발췌 미확인: {quote}")
            continue
        harness_value = dig(json.loads((ROOT / hfile).read_text(encoding="utf-8")), jpath)
        thresholds.append({
            "key": key,
            "korean": korean,
            "source_key": src,
            "basis_level": BASIS_LEVEL[src],
            "citation": cite,
            "source_line": ln,
            "regulated_value": value,
            "direction": direction,
            "quote": quote,
            "harness_file": hfile,
            "harness_path": list(jpath),
            "harness_value": harness_value,
            "status": compare(value, harness_value, direction),
        })
    if unresolved:
        raise SystemExit(f"원문에서 해석되지 않음: {sorted(set(unresolved))}")

    sources = {}
    for k, meta in SOURCES.items():
        ls = lines[k]
        entry = {**meta, "basis_level": BASIS_LEVEL[k], "sha256": digests[k]}
        if k == "바젤":
            entry["n_current_chapters"] = count_current_chapters(ls)
            entry["text_scope"] = (
                "Chapter 단위 source map: BIS 이용조건상 원문 전문을 복제하지 "
                "않는다. Chapter 실재·시행일·공식 URL 까지 대조되며 paragraph "
                "문구 대조는 이 소스북으로 할 수 없다.")
        else:
            entry["n_schedules"] = sum(1 for l in ls if l.startswith("## [별표"))
            entry["n_article_headings"] = sum(1 for l in ls if l.startswith("##### 제"))
        sources[k] = entry

    return {
        "schema_version": "3.0",
        "policy_version": "3.0",
        "sources": sources,
        "precedence": PRECEDENCE,
        "description": (
            "규제 기준(국내 규정·세칙 + 국제 바젤)에서 전개한 적합성검증 항목. "
            "국내 기준이 우선하고, 국내가 정하지 않은 주제는 바젤이 지배하며, "
            "국내 해석이 모호하면 바젤로 보충한다 (precedence 참조). 각 항목의 "
            "citation 은 해당 원문에서 해석되고 source_line 은 손으로 적지 않고 "
            "파생한다. thresholds 는 규정이 정한 계량 임계를 하니스 임계 파일과 "
            "대조한 결과이며 하니스가 규정보다 느슨하면 'looser' 로 드러난다. "
            "바젤 근거는 Chapter 단위 대조까지만 가능하다."
        ),
        "automation_definition": {
            "automated": "하니스에 실행 가능한 통제가 존재 (evidence 1건 이상 실재 필수)",
            "manual": "기준을 덮는 통제가 없어 사람 검토로 남김 (note 필수)",
        },
        "threshold_status_definition": {
            "ok": "하니스 임계가 규정 값과 같다",
            "stricter": "하니스 임계가 규정보다 엄격하다: 통과시키되 보고한다",
            "looser": "하니스 임계가 규정보다 느슨하다: 규제 미달을 통과시키므로 위반이다",
            "missing": "하니스 임계 파일에 해당 값이 없다",
        },
        "sections": SECTIONS,
        "lenses": list(LENSES),
        "criteria": items,
        "thresholds": thresholds,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="harness/regulatory_criteria.json")
    args = ap.parse_args(argv)
    data = build()
    Path(args.out).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    n = len(data["criteria"])
    auto = sum(1 for c in data["criteria"] if c["automation"] == "automated")
    th = data["thresholds"]
    bad = [t for t in th if t["status"] in ("looser", "missing")]
    from collections import Counter
    g = Counter(c["governing"] for c in data["criteria"])
    print(f'{args.out}: 검증 항목 {n}건 (automated {auto}) · '
          f'지배기준 국내 {g["국내"]} · 국내+바젤보충 {g["국내+바젤보충"]} · 바젤 {g["바젤"]} · '
          f'계량 임계 {len(th)}건 (규정 미달 {len(bad)})')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
