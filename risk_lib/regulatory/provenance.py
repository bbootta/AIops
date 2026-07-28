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
    3. 혼합        "합계는 실측 · 배분만 파생" → 혼합 (총액은 앵커, 내부 배분만 파생)
    4. 긍정        "파생값" · "파생 배수" · "대용" · "미보유" · …

**혼합을 실측으로 세지 않는 것이 요점이다.** 합계를 산출값에 앵커한 표는
명세 대사가 자기충족이 아니라는 점에서 순수 파생보다 낫지만, 개별 배분은
여전히 실측이 아니다. 둘을 합쳐 "실측 82%"라고 보고하면 과장이 된다.

분류되지 않은 채 파생 관련 어휘를 품은 라인은 `unclassified()`가 되돌려
준다. 감춰지지 않게 하려는 것이다 — 분류가 조용히 실패하면 파생값이 실측으로
보고된다. 라인이 `basis`를 명시하면 규칙보다 그것을 우선한다.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from types import SimpleNamespace

import pandas as pd

# 산출 근거 구분.
BASIS_MEASURED = "실측"      # 원장·파이프라인 산출값
BASIS_DERIVED = "파생"       # 원장 부재 — 기준일 고정 시드로 파생
BASIS_PROXY = "대용"         # 원장은 있으나 다른 지표로 대신함
BASIS_NOT_COMPUTED = "미산출"  # 산출 체계를 갖추지 않아 0
BASIS_NOT_ENGAGED = "미영위"   # 해당 영업을 하지 않아 0
BASIS_MIXED = "혼합"         # 합계는 산출값에 앵커, 내부 배분만 파생
BASIS_TEXT = "서술"          # 값이 없는 비고 라인

BASES = (BASIS_MEASURED, BASIS_DERIVED, BASIS_PROXY, BASIS_MIXED,
         BASIS_NOT_COMPUTED, BASIS_NOT_ENGAGED, BASIS_TEXT)

# 1. 부정 — 파생이 **아니라고** 밝힌 문장. 가장 먼저 걸러야 한다.
_NEGATIONS = ("파생이 아니라", "파생하지 않고", "파생하지 않았다",
              "파생이 아님", "파생 아님", "난수가 끼지 않는다",
              "파생을 쓰지 않", "파생 없이")

# 2. 동음이의 — derivative(파생상품)이지 derived(파생값)가 아니다.
_HOMONYMS = ("파생상품", "파생거래", "파생 + SFT", "파생 대지급금",
             "파생금융", "파생결합", "파생 EAD", "장외파생", "파생 명목",
             "파생 익스포저", "파생 포지션", "부외·파생", "파생 환산")

# 3. 혼합 — 합계는 실측이고 내부 배분만 파생인 라인. 실측으로 세면 과장이고
# 순수 파생으로 세면 앵커가 있다는 사실이 사라진다.
# "…만 파생"이 혼합의 표지다 — 배분만·구성비만·라벨만·지역만·비중만.
_MIXED = ("합계는 실측", "합계는 산출", "금액은 실측", "비율은 실측",
          "(실측)", "만 파생", "배분은 파생", "실측 합",
          "구성비 파생", "총액은 앵커", "앵커 · ", "· 총액 앵커")

