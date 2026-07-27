"""업무보고서 서식번호 매핑 — 단일 소스.

금융감독원 FINES 업무보고서 ID 마스터를 확보했다 (`fss_master.py`, 기계 생성).
이전에는 배포본을 확보하지 못해 `BA####` 형태의 내부 코드를 배정했는데,
그 코드들이 **실재 FINES 코드와 한 글자 차이로 전혀 다른 서식**을 가리키고
있었다 — 우리 `BA2101`(자기자본비율 총괄) ↔ 실제 `B2101`(대차대조표),
우리 `BA2401`(운영리스크) ↔ 실제 `B2401`(여신건전성 분류) 등 16건. 게다가
`BA` 접두어는 실재하며 바젤Ⅲ 신설 서식 8건 전용이다. 틀린 번호는 번호가
없는 것보다 나쁘므로(제출 단계에서 잘못된 서식에 값이 실린다) 전부 정정했다.

두 종류가 있다.

    official_code   FINES 배포 서식번호. `fss_master.BY_CODE`에 실재해야 한다.
    internal_code   대응하는 FINES 서식이 없는 **내부 관리보고**. `RM-` 접두어를
                    쓴다 — FINES는 `B`/`BA`/`BF`만 쓰므로 충돌하지 않는다.

스트레스테스트·ICAAP·위기상황분석·적기시정조치·신용위험경감·운영손실·
원화유동성비율·경영실태평가 8건은 마스터를 전수 검색해도 대응 서식이 없다.
금감원 제출 업무보고서가 아니라 내부 관리보고이므로 그렇게 표기한다.
"""

from __future__ import annotations

from dataclasses import dataclass

from risk_lib.regulatory.fss_master import BANK_FORMS, BY_CODE, risk_scope


@dataclass(frozen=True)
class FormId:
    internal_code: str
    official_code: str | None = None
    source: str | None = None      # official_code를 어디서 받았는지

    def display(self) -> str:
        if self.official_code:
            return self.official_code
        return f"{self.internal_code} (내부관리)"

    @property
    def is_official(self) -> bool:
        return bool(self.official_code)

    @property
    def official_name(self) -> str | None:
        f = BY_CODE.get(self.official_code or "")
        return f.name if f else None

    @property
    def official_frequency(self) -> str | None:
        f = BY_CODE.get(self.official_code or "")
        return f.frequency if f else None


FSS_SOURCE = "금감원 FINES 업무보고서 ID 마스터 (조사기준일 2025-09-05)"

# ---------------------------------------------------------------- BR-01~34
#
# 기존 34개 서식이 차지하는 FINES 서식번호. 한 서식이 여러 FINES 서식의 내용을
# 담고 있던 경우 **대표 하나만** 여기 두고 나머지는 별도 서식으로 신설했다 —
# FINES 제출 단위가 서식별이므로 묶어 두면 제출본이 성립하지 않는다.
_BR_CLAIMS: dict[str, str] = {
    "BR-01": "BA2301-1",   # BIS기준 총자본비율(바젤Ⅲ, 표준방법)
    "BR-02": "B3101-1",    # 자기자본 산출근거(바젤Ⅲ)
    "BR-03": "BA2305-1",   # 위험가중자산내역-개정 표준방법
    "BR-04": "BA2306-1",   # 위험가중자산내역-개정 내부등급법
    "BR-05": "B2326",      # 시장리스크 소요자기자본 - 요약
    "BR-06": "BA2325-1",   # 운영리스크 소요자기자본
    "BR-07": "B2314",      # 단순기본자본비율 (= 레버리지비율의 국내 명칭)
    "BR-08": "B2602",      # 유동성커버리지비율
    "BR-09": "B2614",      # 순안정자금조달비율
    "BR-10": "B2401",      # 여신건전성 분류
    "BR-11": "B2402-1",    # 대손준비금 적립현황
    "BR-12": "B3107",      # 거액신용공여비율
    "BR-13": "B2909",      # 금리리스크 지표
    "BR-15": "B2101",      # 대차대조표(은행계정, 총괄분)
    "BR-16": "B2110",      # 손익계산서(은행계정, 총괄분)
    "BR-18": "B2908",      # 트레이딩 실제손익 비율
    "BR-20": "BA2304",     # 위험가중자산내역-종합요약 (산출하한 포함)
    "BR-21": "B2325",      # 자본비율 규제준수 현황
    "BR-23": "B2604",      # 외화유동성비율
    "BR-24": "B2613",      # 원화예대율
    "BR-25": "B2415-1",    # 업종별 대출금의 건전성 분류
    "BR-26": "B2404",      # 무수익여신현황
    "BR-27": "B3115",      # 특수관계인에 대한 신용공여 현황
    "BR-28": "B3109",      # 비업무용자산
    "BR-33": "B3120",      # 거액익스포져비율 - 규제대상
    "BR-34": "B2327",      # CVA리스크 소요자기자본 - 요약
}

