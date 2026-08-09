"""[별표 9-1] 제22항 금리리스크 공시서식 <표6>·<표7>.

**이 양식은 자체 조정이 금지된다**(제22항 나). 그래서 행·열 구조를 모듈 상수로
고정하고 `tests/test_irrbb_disclosure.py`가 이름과 순서를 그대로 잠근다. 빌더는
행을 더하지도 빼지도 못하며, 시나리오가 6개가 아니면 만들다가 멈춘다.

## <표6> 금리리스크 수준

시나리오 1~6의 ΔEVE·ΔNII를 당기·전기로 적고, 1~6 중 최대값과 기본자본을
덧붙인다. 8행 × 4열이며 그 구조가 `TABLE6_ROWS`·`TABLE6_COLUMNS`다.

ΔNII는 시나리오 1·2만 채워진다. 제14항이 목표관리기간 1년의 평행상승·평행하락
2개 시나리오만 산출하도록 정하기 때문이다. 3~6의 ΔNII 칸이 비는 것은 결측이
아니라 규정이 그렇게 정한 결과이고, `blank_reason`이 그 사실을 적는다.

**부호 규약.** 별표 <표6>은 ΔEVE·ΔNII의 부호 규약을 적지 않는다. 산출엔진
(`alm/irrbb.py`)은 부호 있는 값(손실이 음수)을 내므로, 공시에는 BCBS IRRBB1과
같이 **감소액을 양수로** 적고 그 사실을 `sign_convention` 컬럼에 남긴다.
1~6 중 최대값은 그 규약 위에서의 최대값, 즉 가장 큰 감소액이다.

기본자본 행은 기간별 값 하나이므로 ΔEVE 열 그룹의 당기·전기 칸에 적고 ΔNII
열 그룹은 비운다. 이것은 표시 규칙이며 원장에는 `measure='기본자본'`으로
남으므로 어느 칸이 무엇인지가 흐려지지 않는다.

## <표7> 산출·관리방법

정성공시 8항목과 정량공시 2항목이다. 정성공시는 산출이 아니라 **수기입력**이며
입력자·승인자·승인일을 함께 담는다. 미입력 항목은 값을 지어내지 않고 빈 채로
남으며 `is_disclosed=False`가 화면·서식에서 그 사실을 드러낸다. 8번 항목만
선택사항이므로 비어 있어도 경고를 만들지 않는다.

**미등재.** 아래 TableSpec은 아직 `datamodel.catalog.ALL_TABLES`에 넣지 않았다.
카탈로그 등재는 실체화 검사·ARCHITECTURE.md 수치 검사와 함께 움직이므로 배선
단계에서 등재한다.

**남은 미확인** (1차자료 §C). 기타 공시의 세부는 세칙 <별표23>이고 그 원문을
확보하지 못했다. 기본자본의 정의는 <별표3>이며 역시 미확보다. 이 모듈은 두
값을 인자로 받을 뿐 스스로 만들지 않는다.
"""

from __future__ import annotations

import pandas as pd

from risk_lib.alm.behaviour import ParamWarning
from risk_lib.alm.kr_irrbb import KR_FRAMEWORK_2026, KR_FRAMEWORK_STATUSES
from risk_lib.alm.params import EVIDENCE_STATUS, IRRBB_SCENARIOS
from risk_lib.datamodel.spec import ColumnSpec as C, TableSpec

__all__ = [
    "TABLE6_FORM_CODE", "TABLE7_FORM_CODE",
    "TABLE6_ROWS", "TABLE6_COLUMNS", "TABLE6_MEASURES", "TABLE6_PERIODS",
    "TABLE6_MAX_ROW", "TABLE6_TIER1_ROW", "SIGN_CONVENTION",
    "TABLE7_QUALITATIVE_ITEMS", "TABLE7_QUANTITATIVE_ITEMS",
    "DISC_TABLE6", "DISC_TABLE7_QUALITATIVE", "DISC_TABLE7_QUANTITATIVE",
    "IRRBB_DISCLOSURE_TABLES",
    "build_table6", "table6_matrix",
    "build_table7_qualitative", "build_table7_quantitative",
]

_CITE = ("은행업감독업무시행세칙 [별표 9-1] 금리리스크 산출기준 "
         "<개정 2026.1.29> 제22항")

TABLE6_FORM_CODE = "<표6>"
TABLE7_FORM_CODE = "<표7>"

