"""PD 설계 구분(TTC·PIT) 검증.

TTC 는 IRB 자본 산출용이라 경기순환주기를 반영한 장기평균이어야 하고, PIT 는
IFRS 9 ECL 용이라 시점 조건부여야 한다. 같은 등급체계를 양쪽에 쓰면서 라벨만
바꿔 다는 것을 잡는 것이 이 도구의 목적이다.

국내 근거는 세칙 별표 3 이다.

    "은행은 PD 추정시 5년 이상의 관측기간에 걸친 외부 데이터, 내부 데이터
     또는 금융기관간 공유 데이터 중 하나 이상을 이용하여야 한다."
    "PD 추정에 사용된 데이터는 경기순환주기를 반영하여야 하며, 과거 1년
     부도율의 평균을 기초로 산출되어야 한다."

검사하는 것:

1. 관측기간이 최소 연수를 충족하는가
2. 등급별 PD 가 연도간 안정적인가 (변동계수)
3. 포트폴리오 평균 PD 변동이 **등급 이동**으로 설명되는가, 아니면 **등급별 PD
   변동**으로 설명되는가. TTC 라면 이동분이 지배해야 한다
4. 등급별 PD 가 거시변수와 유의하게 상관되지 않는가 (TTC 주장 시)
5. 예측 PD 시계열이 실현 부도율 시계열을 추종하는가 (PIT 주장 시)
6. TTC 와 PIT 의 단일요인 변환이 왕복에서 복원되는가

판정은 **설계 주장과 자료가 어긋나는지**를 본다. 어긋나지 않는다고 해서 추정이
옳다는 뜻은 아니다.

사용:
    python -m tools.pd_cyclicality demo [--design TTC|PIT] [--mislabel]
    python -m tools.pd_cyclicality analyse --panel <json>
    python -m tools.pd_cyclicality convert --pd 0.01 --rho 0.15 --z -2.0
"""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parent.parent
THRESHOLDS = ROOT / "harness" / "pd_design_thresholds.json"

DESIGNS = ("TTC", "PIT")


def load_thresholds(path: Path | str = THRESHOLDS) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


# ---------------------------------------------------------------- 단일요인 변환

def ttc_to_pit(ttc_pd: float, rho: float, z: float) -> float:
    """단일요인(Vasicek) 변환. z 는 시스템적 요인이며 침체일수록 음수다."""
    if not 0.0 < ttc_pd < 1.0:
        raise ValueError(f"PD 는 (0,1) 구간이어야 한다: {ttc_pd}")
    if not 0.0 <= rho < 1.0:
        raise ValueError(f"자산상관은 [0,1) 구간이어야 한다: {rho}")
    k = stats.norm.ppf(ttc_pd)
    return float(stats.norm.cdf((k - math.sqrt(rho) * z) / math.sqrt(1.0 - rho)))


def pit_to_ttc(pit_pd: float, rho: float, z: float) -> float:
    """역변환. 같은 z 로 되돌리면 원값이 복원되어야 한다."""
    if not 0.0 < pit_pd < 1.0:
        raise ValueError(f"PD 는 (0,1) 구간이어야 한다: {pit_pd}")
    if not 0.0 <= rho < 1.0:
        raise ValueError(f"자산상관은 [0,1) 구간이어야 한다: {rho}")
    k = stats.norm.ppf(pit_pd)
    return float(stats.norm.cdf(k * math.sqrt(1.0 - rho) + math.sqrt(rho) * z))


def roundtrip(pd_value: float, rho: float, z: float, tol: float) -> dict:
    """PIT 로 갔다가 TTC 로 되돌아왔을 때 복원되는가."""
    pit = ttc_to_pit(pd_value, rho, z)
    back = pit_to_ttc(pit, rho, z)
    diff = back - pd_value
    return {
        "ttc": pd_value, "pit": pit, "restored": back,
        "diff": diff, "tolerance": tol, "passed": abs(diff) <= tol,
    }


