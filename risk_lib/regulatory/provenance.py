"""업무보고서 라인의 산출 근거 분류와 원장 교체 경로.

합성 데이터로 서식을 채우면 어떤 값은 실제 산출이고 어떤 값은 원장이 없어
파생한 것이다. **둘이 섞여 보이면 제출본이 성립하지 않는다** — 감독당국은
"이 숫자 어디서 나왔나"에 라인 단위로 답할 것을 요구하고, 실데이터 전환
시점에는 "어떤 원장을 확보하면 어느 라인이 실측으로 바뀌는가"를 알아야
이행 계획을 세울 수 있다.

이 모듈은 두 가지를 만든다.

    provenance_frame()    라인별 산출 근거 (실측 · 파생 · 대용 · 미산출 · 미영위)
    ledger_impact_frame() 원장별로 해소되는 서식·라인 수

## 분류 방법과 그 한계

라인의 `formula` · `text_value`를 규칙으로 판정한다. 자유 텍스트 판정이라
완벽하지 않으므로 **순서를 정해 오탐을 먼저 걷어낸다**.

    1. 부정        "파생이 아니라" · "파생하지 않았다" → 실측
    2. 동음이의    "파생상품" · "파생거래" · "파생 + SFT" → 실측
                   (derivative를 뜻하지 derived를 뜻하지 않는다)
    3. 긍정        "파생값" · "파생 배수" · "대용" · "미보유" · …

분류되지 않은 채 파생 관련 어휘를 품은 라인은 `unclassified()`가 되돌려
준다. 감춰지지 않게 하려는 것이다 — 분류가 조용히 실패하면 파생값이 실측으로
보고된다. 라인이 `basis`를 명시하면 규칙보다 그것을 우선한다.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# 산출 근거 구분.
BASIS_MEASURED = "실측"      # 원장·파이프라인 산출값
BASIS_DERIVED = "파생"       # 원장 부재 — 기준일 고정 시드로 파생
BASIS_PROXY = "대용"         # 원장은 있으나 다른 지표로 대신함
BASIS_NOT_COMPUTED = "미산출"  # 산출 체계를 갖추지 않아 0
BASIS_NOT_ENGAGED = "미영위"   # 해당 영업을 하지 않아 0
BASIS_TEXT = "서술"          # 값이 없는 비고 라인

BASES = (BASIS_MEASURED, BASIS_DERIVED, BASIS_PROXY,
         BASIS_NOT_COMPUTED, BASIS_NOT_ENGAGED, BASIS_TEXT)

# 1. 부정 — 파생이 **아니라고** 밝힌 문장. 가장 먼저 걸러야 한다.
_NEGATIONS = ("파생이 아니라", "파생하지 않고", "파생하지 않았다",
              "파생이 아님", "난수가 끼지 않는다")

# 2. 동음이의 — derivative(파생상품)이지 derived(파생값)가 아니다.
_HOMONYMS = ("파생상품", "파생거래", "파생 + SFT", "파생 대지급금",
             "파생금융", "파생결합")

# 3. 긍정 — 실제로 파생임을 밝힌 표현.
_DERIVED = ("파생값", "파생 배수", "파생 배분", "여부는 파생", "파생하되",
            "(파생)", "시드 고정", "고정 시드", "결정론적 RNG")
_PROXY = ("대용", "준용", "그럴듯한 배분")
_NOT_COMPUTED = ("미산출", "산출하지 않", "미보유", "미확보", "원장 없",
                 "원장 부재", "체계를 갖추지")
_NOT_ENGAGED = ("미영위", "영위하지 않", "취급하지 않")


def _blob(line) -> str:
    return " ".join(x for x in (getattr(line, "formula", None),
                                getattr(line, "text_value", None)) if x)


def line_basis(line) -> str:
    """라인 하나의 산출 근거를 판정한다."""
    explicit = getattr(line, "basis", None)
    if explicit in BASES:
        return explicit
    blob = _blob(line)
    if getattr(line, "value", None) is None and getattr(line, "text_value", None):
        # 비고 라인은 값이 없으므로 근거를 묻는 대상이 아니다. 다만 그 안에
        # 미산출·미영위 사유가 적혀 있으면 그것을 살린다.
        for m in _NOT_ENGAGED:
            if m in blob:
                return BASIS_NOT_ENGAGED
        for m in _NOT_COMPUTED:
            if m in blob:
                return BASIS_NOT_COMPUTED
        return BASIS_TEXT
    if any(m in blob for m in _NEGATIONS):
        return BASIS_MEASURED
    stripped = blob
    for h in _HOMONYMS:
        stripped = stripped.replace(h, "")
    if any(m in stripped for m in _DERIVED):
        return BASIS_DERIVED
    if any(m in stripped for m in _NOT_ENGAGED):
        return BASIS_NOT_ENGAGED
    if any(m in stripped for m in _NOT_COMPUTED):
        return BASIS_NOT_COMPUTED
    if any(m in stripped for m in _PROXY):
        return BASIS_PROXY
    return BASIS_MEASURED


def unclassified(built: list) -> pd.DataFrame:
    """파생 관련 어휘를 품었는데 실측으로 떨어진 라인 — 감춰지면 안 된다.

    비어 있어야 정상이다. 새 서식이 새 표현을 쓰면 여기 나타나므로, 규칙에
    그 표현을 추가하거나 라인에 `basis`를 명시하면 된다.
    """
    rows = []
    for b in built:
        for ln in b.lines:
            if line_basis(ln) != BASIS_MEASURED:
                continue
            blob = _blob(ln)
            if any(m in blob for m in _NEGATIONS):
                continue
            stripped = blob
            for h in _HOMONYMS:
                stripped = stripped.replace(h, "")
            # "원장"은 단독으로 근거가 되지 못한다 — "트레이딩 원장 합계"처럼
            # 원장이 **있다**는 뜻으로도 쓰인다. 부재를 말하는 표현은 이미
            # _NOT_COMPUTED가 잡으므로 여기서는 파생 어휘만 본다.
            if "파생" in stripped:
                rows.append({"form_id": b.spec.form_id,
                             "line_code": ln.line_code,
                             "line_name": ln.line_name, "text": blob[:160]})
    return pd.DataFrame(rows, columns=["form_id", "line_code", "line_name", "text"])


# ---------------------------------------------------------------- 원장 목록

@dataclass(frozen=True)
class Ledger:
    """확보하면 파생 라인이 실측으로 바뀌는 원장 하나.

    귀속은 두 경로다. `patterns`는 라인 텍스트를 보고, `forms`는 서식 전체를
    이 원장에 건다. 일별 시계열처럼 **라인명이 날짜인** 서식은 텍스트로 닿지
    않으므로 서식 단위 귀속이 필요하다.
    """
    ledger_id: str
    name: str
    unlocks: str                  # 무엇이 실측으로 바뀌는가
    patterns: tuple[str, ...] = ()   # 라인 텍스트에서 이 원장을 가리키는 표현
    forms: tuple[str, ...] = ()      # 이 원장에 통째로 걸리는 FINES 서식번호


LEDGERS: tuple[Ledger, ...] = (
    Ledger("LED-01", "대주주·특수관계인 지정 원장",
           "대주주 신용공여·주식취득 한도, 주주·임원 거래 내역",
           ("대주주", "특수관계인", "주주 및 임원"),
           forms=('B3103', 'B3104')),
    Ledger("LED-02", "연결 자회사·지분 원장",
           "연결 재무제표·연결 위험가중자산·자회사 출자·경영평가",
           ("자회사", "연결 대상", "연결범위", "지분율"),
           forms=('B3112', 'B3113')),
    Ledger("LED-03", "익스포저 ↔ 대차대조표 계정 매핑 원장",
           "계정과목별 위험가중자산 분해",
           ("계정에 매핑", "계정 매핑", "계정과목별", "계정 귀속"),
           forms=('BA2320',)),
    Ledger("LED-04", "가계여신 속성 원장",
           "지역·자금용도·상환방식·소득구간·신규취급 구분 서식",
           ("지역", "자금용도", "상환방식", "소득구간", "신규취급"),
           forms=('B2430', 'B2433')),
    Ledger("LED-05", "여신 세부구분·채권재조정 원장",
           "여신종별 충당금·채권재조정 여신 현황",
           ("여신종별", "채권재조정", "재조정 방식")),
    Ledger("LED-06", "전기말 잔액·변동 원장",
           "사유별 증감내역·대손상각 변동·연체 발생·회수 변동표",
           ("전기말", "기초 잔액", "기초잔액", "변동표", "증감내역"),
           forms=('B2405', 'B2413', 'B2420', 'B2421', 'B2428')),
    Ledger("LED-07", "금융채권 발행 원장",
           "금융채권 발생·상환·잔존만기·월별 발행내역",
           ("금융채권", "발행이력", "발행내역"),
           forms=('B3116', 'B3117', 'B3118')),
    Ledger("LED-08", "일별 시계열 원장",
           "일별 유동성커버리지비율·일별 트레이딩 자산·부채",
           ("일별", "영업일", "월중 경로"),
           forms=('B2316', 'B2602-2', 'B2602-3')),
    Ledger("LED-09", "통화별 자산·부채 원장",
           "외화·중요통화별 유동성커버리지비율, 통화별 편중도",
           ("통화 구분", "중요통화", "통화별")),
    Ledger("LED-10", "인원·점포 원장",
           "인원현황·기구현황·점포 현황·생산성 지표",
           ("인원", "점포", "기구현황", "직원수")),
    Ledger("LED-11", "신용카드 원장",
           "회원·카드·가맹점·이용실적·리볼빙·포인트 전 서식",
           ("카드 회원", "가맹점", "카드수", "리볼빙", "포인트")),
    Ledger("LED-12", "해외점포 원장",
           "해외점포 재무·자산건전성·수익성·자본적정성·현지화평가",
           ("해외점포", "현지법인", "현지직원", "초국적화")),
    Ledger("LED-13", "유가증권 건전성분류 원장",
           "유가증권의 건전성 분류·충당금",
           ("유가증권 건전성", "유가증권의 건전성"),
           forms=('B2408',)),
    Ledger("LED-14", "위탁·임직원 여신 원장",
           "대출모집 위탁현황·임직원 소액대출",
           ("대출모집", "위탁사", "임직원"),
           forms=('B3114', 'B3119', 'B3220')),
    Ledger("LED-15", "신탁·종금 계정 원장",
           "신탁계정·종금계정 대차대조표·손익계산서",
           ("신탁계정", "종금계정", "신탁 상품별")),
    Ledger("LED-16", "집합투자·투자자문 판매 원장",
           "집합투자증권 판매·투자자문 계약·투자조언장치",
           ("집합투자", "투자자문", "투자조언", "수익자")),
    Ledger("LED-17", "휴면금융재산 원장",
           "휴면예금·미거래 예금·휴면 자기앞수표",
           ("휴면", "미거래 예금", "자기앞수표")),
    Ledger("LED-18", "조달처·금융상품별 원장",
           "자금조달 편중도 (중요 거래상대방·중요 금융상품 기준)",
           ("조달 편중", "거래상대방 기준", "중요 금융상품"),
           forms=("B2610",)),
    Ledger("LED-19", "시장·CVA 민감도 원장 (SBM·SA-CVA)",
           "시장리스크 표준방법 위험군별 민감도, SA-CVA 민감도",
           ("SBM", "SA-CVA", "위험군별 민감도"),
           forms=("B2318-1", "B2320-1", "B2320-2", "B2328", "B2329")),
    Ledger("LED-20", "상업용부동산·대체투자 원장",
           "상업용부동산대출 현황, 대체투자 자산운용 현황",
           ("상업용부동산", "대체투자"),
           forms=("B2436",)),
    Ledger("LED-21", "경기대응완충자본 국가별 고시율",
           "국가별 경기대응완충자본 적립률 — 감독당국 고시값",
           ("경기대응완충자본", "국가별 적립률"),
           forms=("B2324",)),
    Ledger("LED-22", "거액익스포저 면제대상 판정 원장",
           "거액익스포져비율 면제대상 구분 (적격CCP·국가 등)",
           ("면제대상", "적격CCP", "적격 CCP"),
           forms=("B3121",)),
)


def _ledgers_for(text: str, form_id: str = "") -> list[str]:
    return [g.ledger_id for g in LEDGERS
            if form_id in g.forms or any(p in text for p in g.patterns)]


def unattributed(built: list) -> pd.DataFrame:
    """실측이 아닌데 어느 원장에도 걸리지 않은 라인.

    비어 있어야 정상이다. 남아 있으면 "이 값을 실측으로 바꾸려면 무엇이
    필요한가"에 답할 수 없다는 뜻이고, 그러면 이행 계획에 구멍이 난다.
    새 서식이 늘 때 여기가 채워지므로 LEDGERS를 갱신하면 된다.
    """
    prov = provenance_frame(built)
    open_ = prov[prov["basis"].isin(
        (BASIS_DERIVED, BASIS_PROXY, BASIS_NOT_COMPUTED))]
    return open_[open_["ledgers"] == ""][
        ["form_id", "form_no", "line_code", "line_name", "basis"]]


# ---------------------------------------------------------------- 표

def provenance_frame(built: list) -> pd.DataFrame:
    """라인 단위 산출 근거 표."""
    rows = []
    for b in built:
        for ln in b.lines:
            basis = line_basis(ln)
            blob = f"{ln.line_name} {_blob(ln)}"
            rows.append({
                "form_id": b.spec.form_id,
                "form_no": b.spec.form_no_display,
                "form_name": b.spec.form_name,
                "section": b.spec.section,
                "line_code": ln.line_code,
                "line_name": ln.line_name,
                "basis": basis,
                "ledgers": (",".join(_ledgers_for(blob, b.spec.form_id))
                            if basis != BASIS_MEASURED else ""),
                "source_module": ln.source_module or "",
                "citation": ln.citation or "",
            })
    return pd.DataFrame(rows)


def ledger_impact_frame(built: list) -> pd.DataFrame:
    """원장을 확보하면 무엇이 실측으로 바뀌는가 — 이행 계획의 근거."""
    prov = provenance_frame(built)
    open_lines = prov[prov["basis"].isin(
        (BASIS_DERIVED, BASIS_PROXY, BASIS_NOT_COMPUTED))]
    rows = []
    for g in LEDGERS:
        hit = open_lines[open_lines["ledgers"].str.contains(g.ledger_id, na=False)]
        rows.append({
            "ledger_id": g.ledger_id,
            "ledger_name": g.name,
            "unlocks": g.unlocks,
            "n_forms": int(hit["form_id"].nunique()),
            "n_lines": int(len(hit)),
            "forms": ", ".join(sorted(hit["form_no"].unique())[:12]),
        })
    out = pd.DataFrame(rows).sort_values("n_lines", ascending=False)
    return out.reset_index(drop=True)


def basis_summary(built: list) -> pd.DataFrame:
    """근거별 라인 수 — 제출본이 얼마나 실측에 서 있는지 한 줄로 본다."""
    prov = provenance_frame(built)
    total = len(prov)
    out = (prov.groupby("basis").size().rename("n_lines").reset_index()
           .sort_values("n_lines", ascending=False))
    out["share"] = out["n_lines"] / total if total else 0.0
    return out.reset_index(drop=True)