# 감소를 양수로 적는다. 별표가 부호 규약을 정하지 않으므로 어느 규약을 썼는지가
# 행마다 남아야 한다.
SIGN_CONVENTION = "감소액을 양수로 적는다. 산출엔진의 부호 있는 값에 −1을 곱한 것이다"

TABLE6_MEASURES: tuple[str, ...] = ("ΔEVE", "ΔNII", "기본자본")
TABLE6_PERIODS: tuple[str, ...] = ("당기", "전기")

TABLE6_MAX_ROW = "최대값"
TABLE6_TIER1_ROW = "기본자본"

# 행 구조. (row_code, row_name, scenario). 시나리오 순서는 <표4>의 1~6 번호
# 순서이며 `params.IRRBB_SCENARIOS`와 같다. 자체 조정 금지 대상이다.
TABLE6_ROWS: tuple[tuple[str, str, str | None], ...] = (
    ("1", "평행상승", "parallel_up"),
    ("2", "평행하락", "parallel_down"),
    ("3", "단기하락·장기상승(스티프너)", "steepener"),
    ("4", "단기상승·장기하락(플래트너)", "flattener"),
    ("5", "단기상승", "short_up"),
    ("6", "단기하락", "short_down"),
    (TABLE6_MAX_ROW, "1~6 중 최대값", None),
    (TABLE6_TIER1_ROW, "기본자본", None),
)

# 열 구조. (col_code, measure, period).
TABLE6_COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("당기_ΔEVE", "ΔEVE", "당기"),
    ("전기_ΔEVE", "ΔEVE", "전기"),
    ("당기_ΔNII", "ΔNII", "당기"),
    ("전기_ΔNII", "ΔNII", "전기"),
)

_COL_CODES: tuple[str, ...] = tuple(c for c, _m, _p in TABLE6_COLUMNS)
_ROW_CODES: tuple[str, ...] = tuple(c for c, _n, _s in TABLE6_ROWS)

# <표7> 가. 정성공시 8항목. 8번만 선택사항이다.
# (item_no, item_name, is_optional)
TABLE7_QUALITATIVE_ITEMS: tuple[tuple[int, str, bool], ...] = (
    (1, "IRRBB의 정의", False),
    (2, "IRRBB의 전반적 관리·경감 전략(한도 대비 EVE·NII 모니터링, 헤지, "
        "위기상황분석, 결과분석, 독립감사의 역할, 리스크관리위원회의 역할, "
        "모형 적정성검증, 적시 업데이트)", False),
    (3, "IRRBB 측정주기와 민감도 측정 방법론", False),
    (4, "적용한 금리충격 시나리오와 위기상황 시나리오", False),
    (5, "주요 모형화 가정. 공시 외 목적으로 산출한 EVE의 가정이 <표6> 가정과 "
        "다르면 그 차이와 직접 영향, 합리적 근거를 설명한다", False),
    (6, "금리리스크 헤지 방법과 관련 회계처리", False),
    (7, "주요 모형화·모수 가정(ΔEVE에 상업적 마진 및 기타 금리구성요소를 "
        "현금흐름·할인율에 포함했는지, 비만기성예금 평균 금리개정만기 결정 "
        "방법, 조기상환율·중도해지율 추정 방법론과 주요 가정, <표6> ΔEVE·ΔNII에 "
        "중대한 영향을 주는 기타 가정, 통화 간 리스크 합산방법과 통화 간 "
        "유의한 금리상관관계)", False),
    (8, "기타 정보", True),
)

# <표7> 나. 정량공시 2항목.
# (item_code, item_name, unit)
TABLE7_QUANTITATIVE_ITEMS: tuple[tuple[str, str, str], ...] = (
    ("NMD_평균_금리개정만기", "비만기성예금의 평균 금리개정만기", "years"),
    ("NMD_최장_금리개정만기", "비만기성예금의 최장 금리개정만기", "years"),
)


# ---------------------------------------------------------------- 스펙

