"""국내 감독규정 → 적합성검증 항목 생성기.

근거 원문(은행업감독업무시행세칙)을 저장소에 두고, 각 검증 항목의 인용이
**원문에서 실제로 해석되는지** 생성 시점에 확인한다. 해석되지 않는 인용은
카탈로그에 실리지 않는다 — 인용이 규정 원문과 맞는지 검증하지 못하던 상태
(이월 CO-004)를 시행세칙 범위에서 닫기 위한 것이다.

라인 번호는 손으로 적지 않는다. 인용 문자열에서 원문을 찾아 파생한다.

사용:
    python -m tools.gen_domestic_criteria --out harness/domestic_rule_criteria.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "harness" / "reference" / "bank_supervision_rules_20260630.md"

SOURCE_TITLE = "은행업감독업무시행세칙"
SOURCE_EFFECTIVE = "2026-06-30"
SOURCE_PROMULGATION = "금융감독원세칙 제9999호, 2026. 6. 26., 일부개정"
SOURCE_URL = "https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq=2200000108789"
BASIS_LEVEL = "국내구속"   # harness/regulatory_rule_catalog.json 의 근거수준 어휘

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

def _lines() -> list[str]:
    return SOURCE.read_text(encoding="utf-8").splitlines()


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
    return None


def heading_of(line_no: int, lines: list[str]) -> str:
    return lines[line_no - 1].lstrip("#").strip()


# ---------------------------------------------------------------- 검증 항목
#
# (인용, 부문, 검증관점, 검증 기준, 자동화, 하니스 근거, 비고)
#
# 자동화는 하니스에 통제가 실재할 때만 'automated' 다. 국내 기준을 덮지 못하면
# 'manual' 로 두고 무엇이 없는지 적는다 — 인용이 있다는 것과 통제가 있다는 것은
# 다르다.
CRITERIA: tuple[tuple, ...] = (
    # ---- 부문 01 RDM·BIS비율
    ("제17조", "01", ("내부통제", "산식"),
     "경영지도비율의 산정기준이 세칙이 지정한 별표(3·3의2·3의3·3의4·3의5·3의6·3의7·3의8·3의10·3의12)를 따르는가",
     "automated", ("harness/capital_adequacy_thresholds.json", "harness/policies/capital_adequacy.md"),
     ""),
    ("제17조", "01", ("데이터", "내부통제"),
     "산정 시점이 지표별로 구분되는가 — 자기자본비중·단순기본자본비율·NSFR·거액익스포져비율은 가결산일·결산일 현재, LCR·원화예대율은 매월 평잔 (제17조제2항)",
     "manual", (),
     "하니스는 LCR·원화예대율을 시점값 하나로 받는다. 월평잔 여부를 판별할 입력이 없어 사람 확인 항목으로 남긴다 — 시점값을 평잔으로 보고하면 잡지 못한다"),
    ("제17조", "01", ("내부통제",),
     "완충자본 포함 자본비율 미달이 예상될 때 배당·자사주매입·성과연동상여 제한과 자본계획 승인 절차로 연결되는가 (제17조제3항)",
     "automated", ("harness/capital_adequacy_thresholds.json", "src/vta/domains/capital.py"),
     ""),
    ("별표 3", "01", ("산식",),
     "신용·운영리스크 위험가중자산과 자기자본비율 산출이 바젤Ⅲ 국내 기준에 따라 재계산되는가",
     "automated", ("harness/basel_risk_taxonomy.json", "src/vta/domains/capital.py"), ""),
    ("별표 3의2", "04", ("산식",),
     "시장리스크를 포함한 위험가중자산 산출기준이 적용되는가",
     "automated", ("harness/market_risk_thresholds.json", "src/vta/domains/market.py"), ""),
    ("별표 3의8", "01", ("산식",),
     "단순기본자본비율(레버리지비율)이 국내 산출기준으로 재계산되는가",
     "automated", ("harness/capital_adequacy_thresholds.json", "src/vta/domains/capital.py"), ""),
    ("별표 3의12", "02", ("산식",),
     "거액익스포져비율(LEX)이 산출기준에 따라 산정되고 한도 저촉이 판정되는가",
     "automated", ("harness/concentration_thresholds.json", "src/vta/domains/concentration.py"), ""),
    ("별표 7", "01", ("데이터", "산식"),
     "경영실태평가 계량지표가 정해진 산정기준으로 산출되는가",
     "manual", (),
     "하니스에 경영실태평가 계량지표 산출 경로가 없다"),
    ("별표 11", "01", ("데이터",),
     "자산·부채 항목별 평가·산정이 세부기준을 따르는가",
     "manual", (), "하니스에 항목별 평가기준 대조가 없다"),
    ("별표 20", "01", ("내부통제",),
     "시스템적 중요도 산정과 추가자본 부과가 세부기준에 따라 반영되는가",
     "automated", ("harness/capital_adequacy_thresholds.json",), ""),
    ("별표 21", "01", ("내부통제",),
     "경기대응완충자본이 세부기준에 따라 자본요구에 반영되는가",
     "automated", ("harness/capital_adequacy_thresholds.json",), ""),

    # ---- 부문 02 신용리스크·RWA
    ("제18조", "02", ("문서화", "내부통제"),
     "자산건전성 분류기준·대손충당금 적립 기준과 그 결과 보고가 매분기 종료 후 20일 이내에 이루어지는가",
     "manual", (),
     "보고 기한 준수는 운영 사실 — 하니스는 산출값만 검증하며 제출 시점 데이터를 갖지 않는다"),
    ("별표 12", "02", ("데이터", "산식"),
     "무수익여신 산정이 기준에 따라 이루어지는가",
     "manual", (), "하니스에 무수익여신 산정 검증이 없다"),
    ("별표 18", "02", ("방법론",),
     "주택관련 담보대출의 LTV·DTI 등 리스크관리 세부기준이 적용되는가",
     "manual", (), "하니스에 주담대 규제비율 점검이 없다"),
    ("별표 24", "02", ("내부통제",),
     "조기경보제도와 여신감리제도가 기준에 따라 운영되는가",
     "automated", ("harness/validation_triggers.json", "tools/validation_trigger.py"),
     ""),
    ("별표 15", "04", ("내부통제",),
     "국가별·거액신용·시장리스크 관리기준이 한도 체계로 운영되는가",
     "automated", ("harness/concentration_thresholds.json", "src/vta/domains/concentration.py"), ""),

    # ---- 부문 03 IFRS 9 ECL
    ("별표 4", "03", ("방법론", "문서화"),
     "회계처리 기준이 충당금·손상 인식에 일관되게 적용되는가",
     "automated", ("harness/policies/ifrs9.md",), ""),

    # ---- 부문 05 ALM·IRRBB·유동성
    ("별표 3의6", "05", ("산식",),
     "유동성커버리지비율이 국내 산출기준(HQLA 계층·유출입 인정률·유입 한도)으로 재계산되는가",
     "automated", ("harness/liquidity_risk_thresholds.json", "src/vta/domains/liquidity.py"), ""),
    ("별표 3의7", "05", ("산식", "데이터"),
     "원화예대율이 월평잔 기준으로 산출되고 양도성예금증서·커버드본드 산입 한도(원화예수금의 1/100·합산 2/100)가 적용되는가",
     "manual", (),
     "하니스에 원화예대율 산출·한도 적용이 없다. ALM 도메인의 예대율은 잔액 기준 관리지표이며 이 기준과 다르다"),
    ("별표 3의10", "05", ("산식",),
     "순안정자금조달비율이 국내 산출기준(ASF·RSF 계수)으로 재계산되는가",
     "automated", ("harness/liquidity_risk_thresholds.json", "src/vta/domains/liquidity.py"), ""),
    ("별표 9의1", "05", ("산식", "방법론"),
     "금리리스크가 연결재무제표 기준 비트레이딩 포지션(은행계정)에 대해 산출되고 은행계정·신탁계정·자회사가 구분 관리되는가",
     "automated", ("harness/irrbb_thresholds.json", "src/vta/domains/irrbb.py"),
     ""),
    ("별표 9의2", "05", ("내부통제",),
     "유동성리스크 관리기준(한도·비상조달계획 등)이 운영되는가",
     "automated", ("harness/policies/liquidity_risk.md", "harness/liquidity_risk_thresholds.json"), ""),
    ("별표 14", "05", ("산식",),
     "외화유동성비율 등이 산정방법에 따라 산출되는가",
     "manual", (), "하니스에 외화유동성비율 산출이 없다"),
    ("별표 14의1", "05", ("산식",),
     "외화안전자산 보유규모가 산출방법에 따라 산정되는가",
     "manual", (), "하니스에 외화안전자산 산출이 없다"),
    ("별표 15의1", "05", ("내부통제",),
     "외화 유동성 리스크 관리기준이 운영되는가",
     "manual", (), "하니스에 외화 유동성 전용 통제가 없다"),
    ("제39조", "05", ("산식", "문서화"),
     "외화유동성비율 등의 산정방법이 세칙이 정한 바를 따르는가",
     "manual", (), "하니스에 외환건전성 지표 산출이 없다"),
    ("제40조", "05", ("내부통제",),
     "외화유동성비율 등 위반 시 달성계획 제출 절차가 작동하는가",
     "manual", (), "제출 절차는 운영 사실 — 하니스 범위 밖"),

    # ---- 부문 06 운영리스크
    ("별표 3의11", "06", ("내부통제",),
     "건전한 운영리스크 관리 원칙이 손실자료 수집·경계 설정에 반영되는가",
     "automated", ("harness/operational_risk_thresholds.json", "harness/policies/operational_risk.md"), ""),
    ("별표 8의2", "06", ("내부통제",),
     "내부통제평가 부문별 평가항목과 등급 정의가 적용되는가",
     "manual", (), "하니스에 내부통제평가 등급 산정이 없다"),

    # ---- 부문 07 통합위기상황분석
    ("제29조의3", "07", ("방법론",),
     "위기상황분석이 세칙이 정한 운용 기준에 따라 실시되는가",
     "automated", ("harness/scenario_floors.json", "harness/policies/macro_scenario.md"), ""),
    ("별표 19", "07", ("방법론", "내부통제"),
     "위기상황분석 실시 기준의 목적·적용대상·활용(위험 식별·제어, 타 방법론 보완)이 충족되는가",
     "automated", ("skills/stress_test_validation.md", "harness/scenario_floors.json"), ""),
    ("제29조의2", "07", ("내부통제",),
     "내부자본적정성 평가·관리체제가 별표 3의9 기준으로 구축되는가",
     "automated", ("harness/icaap_thresholds.json", "src/vta/domains/icaap.py"), ""),
    ("별표 3의9", "07", ("방법론", "내부통제"),
     "내부자본적정성 평가·관리체제의 구축·운용 및 점검이 기준을 충족하는가",
     "automated", ("harness/icaap_thresholds.json", "src/vta/domains/icaap.py"), ""),

    # ---- 부문 08 리스크 적합성검증 (검증 체계 자체)
    ("제29조", "08", ("내부통제",),
     "리스크관리실태 평가가 본점·자회사에 대해 연 1회 이상 실시되는가 (제29조제1항)",
     "automated", ("tools/validation_scope.py", "harness/model_materiality.json"),
     ""),
    ("별표 9", "08", ("방법론", "내부통제"),
     "리스크평가 기준의 평가 항목·주기·조치 부과기준이 검증 계획에 반영되는가",
     "automated", ("harness/validation_policy.md", "tools/validation_scope.py"), ""),
    ("별표 8", "08", ("문서화",),
     "평가등급별 정의가 검증 의견 등급 체계와 정합하는가",
     "automated", ("harness/regulatory_rule_catalog.json",), ""),
    ("별표 23", "08", ("문서화",),
     "경영공시 운영기준이 산출물 공시 범위와 정합하는가",
     "manual", (), "하니스는 공시 산출물을 만들지 않는다 — 대외 확정은 인간 권한 (CLAUDE.md §5)"),
    ("별표 13", "08", ("방법론",),
     "자회사 경영실태평가 기준이 적용되는가",
     "manual", (), "하니스에 자회사 평가 경로가 없다"),
    ("제27조", "08", ("내부통제",),
     "경영실태평가 실시 체계가 검증 대상 범위와 연결되는가",
     "manual", (), "경영실태평가는 감독당국 절차 — 하니스는 산출값 검증만 한다"),
    ("제28조", "08", ("방법론",),
     "경영실태 평가방법·등급 산정이 기준을 따르는가",
     "manual", (), "하니스에 경영실태 등급 산정이 없다"),
)


def build() -> dict:
    lines = _lines()
    digest = hashlib.sha256(SOURCE.read_bytes()).hexdigest()

    items = []
    unresolved = []
    for idx, (cite, section, lenses, criterion, automation, evidence, note) in enumerate(CRITERIA, 1):
        ln = resolve(cite, lines)
        if ln is None:
            unresolved.append(cite)
            continue
        items.append({
            "rule_id": f"KR-{idx:03d}",
            "citation": cite,
            "source_heading": heading_of(ln, lines),
            "source_line": ln,
            "basis_level": BASIS_LEVEL,
            "section": section,
            "section_name": SECTIONS[section],
            "lens": list(lenses),
            "criterion": criterion,
            "automation": automation,
            "evidence": list(evidence),
            "note": note,
        })
    if unresolved:
        raise SystemExit(f"원문에서 해석되지 않는 인용: {sorted(set(unresolved))}")

    # 원문 구조 인덱스 — 인용 가능한 단위를 세서 남긴다 (손으로 적지 않는다)
    schedules = [l for l in lines if l.startswith("## [별표")]
    articles = [l for l in lines if l.startswith("##### 제")]
    return {
        "schema_version": "1.0",
        "policy_version": "1.0",
        "source": {
            "title": SOURCE_TITLE,
            "effective": SOURCE_EFFECTIVE,
            "promulgation": SOURCE_PROMULGATION,
            "url": SOURCE_URL,
            "path": str(SOURCE.relative_to(ROOT)),
            "sha256": digest,
            "n_schedules": len(schedules),
            "n_article_headings": len(articles),
        },
        "description": (
            "국내 은행업감독업무시행세칙에서 전개한 적합성검증 항목. 각 항목의 "
            "citation 은 저장소에 보관한 원문에서 해석되며 source_line 은 손으로 "
            "적지 않고 파생한다 — 인용이 원문과 맞는지 검증하지 못하던 상태(이월 "
            "CO-004)를 시행세칙 범위에서 닫는다. automation='automated' 는 하니스에 "
            "통제가 실재함을 뜻하고 근거 파일이 실재해야 주장할 수 있다. 인용이 "
            "해석된다는 것은 조문·별표가 존재한다는 뜻이지 그 내용을 다 덮는다는 "
            "뜻이 아니다."
        ),
        "automation_definition": {
            "automated": "하니스에 실행 가능한 통제가 존재 (evidence 1건 이상 실재 필수)",
            "manual": "국내 기준을 덮는 통제가 없어 사람 검토로 남김 (note 필수)",
        },
        "sections": SECTIONS,
        "lenses": list(LENSES),
        "criteria": items,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default="harness/domestic_rule_criteria.json")
    args = ap.parse_args(argv)
    data = build()
    Path(args.out).write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    n = len(data["criteria"])
    auto = sum(1 for c in data["criteria"] if c["automation"] == "automated")
    print(f'{args.out} — 국내 검증 항목 {n}건 (automated {auto}) · '
          f'원문 별표 {data["source"]["n_schedules"]} · 조문 heading '
          f'{data["source"]["n_article_headings"]}')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