def phase_sign(ttc_pd: float, pit_pd: float, z: float) -> dict:
    """국면 부호 정합. 호황(z>0)이면 PIT < TTC, 침체(z<0)이면 PIT > TTC 여야 한다."""
    if z > 0:
        expected, ok = "PIT < TTC", pit_pd < ttc_pd
    elif z < 0:
        expected, ok = "PIT > TTC", pit_pd > ttc_pd
    else:
        expected, ok = "PIT = TTC", math.isclose(pit_pd, ttc_pd, rel_tol=1e-12)
    return {"z": z, "expected": expected, "ttc": ttc_pd, "pit": pit_pd, "passed": ok}


# ---------------------------------------------------------------- 패널 분석

def _by_period(obs: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = defaultdict(list)
    for o in obs:
        out[str(o["period"])].append(o)
    return dict(sorted(out.items()))


def grade_pd_stability(obs: list[dict]) -> dict:
    """등급별 예측 PD 의 연도간 변동계수. TTC 라면 낮아야 한다."""
    by_grade: dict[str, list[float]] = defaultdict(list)
    for o in obs:
        by_grade[str(o["grade"])].append(float(o["predicted_pd"]))
    rows = {}
    for g, pds in sorted(by_grade.items()):
        arr = np.array(pds, dtype=float)
        mean = float(arr.mean())
        cv = float(arr.std(ddof=0) / mean) if mean > 0 else float("nan")
        rows[g] = {"n_periods": len(arr), "mean_pd": mean,
                   "std_pd": float(arr.std(ddof=0)), "cv": cv}
    return rows


def mix_level_decomposition(obs: list[dict]) -> dict:
    """포트폴리오 평균 PD 변동을 등급 이동분과 등급별 PD 변동분으로 분해.

    TTC 라면 경기가 나쁠 때 **차주가 하위 등급으로 이동**해야 하고, 등급별 PD
    자체는 크게 움직이지 않아야 한다. 이동분이 작고 수준분이 지배하면 사실상
    PIT 다.
    """
    periods = _by_period(obs)
    keys = list(periods)
    if len(keys) < 2:
        return {"available": False, "reason": "기간이 2개 미만이라 분해할 수 없다"}

    def weights_and_pd(rows):
        total = sum(float(r["n"]) for r in rows)
        w = {str(r["grade"]): float(r["n"]) / total for r in rows} if total else {}
        pd_ = {str(r["grade"]): float(r["predicted_pd"]) for r in rows}
        return w, pd_

    w0, p0 = weights_and_pd(periods[keys[0]])
    w1, p1 = weights_and_pd(periods[keys[-1]])
    grades = sorted(set(w0) | set(w1))

    mix = sum((w1.get(g, 0.0) - w0.get(g, 0.0)) * p0.get(g, 0.0) for g in grades)
    level = sum(w0.get(g, 0.0) * (p1.get(g, 0.0) - p0.get(g, 0.0)) for g in grades)
    inter = sum((w1.get(g, 0.0) - w0.get(g, 0.0)) * (p1.get(g, 0.0) - p0.get(g, 0.0))
                for g in grades)
    avg0 = sum(w0.get(g, 0.0) * p0.get(g, 0.0) for g in grades)
    avg1 = sum(w1.get(g, 0.0) * p1.get(g, 0.0) for g in grades)
    total_delta = avg1 - avg0

    denom = abs(mix) + abs(level)
    share = abs(mix) / denom if denom > 0 else float("nan")
    return {
        "available": True, "base_period": keys[0], "current_period": keys[-1],
        "avg_pd_base": avg0, "avg_pd_current": avg1, "total_delta": total_delta,
        "mix_effect": mix, "level_effect": level, "interaction": inter,
        "reconciles": math.isclose(mix + level + inter, total_delta, abs_tol=1e-12),
        "mix_effect_share": share,
    }


def macro_correlation(obs: list[dict], macro: dict[str, float]) -> dict:
    """등급별 예측 PD 와 거시변수의 상관. TTC 라면 유의하지 않아야 한다."""
    by_grade: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for o in obs:
        by_grade[str(o["grade"])].append((str(o["period"]), float(o["predicted_pd"])))
    rows = {}
    for g, series in sorted(by_grade.items()):
        pairs = [(pd_, macro[p]) for p, pd_ in sorted(series) if p in macro]
        if len(pairs) < 3:
            rows[g] = {"n": len(pairs), "r": None, "p_value": None,
                       "reason": "관측이 3개 미만이라 상관을 내지 않는다"}
            continue
        x = np.array([a for a, _ in pairs], dtype=float)
        y = np.array([b for _, b in pairs], dtype=float)
        if x.std(ddof=0) == 0 or y.std(ddof=0) == 0:
            rows[g] = {"n": len(pairs), "r": 0.0, "p_value": 1.0,
                       "reason": "한쪽이 상수라 상관이 정의되지 않는다"}
            continue
        r, p = stats.pearsonr(x, y)
        rows[g] = {"n": len(pairs), "r": float(r), "p_value": float(p)}
    return rows


def pit_tracking(obs: list[dict]) -> dict:
    """예측 PD 가 실현 부도율을 추종하는가.

    **등급 수준**에서 본다. 포트폴리오 평균으로 보면 TTC 도 통과한다: 등급별 PD
    가 고정돼 있어도 차주가 하위 등급으로 이동하면 평균이 경기를 따라 움직이기
    때문이다. 이 함수의 초판이 평균만 보게 돼 있었고, TTC 표본을 PIT 이라
    주장해도 잡지 못했다. 포트폴리오 값은 참고로만 싣는다.
    """
    periods = _by_period(obs)
    keys = list(periods)

    # 참고: 포트폴리오 평균 (판정에 쓰지 않는다)
    pf_pred, pf_real, pf_keys = [], [], []
    for p, rows in periods.items():
        n = sum(float(r["n"]) for r in rows)
        if n <= 0:
            continue
        pf_keys.append(p)
        pf_pred.append(sum(float(r["n"]) * float(r["predicted_pd"]) for r in rows) / n)
        pf_real.append(sum(float(r["defaults"]) for r in rows) / n)
    portfolio = {"periods": pf_keys,
                 "predicted": [float(v) for v in pf_pred],
                 "realised": [float(v) for v in pf_real]}
    if len(pf_keys) >= 3:
        a, b = np.array(pf_pred), np.array(pf_real)
        if a.std(ddof=0) == 0 or b.std(ddof=0) == 0:
            portfolio["correlation"] = 0.0
        else:
            portfolio["correlation"] = float(stats.pearsonr(a, b)[0])
        portfolio["note"] = ("등급 이동만으로도 움직인다. 설계 판정에 쓰지 않는다.")

    # 판정: 등급 수준
    by_grade: dict[str, list[tuple[str, float, float, float]]] = defaultdict(list)
    for o in obs:
        n = float(o["n"])
        if n <= 0:
            continue
        by_grade[str(o["grade"])].append(
            (str(o["period"]), float(o["predicted_pd"]), float(o["defaults"]) / n, n))

    grades, weights = {}, {}
    for g, series in sorted(by_grade.items()):
        series.sort()
        if len(series) < 3:
            grades[g] = {"n_periods": len(series), "correlation": None,
                         "reason": "기간이 3개 미만이라 추종성을 내지 않는다"}
            continue
        pred = np.array([x[1] for x in series], dtype=float)
        real = np.array([x[2] for x in series], dtype=float)
        if pred.std(ddof=0) == 0 or real.std(ddof=0) == 0:
            r = 0.0
        else:
            r = float(stats.pearsonr(pred, real)[0])
        dp, dr = np.diff(pred), np.diff(real)
        agree = float(np.mean(np.sign(dp) == np.sign(dr))) if len(dp) else float("nan")
        grades[g] = {"n_periods": len(series), "correlation": r,
                     "mad": float(np.mean(np.abs(pred - real))),
                     "direction_agreement": agree}
        weights[g] = sum(x[3] for x in series)

    usable = {g: v for g, v in grades.items() if v.get("correlation") is not None}
    if not usable:
        return {"available": False, "portfolio": portfolio,
                "grades": grades,
                "reason": "등급 수준에서 추종성을 낼 수 있는 등급이 없다"}

    tw = sum(weights[g] for g in usable) or 1.0
    def wmean(field):
        vals = [(weights[g] * usable[g][field]) for g in usable
                if not (isinstance(usable[g][field], float)
                        and math.isnan(usable[g][field]))]
        return float(sum(vals) / tw) if vals else float("nan")

    return {
        "available": True,
        "portfolio": portfolio,
        "grades": grades,
        "weighted_correlation": wmean("correlation"),
        "min_correlation": min(usable[g]["correlation"] for g in usable),
        "weighted_mad": wmean("mad"),
        "weighted_direction_agreement": wmean("direction_agreement"),
    }


# ---------------------------------------------------------------- 판정

def classify(panel: dict, th: dict | None = None) -> dict:
    """설계 주장과 자료가 어긋나는지 판정한다."""
    th = th or load_thresholds()
    claimed = panel.get("claimed_design")
    if claimed not in DESIGNS:
        raise ValueError(f"claimed_design 은 {DESIGNS} 중 하나여야 한다: {claimed}")
    obs = panel["observations"]
    macro = {str(k): float(v) for k, v in (panel.get("macro") or {}).items()}

    n_years = len({str(o["period"]) for o in obs})
    stability = grade_pd_stability(obs)
    decomp = mix_level_decomposition(obs)
    corr = macro_correlation(obs, macro) if macro else {}
    tracking = pit_tracking(obs)

    findings: list[str] = []

    if n_years < th["ttc"]["min_observation_years"]:
        findings.append(
            f'관측기간 {n_years}년으로 최소 {th["ttc"]["min_observation_years"]}년 미달 '
            f'(세칙 별표 3: 5년 이상의 관측기간)')

    if claimed == "TTC":
        bad_cv = {g: v["cv"] for g, v in stability.items()
                  if not math.isnan(v["cv"]) and v["cv"] > th["ttc"]["grade_pd_cv_max"]}
        if bad_cv:
            findings.append(
                f'등급별 PD 변동계수가 임계 {th["ttc"]["grade_pd_cv_max"]} 초과: ' +
                ", ".join(f"{g} {v:.3f}" for g, v in sorted(bad_cv.items())) +
                " (등급별 PD 가 움직이면 TTC 가 아니다)")
        if decomp.get("available") and not math.isnan(decomp["mix_effect_share"]):
            if decomp["mix_effect_share"] < th["ttc"]["mix_effect_share_min"]:
                findings.append(
                    f'평균 PD 변동이 등급 이동으로 설명되지 않는다: 이동분 비중 '
                    f'{decomp["mix_effect_share"]:.3f} < 임계 '
                    f'{th["ttc"]["mix_effect_share_min"]} (수준분이 지배하면 사실상 PIT)')
        sig = {g: v for g, v in corr.items()
               if v.get("r") is not None
               and abs(v["r"]) > th["ttc"]["macro_correlation_abs_max"]
               and v["p_value"] is not None
               and v["p_value"] < th["ttc"]["macro_correlation_alpha"]}
        if sig:
            findings.append(
                "등급별 PD 가 거시변수와 유의하게 상관된다: " +
                ", ".join(f'{g} r={v["r"]:+.3f} p={v["p_value"]:.4f}'
                          for g, v in sorted(sig.items())))
    else:
        if not tracking.get("available"):
            findings.append(f'PIT 추종성을 판정할 수 없다: {tracking.get("reason")}')
        else:
            if tracking["weighted_correlation"] < th["pit"]["tracking_correlation_min"]:
                findings.append(
                    f'등급 수준에서 예측 PD 가 실현 부도율을 추종하지 않는다: '
                    f'가중 상관 {tracking["weighted_correlation"]:.3f} < 임계 '
                    f'{th["pit"]["tracking_correlation_min"]} (시점 정보를 반영하지 '
                    f'않으면 PIT 가 아니다)')
            if tracking["weighted_mad"] > th["pit"]["tracking_mad_max"]:
                findings.append(
                    f'등급 수준 평균절대편차 {tracking["weighted_mad"]:.4f} 가 임계 '
                    f'{th["pit"]["tracking_mad_max"]} 초과')
            if (not math.isnan(tracking["weighted_direction_agreement"])
                    and tracking["weighted_direction_agreement"]
                    < th["pit"]["direction_agreement_min"]):
                findings.append(
                    f'등급 수준 방향 일치율 '
                    f'{tracking["weighted_direction_agreement"]:.3f} 이 임계 '
                    f'{th["pit"]["direction_agreement_min"]} 미만')

    return {
        "claimed_design": claimed,
        "n_observation_years": n_years,
        "grade_pd_stability": stability,
        "mix_level_decomposition": decomp,
        "macro_correlation": corr,
        "pit_tracking": tracking,
        "findings": findings,
        "verdict": "정합" if not findings else "불일치",
    }


# ---------------------------------------------------------------- 합성 표본

def synthetic_panel(design: str, *, seed: int = 42, years: int = 6,
                    mislabel: bool = False) -> dict:
    """설계별 합성 패널. mislabel 이면 자료는 PIT 인데 TTC 라고 주장한다."""
    rng = np.random.default_rng(seed)
    grades = {"A": 0.004, "B": 0.012, "C": 0.040}
    macro = {}
    obs = []
    periods = [str(2020 + i) for i in range(years)]
    cycle = np.array([1.8, 2.4, -1.2, -2.6, 0.9, 2.1, 1.5, -0.4])[:years]

    for i, p in enumerate(periods):
        z = float(cycle[i])
        macro[p] = z
        # 경기가 나쁠수록 하위 등급 비중이 커진다 (등급 이동)
        tilt = -z * 0.04
        base_w = {"A": 0.5 - tilt, "B": 0.3, "C": 0.2 + tilt}
        total_n = 4000
        for g, base_pd in grades.items():
            n = max(50, int(total_n * base_w[g]))
            if design == "TTC":
                pd_ = base_pd * float(rng.normal(1.0, 0.02))   # 등급별 PD 는 안정
            else:
                pd_ = base_pd * math.exp(-0.35 * z)            # 시점 조건부
            realised = base_pd * math.exp(-0.35 * z)
            defaults = int(rng.binomial(n, min(0.999, realised)))
            obs.append({"period": p, "grade": g, "predicted_pd": float(pd_),
                        "n": n, "defaults": defaults})
    claimed = "TTC" if (design == "TTC" or mislabel) else "PIT"
    return {"claimed_design": claimed, "observations": obs, "macro": macro}


# ---------------------------------------------------------------- CLI

def _print_report(res: dict) -> None:
    print(f'PD 설계 판정: 주장 {res["claimed_design"]} · 관측기간 '
          f'{res["n_observation_years"]}년 · 판정 **{res["verdict"]}**\n')
    print("[등급별 PD 안정성]")
    for g, v in res["grade_pd_stability"].items():
        cv = v["cv"]
        print(f'  {g}  평균 {v["mean_pd"]:.5f} · 표준편차 {v["std_pd"]:.5f} · '
              f'변동계수 {cv:.4f}' if not math.isnan(cv) else f'  {g}  변동계수 산출 불가')
    d = res["mix_level_decomposition"]
    if d.get("available"):
        print(f'\n[평균 PD 변동 분해] {d["base_period"]} → {d["current_period"]}')
        print(f'  총 변동 {d["total_delta"]:+.6f} = 이동분 {d["mix_effect"]:+.6f} + '
              f'수준분 {d["level_effect"]:+.6f} + 교차 {d["interaction"]:+.6f}')
        print(f'  합계 대사 {"PASS" if d["reconciles"] else "FAIL"} · '
              f'이동분 비중 {d["mix_effect_share"]:.3f}')
    if res["macro_correlation"]:
        print("\n[등급별 PD 와 거시변수 상관]")
        for g, v in res["macro_correlation"].items():
            if v.get("r") is None:
                print(f'  {g}  {v.get("reason")}')
            else:
                print(f'  {g}  r={v["r"]:+.3f} · p={v["p_value"]:.4f} · n={v["n"]}')
    t = res["pit_tracking"]
    if t.get("available"):
        print(f'\n[시점 추종성 · 등급 수준] 가중 상관 '
              f'{t["weighted_correlation"]:+.3f} · 최소 상관 '
              f'{t["min_correlation"]:+.3f} · 가중 MAD {t["weighted_mad"]:.5f} · '
              f'가중 방향 일치율 {t["weighted_direction_agreement"]:.3f}')
        pf = t["portfolio"].get("correlation")
        if pf is not None:
            print(f'  (참고) 포트폴리오 평균 상관 {pf:+.3f} · '
                  f'등급 이동만으로도 움직이므로 판정에 쓰지 않는다')
    print(f'\n[지적 {len(res["findings"])}건]')
    for f in res["findings"]:
        print(f"  - {f}")
    if not res["findings"]:
        print("  없음. 다만 자료가 주장과 어긋나지 않는다는 뜻이며 "
              "추정이 옳다는 뜻은 아니다.")


def _cmd_demo(args) -> int:
    panel = synthetic_panel(args.design, seed=args.seed, years=args.years,
                            mislabel=args.mislabel)
    if args.mislabel:
        print("합성 표본: 자료는 PIT 인데 TTC 라고 주장한다 (음성 통제)\n")
    res = classify(panel)
    _print_report(res)
    return 0 if res["verdict"] == "정합" else 1


def _cmd_analyse(args) -> int:
    panel = json.loads(Path(args.panel).read_text(encoding="utf-8"))
    res = classify(panel)
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        _print_report(res)
    return 0 if res["verdict"] == "정합" else 1


def _cmd_convert(args) -> int:
    th = load_thresholds()
    lo, hi = th["conversion"]["asset_correlation_plausible"]
    tol = th["conversion"]["roundtrip_tolerance"]
    rt = roundtrip(args.pd, args.rho, args.z, tol)
    sg = phase_sign(rt["ttc"], rt["pit"], args.z)
    print(f'단일요인 변환 (rho={args.rho} · z={args.z})')
    print(f'  TTC {rt["ttc"]:.8f} → PIT {rt["pit"]:.8f} → TTC {rt["restored"]:.8f}')
    print(f'  왕복 차이 {rt["diff"]:+.3e} · 허용 {tol:.1e} · '
          f'{"PASS" if rt["passed"] else "FAIL"}')
    print(f'  국면 부호: {sg["expected"]} 기대 · {"PASS" if sg["passed"] else "FAIL"}')
    if not lo <= args.rho <= hi:
        print(f'  [주의] 자산상관 {args.rho} 가 타당성 대역 [{lo}, {hi}] 밖이다. '
              f'대역 안이라는 것이 CRE31 산식과 맞다는 뜻은 아니다')
    return 0 if (rt["passed"] and sg["passed"]) else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("demo", help="합성 표본으로 판정 시연")
    p.add_argument("--design", choices=DESIGNS, default="TTC")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--years", type=int, default=6)
    p.add_argument("--mislabel", action="store_true",
                   help="PIT 자료를 TTC 로 주장하게 만든다 (음성 통제)")
    p.set_defaults(func=_cmd_demo)

    p = sub.add_parser("analyse", help="패널 파일 판정")
    p.add_argument("--panel", required=True)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=_cmd_analyse)

    p = sub.add_parser("convert", help="TTC·PIT 단일요인 변환과 왕복 검증")
    p.add_argument("--pd", type=float, required=True, help="TTC PD")
    p.add_argument("--rho", type=float, required=True, help="자산상관")
    p.add_argument("--z", type=float, required=True, help="시스템적 요인 (침체일수록 음수)")
    p.set_defaults(func=_cmd_convert)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
