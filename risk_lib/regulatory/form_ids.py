"""업무보고서 서식번호 매핑 — 단일 소스.

금융감독원 배포 서식 파일이 입력으로 주어지지 않았고, 공개 웹(FSS 은행업무보고서
목록·FSC 자료실)은 접근이 차단되어 **공식 서식번호 표를 확보하지 못했다**.
공식 번호를 추측해서 적으면 제출 단계에서 잘못된 서식에 값이 실린다 — 그래서
두 칸으로 나눈다.

    internal_code   이 시스템이 배정한 코드 (BA####). 감독규정 편제를 따른다.
    official_code   금감원 배포본의 실제 서식번호. **확보 전에는 None**.

화면·엑셀·CSV는 official_code가 있으면 그것을, 없으면 internal_code에
`(내부)` 표시를 붙여 보여준다. 공식 번호를 받으면 이 파일 한 장만 고치면
서식·라인·검증·UI가 모두 따라온다.

코드 체계 (internal_code) — 은행업감독규정 편제 대응:

    BA2xxx  자본적정성   (제26조 · 제26조의2~4)
    BA3xxx  유동성       (제26조 LCR·NSFR)
    BA4xxx  자산건전성   (제27조 · 제29조)
    BA5xxx  신용공여 한도 (은행법 제35조)
    BA6xxx  금리리스크·스트레스 (SRP31 · SRP20)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FormId:
    internal_code: str
    official_code: str | None = None
    source: str | None = None      # official_code를 어디서 받았는지

    def display(self) -> str:
        if self.official_code:
            return self.official_code
        return f"{self.internal_code} (내부)"

    @property
    def is_official(self) -> bool:
        return bool(self.official_code)


# form_id → 서식번호. official_code는 배포본 대조 후 채운다.
FORM_IDS: dict[str, FormId] = {
    "BR-01": FormId("BA2101"),   # 자기자본비율 산출 총괄
    "BR-02": FormId("BA2102"),   # 자기자본 구성 명세
    "BR-03": FormId("BA2201"),   # 신용리스크 RWA — 표준방법
    "BR-04": FormId("BA2202"),   # 신용리스크 RWA — 내부등급법
    "BR-05": FormId("BA2301"),   # 시장리스크 소요자기자본
    "BR-06": FormId("BA2401"),   # 운영리스크 소요자기자본
    "BR-07": FormId("BA2501"),   # 레버리지비율
    "BR-08": FormId("BA3101"),   # 유동성커버리지비율
    "BR-09": FormId("BA3201"),   # 순안정자금조달비율
    "BR-10": FormId("BA4101"),   # 자산건전성 분류 및 대손충당금
    "BR-11": FormId("BA4201"),   # 대손준비금 적립
    "BR-12": FormId("BA5101"),   # 거액여신 및 동일차주 신용공여
    "BR-13": FormId("BA6101"),   # 은행계정 금리리스크
    "BR-14": FormId("BA6201"),   # 스트레스테스트 결과
    "BR-15": FormId("BA1101"),   # 재무상태표
    "BR-16": FormId("BA1201"),   # 손익계산서
    "BR-17": FormId("BA2203"),   # 신용위험경감
    "BR-18": FormId("BA2302"),   # 시장리스크 위험요소·백테스팅
    "BR-19": FormId("BA2402"),   # 운영손실 사건 및 회수
    "BR-20": FormId("BA2601"),   # 산출하한 적용내역
    "BR-21": FormId("BA2701"),   # 완충자본 및 배당가능액
    "BR-22": FormId("BA3301"),   # 원화유동성비율
    "BR-23": FormId("BA3401"),   # 외화유동성비율
    "BR-24": FormId("BA3501"),   # 원화예대율
    "BR-25": FormId("BA4102"),   # 자산건전성 분류 — 자산군별
    "BR-26": FormId("BA4301"),   # 부실채권 및 연체 현황
    "BR-27": FormId("BA5201"),   # 대주주 신용공여·주식취득
    "BR-28": FormId("BA5301"),   # 유가증권·자회사·부동산 한도
    "BR-29": FormId("BA6301"),   # 내부자본적정성 (ICAAP)
    "BR-30": FormId("BA6401"),   # 위기상황분석 산출과정
    "BR-31": FormId("BA7101"),   # 경영실태평가
    "BR-32": FormId("BA7201"),   # 적기시정조치 판정
    "BR-33": FormId("BA8101"),   # 부문별 집중도·거액익스포저
    "BR-34": FormId("BA8201"),   # 파생상품·거래상대방 신용위험
}

# 감독규정 편제 → 서식 그룹. 목차·UI가 이 순서로 묶어 보여준다.
SECTIONS: tuple[tuple[str, tuple[str, ...]], ...] = (
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


def section_of(form: str) -> str:
    for name, ids in SECTIONS:
        if form in ids:
            return name
    return "미분류"

UNASSIGNED_NOTE = (
    "서식번호는 이 시스템이 배정한 내부 코드다. 금융감독원 배포본 서식번호가 "
    "확보되면 risk_lib/regulatory/form_ids.py의 official_code만 채우면 되고, "
    "라인코드·산식·규정근거는 그대로 쓴다."
)


def form_id(form: str) -> FormId:
    try:
        return FORM_IDS[form]
    except KeyError:
        raise KeyError(f"서식번호 미등록: {form}") from None


def n_official() -> int:
    return sum(1 for f in FORM_IDS.values() if f.is_official)