DISC_TABLE6 = TableSpec(
    name="disc_irrbb_table6", korean="금리리스크 수준 공시 <표6>",
    product="PRD-ALM",
    grain="기준일 × 행 × 열 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("form_code", "string", "서식", nullable=False),
        C("framework_version", "string", "계정", nullable=False),
        C("row_seq", "int", "행 순서", nullable=False, min_value=1),
        C("row_code", "string", "행", nullable=False, allowed=_ROW_CODES),
        C("row_name", "string", "행 이름", nullable=False),
        C("scenario", "string", "시나리오", nullable=True,
          allowed=IRRBB_SCENARIOS,
          note="최대값·기본자본 행은 시나리오가 없다"),
        C("col_seq", "int", "열 순서", nullable=False, min_value=1),
        C("col_code", "string", "열", nullable=False, allowed=_COL_CODES),
        C("measure", "string", "지표", nullable=False, allowed=TABLE6_MEASURES),
        C("period", "string", "기간", nullable=False, allowed=TABLE6_PERIODS),
        C("value", "float", "금액", nullable=True, unit="KRW",
          citation=f"{_CITE} 나 <표6>"),
        C("sign_convention", "string", "부호 규약", nullable=False,
          note="별표가 부호 규약을 정하지 않으므로 어느 규약을 썼는지를 행이 "
               "스스로 밝힌다"),
        C("blank_reason", "text", "공란 사유", nullable=True,
          note="ΔNII가 시나리오 3~6에서 비는 것은 결측이 아니라 제14항이 평행 "
               "2개만 산출하도록 정한 결과다. 두 공란을 같은 칸으로 두면 "
               "제출 전에 무엇이 빠졌는지 알 수 없다"),
        C("is_adjustable", "bool", "자체 조정 가능", nullable=False,
          citation=f"{_CITE} 나. 이 양식은 자체 조정을 금지한다",
          note="전 행 False다. 값이 아니라 사실을 적는 칸이며, 검사가 이 칸으로 "
               "구조 고정을 확인한다"),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("asof", "row_code", "col_code"),
    note="8행 × 4열 = 32행이 항상 나온다. 값이 없어도 행은 사라지지 않는다. "
         "자체 조정 금지 양식에서 행이 사라지는 것은 조정이다.",
)

DISC_TABLE7_QUALITATIVE = TableSpec(
    name="disc_irrbb_table7_qualitative", korean="산출·관리방법 정성공시 <표7> 가",
    product="PRD-ALM",
    grain="기준일 × 정성공시 항목 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("form_code", "string", "서식", nullable=False),
        C("item_no", "int", "항목 번호", nullable=False, min_value=1),
        C("item_name", "text", "항목", nullable=False),
        C("is_optional", "bool", "선택 항목", nullable=False,
          citation=f"{_CITE} 나 <표7> 가(8). 기타 정보만 선택사항이다"),
        C("narrative", "text", "공시 문안", nullable=True,
          note="수기입력이다. 비어 있으면 지어내지 않고 비운 채로 둔다"),
        C("is_disclosed", "bool", "입력 여부", nullable=False,
          note="빈 항목이 화면·서식에서 비어 보이게 하는 칸이다"),
        C("input_by", "string", "입력자", nullable=True),
        C("approved_by", "string", "승인자", nullable=True),
        C("approved_date", "date", "승인일", nullable=True),
        C("is_approved", "bool", "승인 여부", nullable=False,
          note="문안이 있어도 승인자·승인일이 없으면 False다. 미승인 문안이 "
               "공시로 나가는 것을 막는 칸이다"),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("asof", "item_no"),
    note="8항목이 항상 전건 나온다. 입력되지 않은 항목을 빼면 무엇이 비었는지 "
         "화면에서 사라진다.",
)

DISC_TABLE7_QUANTITATIVE = TableSpec(
    name="disc_irrbb_table7_quantitative",
    korean="산출·관리방법 정량공시 <표7> 나", product="PRD-ALM",
    grain="기준일 × 정량공시 항목 1행",
    columns=(
        C("asof", "date", "기준일", nullable=False),
        C("form_code", "string", "서식", nullable=False),
        C("item_code", "string", "항목 코드", nullable=False),
        C("item_name", "string", "항목", nullable=False),
        C("value", "float", "값", nullable=True, unit="years", min_value=0.0,
          citation=f"{_CITE} 나 <표7> 나. 비만기성예금의 평균·최장 "
                   f"금리개정만기"),
        C("value_unit", "string", "단위", nullable=False),
        C("is_disclosed", "bool", "입력 여부", nullable=False),
        C("basis", "text", "산출 근거", nullable=True),
        C("citation", "text", "근거", nullable=True),
        C("evidence_status", "string", "근거 상태", nullable=False,
          allowed=EVIDENCE_STATUS),
    ),
    primary_key=("asof", "item_code"),
    note="2항목이 항상 나온다. 산출값이 없으면 값이 비고 is_disclosed가 False다.",
)