# 대응하는 FINES 서식이 없는 내부 관리보고. 마스터를 "스트레스/위기상황/
# 내부자본/적기시정/원화유동성/신용위험경감/운영손실/경영실태(국내)" 로 전수
# 검색해 0건임을 확인했다. 금감원 제출본이 아니므로 그렇게 표기한다.
_BR_INTERNAL: dict[str, str] = {
    "BR-14": "RM-6401",    # 스트레스테스트 결과
    "BR-17": "RM-2203",    # 신용위험경감 (담보·보증)
    "BR-19": "RM-2402",    # 운영손실 사건 및 회수
    "BR-22": "RM-3301",    # 원화유동성비율
    "BR-29": "RM-6301",    # 내부자본적정성 (ICAAP)
    "BR-30": "RM-6402",    # 위기상황분석 산출과정
    "BR-31": "RM-7101",    # 경영실태평가 (국내은행 계량지표는 B29xx로 제출)
    "BR-32": "RM-7201",    # 적기시정조치 판정
}


def _build_form_ids() -> dict[str, FormId]:
    """BR-xx 매핑 + 나머지 제출대상 서식을 **마스터에서 생성**한다.

    신설 서식의 form_id는 FINES 서식번호 그 자체다. 손으로 번호를 배정하면
    또 틀리고, 마스터에 없는 번호를 만들어 낼 여지도 생긴다.
    """
    ids: dict[str, FormId] = {}
    for br, code in _BR_CLAIMS.items():
        if code not in BY_CODE:
            raise ValueError(f"{br}: 마스터에 없는 서식번호 {code}")
        ids[br] = FormId(code, code, FSS_SOURCE)
    for br, internal in _BR_INTERNAL.items():
        ids[br] = FormId(internal)
    claimed = set(_BR_CLAIMS.values())
    for f in BANK_FORMS:
        if not f.applicable or f.code in claimed:
            continue
        ids[f.code] = FormId(f.code, f.code, FSS_SOURCE)
    return ids


FORM_IDS: dict[str, FormId] = _build_form_ids()


# ---------------------------------------------------------------- 편제
#
# 감독규정 편제 → 서식 그룹. 목차·UI가 이 순서로 묶어 보여준다. BR-xx는 기존
# 순서를 유지하고, 신설 서식은 마스터의 분류를 따라 붙인다.
_BR_SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("제1편 재무·손익", ("BR-15", "BR-16")),
    ("제2편 자본적정성", ("BR-01", "BR-02", "BR-03", "BR-04", "BR-17",
                          "BR-05", "BR-18", "BR-06", "BR-19", "BR-20",
                          "BR-07", "BR-21")),
    ("제3편 유동성", ("BR-08", "BR-09", "BR-22", "BR-23", "BR-24")),
    ("제4편 자산건전성", ("BR-10", "BR-25", "BR-11", "BR-26")),
    ("제5편 자산운용 한도", ("BR-12", "BR-27", "BR-28")),
    ("제6편 금리리스크", ("BR-13",)),
    ("제7편 내부자본·위기상황분석", ("BR-29", "BR-14", "BR-30")),
    ("제8편 경영실태평가·적기시정조치", ("BR-31", "BR-32")),
    ("제9편 집중도·거래상대방", ("BR-33", "BR-34")),
)

