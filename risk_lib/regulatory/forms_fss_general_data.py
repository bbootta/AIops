"""일반현황·집합투자증권 판매·휴면금융재산·금리인하요구권 서식의 파생 데이터.

**이 그룹은 리스크 산출과 가장 멀고 파생 비중이 가장 높다.** 인사·점포·전자금융·
펀드판매·휴면예금 원장이 이 저장소에 아예 없기 때문이다. 상수를 박으면 서식이
산출과 무관해지고, 실행마다 난수를 새로 뽑으면 제출본 지문
(`forms.submission_digest`)이 흔들려 같은 제출본인지 판별할 수 없다. 그래서
**기준일 고정 시드에서 유도한 결정론적 RNG**로 만든다 — 같은 시드면 언제나 같은
값이다. 시드 기반은 `forms_fss_compliance_data.rng`를 그대로 쓴다. 같은 저장소에
시드 기반이 여럿이면 "어느 파생이 어느 기준일 것인지"를 말할 수 없기 때문이다.

**새로 파생하지 않고 재사용하는 것** (같은 개념을 두 번 파생하면 값이 갈린다)
  임직원 수          `forms_fss_keyfin_data.headcount` — B2701(생산성)이 쓰는 바로
                     그 값이다. 이 모듈은 `headcount`를 다시 내보내기만 하고 새로
                     만들지 않는다. 같은 은행의 임직원 수가 B1101과 B2701에서
                     다르면 제출본이 성립하지 않는다.
  국내 점포 수        `forms_fss_keyfin_data.domestic_branches` — B5103과 같은 값.
  해외 점포           `forms_fss_overseas_data.branch_master` — BF101·B5103과 같은 마스터.
  가계여신 지역분포    `forms_fss_retail_data.household(ctx)["region"]` — B2127·B2426
                     계열이 쓰는 바로 그 분포. B1107의 권역 비중이 여기서 온다.
  대출모집 위탁사      `forms_fss_compliance_data.loan_agent_book` — B3114와 같은 위탁사.
  공공금고 예수금      `forms_fss_keyfin_data.public_deposits` — B1108 금고대행 판정 근거.

원장·산출에서 그대로 오는 것 (파생 아님)
  예수금·자산총계      `pru_balance_sheet` 실측. 휴면예금·미거래예금·펀드판매잔액·
                     전자금융 고객수의 **앵커가 전부 이 표**다.
  가계여신 잔액·건수    `rdm_asset_quality.balance` 실측. B1112(비대면 대출)와
                     B10101(금리인하요구권)의 모집단은 실제 익스포저다.
  기업 차주 수         `rdm_obligor` 실측 — B1110 법인 전자금융 고객 수의 모수.
  차주별 PD           `portfolio.pd` 실측 — B10101 신청·수용 성향의 기울기.

시드 고정으로 파생하는 것 (원장 부재)
  인원 세부구성        성별·직급·신규채용·퇴직·평균근속. 총원은 `headcount`이고
                     세부는 **잔여로 맞춰** 합이 언제나 총원이 된다.
  본점 기구            사업그룹·부서 수. 점포 수에서 파생.
  시·도별 점포         권역(수도권·광역시·기타지방) 비중은 가계 차주 실측 분포이고
                     권역 **안의** 시·도 배분만 파생. 최대잔여법으로 정수 배분해
                     시·도 합이 반드시 국내 점포 수가 된다.
  무인자동화기기        점포당 기기 수·점외 비중·기기 유형.
  개인 고객 수         개인 예수금(실측) ÷ 1인당 예금잔액(파생).
  전자금융 가입자·거래  채널별 침투율·1인당 거래횟수·건당 금액. 등록고객 수는
                     채널 최대값보다 크게 잡아 "가입자 > 고객수"가 나오지 않게 한다.
  비대면 대출 채널      가계 익스포저마다 취급채널을 뽑는다. **금액·건수는 실측**이고
                     채널 라벨만 파생이다.
  업무위수탁·정보처리위탁 위탁 목록·수탁사 수·재위탁 여부. 목록은 난수가 아니라
                     고정 어휘이고 규모만 파생이다.
  부수·겸영업무 영위여부 이 하네스의 원장·산출에 그 업무의 흔적이 있는지로 판정한다
                     (예: 신탁계정 없음 → 미영위, 부외 익스포저에 직접적 신용대체
                     있음 → 지급보증 영위). 판정 근거를 업무마다 서식에 남기되
                     **[원장]·[편제]·[파생]으로 근거의 층위를 구분해 적는다** —
                     파생값을 보고 내린 판정을 원장 대조로 읽히게 두면 안 된다.
  집합투자증권 판매     판매 원장이 없다. 판매잔액은 **예수금 총액(실측) × 파생비율**,
                     유형·수익자 배분과 판매보수율·계좌당 평잔이 파생이다.
                     수익자별 개인·법인 비중은 개인·법인 예수금 실측 비중을 쓴다.
  휴면예금·미거래예금   휴면예금 원장이 없다. **개인 예수금(실측) × 파생 휴면율**이
                     앵커이고 종류·금액구간·경과기간·연령 배분이 파생이다. 금액구간별
                     계좌수는 따로 뽑지 않고 **구간 대표금액으로 나눠** 만든다 —
                     금액과 계좌수를 독립으로 뽑으면 구간 평균잔액이 구간을 벗어난다.
  휴면 자기앞수표      발행대금 원장이 없다. 법인 결제성 예수금(실측)에 앵커한다.
  금리인하요구권 신청·수용 신청·수용 원장이 없다. **대상 여신은 실제 포트폴리오**이고
                     신청·수용 여부와 인하폭만 파생이다.

파생하지 않고 0으로 두는 것
  투자자문업 전 항목    `ADVISORY_LICENSED = False`. 사유는 그 상수 주석에 있다.

파생값이 들어간 서식 라인은 **그 라인 자체의** formula에 그 사실을 남긴다.
상위 소계에만 적어 두면 서식이 flat table로 실체화될 때 하위 셀이 실측으로 읽힌다.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd

from risk_lib.regulatory.forms_fss_compliance_data import (
    loan_agent_book, rng,
)
from risk_lib.regulatory.forms_fss_financial_data import (
    CORP_DEPOSITS, RETAIL_DEPOSITS, bs_amounts,
)
from risk_lib.regulatory.forms_fss_keyfin_data import (
    domestic_branches, headcount, public_deposits,
)
from risk_lib.regulatory.forms_fss_overseas_data import branch_master
from risk_lib.regulatory.forms_fss_retail_data import REGIONS, household

__all__ = [
    "ADVISORY_LICENSED", "ADVISORY_REASON", "headcount", "domestic_branches",
    "staff", "org_units", "region_branches", "atm", "retail_customers",
    "ebank_subscribers", "ebank_transactions", "ebank_loan_book",
    "outsourcing", "it_outsourcing", "ancillary_business", "fund_sales",
    "fund_investors", "dormant_deposits", "inactive_deposits",
    "cashier_checks", "rate_cut_requests",
]


# ---------------------------------------------------------------- 영위 여부

# 투자자문업 영위 여부. **없는 영업을 파생으로 만들어 내는 것이 가장 나쁘다.**
# 판단 근거: (1) 손익계산서(`pru_income_statement`)에 자문수수료 수익 계정이 없고,
# (2) `rdm_*` · `mkt_*` 어디에도 자문계약·자문재산 원장이 없으며,
# (3) 자본시장법상 투자자문업은 별도 등록 업무여서 겸영 흔적이 없으면 미등록으로
# 보는 것이 보수적이다. 흔적이 하나라도 생기면 이 상수부터 고친다 —
# B11101~B11107·B12101 여덟 서식이 전부 이 값 하나를 본다.
ADVISORY_LICENSED = False
ADVISORY_REASON = ("투자자문업 미영위 — 자문계약·자문재산 원장 및 자문수수료 수익 "
                   "계정이 이 산출체계에 존재하지 않는다. 0은 '미조회'가 아니라 "
                   "'해당 영업 없음'이다.")

# 집합투자증권 판매는 미영위가 아니다. B8101~B8104가 FINES 제출대상이고 은행법
# 제28조 겸영업무(투자중개업)로 영위하는 것으로 본다 — 판매 **원장**이 없을 뿐이다.

_DERIVED = "원장 부재 — 기준일 고정 시드 파생값"


def _apportion(total: float, weights: np.ndarray) -> np.ndarray:
    """정수 배분 — 최대잔여법. 합이 반드시 total이어야 소계 대사가 성립한다."""
    w = np.asarray(weights, dtype=float)
    w = w / w.sum() if w.sum() else np.full(len(w), 1.0 / len(w))
    target = int(round(float(total)))
    raw = w * target
    base = np.floor(raw).astype(int)
    order = np.argsort(-(raw - base))
    for i in range(target - int(base.sum())):
        base[order[i % len(base)]] += 1
    return base.astype(float)


def _pick(key: str, weights: np.ndarray, labels: tuple[str, ...]) -> list[str]:
    """행별 확률로 라벨을 하나씩 뽑는다 — 행 순서가 고정돼야 재현된다."""
    w = weights / weights.sum(axis=1, keepdims=True)
    u = rng(key).random(len(w))
    idx = (w.cumsum(axis=1) < u[:, None]).sum(axis=1).clip(0, w.shape[1] - 1)
    return [labels[int(i)] for i in idx]


def _z(s: pd.Series) -> np.ndarray:
    v = s.to_numpy(dtype=float)
    sd = float(np.nanstd(v))
    return (v - float(np.nanmean(v))) / (sd if sd else 1.0)


def retail_deposits(ctx) -> float:
    """개인 예수금 합계 — 휴면·미거래·펀드판매·고객수 파생의 실측 앵커."""
    amt = bs_amounts(ctx)
    return sum(amt[i] for i in RETAIL_DEPOSITS)


def corporate_deposits(ctx) -> float:
    amt = bs_amounts(ctx)
    return sum(amt[i] for i in CORP_DEPOSITS)


# ---------------------------------------------------------------- 인원 (B1101)

RANKS: tuple[str, ...] = ("부점장급", "책임자급(차·과장급)", "행원급")


def staff(ctx) -> dict:
    """인원 세부구성 — 총원은 `headcount`(B2701과 같은 값)이고 구성만 파생이다.

    구성은 전부 **잔여로 맞춘다**. 성별·직급·고용형태를 독립으로 뽑으면 합이
    총원과 어긋나 서식이 스스로 틀린다.
    """
    h = headcount(ctx)
    total, officer = int(h["total"]), int(h["officer"])
    temporary, regular = int(h["temporary"]), int(h["regular"])
    female = int(round(total * float(rng("여성비중").uniform(0.45, 0.58))))
    # 직급은 임원을 뺀 인원만 가른다 — 임원은 직급 체계 밖이다.
    ranks = _apportion(total - officer,
                       rng("직급구성").dirichlet(np.array([1.0, 3.5, 6.0])))
    g = rng("인력이동")
    hired = int(round(total * float(g.uniform(0.010, 0.035))))
    left = int(round(total * float(g.uniform(0.008, 0.030))))
    return {
        "total": float(total), "officer": float(officer),
        "regular": float(regular), "temporary": float(temporary),
        "female": float(female), "male": float(total - female),
        "ranks": dict(zip(RANKS, ranks)),
        "hired": float(hired), "left": float(left),
        "tenure_years": float(rng("평균근속").uniform(10.0, 15.5)),
        "avg_age": float(rng("평균연령").uniform(38.0, 45.0)),
        "assets_per_staff": h["assets_per_staff"],
    }


# ---------------------------------------------------------------- 기구 (B1104)

def org_units(ctx) -> dict:
    """본점 기구 — 부서 수는 원장이 없어 점포 수에서 파생한다.

    영업점·해외점포는 새로 파생하지 않고 B5103과 같은 함수를 읽는다.
    """
    br = domestic_branches(ctx)
    bm = branch_master(ctx)
    g = rng("본점기구")
    return {
        "hq_group": float(int(g.integers(4, 9))),      # 사업그룹(본부)
        "hq_dept": float(int(g.integers(24, 46))),     # 본점 부서
        "head_office": br["head_office"],
        "branch": br["branch"],
        "sub_office": br["sub_office"],
        "domestic_total": br["total"],
        "ov_branch": float(int((bm["kind"] == "지점").sum())),
        "ov_subsidiary": float(int((bm["kind"] == "현지법인").sum())),
        "ov_rep": float(int((bm["kind"] == "사무소").sum())),
        "ov_total": float(len(bm)),
    }


# ---------------------------------------------------------------- 점포 (B1107)

# 행정구역 어휘 — `forms_fss_retail_data.REGIONS`의 3개 권역을 시·도로 편다.
# 권역 라벨이 갈리면 B1107과 B2426 계열의 지역 집계를 맞댈 수 없다.
REGION_SIDO: dict[str, tuple[str, ...]] = {
    "수도권": ("서울특별시", "인천광역시", "경기도"),
    "광역시": ("부산광역시", "대구광역시", "광주광역시", "대전광역시", "울산광역시"),
    "기타 지방": ("세종특별자치시", "강원특별자치도", "충청북도", "충청남도",
              "전북특별자치도", "전라남도", "경상북도", "경상남도", "제주특별자치도"),
}


def region_branches(ctx) -> pd.DataFrame:
    """시·도별 점포 수 — 권역 비중은 가계 차주 실측 분포, 시·도 배분만 파생이다.

    권역 비중을 새로 뽑지 않는 것이 중요하다. B2426 계열이 쓰는 지역분포와 다른
    분포로 점포를 깔면 "영업점은 지방에 있는데 여신은 수도권"인 서식이 나온다.
    """
    hh = household(ctx)
    share = (hh["region"].value_counts(normalize=True)
             .reindex(list(REGIONS)).fillna(0.0))
    total = domestic_branches(ctx)["total"]
    by_region = _apportion(total, share.to_numpy(dtype=float))
    rows = []
    for region, n in zip(REGIONS, by_region):
        sido = REGION_SIDO[region]
        w = rng(f"시도배분:{region}").dirichlet(np.full(len(sido), 2.0))
        for name, cnt in zip(sido, _apportion(n, w)):
            rows.append({"region": region, "sido": name, "n_branch": cnt,
                         "region_share": float(share[region])})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 기기 (B1105)

ATM_KINDS: tuple[str, ...] = ("현금자동지급기(CD)", "현금자동입출금기(ATM)",
                              "지능형 자동화기기(STM)")


def atm(ctx) -> dict:
    """무인자동화기기 — 기기 원장이 없어 점포 수에서 파생한다."""
    branches = domestic_branches(ctx)["total"]
    per_branch = float(rng("점포당기기").uniform(2.0, 3.6))
    total = float(round(branches * per_branch))
    outside = float(round(total * float(rng("점외비중").uniform(0.25, 0.45))))
    kinds = _apportion(total, rng("기기유형").dirichlet(np.array([2.0, 6.0, 1.5])))
    return {
        "total": total, "inside": total - outside, "outside": outside,
        "per_branch": per_branch, "kinds": dict(zip(ATM_KINDS, kinds)),
        # 공동망 제휴기기는 자행 설치분이 아니므로 총계에 넣지 않는다.
        "shared_network": float(round(total
                                      * float(rng("공동망비중").uniform(0.1, 0.3)))),
    }


# ---------------------------------------------------------------- 전자금융 (B1110~B1112)

EBANK_CHANNELS: tuple[str, ...] = ("인터넷뱅킹", "모바일뱅킹", "텔레뱅킹", "오픈뱅킹")
# 채널별 (개인 침투율 하한, 상한, 법인 침투율 하한, 상한). 텔레뱅킹은 개인이,
# 오픈뱅킹은 법인이 낮다는 것 말고 다른 관찰 근거는 없다 — 전부 가정치다.
_PENETRATION: dict[str, tuple[float, float, float, float]] = {
    "인터넷뱅킹": (0.42, 0.58, 0.70, 0.90),
    "모바일뱅킹": (0.58, 0.78, 0.35, 0.55),
    "텔레뱅킹": (0.08, 0.18, 0.10, 0.25),
    "오픈뱅킹": (0.20, 0.36, 0.05, 0.15),
}


def retail_customers(ctx) -> dict:
    """고객 수 — 개인은 예수금(실측) ÷ 1인당 예금(파생), 법인은 차주 수(실측)다.

    개인 고객 원장이 없다. 1인당 예금잔액을 뽑아 나누면 예수금 규모가 커질수록
    고객 수도 커져 서식이 산출과 같이 움직인다. 반대로 고객 수를 직접 뽑으면
    1인당 예금이 은행 규모와 무관하게 흔들린다.
    """
    per_head = float(rng("1인당예금").uniform(8.0e6, 1.5e7))
    individual = float(round(retail_deposits(ctx) / per_head))
    corp = float(ctx.tables["rdm_obligor"]
                 .query("asset_class in ['corporate', 'bank', 'sovereign']")
                 ["obligor_id"].nunique())
    return {"individual": individual, "corporate": corp,
            "deposit_per_head": per_head}


def ebank_subscribers(ctx) -> pd.DataFrame:
    """채널별 전자금융 가입자 수 — 고객 수 × 채널 침투율(파생).

    채널 가입은 중복되므로 채널 합계는 고객 수를 넘을 수 있다. 대신 중복을 제외한
    **등록고객 수**를 따로 두고, 채널 최댓값보다 크게 잡는다 — 어느 채널 가입자가
    등록고객보다 많은 서식은 그 자체로 틀렸다.
    """
    cust = retail_customers(ctx)
    rows = []
    for ch in EBANK_CHANNELS:
        lo, hi, clo, chi = _PENETRATION[ch]
        g = rng(f"침투율:{ch}")
        rows.append({
            "channel": ch,
            "individual": float(round(cust["individual"] * g.uniform(lo, hi))),
            "corporate": float(round(cust["corporate"] * g.uniform(clo, chi))),
        })
    df = pd.DataFrame(rows)
    df["total"] = df["individual"] + df["corporate"]
    return df


def ebank_registered(ctx) -> dict:
    """중복 제외 등록고객 수 — 채널 최댓값에 여유배수를 곱해 만든다."""
    sub = ebank_subscribers(ctx)
    cust = retail_customers(ctx)
    out = {}
    for col in ("individual", "corporate"):
        peak = float(sub[col].max())
        slack = float(rng(f"등록여유:{col}").uniform(1.03, 1.18))
        out[col] = float(round(min(cust[col], peak * slack)))
    out["total"] = out["individual"] + out["corporate"]
    return out


def ebank_transactions(ctx) -> pd.DataFrame:
    """채널별 분기 거래 — 거래 원장이 없어 가입자 × 1인당 건수 × 건당 금액이다."""
    sub = ebank_subscribers(ctx)
    rows = []
    for _, r in sub.iterrows():
        g = rng(f"거래:{r['channel']}")
        # 조회거래는 제외하고 자금이동 거래만 센다 — 건당 금액이 정의되는 거래다.
        per_user = float(g.uniform(4.0, 22.0))
        per_txn = float(g.uniform(3.0e5, 2.6e6))
        n = float(round(r["total"] * per_user))
        rows.append({"channel": r["channel"], "n_txn": n,
                     "amount": n * per_txn, "per_user": per_user,
                     "per_txn": per_txn})
    return pd.DataFrame(rows)


EBANK_LOAN_CHANNELS: tuple[str, ...] = ("영업점 창구", "인터넷뱅킹", "모바일뱅킹")


def ebank_loan_book(ctx) -> pd.DataFrame:
    """가계여신 취급채널 — **잔액·건수는 실측이고 채널 라벨만 파생이다.**

    비대면 비중을 잔액에 곱해 만들지 않는다. 익스포저마다 채널을 붙이면 채널별
    합계가 자동으로 실측 총액이 되고, 연체·건전성 같은 다른 축과도 교차된다.
    주담대는 담보 실행 절차 때문에 창구로, 잔액이 작을수록 모바일로 기운다 —
    비대면 대출이 소액 신용대출 중심이라는 관찰을 담았다. 기울기를 신용점수로
    잡지 않은 것은 `credit_score`가 기타가계에만 있어 주담대 쪽이 NaN이 되기
    때문이다(NaN이 섞이면 전 건이 첫 채널로 몰린다).
    """
    hh = household(ctx).copy()
    rm = hh["is_mortgage"].to_numpy()
    zs = -_z(np.log(hh["balance"].clip(lower=1.0)))
    hh["channel"] = _pick("취급채널", np.column_stack([
        np.where(rm, 0.80, np.clip(0.45 - 0.10 * zs, 0.10, 0.85)),
        np.where(rm, 0.12, np.clip(0.20 + 0.03 * zs, 0.05, 0.50)),
        np.where(rm, 0.08, np.clip(0.35 + 0.10 * zs, 0.05, 0.85))]),
        EBANK_LOAN_CHANNELS)
    return hh


# ---------------------------------------------------------------- 위수탁 (B1115·B1116)

# 위탁업무 어휘 — 규정이 열거한 목록이 아니라 편제용 고정 어휘다. 목록 자체는
# 난수가 아니고 수탁사 수·재위탁 여부만 파생이다.
OUTSOURCING_ITEMS: tuple[tuple[str, str], ...] = (
    ("전산시스템 운영·유지보수", "비계열 국내법인"),
    ("콜센터(고객상담) 운영", "비계열 국내법인"),
    ("연체채권 추심", "비계열 국내법인"),
    ("대출모집", "비계열 국내법인"),
    ("신용카드 회원모집", "비계열 국내법인"),
    ("우편·통지서 인쇄 및 발송", "비계열 국내법인"),
    ("현금 수송·정사", "비계열 국내법인"),
    ("문서 보관·파기", "비계열 국내법인"),
    ("담보물 감정평가", "비계열 국내법인"),
    ("인사·급여 처리", "계열회사"),
)

IT_OUTSOURCING_ITEMS: tuple[tuple[str, str, bool], ...] = (
    # (위탁업무, 수탁자 소재, 고유식별정보 처리 여부)
    ("계정계 시스템 운영", "국내", True),
    ("정보계·데이터웨어하우스 운영", "국내", True),
    ("인터넷·모바일뱅킹 채널 운영", "국내", True),
    ("클라우드 이용(IaaS)", "국내", False),
    ("클라우드 이용(SaaS)", "국외", False),
    ("보안관제(SOC)", "국내", False),
    ("백업·재해복구센터 운영", "국내", True),
)


def outsourcing(ctx) -> pd.DataFrame:
    """업무위수탁 명세 — 대출모집만 B3114와 같은 위탁사 수를 쓴다."""
    hh_balance = float(household(ctx)["balance"].sum())
    agents = len(loan_agent_book(hh_balance))
    g = rng("위탁사수")
    rows = []
    for item, party in OUTSOURCING_ITEMS:
        n = agents if item == "대출모집" else int(g.integers(1, 6))
        rows.append({
            "item": item, "party_type": party, "n_vendor": float(n),
            "resale": bool(rng(f"재위탁:{item}").random() < 0.25),
            "from_ledger": item == "대출모집",
        })
    return pd.DataFrame(rows)


def it_outsourcing() -> pd.DataFrame:
    """정보처리 업무위탁 명세 — 목록은 고정 어휘, 수탁사 수만 파생이다."""
    g = rng("정보처리위탁")
    rows = []
    for item, location, pii in IT_OUTSOURCING_ITEMS:
        rows.append({"item": item, "location": location, "pii": pii,
                     "n_vendor": float(int(g.integers(1, 4)))})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- 부수·겸영 (B1108)

def ancillary_business(ctx) -> pd.DataFrame:
    """부수업무·겸영업무 영위 현황.

    **영위 여부는 이 하네스의 원장·산출에 그 업무의 흔적이 있는지로 판정한다.**
    흔적이 없으면 미영위로 적고 사유를 남긴다 — 하지 않는 영업을 파생으로 만들어
    내는 것보다, 하고 있는데 원장이 없어 못 적었다고 밝히는 편이 낫다. 실제
    제출 시에는 업무 마스터로 대체해야 한다.

    판정근거에는 **근거의 층위**를 함께 적는다. 원장을 실제로 읽은 판정과, 이
    저장소의 편제(어느 서식을 제출하기로 했는가)에서 온 판정과, 판정 대상이
    파생값인 판정은 무게가 다르다. 셋을 같은 문장으로 적으면 읽는 쪽이 전부
    원장 대조 결과로 읽는다.
    """
    # 신탁 계정과목이 재무상태표에 있는지로 판정한다 — B2203·B2104와 같은 근거다.
    has_trust = any("신탁" in str(i)
                    for i in ctx.tables["pru_balance_sheet"]["item"])
    has_public = float(public_deposits(ctx)["balance"].sum()) > 0.0
    has_deriv = len(ctx.tables["mkt_trade"]) > 0
    fund = float(fund_sales(ctx)["balance"].sum())
    # 은행이 **제공한** 지급보증·어음인수는 부외 익스포저의 신용환산 유형에 남는다
    # (직접적 신용대체 = 지급보증·어음인수, 거래관련 우발채무 = 이행보증).
    # `rdm_guarantee`는 은행이 **수취한** 신용보장(CRM) 원장이라 방향이 반대이므로
    # 이 판정의 근거가 될 수 없다.
    ex = ctx.tables["rdm_exposure"]
    sub = ex[ex["ccf_type"].isin(("direct_credit_substitute",
                                  "transaction_related"))]
    guarantee_undrawn = float(sub["undrawn"].sum())
    has_guarantee = guarantee_undrawn > 0.0
    rows = [
        # (구분, 업무명, 영위, 판정근거)
        ("부수업무", "채무의 보증 및 어음의 인수", has_guarantee,
         "[원장] rdm_exposure 부외 익스포저의 직접적 신용대체·거래관련 우발채무 "
         f"미사용액 {guarantee_undrawn:,.0f}원 > 0"),
        ("부수업무", "지방자치단체 등 공공금고 대행", has_public,
         "[파생] keyfin public_deposits 공공금고 예수금 > 0 (B2202) — 금고 비중 "
         "자체가 파생이므로 원장 대조가 아니라 B2202와 같은 전제를 따른 판정"),
        ("부수업무", "유가증권의 보호예수", False, "[원장 부재] 보호예수 원장 없음"),
        ("부수업무", "수납 및 지급 대행", False, "[원장 부재] 수납·지급대행 원장 없음"),
        ("부수업무", "전자상거래 대금 지급대행", False, "[원장 부재] 지급대행 원장 없음"),
        ("부수업무", "금융 관련 연수·도서출판", False, "[원장 부재] 해당 사업 원장 없음"),
        ("겸영업무", "집합투자증권의 판매(투자중개업)", fund > 0.0,
         "[편제] B8101~B8104 판매현황 제출대상 — 판매잔액 자체가 예수금 앵커 "
         "파생이므로 원장 대조가 아니라 제출 편제에 따른 판정"),
        ("겸영업무", "신탁업", has_trust,
         "[원장] 원천 데이터에 신탁 계정과목 없음 — B2203·B2104와 같은 판정"),
        ("겸영업무", "신용카드업", True,
         "[편제] FINES 신용카드 서식(B28xx) 제출대상 — 이 하네스에 카드 원장이 "
         "없어 forms_fss_card가 포트폴리오에서 파생한다. 원장 대조가 아니다"),
        ("겸영업무", "파생상품의 매매·중개", has_deriv,
         "[원장] mkt_trade 트레이딩 원장에 파생 거래(스왑·옵션·CDS) 존재"),
        ("겸영업무", "보험대리점(방카슈랑스)", False, "[원장 부재] 보험모집 실적 원장 없음"),
        ("겸영업무", "퇴직연금사업", False, "[원장 부재] 퇴직연금 적립금 원장 없음"),
    ]
    return pd.DataFrame(rows, columns=["kind", "item", "operating", "basis"])


# ---------------------------------------------------------------- 펀드판매 (B81xx)

FUND_TYPES: tuple[str, ...] = (
    "증권 — 주식형", "증권 — 혼합형", "증권 — 채권형", "단기금융(MMF)",
    "부동산", "특별자산", "재간접", "파생형", "기타",
)
FUND_INVESTORS: tuple[str, ...] = ("개인", "법인(일반)", "기관투자자")


def fund_sales(ctx) -> pd.DataFrame:
    """집합투자증권 판매 — 판매잔액 총액만 예수금(실측)에 앵커하고 나머지가 파생이다.

    판매 원장이 없다. 예수금 총액에 파생 비율을 곱하면 수신 규모가 커질수록 판매
    잔액도 커져 서식이 산출과 같이 움직인다. 계좌수는 따로 뽑지 않고 **잔액 ÷
    계좌당 평잔**으로 만든다 — 셋을 독립으로 뽑으면 계좌당 평잔이 서식 안에서
    자기모순이 된다.
    """
    base = retail_deposits(ctx) + corporate_deposits(ctx)
    share = float(rng("펀드판매비중").uniform(0.06, 0.14))
    n = len(FUND_TYPES)
    w = rng("펀드유형배분").dirichlet(np.full(n, 2.0))
    balance = base * share * w
    g = rng("펀드보수율")
    df = pd.DataFrame({
        "fund_type": list(FUND_TYPES),
        "balance": balance,
        # 판매보수(연율)·선취판매수수료율·월 신규판매 회전율·계좌당 평잔
        "fee_rate": g.uniform(0.0020, 0.0110, n),
        "front_rate": rng("선취수수료율").uniform(0.0000, 0.0100, n),
        "turnover": rng("펀드월회전율").uniform(0.010, 0.060, n),
        "per_account": rng("계좌당평잔").uniform(4.0e6, 3.0e7, n),
    })
    df["new_sales"] = df["balance"] * df["turnover"]
    df["fee_income"] = df["balance"] * df["fee_rate"] / 12.0   # 월 서식
    df["front_income"] = df["new_sales"] * df["front_rate"]
    df["n_account"] = np.round(df["balance"] / df["per_account"])
    df["deposit_base"] = base
    df["share"] = share
    return df


def fund_investors(ctx) -> pd.DataFrame:
    """수익자별 판매잔액 — 개인·법인 비중은 **예수금 실측 비중**을 그대로 쓴다.

    수익자 구분을 새로 뽑으면 같은 은행의 개인·법인 고객 구성이 수신 서식과
    펀드 서식에서 갈린다. 기관투자자만 원장이 없어 몫을 파생으로 떼어낸다.
    """
    total = float(fund_sales(ctx)["balance"].sum())
    accounts = float(fund_sales(ctx)["n_account"].sum())
    inst = float(rng("기관투자자비중").uniform(0.10, 0.25))
    retail, corp = retail_deposits(ctx), corporate_deposits(ctx)
    r_share = retail / (retail + corp)
    w = np.array([(1.0 - inst) * r_share, (1.0 - inst) * (1.0 - r_share), inst])
    # 계좌당 평잔은 개인이 작고 기관이 크다 — 계좌수 배분의 가중치다.
    aw = w / np.array([1.0, 6.0, 40.0])
    return pd.DataFrame({
        "investor": list(FUND_INVESTORS),
        "balance": total * w,
        "n_account": _apportion(accounts, aw),
        "deposit_share": [r_share, 1.0 - r_share, float("nan")],
    })


# ---------------------------------------------------------------- 휴면예금 (B91xx)

DORMANT_KINDS: tuple[str, ...] = ("보통예금", "저축예금", "정기예금", "정기적금",
                                  "기타 예금")
# (상한, 라벨, 구간 대표금액). 대표금액은 계좌수를 만드는 데만 쓴다 — 금액을
# 대표금액으로 나눠야 구간 평균잔액이 그 구간을 벗어나지 않는다.
AMOUNT_BANDS: tuple[tuple[float, str, float], ...] = (
    (1.0e4, "1만원 이하", 4.0e3),
    (5.0e4, "1만원 초과 5만원 이하", 2.6e4),
    (1.0e5, "5만원 초과 10만원 이하", 7.2e4),
    (5.0e5, "10만원 초과 50만원 이하", 2.4e5),
    (1.0e6, "50만원 초과 100만원 이하", 7.2e5),
    (1.0e7, "100만원 초과 1천만원 이하", 3.0e6),
    (math.inf, "1천만원 초과", 2.2e7),
)
ELAPSED_BANDS: tuple[str, ...] = ("1년 이상 2년 미만", "2년 이상 3년 미만",
                                  "3년 이상 5년 미만", "5년 이상")
AGE_BANDS: tuple[str, ...] = ("20세 미만", "20대", "30대", "40대", "50대", "60대",
                              "70세 이상")


def _amount_bands(key: str, total: float, alpha: np.ndarray,
                  bands: tuple[tuple[float, str, float], ...] = AMOUNT_BANDS
                  ) -> pd.DataFrame:
    """금액구간 배분 — **계좌수를 먼저 배분하고 금액은 계좌수 × 대표금액**이다.

    금액을 먼저 뽑고 대표금액으로 나눠 계좌수를 만들면 소액 구간이 무너진다.
    "1만원 이하" 구간은 대표금액이 작아 총액의 몇 %만 줘도 계좌수가 고객 수를
    넘어선다. 그래서 계좌 구성비를 먼저 뽑고, 총 계좌수는 **총액 ÷ 구성비 가중
    평균 대표금액**으로 역산한다 — 이러면 구간 평균잔액이 대표금액과 같아져
    어느 구간도 자기 금액구간을 벗어나지 않는다.

    구간 하한·상한·대표금액을 함께 돌려준다. 그래야 서식이 "구간 평균잔액이
    그 구간 안에 있다"를 **FormCheck로 대사**할 수 있다 — 주장만 적어 두고
    검증하지 않으면 배분이 무너져도 아무도 모른다.
    """
    w = rng(key).dirichlet(alpha)
    reps = np.array([b[2] for b in bands])
    counts = _apportion(total / float((w * reps).sum()), w)
    raw = counts * reps
    uppers = [b[0] for b in bands]
    return pd.DataFrame({
        "band": [b[1] for b in bands],
        "amount": total * raw / raw.sum(),
        "n_account": counts,
        "rep": reps,
        "lower": [0.0] + uppers[:-1],
        "upper": uppers,
    })


def dormant_deposits(ctx) -> dict:
    """휴면예금 — **합계는 개인 예수금(실측) × 파생 휴면율**이다.

    휴면예금 원장이 없다. 잔액·환급·신규발생을 따로 뽑으면 롤포워드가 닫히지
    않으므로 **기말 잔액을 앵커로 두고 기초를 역산**한다. 그러면 기초 + 신규 −
    환급 − 출연 = 기말 항등식이 언제나 성립한다.
    """
    base = retail_deposits(ctx)
    rate = float(rng("휴면예금비율").uniform(0.0008, 0.0026))
    closing = base * rate
    kinds = closing * rng("휴면종류배분").dirichlet(
        np.array([4.0, 3.0, 2.0, 1.5, 1.0]))
    g = rng("휴면롤포워드")
    new = closing * float(g.uniform(0.15, 0.32))       # 반기 중 신규 휴면 편입
    refund = closing * float(g.uniform(0.10, 0.26))    # 반기 중 환급(지급)
    # 서민금융진흥원 출연분 — 출연하면 은행 계정에서 빠진다.
    donation = closing * float(g.uniform(0.02, 0.09))
    return {
        "deposit_base": base, "rate": rate, "closing": closing,
        "opening": closing - new + refund + donation,
        "new": new, "refund": refund, "donation": donation,
        "kinds": pd.DataFrame({"kind": list(DORMANT_KINDS), "amount": kinds}),
        # 휴면예금은 소액 계좌가 압도적이다 — 구간 구성비를 소액에 몰아준다.
        "bands": _amount_bands("휴면금액구간", closing,
                               np.array([12.0, 8.0, 4.0, 2.0, 1.2, 0.8, 0.4])),
        "refund_count": float(round(refund / float(
            rng("환급건당").uniform(6.0e4, 2.2e5)))),
    }


def inactive_deposits(ctx) -> dict:
    """미거래 예금 — 휴면 도래 전 단계. 앵커는 같은 개인 예수금(실측)이다.

    연령 분포는 예금주 원장이 없어 파생이다. 연령별 잔액은 계좌수 배분에 연령별
    평잔 배수를 곱해 만든다 — 계좌수와 잔액을 독립으로 뽑으면 20대 계좌 평잔이
    60대보다 큰 서식이 나온다.
    """
    base = retail_deposits(ctx)
    rate = float(rng("미거래비율").uniform(0.015, 0.040))
    total = base * rate
    elapsed = total * rng("미거래경과배분").dirichlet(np.array([5.0, 3.0, 2.0, 1.0]))
    # 미거래 예금은 휴면예금보다 계좌 규모가 크다 — 구성비를 중·고액으로 옮긴다.
    bands = _amount_bands("미거래금액구간", total,
                          np.array([5.0, 5.0, 4.0, 4.0, 2.5, 2.0, 0.8]))
    n_account = float(bands["n_account"].sum())
    # 알파를 작게 두면 디리클레 변동이 커져 "20세 미만"이 40대보다 많아진다.
    aw = rng("미거래연령배분").dirichlet(
        np.array([1.0, 4.0, 6.0, 7.0, 6.0, 4.0, 2.5]))
    counts = _apportion(n_account, aw)
    # 연령이 높을수록 평잔이 크다 — 계좌수 배분에 이 배수를 곱해 잔액을 만든다.
    mult = np.array([0.3, 0.6, 0.9, 1.2, 1.5, 1.8, 2.0])
    amt_w = counts * mult
    return {
        "deposit_base": base, "rate": rate, "total": total,
        "n_account": n_account,
        "elapsed": pd.DataFrame({"band": list(ELAPSED_BANDS), "amount": elapsed}),
        "bands": bands,
        "ages": pd.DataFrame({"band": list(AGE_BANDS), "n_account": counts,
                              "amount": total * amt_w / amt_w.sum()}),
    }


CHECK_BANDS: tuple[tuple[float, str, float], ...] = (
    (1.0e5, "10만원 이하", 8.0e4),
    (5.0e5, "10만원 초과 50만원 이하", 2.6e5),
    (1.0e6, "50만원 초과 100만원 이하", 7.5e5),
    (5.0e6, "100만원 초과 500만원 이하", 2.4e6),
    (math.inf, "500만원 초과", 1.2e7),
)


def cashier_checks(ctx) -> dict:
    """휴면 자기앞수표 발행대금 — 법인 결제성 예수금(실측)에 앵커한다.

    자기앞수표는 결제성 자금이므로 결제성 예수금을 모수로 잡는다. 롤포워드는
    휴면예금과 같은 방식으로 기말을 앵커에 두고 기초를 역산한다.
    """
    amt = bs_amounts(ctx)
    settle = amt["예수금 — 법인 결제성"]
    issue_rate = float(rng("자기앞수표발행비율").uniform(0.010, 0.030))
    issued = settle * issue_rate
    dormant_rate = float(rng("자기앞수표휴면비율").uniform(0.004, 0.018))
    closing = issued * dormant_rate
    g = rng("수표롤포워드")
    new = closing * float(g.uniform(0.18, 0.40))
    refund = closing * float(g.uniform(0.12, 0.30))
    donation = closing * float(g.uniform(0.02, 0.08))
    return {
        "settle_deposit": settle, "issue_rate": issue_rate, "issued": issued,
        "rate": dormant_rate, "closing": closing,
        "opening": closing - new + refund + donation,
        "new": new, "refund": refund, "donation": donation,
        "bands": _amount_bands("수표금액구간", closing,
                               np.array([5.0, 3.0, 2.0, 1.2, 0.6]), CHECK_BANDS),
        "refund_count": float(round(refund / float(
            rng("수표환급건당").uniform(2.0e5, 8.0e5)))),
    }


# ---------------------------------------------------------------- 금리인하요구권 (B10101)

def rate_cut_requests(ctx) -> pd.DataFrame:
    """금리인하요구권 — **대상 여신은 실제 포트폴리오**이고 신청·수용만 파생이다.

    신청 원장이 없다. 익스포저마다 신청·수용 여부를 뽑으면 신청·수용 잔액이
    실측 잔액의 부분집합이 되어 "대상 여신 ≥ 신청 ≥ 수용" 관계가 서식 안에서
    자동으로 성립한다. 비율에 잔액을 곱해 만들면 그 관계를 따로 지켜야 한다.

    신용도가 좋아진 차주가 신청하고 수용된다는 관계를 담기 위해 PD가 낮을수록
    신청·수용 확률을 올린다. 국가·은행 익스포저는 금리인하 요구의 대상이 아니므로
    (개인·기업 여신에 한한다) 모집단에서 뺀다.
    """
    p = ctx.portfolio[["exposure_id", "asset_class", "sector", "pd", "dpd"]]
    aq = ctx.tables["rdm_asset_quality"][["exposure_id", "classification",
                                          "balance"]]
    df = (p[p["asset_class"].isin(("residential_mortgage", "retail_other",
                                   "corporate"))]
          .merge(aq, on="exposure_id")
          .sort_values("exposure_id").reset_index(drop=True))
    df["is_household"] = df["asset_class"] != "corporate"
    # PD가 낮을수록(신용도가 좋을수록) 신청·수용 확률이 높다.
    zp = -_z(np.log(df["pd"].clip(lower=1e-6)))
    n = len(df)
    apply_p = np.clip(0.045 * np.exp(0.35 * zp), 0.0, 0.4)
    df["applied"] = rng("금리인하신청").random(n) < apply_p
    accept_p = np.clip(0.55 + 0.12 * zp, 0.05, 0.95)
    df["accepted"] = df["applied"] & (rng("금리인하수용").random(n) < accept_p)
    # 인하폭과 연간 이자경감액 — 경감액은 잔액 × 인하폭(연율)이다.
    # 단위는 **연율 비율**이지 bp가 아니다(0.0075 = 0.75%p = 75bp). 열 이름을
    # bp로 두면 서식이 75를 적어야 할 자리에 0.0075를 적고도 아무도 못 찾는다.
    cut = rng("인하폭").uniform(0.0005, 0.0075, n)
    df["cut_rate"] = np.where(df["accepted"], cut, 0.0)
    df["relief"] = df["balance"] * df["cut_rate"]
    return df
