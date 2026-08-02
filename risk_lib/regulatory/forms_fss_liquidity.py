"""금감원 FINES 업무보고서 — 유동성 12건.

근거는 은행업감독규정 제26조(유동성·LCR)와 제63조(외화유동성), Basel LCR20~40 ·
NSF20~30 · SRP50(유동성 모니터링 지표)이다. 서식명·작성주기는 여기 적지 않는다 —
FINES 마스터가 정본이고 forms.py가 붙인다.

**만기 구간은 새로 만들지 않는다.** 모든 만기 사다리는 `alm_repricing_gap`
(= `alm.balance_sheet.REPRICING_BUCKETS`)을 그대로 쓴다. 서식이 자기 사다리를
들고 있으면 IRRBB 화면과 유동성 화면이 서로 다른 만기 분포를 보고하게 된다.
재설정 사다리는 계약상 만기의 **대용**이며(비만기성 예금은 행태만기로 슬로팅되어
있다), 그 사실은 해당 서식의 text 라인에 남긴다. 사다리는 **금리민감** 자산·부채만
담으므로 대차대조표 총액과 차이가 난다 — B2601·B2609는 그 차를 "만기구간 미배분"
라인으로 드러내고 FormCheck로 대사한다. 드러내지 않으면 총자산의 9%·총부채의 7%가
잔액기준 서식에서 조용히 사라진다.

**외화 비중은 자산·부채 대칭이다.** 합성 대차대조표에 통화 구분이 없어
`risk_lib.prudential.liquidity.FX_SHARE`(13%)를 자산·부채에 **같은 값**으로
적용한다. 비대칭 비중을 쓰면 존재하지 않는 통화 불일치가 비율에 섞여 들어가
가정이 만든 위반을 보고하게 된다 — 과거 독립검증에서 지적된 사안이다. 그 결과
외화 LCR·중장기외화조달비율은 총액 기준과 같은 값이 되며, 이 서식들이 드러내는
것은 통화 불일치가 아니라 **만기 불일치**뿐이다. FormCheck로 그 항등식을 건다.

**원장이 없어 파생한 항목** — 세 건뿐이다. 나머지는 산출값 그대로다.

  B2602-2 · B2602-3  일별(외화) LCR 경로
    일별 유동성 원장이 없다. 보고월 영업일별 LCR을 **시드 고정 RNG**로 만들되
    변동 폭은 지어내지 않고 `(30일 순현금유출 ÷ 30) ÷ HQLA` — 즉 하루치 순유출이
    HQLA에서 차지하는 비중 — 을 일별 상대 변동성으로 쓴다. 마지막 영업일은
    `result.alm["lcr"].lcr`에 정확히 고정하며 FormCheck로 대사한다. 시드는
    `result.meta["seed"]`라 같은 파이프라인 실행이면 같은 경로가 나온다.

  B2610  거래상대방별 도매조달 배분
    예금자·차입처 원장이 없다. 금융기관 도매조달 **총액은 산출값**이고, 그것을
    거래상대방에 나누는 비중만 파생한다. 난수가 아니라 `result.ccr.by_counterparty`
    의 실제 거래상대방별 EAD 비중을 거래관계 강도의 대용으로 쓴다 — 같은 산출이면
    같은 배분이 나온다. 개인·법인 예금은 예금자 원장이 없어 중요 거래상대방
    판정에서 제외했고(과소계상 가능), 그 사실을 라인에 남긴다.

  B2602-1 · B2611  외화 안의 통화 구성비
    통화 원장이 없다. 차주 소재국(`rdm_obligor.country`) 통화로 익스포저가
    표시된다고 보고 소재국별 EAD 비중을 구성비로 쓴다 — 난수가 아니라 원장
    집계이며, 자산·부채에 **같은 구성비**를 적용해 통화별 불일치를 만들지 않는다.

미산출로 남긴 것("없다"와 "안 봤다"는 다르다):
  B2612  담보부 조달(RP·커버드본드·중앙은행 차입) 원장이 없다. 합성 조달구성이
         전액 무담보라 처분제한 자산은 파생거래 변동증거금 소요액뿐이며, 그
         금액은 `result.ccr.by_counterparty`의 순시장가치에서 산출한다.
         `rdm_collateral`은 은행이 **수취한** 담보이지 제공한 담보가 아니다.
  B2602-4 연결 자회사 원장이 없어 연결 = 단독이다.
"""

from __future__ import annotations

from typing import Callable

import numpy as np
import pandas as pd

from risk_lib.limits.concentration import hhi
from risk_lib.prudential.liquidity import FX_SHARE
from risk_lib.references import LCR_HAIRCUT_L2A, LCR_HAIRCUT_L2B, LCR_INFLOW_CAP
from risk_lib.regulatory.forms_base import (
    FormCheck, FormLine, _ratio_check, _sum_check, _val, month_business_days,
)

_M_BS = "risk_lib.alm.balance_sheet"
_M_LCR = "risk_lib.alm.lcr"
_M_IRRBB = "risk_lib.alm.irrbb"
_M_PRU = "risk_lib.prudential.liquidity"
_M_CCR = "risk_lib.ccr"
_M_RDM = "risk_lib.datamodel.materialize_detail"
_M_SELF = "risk_lib.regulatory.forms_fss_liquidity"

_C26 = "은행업감독규정 제26조 제1항"
_C63 = "은행업감독규정 제63조 — 외화유동성"
_C99 = "은행업감독규정 제99조 업무보고서"
_SRP50 = "Basel SRP50 유동성 모니터링 지표"
_LADDER = "만기 구간은 alm.balance_sheet.REPRICING_BUCKETS (SRP31.94)"

# 재설정 사다리를 잔존만기로 읽을 때의 한계 — 서식마다 되풀이하지 않도록 한 곳에.
_LADDER_NOTE = ("만기 구간은 IRRBB 재설정 사다리(alm_repricing_gap)를 쓴다. "
                "비만기성 예금이 행태만기로 슬로팅되어 있어 계약상 만기와 완전히 "
                "같지 않다 — 서식별 사다리를 새로 만들면 IRRBB 화면과 유동성 화면이 "
                "서로 다른 만기 분포를 보고하게 되므로 카탈로그 사다리를 그대로 쓴다.")

_FX_NOTE = (f"외화 비중 {FX_SHARE:.0%}는 자산·부채에 **동일하게** 적용한다"
            f"(risk_lib.prudential.liquidity.FX_SHARE). 통화 구분 원장이 없는데 "
            f"비대칭 비중을 쓰면 존재하지 않는 통화 불일치가 만들어진다. 그래서 "
            f"이 서식이 드러내는 것은 통화 불일치가 아니라 만기 불일치뿐이다.")

_CCY = {"CN": "CNY", "JP": "JPY", "US": "USD", "VN": "VND"}
_SIG_CCY = 0.05        # SRP50 중요통화 — 총부채의 5% 이상
_SIG_CP = 0.01         # SRP50 중요 거래상대방 — 총부채의 1% 이상
_SIG_INSTR = 0.01      # SRP50 중요 금융상품 — 총부채의 1% 이상

# 조달수단 한글명 — 대차대조표(pru_balance_sheet)와 같은 어휘를 쓴다.
_FUNDING_KO = {
    "retail_stable": "예수금 — 개인 안정",
    "retail_less_stable": "예수금 — 개인 준안정",
    "corporate_operational": "예수금 — 법인 결제성",
    "corporate_non_operational": "예수금 — 법인 비결제성",
    "wholesale_fi_lt6m": "차입금 — 금융기관 6개월 이내",
    "wholesale_fi_6to12m": "차입금 — 금융기관 6~12개월",
    "funding_gt1y": "사채 및 장기차입금",
}
_WHOLESALE_FI = ("wholesale_fi_lt6m", "wholesale_fi_6to12m")

_LCR_KO = {
    "retail_stable": "개인 안정예금 이탈",
    "retail_less_stable": "개인 준안정예금 이탈",
    "corporate_operational": "법인 결제성예금 이탈",
    "corporate_non_operational": "법인 비결제성예금 이탈",
    "wholesale_fi_unsecured": "금융기관 무담보차입 이탈",
    "committed_facilities": "약정 미사용액 인출",
    "retail_inflows": "개인 여신 회수",
    "wholesale_inflows": "법인 여신 회수",
    "fi_inflows": "금융기관 여신 회수",
}


# ---------------------------------------------------------------- 공용 조회

def _rep(ctx) -> pd.DataFrame:
    """재설정 사다리 — 만기 구간의 유일한 정본."""
    return ctx.tables["alm_repricing_gap"].sort_values("seq").reset_index(drop=True)


def _ccy_weights(ctx) -> list[tuple[str, float]]:
    """외화 익스포저의 통화 구성비.

    통화 원장은 없지만 차주 소재국(`rdm_obligor.country`)은 원장이다. 소재국
    통화로 익스포저가 표시된다고 보고 구성비를 만든다 — 난수가 아니라 원장
    집계이며, 같은 포트폴리오면 같은 비중이 나온다.
    """
    ex = ctx.tables["rdm_exposure"][["obligor_id", "ead"]]
    ob = ctx.tables["rdm_obligor"][["obligor_id", "country"]]
    m = ex.merge(ob, on="obligor_id", how="left")
    g = m[m["country"].isin(list(_CCY))].groupby("country")["ead"].sum()
    total = float(g.sum())
    return [(_CCY[c], float(v) / total) for c, v in sorted(g.items())]