# 4. 긍정 — 실제로 파생임을 밝힌 표현.
_DERIVED = ("파생값", "파생 배수", "파생 배분", "여부는 파생", "파생하되",
            "(파생)", "시드 고정", "고정 시드", "결정론적 RNG",
            "완전 파생", "앵커할 산출값 없음")
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
    if any(m in stripped for m in _MIXED):
        return BASIS_MIXED
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

    귀속은 세 경로다. `patterns`는 라인 텍스트를, `forms`는 서식을, `sections`는
    편제 전체를 이 원장에 건다. 일별 시계열처럼 **라인명이 날짜인** 서식은
    텍스트로 닿지 않고, 신용카드·해외점포·휴면금융재산처럼 **편제 전체가 하나의
    원장을 필요로 하는** 경우는 서식을 일일이 적는 것이 곧 낡는다.
    """
    ledger_id: str
    name: str
    unlocks: str                  # 무엇이 실측으로 바뀌는가
    patterns: tuple[str, ...] = ()   # 라인 텍스트에서 이 원장을 가리키는 표현
    forms: tuple[str, ...] = ()      # 이 원장에 통째로 걸리는 FINES 서식번호
    sections: tuple[str, ...] = ()   # 이 원장에 통째로 걸리는 편제


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
           ("인원", "점포", "기구현황", "직원수"),
           sections=("제15편 일반현황", "제19편 생산성")),
    Ledger("LED-11", "신용카드 원장",
           "회원·카드·가맹점·이용실적·리볼빙·포인트 전 서식",
           ("카드 회원", "가맹점", "카드수", "리볼빙", "포인트"),
           sections=("제20편 신용카드",)),
    Ledger("LED-12", "해외점포 원장",
           "해외점포 재무·자산건전성·수익성·자본적정성·현지화평가",
           ("해외점포", "현지법인", "현지직원", "초국적화"),
           sections=("제22편 해외점포 — 일반현황", "제23편 해외점포 — 재무제표",
                     "제24편 해외점포 — 유동성", "제25편 해외점포 — 자산건전성",
                     "제26편 해외점포 — 수익성", "제27편 해외점포 — 자본적정성",
                     "제28편 해외점포 — 현지화평가")),
    Ledger("LED-13", "유가증권 건전성분류 원장",
           "유가증권의 건전성 분류·충당금",
           ("유가증권 건전성", "유가증권의 건전성"),
           forms=('B2408',)),
    Ledger("LED-14", "위탁·임직원 여신 원장",
           "대출모집 위탁현황·임직원 소액대출",
           ("대출모집", "위탁사", "임직원"),
           forms=('B3114', 'B3119', 'B3220')),
    Ledger("LED-15", "신탁·종금 계정 원장",
           "신탁계정·종금계정 대차대조표·손익계산서, 계정과목별 재무제표",
           ("신탁계정", "종금계정", "신탁 상품별"),
           sections=("제16편 재무제표",)),
    Ledger("LED-16", "집합투자·투자자문 판매 원장",
           "집합투자증권 판매·투자자문 계약·투자조언장치",
           ("집합투자", "투자자문", "투자조언", "수익자"),
           sections=("제29편 집합투자증권 판매", "제32편 투자자문업",
                     "제33편 전자적 투자조언장치")),
    Ledger("LED-17", "휴면금융재산 원장",
           "휴면예금·미거래 예금·휴면 자기앞수표",
           ("휴면", "미거래 예금", "자기앞수표"),
           sections=("제30편 휴면금융재산",)),
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
    Ledger("LED-23", "손익 세부 원장 (수수료·부문별·금리구간)",
           "손익현황·수수료수입·부문별 손익·금리구간별 잔액·이익잉여금 처분",
           ("수수료 신설", "부문별 손익", "금리구간"),
           sections=("제18편 수익성",)),
    Ledger("LED-24", "조달·운용 평잔 원장",
           "자금조달·운용 기중평잔, 대출약정·금액대별 여신, D-SIB 평가지표",
           ("기중평잔", "평잔", "금액대별"),
           sections=("제17편 주요재무현황",)),
    Ledger("LED-25", "연결 경영지표·자지점 원장",
           "연결기준 경영지표·자회사 경영평가·자지점 현황",
           ("자지점", "경영평가"),
           sections=("제21편 은행유형별 업무현황",)),
    Ledger("LED-26", "금리인하요구권 접수·심사 원장",
           "금리인하요구권 신청·수용·인하폭 현황",
           ("금리인하요구",),
           sections=("제31편 금리인하요구권",)),
    Ledger("LED-22", "거액익스포저 면제대상 판정 원장",
           "거액익스포져비율 면제대상 구분 (적격CCP·국가 등)",
           ("면제대상", "적격CCP", "적격 CCP"),
           forms=("B3121",)),
)


def _ledgers_for(text: str, form_id: str = "", section: str = "") -> list[str]:
    return [g.ledger_id for g in LEDGERS
            if form_id in g.forms or section in g.sections
            or any(p in text for p in g.patterns)]


def unattributed(built: list) -> pd.DataFrame:
    """실측이 아닌데 어느 원장에도 걸리지 않은 라인.

    비어 있어야 정상이다. 남아 있으면 "이 값을 실측으로 바꾸려면 무엇이
    필요한가"에 답할 수 없다는 뜻이고, 그러면 이행 계획에 구멍이 난다.
    새 서식이 늘 때 여기가 채워지므로 LEDGERS를 갱신하면 된다.
    """
    prov = provenance_frame(built)
    open_ = prov[prov["basis"].isin(
        (BASIS_DERIVED, BASIS_MIXED, BASIS_PROXY, BASIS_NOT_COMPUTED))]
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
                "ledgers": (",".join(_ledgers_for(blob, b.spec.form_id,
                                                  b.spec.section))
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


# ---------------------------------------------------------------- 생성 문장·표
#
# 라인 수·실측 비중은 기계가 만드는 값이다. 그런데 문서와 가정 공시에는 손으로
# 옮겨 적혀 있었고, 그 값은 제출본(asof 2026-06-30)이 아니라 시험 고정일
# (2026-06-11) 실행에서 나온 것이었다 — 지적 F-501. 산출값 오류는 아니었지만
# 문서를 인용하는 검토자·결재선이 제출본과 다른 실행을 근거로 판단하게 된다.
# 문서 수치가 코드 사실과 어긋난 네 번째 재발이었으므로, 문장도 표도 여기서
# 만들어 손으로 적을 자리를 없앤다.


def _stats(bases: list[str], n_forms: int) -> dict:
    total = len(bases)
    return {
        "n_forms": int(n_forms),
        "n_lines": total,
        # 비중은 문장·표가 그대로 쓰므로 여기서 한 번만 반올림한다. 렌더러가
        # 제각기 반올림하면 같은 실행에서 다른 숫자가 나온다.
        "by_basis": {b: {"n_lines": n, "share": round(n / total, 6)}
                     for b, n in Counter(bases).most_common()},
    }


def provenance_stats(built: list) -> dict:
    """근거별 라인 수·비중 — 문장·표·독립검증 요청이 전부 이 dict에서 나온다."""
    prov = provenance_frame(built)
    return _stats(list(prov["basis"]), prov["form_id"].nunique())


def provenance_stats_from_lines(lines: pd.DataFrame) -> dict:
    """정규 테이블 `reg_form_line`만으로 같은 통계를 낸다.

    독립검증 요청을 만드는 `build_request`는 조립된 서식 객체가 아니라 정규
    테이블을 받는다. 통계를 "가진 쪽에서만 싣는다"로 두면 요청 패키지는 다시
    손으로 적은 문장을 담게 되므로 여기서도 산출되게 한다.

    판정은 `line_basis` 하나를 그대로 쓰고 결측만 되돌린다 — 표로 실체화되면
    값 없는 비고 라인의 `value`가 None이 아니라 NaN이라 그 분기를 타지 못하고,
    `formula`·`text_value`의 NaN은 진리값이 참이라 `_blob`이 깨진다.
    """
    rows = [SimpleNamespace(
        value=None if pd.isna(r.value) else float(r.value),
        text_value=None if pd.isna(r.text_value) else str(r.text_value),
        formula=None if pd.isna(r.formula) else str(r.formula))
        for r in lines.itertuples(index=False)]
    return _stats([line_basis(r) for r in rows], lines["form_id"].nunique())


def provenance_sentence(stats: dict) -> str:
    """독립검증 요청서에 실을 한 문장.

    서식 수는 **산출한** 서식이지 제출대상 서식이 아니다 — 내부 관리보고가
    섞여 있어 둘은 다르다. 같은 목록의 다른 가정이 제출대상 건수를 말하므로,
    라벨이 없으면 3선이 두 수를 같은 것으로 보고 불일치로 읽는다.
    """
    parts = " · ".join(f"{b} {d['share']:.1%}"
                       for b, d in stats["by_basis"].items())
    return (f"산출 근거 분류(실행 시점 생성): 산출한 서식 {stats['n_forms']:,}건 · 전체 "
            f"{stats['n_lines']:,}라인 기준 {parts}. 이 수치는 문서에 손으로 적지 "
            f"않고 provenance_stats가 만든다 — 라인별 근거와 원장별 해소 경로는 "
            f"risk_lib.regulatory.provenance가 산출한다 "
            f"(산출물 Pack 05_regulatory/산출근거_라인별.csv · 지적 F-501).")


def provenance_report_md(stats: dict, asof: str) -> str:
    """시정 문서에 붙일 표.

    기준일을 함께 찍는 것이 요점이다 — F-501은 다른 기준일 실행의 값을 제출본
    설명에 옮겨 적은 것이었고, 표에 기준일이 없으면 그 어긋남이 보이지 않는다.
    """
    share_total = sum(d["share"] for d in stats["by_basis"].values())
    return "\n".join((
        f"기준일 {asof} · 서식 {stats['n_forms']:,}건 — "
        f"risk_lib.regulatory.provenance 생성 (손으로 적지 않는다)",
        "",
        "| 산출 근거 | 라인 수 | 비중 |",
        "|---|---:|---:|",
        *(f"| {b} | {d['n_lines']:,} | {d['share']:.2%} |"
          for b, d in stats["by_basis"].items()),
        f"| **합계** | **{stats['n_lines']:,}** | **{share_total:.2%}** |",
    ))


# ---------------------------------------------------------------- 검증의 세기

def check_strength(built: list) -> dict:
    """서식검증이 실제로 통제력을 갖는지 — "실패 0"의 뜻을 좁힌다.

    독립검증 지적 F-602: 쟁점을 지키던 검증이 `min(0, Σmax(0,xᵢ) − max(0,Σxᵢ))`
    였는데 두 값의 대소가 **정리**로 정해져 있어 어떤 자료에서도 정확히 0이었다.
    실패 불가능성이 데이터가 아니라 산식 구조에서 나오면 그것은 통제가 아니다.

    여기서 세는 것은 **양변이 모두 0인 검증**이다. 그중에는 정당한 것도 있다 —
    영위하지 않는 업무(신탁·종금·투자자문)나 보유하지 않은 익스포저(유동화)는
    0을 단언하는 것이 옳고, 원장이 생기면 살아난다. 그러나 구조적 항진명제도
    같은 모습이므로 **이 수가 곧 통제 세기는 아니다**. 3선이 판별할 수 있도록
    수를 넘긴다.
    """
    total = zero_both = 0
    for b in built:
        for c in b.checks:
            total += 1
            if max(abs(float(c.expected)), abs(float(c.actual))) == 0.0:
                zero_both += 1
    return {
        "n_checks": total,
        "n_zero_both": zero_both,
        "n_live": total - zero_both,
        "live_share": (total - zero_both) / total if total else 0.0,
    }


def check_strength_sentence(strength: dict) -> str:
    """요청서에 실을 한 문장 — 손으로 적지 않는다 (지적 F-501·F-603)."""
    return (
        f"서식검증 {strength['n_checks']:,}건 중 {strength['n_zero_both']:,}건은 "
        f"양변이 모두 0이라 현 자료에서 실패할 수 없다 (실질 대사 "
        f"{strength['n_live']:,}건 · {strength['live_share']:.1%}). 영위하지 않는 "
        f"업무·미보유 익스포저의 0 단언이 다수이나 구조적 항진명제도 같은 모습이며, "
        f"둘의 판별은 미완이다 — '검증 N건 실패 0'을 통제 세기로 읽지 말 것 "
        f"(지적 F-602)."
    )