IRRBB_DISCLOSURE_TABLES: tuple[TableSpec, ...] = (
    DISC_TABLE6, DISC_TABLE7_QUALITATIVE, DISC_TABLE7_QUANTITATIVE,
)


# ---------------------------------------------------------------- <표6>

_NII_BLANK = ("제14항. ΔNII는 목표관리기간 1년의 평행상승·평행하락 2개 "
              "시나리오만 산출한다")
_TIER1_BLANK = "기본자본은 기간별 값 하나이므로 ΔNII 열에 적지 않는다"
_MISSING_PRIOR = "전기 산출값이 제공되지 않았다"
_MISSING_CURRENT = "당기 산출값이 제공되지 않았다"

# 폐지 계정의 상태 문자열. `alm_irrbb_result`는 어느 계정으로 산출했는지를
# framework_status에 싣고, 폐지 계정(별표9의1_2014)으로 낸 수치는 공시에
# 올라가면 안 된다.
_REPEALED_STATUS = KR_FRAMEWORK_STATUSES[1]


def _scenario_values(result: pd.DataFrame | None, *,
                     label: str) -> dict[str, dict[str, float | None]]:
    """산출결과 → {시나리오: {지표: 감소액}}. 부호를 여기서 한 번만 뒤집는다.

    입력은 산출기준(basis) 하나로 좁힌 표여야 한다. `alm_irrbb_result`의 낟알은
    (기준일, 산출기준, 시나리오)이므로 좁히지 않고 넘기면 시나리오가 중복되고,
    그중 마지막 행 하나가 조용히 공시값이 된다. 중복을 그대로 받지 않는다.

    폐지 계정(2019.11.29 개정으로 대체된 별표9의1_2014)으로 산출한 행도 받지
    않는다. 그 수치가 <표6>에 들어가면 폐지된 체계의 값이 현행 공시로 나간다.
    """
    if result is None or result.empty:
        return {}
    if "framework_status" in result.columns:
        repealed = sorted({
            str(r.framework_version) for r in result.itertuples()
            if str(r.framework_status) == _REPEALED_STATUS})
        if repealed:
            raise ValueError(
                f"{label} 산출결과에 폐지 계정 {repealed} 행이 있다. 폐지된 "
                f"체계의 수치는 <표6>에 올리지 않는다")
    counts = result["scenario"].value_counts()
    dup = sorted(str(s) for s, n in counts.items() if n > 1)
    if dup:
        raise ValueError(
            f"{label} 산출결과에 시나리오 {dup}가 여러 행이다. <표6>은 산출기준 "
            f"하나의 표를 받는다. 좁히지 않으면 어느 행이 공시값인지 정해지지 "
            f"않는다")
    missing = sorted(set(IRRBB_SCENARIOS) - {str(s) for s in result["scenario"]})
    if missing:
        raise ValueError(
            f"{label} 산출결과에 시나리오 {missing}가 없다. <표6>은 6개 시나리오 "
            "전건을 요구하며 자체 조정이 금지된다")
    out: dict[str, dict[str, float | None]] = {}
    for r in result.itertuples():
        eve = float(r.delta_eve)
        nii = getattr(r, "delta_nii", None)
        nii = None if nii is None or pd.isna(nii) else float(nii)
        out[str(r.scenario)] = {
            TABLE6_MEASURES[0]: -eve,
            TABLE6_MEASURES[1]: None if nii is None else -nii,
        }
    return out