def _lcr_path(ctx) -> tuple[pd.DatetimeIndex, np.ndarray, float]:
    """보고월 영업일별 LCR 경로를 파생한다 — 월말은 산출값에 고정한다.

    변동 폭까지 지어내지 않으려고 상대 변동성은 하루치 순현금유출이 HQLA에서
    차지하는 비중(= 순현금유출 ÷ 30 ÷ HQLA)에서 뽑는다. 경로 모양만 시드 고정
    RNG가 만들고, 마지막 영업일은 `result.alm["lcr"].lcr`로 못박는다.
    """
    lcr = ctx.result.alm["lcr"]
    asof = pd.Timestamp(str(ctx.result.meta["asof"]))
    days = month_business_days(asof)
    sigma = (float(lcr.net_outflow) / 30.0 / float(lcr.hqla_total)
             if lcr.hqla_total else 0.0)
    z = np.random.default_rng(int(ctx.result.meta["seed"]) + 2602) \
        .standard_normal(len(days))
    z[-1] = 0.0                     # 마지막 영업일 = 월말 산출값
    return days, float(lcr.lcr) * np.exp(sigma * z), sigma


def _path_stat_lines(base: int, days, path, label: str) -> list[FormLine]:
    """일별 서식의 요약 4행 — 영업일수·일평균·최고·최저."""
    return [
        FormLine(str(base), "보고월 영업일수", 0, "count", float(len(days)),
                 formula=f"{days[0]:%Y-%m-%d}~{days[-1]:%Y-%m-%d} · 공휴일 달력 미적용",
                 citation=_C99, source_module=_M_SELF, is_subtotal=True),
        FormLine(str(base + 10), f"월중 일평균 {label}", 0, "ratio",
                 float(path.mean()), formula="Σ 일별 비율 ÷ 영업일수",
                 citation=_C99, source_module=_M_SELF),
        FormLine(str(base + 20), f"월중 최고 {label}", 0, "ratio",
                 float(path.max()), formula="일별 경로의 최대값", citation=_C99,
                 source_module=_M_SELF),
        FormLine(str(base + 30), f"월중 최저 {label}", 0, "ratio",
                 float(path.min()), formula="일별 경로의 최소값", citation=_C99,
                 source_module=_M_SELF),
    ]


def _path_checks(L: list[FormLine], base: int, days, path, label: str,
                 day_codes: list[str]) -> list[FormCheck]:
    """요약 4행을 **방출된 일별 라인**과 대사한다.

    내부 배열(`path`)끼리 비교하면 일별 라인 생성이 깨져도 전부 PASS한다 —
    대사는 서식에 실제로 실리는 값을 봐야 한다.
    """
    vals = [_val(L, c) for c in day_codes]
    return [
        FormCheck(f"일별 {label} 라인 수 = 보고월 영업일수", float(len(days)),
                  _val(L, str(base)), 1e-12),
        FormCheck(f"일평균 × 영업일수 = 일별 {label} 라인 합", float(sum(vals)),
                  _val(L, str(base + 10)) * len(days), 1e-9),
        FormCheck(f"최고 {label} = 일별 라인 최대값", max(vals),
                  _val(L, str(base + 20)), 1e-12),
        FormCheck(f"최저 {label} = 일별 라인 최소값", min(vals),
                  _val(L, str(base + 30)), 1e-12),
    ]


# ---------------------------------------------------------------- B2601