# 신설 서식이 들어갈 편제 — 마스터 분류 그대로다.
_GROUP_SECTIONS: tuple[tuple[str, str], ...] = (
    ("제10편 자본적정성 (금감원 서식)", "자본적정성"),
    ("제11편 자산건전성 (금감원 서식)", "자산건전성"),
    ("제12편 유동성 (금감원 서식)", "유동성"),
    ("제13편 리스크 지표 (금감원 서식)", "리스크지표"),
    ("제14편 업무규제 준수 (금감원 서식)", "업무규제준수"),
)

# 리스크 소관 밖 편제 — 마스터의 원 분류를 그대로 편으로 쓴다. 분류 문자열이
# 곧 금감원 편제이므로 여기서 이름을 새로 짓지 않는다.
_OUT_OF_SCOPE_SECTIONS: tuple[tuple[str, str], ...] = (
    ("제15편 일반현황", "1. 일반현황 / 세부 분류"),
    ("제16편 재무제표", "2. 재무현황 / 가. 재무제표"),
    ("제17편 주요재무현황", "2. 재무현황 / 나. 주요재무현황"),
    ("제18편 수익성", "2. 재무현황 / 마. 수익성"),
    ("제19편 생산성", "2. 재무현황 / 사. 생산성"),
    ("제20편 신용카드", "2. 재무현황 / 아. 신용카드"),
    ("제21편 은행유형별 업무현황", "5. 은행유형별 업무현황 / 가. 일반은행"),
    ("제22편 해외점포 — 일반현황", "7. 해외점포 / 가. 일반현황"),
    ("제23편 해외점포 — 재무제표", "7. 해외점포 / 나. 재무제표"),
    ("제24편 해외점포 — 유동성", "7. 해외점포 / 다. 유동성"),
    ("제25편 해외점포 — 자산건전성", "7. 해외점포 / 라. 자산건전성"),
    ("제26편 해외점포 — 수익성", "7. 해외점포 / 마. 수익성"),
    ("제27편 해외점포 — 자본적정성", "7. 해외점포 / 바. 자본적정성"),
    ("제28편 해외점포 — 현지화평가", "7. 해외점포 / 사. 현지화평가"),
    ("제29편 집합투자증권 판매", "8. 집합투자증권 판매 / 사. 현지화평가"),
    ("제30편 휴면금융재산", "9. 휴면금융재산 현황 / 사. 현지화평가"),
    ("제31편 금리인하요구권", "10. 금리인하요구권 운영현황 / 사. 현지화평가"),
    ("제32편 투자자문업", "11. 투자자문업 현황 / 사. 현지화평가"),
    ("제33편 전자적 투자조언장치", "12. 전자적 투자조언장치 현황 / 사. 현지화평가"),
)


def _build_sections() -> tuple[tuple[str, tuple[str, ...]], ...]:
    claimed = set(_BR_CLAIMS.values())
    out = list(_BR_SECTIONS)
    for name, group in _GROUP_SECTIONS:
        codes = tuple(f.code for f in risk_scope()
                      if f.group == group and f.code not in claimed)
        if codes:
            out.append((name, codes))
    for name, category in _OUT_OF_SCOPE_SECTIONS:
        codes = tuple(f.code for f in BANK_FORMS
                      if f.applicable and f.category == category
                      and f.code not in claimed)
        if codes:
            out.append((name, codes))
    return tuple(out)


SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = _build_sections()


def section_of(form: str) -> str:
    for name, ids in SECTIONS:
        if form in ids:
            return name
    return "미분류"


UNASSIGNED_NOTE = (
    "서식번호는 금융감독원 FINES 업무보고서 ID 마스터와 대조해 배정했다. "
    "`RM-` 접두어는 대응하는 금감원 배포 서식이 없는 내부 관리보고이며, "
    "제출 대상이 아니다 (스트레스테스트·ICAAP·위기상황분석·적기시정조치 등)."
)

# 국내 일반은행이 제출하지 않는 서식과 그 사유 — 누락과 구분하기 위해 남긴다.
NOT_APPLICABLE: dict[str, str] = {
    f.code: f.not_applicable for f in BANK_FORMS if not f.applicable
}


def form_id(form: str) -> FormId:
    try:
        return FORM_IDS[form]
    except KeyError:
        raise KeyError(f"서식번호 미등록: {form}") from None


def n_official() -> int:
    return sum(1 for f in FORM_IDS.values() if f.is_official)