def build_table6(
    current: pd.DataFrame | None,
    prior: pd.DataFrame | None = None,
    *,
    asof: str,
    tier1_current: float | None = None,
    tier1_prior: float | None = None,
    framework_version: str = KR_FRAMEWORK_2026,
) -> tuple[pd.DataFrame, list[ParamWarning]]:
    """제22항 나 <표6> 금리리스크 수준 공시.

    `current`·`prior`는 `alm_irrbb_result`를 산출기준 하나로 좁힌 표이며
    `scenario`·`delta_eve`·`delta_nii` 컬럼을 읽는다. 6개 시나리오가 전건
    있어야 하고, 없으면 만들다가 멈춘다. 자체 조정 금지 양식이므로 행을 빼는
    것으로 결손을 넘어가지 않는다. 좁히지 않은 표(시나리오 중복)와 폐지 계정으로
    산출한 행도 받지 않는다.

    전기 산출값이나 기본자본이 없으면 그 칸이 비고 `blank_reason`이 사유를
    적는다. 당기 값을 전기 칸에 복사하지 않는다.
    """
    warns: list[ParamWarning] = []
    cur = _scenario_values(current, label=TABLE6_PERIODS[0])
    pri = _scenario_values(prior, label=TABLE6_PERIODS[1])
    if current is None or current.empty:
        warns.append(ParamWarning(
            "disc_irrbb_table6", "당기", "delta_eve", _MISSING_CURRENT))
    if prior is None or prior.empty:
        warns.append(ParamWarning(
            "disc_irrbb_table6", "전기", "delta_eve", _MISSING_PRIOR))
    tier1 = {TABLE6_PERIODS[0]: tier1_current, TABLE6_PERIODS[1]: tier1_prior}
    for period, v in tier1.items():
        if v is None:
            warns.append(ParamWarning(
                "disc_irrbb_table6", period, "tier1",
                "기본자본이 제공되지 않았다. <표6>의 기본자본 행을 비운다"))

    src = {TABLE6_PERIODS[0]: cur, TABLE6_PERIODS[1]: pri}
    rows = []
    for row_seq, (row_code, row_name, scenario) in enumerate(TABLE6_ROWS, start=1):
        for col_seq, (col_code, measure, period) in enumerate(TABLE6_COLUMNS,
                                                              start=1):
            value: float | None = None
            blank: str | None = None
            vals = src[period]

            if row_code == TABLE6_TIER1_ROW:
                if measure == TABLE6_MEASURES[0]:
                    value = None if tier1[period] is None else float(tier1[period])
                    blank = None if value is not None else (
                        "기본자본이 제공되지 않았다")
                else:
                    blank = _TIER1_BLANK
            elif not vals:
                blank = (_MISSING_CURRENT if period == TABLE6_PERIODS[0]
                         else _MISSING_PRIOR)
            elif row_code == TABLE6_MAX_ROW:
                seen = [vals[s][measure] for _c, _n, s in TABLE6_ROWS[:len(IRRBB_SCENARIOS)]
                        if s is not None and vals[s][measure] is not None]
                if seen:
                    value = max(seen)
                else:
                    blank = _NII_BLANK
            else:
                value = vals[scenario][measure]
                if value is None:
                    blank = _NII_BLANK

            rows.append({
                "asof": asof, "form_code": TABLE6_FORM_CODE,
                "framework_version": framework_version,
                "row_seq": row_seq, "row_code": row_code, "row_name": row_name,
                "scenario": scenario, "col_seq": col_seq, "col_code": col_code,
                "measure": (TABLE6_MEASURES[2]
                            if row_code == TABLE6_TIER1_ROW else measure),
                "period": period, "value": value,
                "sign_convention": SIGN_CONVENTION, "blank_reason": blank,
                "is_adjustable": False,
                "citation": f"{_CITE} 나 <표6>",
                "evidence_status": "원문확인",
            })

    df = pd.DataFrame(rows, columns=[c.name for c in DISC_TABLE6.columns])
    return df.astype({"value": "float64", "row_seq": "int64",
                      "col_seq": "int64", "is_adjustable": "bool"}), warns


def table6_matrix(table6: pd.DataFrame) -> pd.DataFrame:
    """<표6>을 8행 × 4열 표로 편다. 화면·엑셀이 그리는 모양이다.

    행·열 이름과 순서는 `TABLE6_ROWS`·`TABLE6_COLUMNS`가 정하며 데이터에서
    추론하지 않는다. 값이 빠진 셀이 있어도 표의 모양은 변하지 않는다.
    """
    wide = table6.pivot(index="row_code", columns="col_code", values="value")
    out = wide.reindex(index=list(_ROW_CODES), columns=list(_COL_CODES))
    names = {code: name for code, name, _s in TABLE6_ROWS}
    out.insert(0, "row_name", [names[c] for c in out.index])
    return out


# ---------------------------------------------------------------- <표7>