def _b2601(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """자산·부채 만기구조현황(잔액기준) — 구간별 잔액과 만기갭."""
    rep = _rep(ctx)
    bs = ctx.result.alm["balance_sheet"]
    a_tot, l_tot = float(rep["asset"].sum()), float(rep["liability"].sum())
    # 재설정 사다리는 **금리민감** 자산·부채만 담는다. 잔액기준 서식이므로
    # 대차대조표 총액과의 차(미배분 잔액)를 라인으로 드러내고 대사한다 —
    # 그러지 않으면 총자산의 9%, 총부채의 7%가 서식에서 조용히 사라진다.
    a_all = float(bs.total_assets)
    l_all = float(bs.funding_total())
    L = [
        FormLine("0100", "총자산 (대차대조표)", 0, "KRW", a_all,
                 formula="만기구간 배분액 + 미배분액", citation=_C99,
                 source_module=_M_BS, is_subtotal=True),
        FormLine("0200", "총부채 (조달 합계)", 0, "KRW", l_all,
                 formula="만기구간 배분액 + 미배분액", citation=_C99,
                 source_module=_M_BS, is_subtotal=True),
        FormLine("1000", "만기구간 배분 자산 합계", 0, "KRW", a_tot,
                 formula="금리민감자산 = 대출채권 + HQLA", citation=_LADDER,
                 source_module=_M_BS, is_subtotal=True),
        FormLine("2000", "만기구간 배분 부채 합계", 0, "KRW", l_tot,
                 formula="금리민감부채 (비민감분 제외)", citation=_LADDER,
                 source_module=_M_BS, is_subtotal=True),
        FormLine("3000", "순 만기갭 합계", 0, "KRW", a_tot - l_tot,
                 formula="자산 합계 − 부채 합계", citation=_C26,
                 source_module=_M_IRRBB, is_subtotal=True),
    ]
    a_codes, l_codes, g_codes = [], [], []
    for _, row in rep.iterrows():
        i = int(row["seq"])
        b = str(row["bucket"])
        a_codes.append(f"{1000 + i * 10}")
        l_codes.append(f"{2000 + i * 10}")
        g_codes.append(f"{3000 + i * 10}")
        L += [
            FormLine(a_codes[-1], f"자산 · {b}", 1, "KRW", float(row["asset"]),
                     citation=_LADDER, source_module=_M_BS),
            FormLine(l_codes[-1], f"부채 · {b}", 1, "KRW",
                     float(row["liability"]), citation=_LADDER,
                     source_module=_M_BS),
            FormLine(g_codes[-1], f"만기갭 · {b}", 1, "KRW", float(row["gap"]),
                     formula="자산 − 부채", citation=_C26,
                     source_module=_M_IRRBB),
            FormLine(f"{4000 + i * 10}", f"누적 만기갭 · {b}", 2, "KRW",
                     float(row["cumulative_gap"]),
                     formula="당 구간까지의 만기갭 누계", citation=_C26,
                     source_module=_M_IRRBB),
        ]
    L += [
        FormLine("1900", "만기구간 미배분 자산 (비금리민감)", 0, "KRW",
                 a_all - a_tot,
                 formula="총자산 − 만기구간 배분 자산 = 대차대조표 기타자산",
                 citation=_C99, source_module=_M_BS),
        FormLine("2900", "만기구간 미배분 부채 (비금리민감)", 0, "KRW",
                 l_all - l_tot,
                 formula="총부채 − 만기구간 배분 부채", citation=_C99,
                 source_module=_M_BS),
        FormLine("5000", "1개월 이내 만기갭 비율 (배분자산 기준)", 0, "ratio",
                 float(rep["gap"].iloc[0]) / a_tot if a_tot else 0.0,
                 formula="1개월 만기갭 ÷ 만기구간 배분 자산 합계", citation=_C26,
                 source_module=_M_IRRBB),
        FormLine("5100", "1개월 이내 만기갭 비율 (총자산 기준)", 0, "ratio",
                 float(rep["gap"].iloc[0]) / a_all if a_all else 0.0,
                 formula="1개월 만기갭 ÷ 총자산 — B2609 누적 불일치 비율과 같은 분모",
                 citation=_C26, source_module=_M_IRRBB),
        FormLine("9000", "만기 사다리의 성격", 0, "text", None,
                 text_value=(_LADDER_NOTE + " 사다리는 금리민감 자산·부채만 담으므로 "
                             "총자산·총부채와의 차를 1900·2900에 미배분 잔액으로 "
                             "드러내고 대사한다. 갭비율은 분모가 둘이라 값이 달라진다 "
                             "— 5000은 배분자산 기준, 5100은 총자산 기준이며 B2609의 "
                             "누적 불일치 비율은 5100과 같은 분모를 쓴다."),
                 citation=_LADDER),
    ]
    last = f"{4000 + int(rep['seq'].iloc[-1]) * 10}"
    checks = [
        _sum_check("자산 합계 = 구간별 합", L, "1000", tuple(a_codes)),
        _sum_check("부채 합계 = 구간별 합", L, "2000", tuple(l_codes)),
        _sum_check("순 만기갭 합계 = 구간별 갭 합", L, "3000", tuple(g_codes)),
        _sum_check("총자산 = 배분 자산 + 미배분 자산", L, "0100",
                   ("1000", "1900"), max(1.0, a_all * 1e-9)),
        _sum_check("총부채 = 배분 부채 + 미배분 부채", L, "0200",
                   ("2000", "2900"), max(1.0, l_all * 1e-9)),
        # 위 두 건은 미배분액을 잔차로 정의한 항등식이라 그것만으로는 사다리가
        # 옳다는 근거가 못 된다. 아래 두 건이 사다리 총액을 대차대조표의 **독립
        # 구성요소**(대출채권·HQLA·기타자산)에 묶는 실질 대사다.
        FormCheck("배분 자산 = 대출채권 + HQLA (금리민감자산 정의)",
                  float(bs.loans) + float(sum(bs.hqla.values())),
                  _val(L, "1000"), max(1.0, a_all * 1e-9)),
        FormCheck("미배분 자산 = 대차대조표 기타자산",
                  float(bs.other_assets), _val(L, "1900"),
                  max(1.0, a_all * 1e-9)),
        FormCheck("배분 부채 ≤ 총부채", 0.0,
                  max(0.0, _val(L, "2000") - _val(L, "0200")), 1.0),
        FormCheck("순 만기갭 = 자산 − 부채", a_tot - l_tot,
                  _val(L, "3000"), 1.0),
        FormCheck("최종 누적갭 = 순 만기갭 합계", _val(L, "3000"),
                  _val(L, last), 1.0),
        _ratio_check("1개월 갭비율(배분자산) = 1개월 갭 ÷ 배분 자산 합계", L,
                     "5000", "3010", "1000"),
        _ratio_check("1개월 갭비율(총자산) = 1개월 갭 ÷ 총자산", L, "5100",
                     "3010", "0100"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2602-1

def _b2602_1(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """외화 및 중요통화별 LCR — 통화 배분은 대칭이라 비율이 총액 기준과 같다."""
    lcr = ctx.result.alm["lcr"]
    liab_total = float(ctx.result.alm["balance_sheet"].funding_total())
    hqla_fx = float(lcr.hqla_total) * FX_SHARE
    out_fx = float(lcr.net_outflow) * FX_SHARE
    L = [
        FormLine("1000", "고유동성자산(HQLA) 인정액", 0, "KRW",
                 float(lcr.hqla_total), formula="Level 1 + 2A + 2B (상한·haircut 후)",
                 citation="Basel LCR30.34~30.47", source_module=_M_LCR,
                 is_subtotal=True),
        FormLine("1100", "순현금유출액 (30일)", 0, "KRW",
                 float(lcr.net_outflow), formula="총유출 − 인식유입(총유출 75% 상한)",
                 citation="Basel LCR40", source_module=_M_LCR, is_subtotal=True),
        FormLine("1200", "유동성커버리지비율 (총액 기준)", 0, "ratio",
                 float(lcr.lcr), formula="HQLA ÷ 순현금유출액", citation=_C26,
                 source_module=_M_LCR, is_subtotal=True),
        FormLine("2000", "외화 HQLA 인정액", 0, "KRW", hqla_fx,
                 formula=f"HQLA × 외화비중 {FX_SHARE:.0%}", citation=_C63,
                 source_module=_M_PRU, is_subtotal=True),
        FormLine("2100", "외화 순현금유출액", 0, "KRW", out_fx,
                 formula=f"순현금유출 × 외화비중 {FX_SHARE:.0%}", citation=_C63,
                 source_module=_M_PRU, is_subtotal=True),
        FormLine("2200", "외화 유동성커버리지비율", 0, "ratio",
                 hqla_fx / out_fx if out_fx else 0.0,
                 formula="외화 HQLA ÷ 외화 순현금유출액", citation=_C63,
                 source_module=_M_PRU, is_subtotal=True),
        FormLine("2300", "총부채 대비 외화부채 비중", 0, "ratio", FX_SHARE,
                 formula="자산·부채 동일 적용", citation=_C63,
                 source_module=_M_PRU),
    ]
    h_codes, o_codes, r_codes, s_codes, n_sig = [], [], [], [], 0
    for i, (ccy, w) in enumerate(_ccy_weights(ctx), start=1):
        base = 3000 + i * 100
        share = FX_SHARE * w
        sig = share >= _SIG_CCY
        n_sig += int(sig)
        h_codes.append(str(base))
        o_codes.append(str(base + 10))
        r_codes.append((ccy, str(base + 20), str(base), str(base + 10)))
        s_codes.append(str(base + 30))
        L += [
            FormLine(str(base), f"{ccy} HQLA 인정액", 1, "KRW", hqla_fx * w,
                     formula=f"외화 HQLA × 통화구성비 {w:.2%}",
                     citation=f"{_SRP50} — 중요통화 LCR", source_module=_M_SELF),
            FormLine(str(base + 10), f"{ccy} 순현금유출액", 1, "KRW",
                     out_fx * w, formula=f"외화 순유출 × 통화구성비 {w:.2%}",
                     citation=f"{_SRP50} — 중요통화 LCR", source_module=_M_SELF),
            FormLine(str(base + 20), f"{ccy} 유동성커버리지비율", 1, "ratio",
                     float(lcr.lcr), formula="통화별 HQLA ÷ 순현금유출액",
                     citation=_C63, source_module=_M_SELF),
            FormLine(str(base + 30), f"{ccy} 총부채 대비 비중", 2, "ratio",
                     share, formula=f"외화비중 {FX_SHARE:.0%} × 통화구성비 {w:.2%}",
                     citation=f"{_SRP50} — 중요통화 정의", source_module=_M_SELF),
            FormLine(str(base + 40), f"{ccy} 중요통화 여부", 2, "count",
                     1.0 if sig else 0.0,
                     formula=f"1 = 총부채의 {_SIG_CCY:.0%} 이상",
                     citation=f"{_SRP50} — 중요통화 정의", source_module=_M_SELF),
        ]
    L += [
        # B2611의 "중요통화 수"는 원화를 포함한다. 같은 이름으로 다른 값을 실으면
        # 같은 제출본 안에서 숫자가 어긋난 것처럼 보인다 — 범위를 이름에 박는다.
        FormLine("8000", "중요통화 수 (외화 중, 원화 제외)", 0, "count",
                 float(n_sig),
                 formula=(f"총부채 {liab_total:,.0f}원 대비 {_SIG_CCY:.0%} 이상 외화 "
                          f"— 원화 포함 기준은 B2611 8000 라인"),
                 citation=f"{_SRP50} — 중요통화 정의", source_module=_M_SELF,
                 is_subtotal=True),
        FormLine("9000", "외화 배분 가정", 0, "text", None,
                 text_value=(_FX_NOTE + " 통화 구성비는 차주 소재국 원장에서 뽑았고 "
                             "자산·부채에 같은 구성비를 적용했다 — 그래서 통화별 "
                             "LCR이 총액 기준 LCR과 같다. 8000의 중요통화 수는 "
                             "외화만 센 값이며, 원화를 포함한 수는 B2611 8000에 있다."),
                 citation=_C63),
    ]
    checks = [
        _ratio_check("LCR = HQLA ÷ 순현금유출", L, "1200", "1000", "1100"),
        _ratio_check("외화 LCR = 외화 HQLA ÷ 외화 순현금유출", L, "2200",
                     "2000", "2100"),
        FormCheck("외화 LCR = 총액 기준 LCR (외화비중 대칭 가정의 귀결)",
                  _val(L, "1200"), _val(L, "2200"), 1e-12),
        _sum_check("통화별 HQLA 합 = 외화 HQLA", L, "2000", tuple(h_codes)),
        _sum_check("통화별 순현금유출 합 = 외화 순현금유출", L, "2100",
                   tuple(o_codes)),
        # 통화별 LCR은 총액 LCR을 그대로 실은 라인이라 분자·분모 라인과 독립이다.
        # 대사를 걸지 않으면 통화별 HQLA·순유출이 틀려도 비율은 그대로 맞아 보인다.
        *[_ratio_check(f"{c} LCR = {c} HQLA ÷ {c} 순현금유출", L, rc, hc, oc)
          for c, rc, hc, oc in r_codes],
        FormCheck("통화별 총부채 비중 합 = 외화비중", FX_SHARE,
                  sum(_val(L, c) for c in s_codes), 1e-12),
    ]
    return L, checks


# ---------------------------------------------------------------- B2602-2

def _b2602_2(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """일별 유동성커버리지비율 — 일별 값은 파생, 월말은 산출값에 고정."""
    days, path, sigma = _lcr_path(ctx)
    lcr = ctx.result.alm["lcr"]
    L = [
        FormLine("1000", "월말 유동성커버리지비율", 0, "ratio", float(lcr.lcr),
                 formula="HQLA ÷ 순현금유출액 — 일별 경로의 앵커",
                 citation=_C26, source_module=_M_LCR, is_subtotal=True),
        FormLine("1100", "월말 HQLA 인정액", 0, "KRW", float(lcr.hqla_total),
                 citation="Basel LCR30", source_module=_M_LCR),
        FormLine("1200", "월말 순현금유출액", 0, "KRW", float(lcr.net_outflow),
                 citation="Basel LCR40", source_module=_M_LCR),
        FormLine("1300", "규제 최저비율", 0, "ratio", 1.0,
                 formula="이상", citation=_C26),
    ]
    L += _path_stat_lines(2000, days, path, "LCR")
    day_codes = []
    for i, (d, v) in enumerate(zip(days, path), start=1):
        code = f"{3000 + i}"
        day_codes.append(code)
        L.append(FormLine(code, f"{d:%Y-%m-%d} LCR", 1, "ratio", float(v),
                          formula=f"월말 LCR × exp({sigma:.6f} × z) — 파생값",
                          citation="파생 근거는 9000 라인", source_module=_M_SELF))
    below = sum(1 for v in path if v < 1.0)
    L += [
        FormLine("2100", "규제 최저비율 미달 영업일수", 0, "count", float(below),
                 formula="일별 LCR < 100% 인 날의 수", citation=_C26,
                 source_module=_M_SELF),
        FormLine("9000", "일별 값의 성격", 0, "text", None,
                 text_value=(f"일별 유동성 원장이 없다. 일별 LCR은 원장이 아니라 "
                             f"파생값이며, 상대 변동성 {sigma:.4%}는 하루치 "
                             f"순현금유출(30일 순유출 ÷ 30)이 HQLA에서 차지하는 "
                             f"비중으로 실제 산출에서 뽑았다. 경로는 seed="
                             f"{int(ctx.result.meta['seed']) + 2602} 고정 RNG로 "
                             f"만들었고 마지막 영업일은 월말 산출값에 고정했다 — "
                             f"같은 seed면 같은 경로가 나온다."),
                 citation=_C99),
    ]
    checks = [
        FormCheck("마지막 영업일 LCR = 월말 산출 LCR", float(lcr.lcr),
                  _val(L, day_codes[-1]), 1e-12),
        _ratio_check("월말 LCR = HQLA ÷ 순현금유출", L, "1000", "1100", "1200"),
    ] + _path_checks(L, 2000, days, path, "LCR", day_codes)
    return L, checks


# ---------------------------------------------------------------- B2602-3

def _b2602_3(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """일별 외화 LCR — 외화비중이 대칭이라 비율 경로는 총액 기준과 일치한다."""
    days, path, sigma = _lcr_path(ctx)
    lcr = ctx.result.alm["lcr"]
    hqla_fx = float(lcr.hqla_total) * FX_SHARE
    out_fx = float(lcr.net_outflow) * FX_SHARE
    L = [
        FormLine("1000", "월말 외화 유동성커버리지비율", 0, "ratio",
                 hqla_fx / out_fx if out_fx else 0.0,
                 formula="외화 HQLA ÷ 외화 순현금유출액", citation=_C63,
                 source_module=_M_PRU, is_subtotal=True),
        FormLine("1100", "월말 외화 HQLA 인정액", 0, "KRW", hqla_fx,
                 formula=f"HQLA × 외화비중 {FX_SHARE:.0%}", citation=_C63,
                 source_module=_M_PRU),
        FormLine("1200", "월말 외화 순현금유출액", 0, "KRW", out_fx,
                 formula=f"순현금유출 × 외화비중 {FX_SHARE:.0%}", citation=_C63,
                 source_module=_M_PRU),
    ]
    L += _path_stat_lines(2000, days, path, "외화 LCR")
    day_codes, hqla_codes = [], []
    for i, (d, v) in enumerate(zip(days, path), start=1):
        L.append(FormLine(f"{3000 + i}", f"{d:%Y-%m-%d} 외화 LCR", 1, "ratio",
                          float(v),
                          formula=f"월말 외화 LCR × exp({sigma:.6f} × z) — 파생값",
                          citation="파생 근거는 9000 라인", source_module=_M_SELF))
        # 분자만 움직인다고 본다 — 30일 계약 유출은 하루 단위로 바뀌지 않는다.
        L.append(FormLine(f"{4000 + i}", f"{d:%Y-%m-%d} 외화 HQLA", 2, "KRW",
                          hqla_fx * float(v) / float(lcr.lcr),
                          formula="일별 외화 LCR × 외화 순현금유출액",
                          citation="파생 근거는 9000 라인", source_module=_M_SELF))
        day_codes.append(f"{3000 + i}")
        hqla_codes.append(f"{4000 + i}")
    below = sum(1 for v in path if v < 1.0)
    L += [
        FormLine("2100", "규제 최저비율 미달 영업일수", 0, "count", float(below),
                 formula="일별 외화 LCR < 100% 인 날의 수", citation=_C63,
                 source_module=_M_SELF),
        FormLine("9000", "일별 값의 성격", 0, "text", None,
                 text_value=(f"일별 외화 유동성 원장이 없다. {_FX_NOTE} 일별 경로는 "
                             f"상대 변동성 {sigma:.4%}(하루치 순현금유출 ÷ HQLA)와 "
                             f"seed={int(ctx.result.meta['seed']) + 2602} 고정 RNG로 "
                             f"만든 파생값이고, 마지막 영업일은 월말 산출값에 "
                             f"고정했다. 외화비중이 대칭이라 외화 LCR 경로는 총액 "
                             f"기준 경로(B2602-2)와 일치한다 — 통화별 원장이 들어오면 "
                             f"갈라진다."),
                 citation=_C63),
    ]
    checks = [
        FormCheck("마지막 영업일 외화 LCR = 월말 산출 LCR", float(lcr.lcr),
                  _val(L, day_codes[-1]), 1e-12),
        FormCheck("마지막 영업일 외화 HQLA = 월말 외화 HQLA", hqla_fx,
                  _val(L, hqla_codes[-1]), 1.0),
        _ratio_check("월말 외화 LCR = 외화 HQLA ÷ 외화 순현금유출", L, "1000",
                     "1100", "1200"),
        FormCheck("일별 외화 HQLA 합 = 일별 외화 LCR 합 × 외화 순현금유출",
                  sum(_val(L, c) for c in hqla_codes),
                  sum(_val(L, c) for c in day_codes) * out_fx,
                  max(1.0, hqla_fx * 1e-9)),
    ] + _path_checks(L, 2000, days, path, "외화 LCR", day_codes)
    return L, checks


# ---------------------------------------------------------------- B2602-4

def _b2602_4(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """외화 LCR 관련 자산·부채 현황 — 항목별 외화분과 난외 약정."""
    lcr = ctx.result.alm["lcr"]
    item = ctx.tables["alm_lcr_item"]
    undrawn = float(ctx.tables["rdm_exposure"]["undrawn"].sum())
    hqla_fx = float(lcr.hqla_total) * FX_SHARE
    gross_fx = float(lcr.gross_outflow) * FX_SHARE
    inflow_fx = float(lcr.inflow_capped) * FX_SHARE
    L = [
        FormLine("1000", "외화 HQLA 인정액", 0, "KRW", hqla_fx,
                 formula=f"상한 적용 후 HQLA × 외화비중 {FX_SHARE:.0%}",
                 citation="Basel LCR30.34~30.47", source_module=_M_LCR,
                 is_subtotal=True),
    ]
    h_codes = []
    for i, (_, r) in enumerate(lcr.hqla_detail.iterrows(), start=1):
        code = f"{1000 + i * 10}"
        h_codes.append(code)
        L.append(FormLine(code, f"외화 {r['component']} 인정액", 1, "KRW",
                          float(r["included"]) * FX_SHARE,
                          formula=(f"시가 {float(r['market_value']) * FX_SHARE:,.0f} × "
                                   f"(1 − haircut {float(r['haircut']):.0%}) · 상한 적용 후"),
                          citation="Basel LCR30.34~30.47", source_module=_M_LCR))
    L.append(FormLine("2000", "외화 총 현금유출액", 0, "KRW", gross_fx,
                      formula=f"Σ 잔액 × 이탈률 × 외화비중 {FX_SHARE:.0%}",
                      citation="Basel LCR40", source_module=_M_LCR,
                      is_subtotal=True))
    o_codes = []
    for i, (_, r) in enumerate(item[item["section"] == "OUTFLOW"].iterrows(),
                               start=1):
        code = f"{2000 + i * 10}"
        o_codes.append(code)
        L.append(FormLine(code, f"외화 {_LCR_KO[r['category']]}", 1, "KRW",
                          float(r["weighted"]) * FX_SHARE,
                          formula=(f"외화 잔액 {float(r['amount']) * FX_SHARE:,.0f} × "
                                   f"이탈률 {float(r['factor']):.0%}"),
                          citation=str(r["citation"]), source_module=_M_LCR))
    L.append(FormLine("3000", "외화 현금유입 인식액", 0, "KRW", inflow_fx,
                      formula=f"min(Σ 유입, 총유출 × {LCR_INFLOW_CAP:.0%})",
                      citation="Basel LCR40.61", source_module=_M_LCR,
                      is_subtotal=True))
    i_codes = []
    for i, (_, r) in enumerate(item[item["section"] == "INFLOW"].iterrows(),
                               start=1):
        code = f"{3000 + i * 10}"
        i_codes.append(code)
        L.append(FormLine(code, f"외화 {_LCR_KO[r['category']]}", 1, "KRW",
                          float(r["weighted"]) * FX_SHARE,
                          formula=(f"외화 잔액 {float(r['amount']) * FX_SHARE:,.0f} × "
                                   f"인식률 {float(r['factor']):.0%}"),
                          citation=str(r["citation"]), source_module=_M_LCR))
    L += [
        FormLine("3100", "유입 인식 상한", 0, "KRW", gross_fx * LCR_INFLOW_CAP,
                 formula=f"외화 총유출 × {LCR_INFLOW_CAP:.0%}",
                 citation="Basel LCR40.61", source_module=_M_LCR),
        FormLine("4000", "외화 순현금유출액", 0, "KRW",
                 float(lcr.net_outflow) * FX_SHARE,
                 formula="외화 총유출 − 외화 인식유입", citation="Basel LCR40",
                 source_module=_M_LCR, is_subtotal=True),
        FormLine("5000", "난외 미사용약정 잔액 (원장, 외화분)", 0, "KRW",
                 undrawn * FX_SHARE,
                 formula=(f"rdm_exposure.undrawn {undrawn:,.0f} × "
                          f"외화비중 {FX_SHARE:.0%}"),
                 citation="Basel CRE20.94 · LCR40 약정",
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("9000", "연결 범위와 외화 배분", 0, "text", None,
                 text_value=("연결 자회사 원장이 없어 연결기준 = 단독기준이다. "
                             + _FX_NOTE + " 난외 약정 유출은 LCR 산출에서 대출채권의 "
                             "10%를 약정 잔액 대용으로 쓰므로 5000의 원장 잔액과 "
                             "일치하지 않는다 — 원장 잔액은 참고치로만 싣는다."),
                 citation=_C63),
    ]
    checks = [
        _sum_check("외화 HQLA = 등급별 합", L, "1000", tuple(h_codes),
                   max(1.0, hqla_fx * 1e-9)),
        _sum_check("외화 총유출 = 항목별 합", L, "2000", tuple(o_codes),
                   max(1.0, gross_fx * 1e-9)),
        FormCheck("외화 인식유입 = min(Σ 유입, 상한)",
                  min(sum(_val(L, c) for c in i_codes), gross_fx * LCR_INFLOW_CAP),
                  _val(L, "3000"), max(1.0, inflow_fx * 1e-9)),
        FormCheck("외화 순현금유출 = 총유출 − 인식유입", gross_fx - inflow_fx,
                  _val(L, "4000"), max(1.0, gross_fx * 1e-9)),
        FormCheck("외화 HQLA = 산출 HQLA × 외화비중",
                  float(lcr.hqla_total) * FX_SHARE, _val(L, "1000"), 1.0),
    ]
    return L, checks


# ---------------------------------------------------------------- B2605

def _b2605(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """단기대출비율 — 단기조달로 받은 자금이 단기여신으로 운용되는 정도."""
    ex = ctx.tables["rdm_exposure"]
    rep = _rep(ctx)
    short = float(ex.loc[ex["maturity"] <= 1.0, "ead"].sum())
    total = float(ex["ead"].sum())
    fund = float(rep.loc[rep["seq"] <= 4, "liability"].sum())   # 1년 이내 4개 구간
    L = [
        FormLine("1000", "총 대출금 (EAD 기준)", 0, "KRW", total,
                 formula="rdm_exposure.ead 합계", citation=_C99,
                 source_module=_M_RDM, is_subtotal=True),
        FormLine("1100", "단기대출금 (잔존만기 1년 이내)", 1, "KRW", short,
                 formula=f"maturity ≤ 1.0 인 익스포저 {int((ex['maturity'] <= 1.0).sum()):,}건",
                 citation=_C26, source_module=_M_RDM),
        FormLine("1200", "장기대출금 (잔존만기 1년 초과)", 1, "KRW",
                 total - short, citation=_C26, source_module=_M_RDM),
        FormLine("2000", "단기조달금 (잔존만기 1년 이내)", 0, "KRW", fund,
                 formula="재설정 사다리 0-1m·1-3m·3-6m·6-12m 부채 합",
                 citation=_LADDER, source_module=_M_BS, is_subtotal=True),
        FormLine("3000", "단기대출비율", 0, "ratio",
                 short / fund if fund else 0.0,
                 formula="단기대출금 ÷ 단기조달금", citation=_C26,
                 source_module=_M_SELF, is_subtotal=True),
        FormLine("3100", "총 대출금 대비 단기대출 비중", 0, "ratio",
                 short / total if total else 0.0,
                 formula="단기대출금 ÷ 총 대출금", citation=_C26,
                 source_module=_M_SELF),
        FormLine("9000", "구간 정의", 0, "text", None,
                 text_value=("서식 정본의 단기 구간 정의(3개월/1년)와 분모(단기조달/"
                             "총대출)를 확인하지 못해 **잔존만기 1년 이내 ÷ 1년 이내 "
                             "조달**로 두고 총대출 대비 비중을 참고로 함께 싣는다. "
                             "포트폴리오의 최단 잔존만기가 0.6년이라 3개월 컷은 전량 "
                             "0이 되어 서식이 비어버린다. 대출은 계약 잔존만기, 조달은 "
                             "재설정 사다리라 기준이 서로 다르다 — 제출 전 반드시 "
                             "정본 정의로 대체해야 하는 칸이다."),
                 citation=_C26),
    ]
    checks = [
        _sum_check("총 대출금 = 단기 + 장기", L, "1000", ("1100", "1200")),
        _ratio_check("단기대출비율 = 단기대출 ÷ 단기조달", L, "3000",
                     "1100", "2000"),
        _ratio_check("단기대출 비중 = 단기대출 ÷ 총대출", L, "3100",
                     "1100", "1000"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2606

def _b2606(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """업무용고정자산비율 — 자기자본 대비 업무용부동산 보유."""
    t = ctx.tables["pru_ownership_limit"]
    r = t[t["item"] == "업무용부동산 소유"].iloc[0]
    equity = float(ctx.result.meta["capital"].total)
    used = float(r["used"])
    M = "risk_lib.prudential.ownership"
    L = [
        FormLine("1000", "자기자본", 0, "KRW", equity,
                 formula="보통주자본 + 기타기본자본 + 보완자본",
                 citation="은행법 제2조 제1항 자기자본", source_module=M,
                 is_subtotal=True),
        FormLine("2000", "업무용고정자산", 0, "KRW", used,
                 formula=str(r["basis"]), citation=str(r["citation"]),
                 source_module=M, is_subtotal=True),
        FormLine("3000", "업무용고정자산비율", 0, "ratio",
                 used / equity if equity else 0.0,
                 formula="업무용고정자산 ÷ 자기자본", citation=str(r["citation"]),
                 source_module=M, is_subtotal=True),
        FormLine("4000", "한도비율", 0, "ratio", float(r["limit_pct"]),
                 formula="이하", citation=str(r["citation"])),
        FormLine("4100", "한도금액", 0, "KRW", float(r["limit_amount"]),
                 formula="자기자본 × 한도비율", citation=str(r["citation"]),
                 source_module=M),
        FormLine("5000", "한도 소진율", 0, "ratio", float(r["utilisation"]),
                 formula="업무용고정자산 ÷ 한도금액", citation=str(r["citation"]),
                 source_module=M),
        FormLine("6000", "한도 내 여부", 0, "count",
                 1.0 if bool(r["passes"]) else 0.0, formula="1 = 한도 내",
                 citation=str(r["citation"]), source_module=M),
    ]
    checks = [
        FormCheck("한도금액 = 자기자본 × 한도비율", equity * float(r["limit_pct"]),
                  _val(L, "4100"), 1.0),
        _ratio_check("업무용고정자산비율 = 자산 ÷ 자기자본", L, "3000",
                     "2000", "1000"),
        _ratio_check("한도 소진율 = 자산 ÷ 한도금액", L, "5000", "2000", "4100"),
        FormCheck("한도 내 판정 = (비율 ≤ 한도비율)",
                  1.0 if _val(L, "3000") <= _val(L, "4000") else 0.0,
                  _val(L, "6000"), 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B2608

def _b2608(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """중장기외화자금조달비율 — 1년 초과 외화조달 ÷ 1년 초과 외화운용."""
    rep = _rep(ctx)
    lt = rep[rep["seq"] >= 5]                     # 1-2y 이후 = 잔존만기 1년 초과
    fund = float(lt["liability"].sum()) * FX_SHARE
    use = float(lt["asset"].sum()) * FX_SHARE
    L = [
        FormLine("1000", "1년 초과 외화조달 합계", 0, "KRW", fund,
                 formula=f"1년 초과 부채 × 외화비중 {FX_SHARE:.0%}", citation=_C63,
                 source_module=_M_PRU, is_subtotal=True),
        FormLine("2000", "1년 초과 외화운용 합계", 0, "KRW", use,
                 formula=f"1년 초과 자산 × 외화비중 {FX_SHARE:.0%}", citation=_C63,
                 source_module=_M_PRU, is_subtotal=True),
    ]
    f_codes, u_codes = [], []
    for _, row in lt.iterrows():
        i = int(row["seq"])
        b = str(row["bucket"])
        f_codes.append(f"{1000 + i * 10}")
        u_codes.append(f"{2000 + i * 10}")
        L += [
            FormLine(f_codes[-1], f"외화조달 · {b}", 1, "KRW",
                     float(row["liability"]) * FX_SHARE, citation=_LADDER,
                     source_module=_M_PRU),
            FormLine(u_codes[-1], f"외화운용 · {b}", 1, "KRW",
                     float(row["asset"]) * FX_SHARE, citation=_LADDER,
                     source_module=_M_PRU),
        ]
    ratio = fund / use if use else 0.0
    L += [
        FormLine("3000", "중장기외화자금조달비율", 0, "ratio", ratio,
                 formula="1년 초과 외화조달 ÷ 1년 초과 외화운용", citation=_C63,
                 source_module=_M_PRU, is_subtotal=True),
        FormLine("3100", "규제 기준", 0, "ratio", 1.0, formula="이상",
                 citation=_C63),
        FormLine("3200", "충족 여부", 0, "count", 1.0 if ratio >= 1.0 else 0.0,
                 formula="1 = 충족", citation=_C63, source_module=_M_PRU),
        FormLine("4000", "총액 기준 동일 비율 (참고)", 0, "ratio",
                 float(lt["liability"].sum()) / float(lt["asset"].sum())
                 if float(lt["asset"].sum()) else 0.0,
                 formula="외화비중이 대칭이라 외화 기준과 같은 값이 된다",
                 citation=_C63, source_module=_M_PRU),
        FormLine("9000", "외화 배분 가정", 0, "text", None,
                 text_value=(_FX_NOTE + " " + _LADDER_NOTE),
                 citation=_C63),
    ]
    checks = [
        _sum_check("1년 초과 외화조달 = 구간별 합", L, "1000", tuple(f_codes),
                   max(1.0, fund * 1e-9)),
        _sum_check("1년 초과 외화운용 = 구간별 합", L, "2000", tuple(u_codes),
                   max(1.0, use * 1e-9)),
        _ratio_check("조달비율 = 외화조달 ÷ 외화운용", L, "3000", "1000", "2000"),
        FormCheck("외화 기준 = 총액 기준 (외화비중 대칭 가정의 귀결)",
                  _val(L, "4000"), _val(L, "3000"), 1e-12),
        FormCheck("충족 판정 = (비율 ≥ 100%)",
                  1.0 if _val(L, "3000") >= _val(L, "3100") else 0.0,
                  _val(L, "3200"), 1e-9),
    ]
    return L, checks


# ---------------------------------------------------------------- B2609

def _b2609(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """계약상 만기불일치 — 구간별 유입·유출과 누적 불일치 비율."""
    rep = _rep(ctx)
    assets = float(rep["asset"].sum())
    liabs = float(rep["liability"].sum())
    bs = ctx.result.alm["balance_sheet"]
    total_assets = float(bs.total_assets)
    total_liabs = float(bs.funding_total())
    L = [
        FormLine("1000", "총자산 (대차대조표)", 0, "KRW", total_assets,
                 formula="누적 불일치 비율의 분모 — B2601 0100과 같은 값",
                 citation=_C99, source_module=_M_BS, is_subtotal=True),
        FormLine("1100", "만기구간 미배분 자산 (비금리민감)", 0, "KRW",
                 total_assets - assets,
                 formula="총자산 − 만기도래 자산 합계", citation=_C99,
                 source_module=_M_BS),
        FormLine("1200", "총부채 (조달 합계)", 0, "KRW", total_liabs,
                 citation=_C99, source_module=_M_BS, is_subtotal=True),
        FormLine("1300", "만기구간 미배분 부채 (비금리민감)", 0, "KRW",
                 total_liabs - liabs,
                 formula="총부채 − 만기도래 부채 합계", citation=_C99,
                 source_module=_M_BS),
        FormLine("2000", "만기도래 자산 합계 (유입)", 0, "KRW", assets,
                 citation=_LADDER, source_module=_M_BS, is_subtotal=True),
        FormLine("3000", "만기도래 부채 합계 (유출)", 0, "KRW", liabs,
                 citation=_LADDER, source_module=_M_BS, is_subtotal=True),
        FormLine("4000", "순 만기불일치 합계", 0, "KRW",
                 float(rep["gap"].sum()), formula="유입 합계 − 유출 합계",
                 citation=f"{_SRP50} — 계약상 만기 불일치", source_module=_M_IRRBB,
                 is_subtotal=True),
    ]
    in_codes, out_codes, net_codes = [], [], []
    for _, row in rep.iterrows():
        i = int(row["seq"])
        b = str(row["bucket"])
        in_codes.append(f"{2000 + i * 10}")
        out_codes.append(f"{3000 + i * 10}")
        net_codes.append(f"{4000 + i * 10}")
        L += [
            FormLine(in_codes[-1], f"유입 · {b}", 1, "KRW", float(row["asset"]),
                     citation=_LADDER, source_module=_M_BS),
            FormLine(out_codes[-1], f"유출 · {b}", 1, "KRW",
                     float(row["liability"]), citation=_LADDER,
                     source_module=_M_BS),
            FormLine(net_codes[-1], f"순 불일치 · {b}", 1, "KRW",
                     float(row["gap"]), formula="유입 − 유출",
                     citation=f"{_SRP50} — 계약상 만기 불일치",
                     source_module=_M_IRRBB),
            FormLine(f"{5000 + i * 10}", f"누적 불일치 · {b}", 2, "KRW",
                     float(row["cumulative_gap"]), formula="당 구간까지 누계",
                     citation=f"{_SRP50} — 계약상 만기 불일치",
                     source_module=_M_IRRBB),
            FormLine(f"{6000 + i * 10}", f"누적 불일치 비율 · {b}", 2, "ratio",
                     float(row["cumulative_gap"]) / total_assets
                     if total_assets else 0.0,
                     formula="누적 불일치 ÷ 총자산",
                     citation=f"{_SRP50} — 계약상 만기 불일치",
                     source_module=_M_SELF),
        ]
    L.append(FormLine("9000", "만기 사다리의 성격", 0, "text", None,
                      text_value=(_LADDER_NOTE + " 사다리는 금리민감 자산·부채만 "
                                  "담으므로 총자산·총부채와의 차를 1100·1300에 "
                                  "미배분 잔액으로 드러내고 대사한다 — 누적 불일치 "
                                  "비율의 분모는 총자산이고 분자는 배분분에서만 "
                                  "나오므로 비율은 그만큼 보수적으로 작아진다."),
                      citation=_LADDER))
    last = int(rep["seq"].iloc[-1])
    checks = [
        _sum_check("유입 합계 = 구간별 합", L, "2000", tuple(in_codes)),
        _sum_check("유출 합계 = 구간별 합", L, "3000", tuple(out_codes)),
        _sum_check("순 불일치 합계 = 구간별 합", L, "4000", tuple(net_codes)),
        _sum_check("총자산 = 만기도래 자산 + 미배분 자산", L, "1000",
                   ("2000", "1100"), max(1.0, total_assets * 1e-9)),
        _sum_check("총부채 = 만기도래 부채 + 미배분 부채", L, "1200",
                   ("3000", "1300"), max(1.0, total_liabs * 1e-9)),
        # 잔차 항등식만으로는 사다리를 검증하지 못한다 — 대차대조표의 독립
        # 구성요소에 묶는다.
        FormCheck("만기도래 자산 = 대출채권 + HQLA (금리민감자산 정의)",
                  float(bs.loans) + float(sum(bs.hqla.values())),
                  _val(L, "2000"), max(1.0, total_assets * 1e-9)),
        FormCheck("미배분 자산 = 대차대조표 기타자산",
                  float(bs.other_assets), _val(L, "1100"),
                  max(1.0, total_assets * 1e-9)),
        FormCheck("총자산 = B2601 총자산 (같은 대차대조표)",
                  float(bs.total_assets), _val(L, "1000"), 1.0),
        FormCheck("최종 누적 불일치 = 순 불일치 합계", _val(L, "4000"),
                  _val(L, f"{5000 + last * 10}"), 1.0),
        _ratio_check("1개월 누적 불일치 비율 = 누적 ÷ 총자산", L, "6010",
                     "5010", "1000"),
        _ratio_check("최종 누적 불일치 비율 = 누적 ÷ 총자산", L,
                     f"{6000 + last * 10}", f"{5000 + last * 10}", "1000"),
    ]
    return L, checks


# ---------------------------------------------------------------- B2610

def _b2610(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """자금조달 편중도 — 중요 거래상대방·중요 금융상품 기준."""
    bs = ctx.result.alm["balance_sheet"]
    liab = float(bs.funding_total())
    wholesale = sum(float(bs.funding[k]) for k in _WHOLESALE_FI)

    # 예금자·차입처 원장이 없다. 총액은 산출값이고 배분 비중만 파생이다 —
    # 난수가 아니라 실제 파생거래 상대방별 EAD 비중을 거래관계 강도로 쓴다.
    cp = ctx.result.ccr.by_counterparty
    w = cp["ead"] / float(cp["ead"].sum())
    alloc = (cp[["counterparty"]].assign(funding=wholesale * w)
             .sort_values("funding", ascending=False).reset_index(drop=True))
    sig = alloc[alloc["funding"] >= liab * _SIG_CP]
    top5 = float(alloc["funding"].head(5).sum())

    L = [
        FormLine("1000", "총부채 (조달 합계)", 0, "KRW", liab,
                 formula="Σ 조달수단별 잔액", citation=_C99, source_module=_M_BS,
                 is_subtotal=True),
        FormLine("1100", "금융기관 도매조달 합계", 0, "KRW", wholesale,
                 formula=" + ".join(_FUNDING_KO[k] for k in _WHOLESALE_FI),
                 citation=f"{_SRP50} — 자금조달 편중도", source_module=_M_BS,
                 is_subtotal=True),
        FormLine("2000", "중요 거래상대방 수", 0, "count", float(len(sig)),
                 formula=f"조달액이 총부채의 {_SIG_CP:.0%} 이상인 거래상대방",
                 citation=f"{_SRP50} — 중요 거래상대방 정의",
                 source_module=_M_SELF, is_subtotal=True),
        FormLine("2100", "중요 거래상대방 조달 합계", 0, "KRW",
                 float(sig["funding"].sum()), formula="중요 거래상대방 배분액 합",
                 citation=f"{_SRP50} — 자금조달 편중도", source_module=_M_SELF,
                 is_subtotal=True),
        FormLine("2200", "중요 거래상대방 조달 비중", 0, "ratio",
                 float(sig["funding"].sum()) / liab if liab else 0.0,
                 formula="중요 거래상대방 조달 ÷ 총부채",
                 citation=f"{_SRP50} — 자금조달 편중도", source_module=_M_SELF),
        FormLine("2300", "상위 5 거래상대방 조달 비중", 0, "ratio",
                 top5 / liab if liab else 0.0,
                 formula="상위 5 조달 ÷ 총부채",
                 citation=f"{_SRP50} — 자금조달 편중도", source_module=_M_SELF),
        FormLine("2400", "도매조달 HHI", 0, "ratio",
                 hhi(alloc["funding"]), formula="Σ 거래상대방 점유율²",
                 citation="SRP30 집중리스크",
                 source_module="risk_lib.limits.concentration"),
    ]
    for i, (_, r) in enumerate(alloc.head(10).iterrows(), start=1):
        L.append(FormLine(f"{3000 + i * 10}", f"상위 거래상대방 {i} · {r['counterparty']}",
                          1, "KRW", float(r["funding"]),
                          formula=(f"도매조달 × EAD 비중 — 배분 비중은 파생값 "
                                   f"(총부채 대비 {float(r['funding']) / liab:.2%})"),
                          citation="파생 근거는 9000 라인", source_module=_M_SELF))
    n_sig_instr = 0
    instr_codes, wh_codes = [], []
    for i, (k, ko) in enumerate(_FUNDING_KO.items(), start=1):
        amt = float(bs.funding[k])
        code = f"{4000 + i * 10}"
        instr_codes.append(code)
        if k in _WHOLESALE_FI:      # 코드를 박아두면 _FUNDING_KO 순서가 바뀔 때
            wh_codes.append(code)   # 검증이 조용히 엉뚱한 라인을 대사한다.
        n_sig_instr += int(amt >= liab * _SIG_INSTR)
        L.append(FormLine(code, f"조달수단 · {ko}", 1, "KRW", amt,
                          formula=f"총부채 대비 {amt / liab:.2%}",
                          citation=f"{_SRP50} — 중요 금융상품",
                          source_module=_M_BS))
    L += [
        FormLine("4000", "중요 금융상품 수", 0, "count", float(n_sig_instr),
                 formula=f"잔액이 총부채의 {_SIG_INSTR:.0%} 이상인 조달수단",
                 citation=f"{_SRP50} — 중요 금융상품 정의", source_module=_M_SELF,
                 is_subtotal=True),
        FormLine("4100", "조달수단 HHI", 0, "ratio",
                 hhi(pd.Series(list(bs.funding.values()))),
                 formula="Σ 조달수단 점유율²", citation="SRP30 집중리스크",
                 source_module="risk_lib.limits.concentration"),
        FormLine("9000", "거래상대방 배분의 성격", 0, "text", None,
                 text_value=("예금자·차입처 원장이 없다. 금융기관 도매조달 **총액은 "
                             "산출값**이고 거래상대방별 배분 비중만 파생값이다 — 난수가 "
                             "아니라 result.ccr.by_counterparty의 실제 거래상대방별 "
                             "EAD 비중을 거래관계 강도의 대용으로 썼으므로 같은 산출이면 "
                             "같은 배분이 나온다. 개인·법인 예금은 예금자 원장이 없어 "
                             "중요 거래상대방 판정에서 제외했다 — 중요 거래상대방 수가 "
                             "과소계상될 수 있는 칸이다."),
                 citation=f"{_SRP50} — 자금조달 편중도"),
    ]
    checks = [
        _sum_check("조달수단별 합 = 총부채", L, "1000", tuple(instr_codes)),
        _sum_check("도매조달 합계 = 도매 조달수단 합", L, "1100",
                   tuple(wh_codes)),
        FormCheck("거래상대방 배분 합 = 도매조달 합계", wholesale,
                  float(alloc["funding"].sum()), max(1.0, wholesale * 1e-9)),
        FormCheck("상위 10 배분 합 ≤ 도매조달 합계", 0.0,
                  max(0.0, sum(_val(L, f"{3000 + i * 10}") for i in range(1, 11))
                      - wholesale), 1.0),
        _ratio_check("중요 거래상대방 비중 = 조달 ÷ 총부채", L, "2200",
                     "2100", "1000"),
        FormCheck("HHI는 0~1 범위", 0.0,
                  max(0.0, _val(L, "2400") - 1.0) + max(0.0, _val(L, "4100") - 1.0),
                  1e-12),
    ]
    return L, checks


# ---------------------------------------------------------------- B2611

def _b2611(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """자금조달 편중도 — 중요 통화별 자산·부채 기준."""
    bs = ctx.result.alm["balance_sheet"]
    assets = float(bs.total_assets)
    liab = float(bs.funding_total())
    weights = [("KRW", 1.0 - FX_SHARE)] + [(c, FX_SHARE * w)
                                           for c, w in _ccy_weights(ctx)]
    L = [
        FormLine("1000", "총자산", 0, "KRW", assets, citation=_C99,
                 source_module=_M_BS, is_subtotal=True),
        FormLine("2000", "총부채", 0, "KRW", liab, citation=_C99,
                 source_module=_M_BS, is_subtotal=True),
    ]
    a_codes, l_codes, n_sig, max_dev, liab_by_ccy = [], [], 0, 0.0, []
    fx_share_codes = []
    for i, (ccy, share) in enumerate(weights, start=1):
        base = 3000 + i * 100
        a, l = assets * share, liab * share
        sig = share >= _SIG_CCY
        n_sig += int(sig)
        max_dev = max(max_dev, abs((a / assets) - (l / liab)))
        liab_by_ccy.append(l)
        a_codes.append(str(base))
        l_codes.append(str(base + 10))
        if ccy != "KRW":
            fx_share_codes.append(str(base + 30))
        L += [
            FormLine(str(base), f"{ccy} 자산", 1, "KRW", a,
                     formula=f"총자산 × 통화비중 {share:.2%}", citation=_C63,
                     source_module=_M_SELF),
            FormLine(str(base + 10), f"{ccy} 부채", 1, "KRW", l,
                     formula=f"총부채 × 통화비중 {share:.2%}", citation=_C63,
                     source_module=_M_SELF),
            FormLine(str(base + 20), f"{ccy} 자산 비중", 2, "ratio",
                     a / assets if assets else 0.0, formula="통화별 자산 ÷ 총자산",
                     citation=_C63, source_module=_M_SELF),
            FormLine(str(base + 30), f"{ccy} 부채 비중", 2, "ratio",
                     l / liab if liab else 0.0, formula="통화별 부채 ÷ 총부채",
                     citation=f"{_SRP50} — 중요통화 정의", source_module=_M_SELF),
            FormLine(str(base + 40), f"{ccy} 자산−부채 차이", 2, "KRW", a - l,
                     formula=("자산·부채 통화비중이 같으므로 이 차이는 통화 불일치가 "
                              "아니라 자기자본(자산 − 부채)의 통화별 배분이다"),
                     citation=_C63, source_module=_M_SELF),
            FormLine(str(base + 50), f"{ccy} 중요통화 여부", 2, "count",
                     1.0 if sig else 0.0,
                     formula=f"1 = 총부채의 {_SIG_CCY:.0%} 이상",
                     citation=f"{_SRP50} — 중요통화 정의", source_module=_M_SELF),
        ]
    L += [
        FormLine("8000", "중요통화 수 (원화 포함)", 0, "count", float(n_sig),
                 formula=(f"총부채의 {_SIG_CCY:.0%} 이상 통화 — 원화 제외 기준은 "
                          f"B2602-1 8000 라인"),
                 citation=f"{_SRP50} — 중요통화 정의", source_module=_M_SELF,
                 is_subtotal=True),
        FormLine("8100", "외화부채 비중", 0, "ratio", FX_SHARE,
                 formula="자산·부채 동일 적용 — 비원화 부채비중 합과 대사한다",
                 citation=_C63, source_module=_M_PRU),
        FormLine("8200", "통화별 부채 HHI", 0, "ratio",
                 hhi(pd.Series(liab_by_ccy)), formula="Σ 통화 점유율²",
                 citation="SRP30 집중리스크",
                 source_module="risk_lib.limits.concentration"),
        FormLine("9000", "통화 배분의 성격", 0, "text", None,
                 text_value=(_FX_NOTE + " 외화 안의 통화 구성비는 차주 소재국 원장에서 "
                             "뽑아 자산·부채에 같은 값을 적용했다 — 통화별 순포지션은 "
                             "통화 불일치가 아니라 자기자본의 통화별 배분이다."),
                 citation=_C63),
    ]
    checks = [
        _sum_check("통화별 자산 합 = 총자산", L, "1000", tuple(a_codes),
                   max(1.0, assets * 1e-9)),
        _sum_check("통화별 부채 합 = 총부채", L, "2000", tuple(l_codes),
                   max(1.0, liab * 1e-9)),
        FormCheck("통화별 자산비중 = 부채비중 (대칭 가정 — 통화 불일치 없음)",
                  0.0, max_dev, 1e-12),
        FormCheck("비원화 부채비중 합 = 외화부채 비중", _val(L, "8100"),
                  sum(_val(L, c) for c in fx_share_codes), 1e-12),
        FormCheck("HHI는 0~1 범위", 0.0, max(0.0, _val(L, "8200") - 1.0), 1e-12),
    ]
    return L, checks


# ---------------------------------------------------------------- B2612

def _b2612(ctx) -> tuple[list[FormLine], list[FormCheck]]:
    """처분제한이 없는 자산규모 — LCR HQLA와 겹치지만 상한 전, 담보제공 차감 후."""
    bs = ctx.result.alm["balance_sheet"]
    lcr = ctx.result.alm["lcr"]
    cp = ctx.result.ccr.by_counterparty
    # 은행이 **제공한** 담보. 조달구성이 전액 무담보라 담보제공 소요는 파생거래
    # 순시장가치가 음(-)인 거래상대방에 대한 변동증거금뿐이다 — 산출값이다.
    pledged = float(np.maximum(-cp["v"], 0.0).sum())
    levels = [("Level 1", "level_1", 0.0),
              ("Level 2A", "level_2a", LCR_HAIRCUT_L2A),
              ("Level 2B", "level_2b", LCR_HAIRCUT_L2B)]
    mv = {k: float(bs.hqla[k]) for _, k, _ in levels}
    total_mv = sum(mv.values())

    # 고유동성 순서대로 담보를 제공한다 — 배분 규칙이지 난수가 아니다.
    remain, pledge = pledged, {}
    for _, key, _ in levels:
        pledge[key] = min(remain, mv[key])
        remain -= pledge[key]

    L = [
        FormLine("1000", "유가증권 시가 합계", 0, "KRW", total_mv,
                 formula="Level 1 + 2A + 2B 시가 (상한 적용 전)",
                 citation="Basel LCR30.34~30.47", source_module=_M_BS,
                 is_subtotal=True),
        FormLine("2000", "처분제한 자산 합계 (담보제공)", 0, "KRW", pledged,
                 formula="Σ max(−순시장가치, 0) — 파생거래 변동증거금 소요액",
                 citation=f"{_SRP50} — 처분제한 없는 자산", source_module=_M_CCR,
                 is_subtotal=True),
        FormLine("3000", "처분제한이 없는 자산", 0, "KRW", total_mv - pledged,
                 formula="유가증권 시가 합계 − 담보제공액", citation=_SRP50,
                 source_module=_M_SELF, is_subtotal=True),
    ]
    mv_codes, pl_codes, free_codes = [], [], []
    haircut_free = 0.0
    for i, (name, key, hc) in enumerate(levels, start=1):
        free = mv[key] - pledge[key]
        haircut_free += free * (1 - hc)
        mv_codes.append(f"{1000 + i * 10}")
        pl_codes.append(f"{2000 + i * 10}")
        free_codes.append(f"{3000 + i * 10}")
        L += [
            FormLine(mv_codes[-1], f"{name} 시가", 1, "KRW", mv[key],
                     citation="Basel LCR30.34~30.47", source_module=_M_BS),
            FormLine(pl_codes[-1], f"{name} 담보제공액", 1, "KRW", pledge[key],
                     formula="고유동성 순서로 충당", citation=_SRP50,
                     source_module=_M_SELF),
            FormLine(free_codes[-1], f"{name} 처분제한 없는 잔액", 1, "KRW", free,
                     formula=f"시가 − 담보제공액 · haircut {hc:.0%}",
                     citation=_SRP50, source_module=_M_SELF),
        ]
    L += [
        FormLine("4000", "haircut 적용 후 처분제한 없는 자산", 0, "KRW",
                 haircut_free, formula="Σ 등급별 잔액 × (1 − haircut)",
                 citation="Basel LCR30.34~30.47", source_module=_M_SELF,
                 is_subtotal=True),
        FormLine("5000", "LCR 인정 HQLA (참고)", 0, "KRW",
                 float(lcr.hqla_total),
                 formula="Level 2 40% · Level 2B 15% 상한 적용 후",
                 citation="Basel LCR30.47", source_module=_M_LCR),
        FormLine("5100", "처분제한 없는 자산 − LCR 인정액", 0, "KRW",
                 haircut_free - float(lcr.hqla_total),
                 formula="차이는 담보제공액과 LCR 등급 상한에서 나온다",
                 citation="Basel LCR30.47", source_module=_M_SELF),
        FormLine("6000", "수취 담보 시가 합계 (참고)", 0, "KRW",
                 float(ctx.tables["rdm_collateral"]["market_value"].sum()),
                 formula=(f"rdm_collateral {len(ctx.tables['rdm_collateral']):,}건 — "
                          f"은행이 **수취한** 담보이며 재담보 가정을 두지 않아 "
                          f"처분제한 없는 자산에 포함하지 않는다"),
                 citation="Basel CRE22 담보 인식", source_module=_M_RDM),
        FormLine("9000", "담보제공 범위", 0, "text", None,
                 text_value=("RP·커버드본드·중앙은행 차입 등 담보부 조달 원장이 없다. "
                             "합성 조달구성이 전액 무담보라 처분제한 자산은 파생거래 "
                             "변동증거금 소요액(순시장가치가 음인 거래상대방 합계)뿐이며 "
                             "이 값은 파생이 아니라 산출값이다. 담보부 조달이 들어오면 "
                             "처분제한 자산은 늘고 이 서식의 잔액은 줄어든다 — 현재 값은 "
                             "상한선으로 읽어야 한다."),
                 citation=f"{_SRP50} — 처분제한 없는 자산"),
    ]
    checks = [
        _sum_check("유가증권 시가 합계 = 등급별 합", L, "1000", tuple(mv_codes)),
        _sum_check("담보제공 합계 = 등급별 합", L, "2000", tuple(pl_codes)),
        _sum_check("처분제한 없는 자산 = 등급별 합", L, "3000", tuple(free_codes)),
        FormCheck("처분제한 없는 자산 = 시가 합계 − 담보제공액",
                  total_mv - pledged, _val(L, "3000"), 1.0),
        FormCheck("haircut 후 잔액 = Σ 등급별 × (1 − haircut)",
                  sum((mv[k] - pledge[k]) * (1 - hc) for _, k, hc in levels),
                  _val(L, "4000"), 1.0),
        FormCheck("담보제공액 = Σ max(−순시장가치, 0)", pledged,
                  _val(L, "2000"), 1.0),
        FormCheck("LCR 인정액과의 차 = haircut 후 잔액 − LCR 인정 HQLA",
                  _val(L, "4000") - _val(L, "5000"), _val(L, "5100"), 1.0),
        # 담보제공 소요가 유가증권 시가를 넘으면 등급별 충당이 pledged를 다 못
        # 담아 3000이 음수로 새어나간다. 현재 데이터에선 발생하지 않지만
        # 대사 없이 넘기면 조용히 틀린다.
        FormCheck("담보제공 소요 ≤ 유가증권 시가 합계", 0.0,
                  max(0.0, pledged - total_mv), 1.0),
    ]
    return L, checks


# ---------------------------------------------------------------- 등록

BUILDERS: dict[str, tuple[str, str, Callable]] = {
    "B2601": ("은행업감독규정 제26조 · Basel SRP31.94 표준 만기 구간", "PRD-ALM",
              _b2601),
    "B2602-1": ("은행업감독규정 제26조·제63조 · Basel LCR20~40 · SRP50 중요통화",
                "PRD-ALM", _b2602_1),
    "B2602-2": ("은행업감독규정 제26조 제1항 · Basel LCR20", "PRD-ALM", _b2602_2),
    "B2602-3": ("은행업감독규정 제63조 · Basel LCR20 · SRP50 중요통화", "PRD-ALM",
                _b2602_3),
    "B2602-4": ("은행업감독규정 제63조 · Basel LCR30·LCR40", "PRD-ALM", _b2602_4),
    "B2605": ("은행업감독규정 제26조 제1항 유동성 관리", "PRD-ALM", _b2605),
    "B2606": ("은행법 제38조 제3호 — 자기자본 60% 이내", "PRD-CAP", _b2606),
    "B2608": ("은행업감독규정 제63조 · Basel NSF20~30", "PRD-ALM", _b2608),
    "B2609": ("Basel SRP50 계약상 만기 불일치 · 은행업감독규정 제26조", "PRD-ALM",
              _b2609),
    "B2610": ("Basel SRP50 자금조달 편중도 · SRP30 집중리스크", "PRD-RDM", _b2610),
    "B2611": ("Basel SRP50 자금조달 편중도(통화별) · 은행업감독규정 제63조",
              "PRD-ALM", _b2611),
    "B2612": ("Basel SRP50 처분제한 없는 자산 · 은행업감독규정 제26조", "PRD-ALM",
              _b2612),
}
