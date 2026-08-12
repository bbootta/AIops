"""FSS FINES 업무보고서 마스터 → risk_lib/regulatory/fss_master.py 생성기.

서식번호·보고서명·작성주기를 손으로 옮겨 적지 않는다. 손으로 적으면 틀리고,
틀린 서식번호는 번호가 없는 것보다 나쁘다 (제출 단계에서 잘못된 서식에 값이
실린다). 이 스크립트는 금감원 배포 마스터 엑셀을 읽어 은행 업권 전 서식을
그대로 모듈로 굳힌다.

    python3 tools/gen_fss_master.py <마스터.xlsx>
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

OUT = Path("risk_lib/regulatory/fss_master.py")

# 리스크관리 소관 편제 — 이 다섯 분류가 본 하네스의 산출 범위다.
RISK_CATEGORIES = {
    "2. 재무현황 / 다. 자본적정성": "자본적정성",
    "2. 재무현황 / 라. 자산건전성": "자산건전성",
    "2. 재무현황 / 바. 유동성": "유동성",
    "2. 재무현황 / 자. 리스크": "리스크지표",
    "3. 업무규제 준수현황 / 자. 리스크": "업무규제준수",
}

# 국내 일반은행이 제출하지 않는 서식 — 제출 주체가 다르다.
# 판정 근거는 보고서명의 괄호 표기이며, 여기 없는 것은 전부 제출 대상이다.
NOT_APPLICABLE = {
    "B2303": "외국은행 국내지점 전용",
    "B2307": "외국은행 국내지점 전용",
    "B2310": "외국은행 국내지점 전용",
    "B2313": "외국은행 국내지점 전용",
    "B3102": "외국은행 국내지점 전용",
    "B3105": "산업·기업·수출입은행 근거법 전용",
    "B3106": "농협·수협 근거법 전용",
    # 리스크 소관 밖 편제에도 외은 국내지점 전용 서식이 있다. 편제 분류가
    # "외국은행 국내지점"이거나 보고서명에 (외은) 표기가 있으면 제출 주체가
    # 다르다 — 국내 일반은행은 (일은) 표기 서식을 제출한다.
    "B1103": "외국은행 국내지점 전용 (국내은행은 B1101)",
    "B2702": "외국은행 국내지점 전용 (국내은행은 B2701)",
    "B5301": "외국은행 국내지점 전용",
    "B5302": "외국은행 국내지점 전용",
    "B5303": "외국은행 국내지점 전용",
    "B5304": "외국은행 국내지점 전용",
    "B5305": "외국은행 국내지점 전용",
    "B5306": "외국은행 국내지점 전용",
    "B6101": "외국은행 국내지점 전용",
    "B6102": "외국은행 국내지점 전용",
}


def main(src: str) -> int:
    m = pd.read_excel(src, sheet_name="ID_마스터")
    bank = m[m["업권"] == "은행"].copy()
    bank["구분"] = bank["분류"].map(RISK_CATEGORIES).fillna("범위밖")
    bank = bank.sort_values(["구분", "업무보고서_ID"])

    rows = []
    for _, r in bank.iterrows():
        code = str(r["업무보고서_ID"])
        rows.append((code, str(r["보고서명"]), str(r["구분"]),
                     str(r["작성주기"]), str(r["분류"]),
                     NOT_APPLICABLE.get(code)))

    body = "\n".join(
        f"    FssForm({c!r}, {n!r}, {g!r}, {f!r}, {cat!r}, {na!r}),"
        for c, n, g, f, cat, na in rows)

    asof = pd.read_excel(src, sheet_name="ID_마스터")["첨부파일_기준일"].max()
    OUT.write_text(f'''"""금융감독원 FINES 업무보고서 마스터 — 은행 업권 전 서식.

**이 파일은 기계 생성물이다.** 직접 고치지 말고 `tools/gen_fss_master.py`를
다시 돌린다. 서식번호를 손으로 옮겨 적으면 틀리고, 틀린 서식번호는 번호가
없는 것보다 나쁘다 — 제출 단계에서 잘못된 서식에 값이 실린다.

출처: 금감원 FINES 업무보고서 ID 마스터 (조사기준일 {str(asof)[:10]})
은행 업권 {len(rows)}건 — B(국내) · BA(바젤Ⅲ 신설) · BF(해외점포).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FssForm:
    code: str                     # FINES 서식번호
    name: str                     # 공식 보고서명
    group: str                    # 자본적정성·자산건전성·유동성·리스크지표·업무규제준수·범위밖
    frequency: str                # 작성주기
    category: str                 # 원 분류 문자열
    not_applicable: str | None = None   # 제출 대상이 아니면 그 사유

    @property
    def applicable(self) -> bool:
        return self.not_applicable is None


BANK_FORMS: tuple[FssForm, ...] = (
{body}
)

BY_CODE: dict[str, FssForm] = {{f.code: f for f in BANK_FORMS}}

# 리스크관리 소관 — 이 범위의 제출 대상 서식은 빠짐없이 산출해야 한다.
RISK_GROUPS: tuple[str, ...] = (
    "자본적정성", "자산건전성", "유동성", "리스크지표", "업무규제준수")


def risk_scope(applicable_only: bool = True) -> tuple[FssForm, ...]:
    return tuple(f for f in BANK_FORMS
                 if f.group in RISK_GROUPS and (f.applicable or not applicable_only))
''', encoding="utf-8")
    print(f"{OUT} 생성 — 은행 {len(rows)}건 "
          f"(리스크 소관 {sum(1 for r in rows if r[2] != '범위밖')}건, "
          f"해당없음 {sum(1 for r in rows if r[5])}건)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