def build_table7_qualitative(
    entries: pd.DataFrame | None = None, *, asof: str,
) -> tuple[pd.DataFrame, list[ParamWarning]]:
    """제22항 나 <표7> 가 정성공시 8항목.

    `entries`는 수기입력 표이며 `item_no`·`narrative`·`input_by`·`approved_by`·
    `approved_date`를 읽는다. 8항목은 입력 여부와 무관하게 전건 나오고, 미입력
    항목은 문안이 빈 채로 `is_disclosed=False`가 된다. 항목을 빼면 무엇이
    비었는지가 화면에서 사라진다.

    선택사항인 8번(기타 정보)이 비어 있는 것은 경고를 만들지 않는다. 1~7번이
    비면 경고가 나간다. 문안이 있는데 승인자·승인일이 없으면 `is_approved`가
    False이고 경고가 붙는다.
    """
    warns: list[ParamWarning] = []
    by_no: dict[int, object] = {}
    if entries is not None and not entries.empty:
        known = {no for no, _n, _o in TABLE7_QUALITATIVE_ITEMS}
        unknown = sorted({int(n) for n in entries["item_no"]} - known)
        if unknown:
            raise ValueError(
                f"정성공시에 없는 항목 번호 {unknown}. <표7> 가는 "
                f"{sorted(known)} 8항목이며 자체 조정이 금지된다")
        by_no = {int(r.item_no): r for r in entries.itertuples()}

    rows = []
    for item_no, item_name, optional in TABLE7_QUALITATIVE_ITEMS:
        rec = by_no.get(item_no)
        narrative = input_by = approved_by = approved_date = None
        if rec is not None:
            narrative = _text(getattr(rec, "narrative", None))
            input_by = _text(getattr(rec, "input_by", None))
            approved_by = _text(getattr(rec, "approved_by", None))
            approved_date = _text(getattr(rec, "approved_date", None))
        disclosed = narrative is not None
        approved = disclosed and approved_by is not None and approved_date is not None

        if not disclosed and not optional:
            warns.append(ParamWarning(
                "disc_irrbb_table7", f"정성공시 {item_no}", "narrative",
                "공시 문안이 입력되지 않았다. 문안을 지어내지 않고 비운 채로 둔다"))
        elif disclosed and not approved:
            warns.append(ParamWarning(
                "disc_irrbb_table7", f"정성공시 {item_no}", "approved_by",
                "공시 문안에 승인자 또는 승인일이 없다"))

        rows.append({
            "asof": asof, "form_code": TABLE7_FORM_CODE, "item_no": item_no,
            "item_name": item_name, "is_optional": optional,
            "narrative": narrative, "is_disclosed": disclosed,
            "input_by": input_by, "approved_by": approved_by,
            "approved_date": approved_date, "is_approved": approved,
            "citation": f"{_CITE} 나 <표7> 가({item_no})",
            "evidence_status": "원문확인",
        })

    df = pd.DataFrame(rows,
                      columns=[c.name for c in DISC_TABLE7_QUALITATIVE.columns])
    return df.astype({"item_no": "int64", "is_optional": "bool",
                      "is_disclosed": "bool", "is_approved": "bool"}), warns


def build_table7_quantitative(
    values: dict[str, float | None] | None = None,
    *,
    asof: str,
    basis: dict[str, str] | None = None,
) -> tuple[pd.DataFrame, list[ParamWarning]]:
    """제22항 나 <표7> 나 정량공시 2항목.

    비만기성예금의 평균 금리개정만기와 최장 금리개정만기다. 두 값은 비만기성
    예금 슬로팅 산출에서 나오며 이 모듈이 만들지 않는다. 넘어오지 않으면 값이
    비고 경고가 나간다.
    """
    warns: list[ParamWarning] = []
    given = dict(values or {})
    basis = dict(basis or {})
    unknown = sorted(set(given) - {c for c, _n, _u in TABLE7_QUANTITATIVE_ITEMS})
    if unknown:
        raise ValueError(
            f"정량공시에 없는 항목 코드 {unknown}. <표7> 나는 2항목이며 자체 "
            "조정이 금지된다")

    rows = []
    for code, name, unit in TABLE7_QUANTITATIVE_ITEMS:
        v = given.get(code)
        v = None if v is None or pd.isna(v) else float(v)
        if v is None:
            warns.append(ParamWarning(
                "disc_irrbb_table7", code, "value",
                "금리개정만기 산출값이 넘어오지 않았다. 값을 비운다"))
        rows.append({
            "asof": asof, "form_code": TABLE7_FORM_CODE, "item_code": code,
            "item_name": name, "value": v, "value_unit": unit,
            "is_disclosed": v is not None, "basis": basis.get(code),
            "citation": f"{_CITE} 나 <표7> 나",
            "evidence_status": "원문확인",
        })

    df = pd.DataFrame(
        rows, columns=[c.name for c in DISC_TABLE7_QUANTITATIVE.columns])
    return df.astype({"value": "float64", "is_disclosed": "bool"}), warns


def _text(value) -> str | None:
    """빈 문자열과 결측을 같은 '미입력'으로 읽는다."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    s = str(value).strip()
    return s or None
