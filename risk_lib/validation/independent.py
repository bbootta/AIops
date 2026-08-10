"""상시 독립검증 위임 — 적합성검증 팀에이전트(3선)로의 요청·응답·게이트.

**자체검증과 독립검증은 다른 것이다.**

  자체검증 (2선)   risk-validator. 이 팀이 만든 산출을 이 팀이 점검한다.
                   정합성·규제기준·통계 체크. 만든 사람과 분리돼 있지만
                   **같은 코드·같은 가정**을 쓴다.
  독립검증 (3선)   적합성검증 팀에이전트 (branch `claude/validation-team-agent-Pw9F5`).
                   개발조직과 분리된 기준셋으로 **다시 계산**한다. 같은 가정을
                   공유하지 않는 것이 요점이다.

자체검증만으로 결재하면 "우리 코드가 우리 코드를 통과시켰다"가 된다. 그래서
매 작업마다 독립검증을 **요청**하고, 응답이 오기 전에는 결재 상신을 막는다.

게이트는 **fail-closed**다 — 응답이 없으면 통과가 아니라 대기다. 응답 파일이
없을 때 조용히 통과시키면 위임 자체가 형식이 된다.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from risk_lib.regulatory.fss_master import BANK_FORMS, risk_scope

# 독립검증 팀에이전트가 사는 곳. 요청 패키지에 박아 두어 수신자가 분명해진다.
VALIDATION_TEAM_BRANCH = "claude/validation-team-agent-Pw9F5"
VALIDATION_TEAM = "적합성검증 팀에이전트"

# 응답 파일 규약 — 요청 옆에 같은 run_id로 떨어진다.
RESPONSE_SUFFIX = ".response.json"
DEFAULT_DIR = Path("docs/independent_validation")

VERDICTS = ("적합", "경부적합", "중부적합")
STATUSES = ("요청됨", "응답대기", "적합", "부적합")

# 독립검증에 반드시 넘기는 재계산 대상. 여기 없는 수치는 3선이 다시 계산하지
# 않으므로, 새 headline을 만들면 여기에도 넣어야 한다.
RECALC_SCOPE: tuple[tuple[str, str, str], ...] = (
    ("rwa_final_total", "위험가중자산 합계", "CRE20.1 · RBC20.11"),
    # 구조화 두 항목은 분모의 30.6%다. 합계만 재계산 대상에 두면 3선이 "총액은
    # 맞다"까지만 말할 수 있고, 어느 방법(LTA/MBA · IRBA/ERBA/SA)을 어떻게
    # 채택했는지는 검증되지 않은 채로 남는다.
    ("rwa_fund", "집합투자증권 위험가중자산", "CRE60"),
    ("rwa_securitisation", "유동화 위험가중자산", "CRE40 · CRE41 · CRE44"),
    ("cet1_ratio", "보통주자본비율", "은행업감독규정 제26조"),
    ("total_ratio", "총자본비율", "은행업감독규정 제26조"),
    ("leverage_ratio", "레버리지비율", "LEV20.1"),
    # ECL은 두 값이 다르고 둘 다 공표된다 — TTC(시점추정)는 서식·충당금 기준이고
    # PIT(확률가중, forward-looking)는 이사회 팩·경영진 보고서의 KPI다. 하나만
    # 재계산 대상에 두면 3선이 본 적 없는 값이 결재로 넘어간다. IFRS 9 5.5.17이
    # 요구하는 확률가중 금액은 PIT 쪽이므로 특히 그렇다.
    ("ecl_total", "기대신용손실 합계 (TTC · 시점추정)", "IFRS 9 5.5"),
    ("ecl_weighted_total", "기대신용손실 합계 (PIT · 확률가중)", "IFRS 9 5.5.17"),
    ("lcr", "유동성커버리지비율", "LCR20.1"),
    ("nsfr", "순안정자금조달비율", "NSF20.1"),
    # IRRBB·생존기간은 이사회 팩 KPI·KRI·제출서식(BR-13·B2909-1)으로 나가면서도
    # 3선 재계산 대상에 없었다. 여기 없으면 다시 계산되지 않는다.
    # ΔEVE는 헤드라인 산출기준(행동조정)의 최악 시나리오이며, 계약기준 값은
    # `alm_irrbb_result`에 나란히 있어 3선이 두 기준을 대조할 수 있다.
    ("irrbb_worst_pct_tier1", "IRRBB 최대 ΔEVE 감소 / 기본자본",
     "SRP31.92 · 은행업감독규정 — 분모는 총자기자본이 아니라 Tier 1"),
    ("irrbb_delta_nii_parallel", "ΔNII 평행충격 (12개월, 마진 포함)",
     "BCBS d368 §132 · EBA GL 2022-14"),
    ("survival_days", "생존기간 (기관고유 스트레스, 시계 우측절단)",
     "BCBS d144 Principle 10 — 시계 안에서 소진되지 않으면 시계 길이로 절단된 "
     "값이다. 목표 생존기간에는 규정값이 없고 이사회 승인 대상이다(Principle 11)"),
    ("stress_trough_cet1", "심각 시나리오 CET1 저점", "SRP20"),
    ("reverse_critical_severity", "역스트레스 임계 심도", "SRP20"),
    ("reserve_shortfall", "대손준비금 소요액", "은행업감독규정 제29조 제2항"),
    # 국내기준 IRRBB — 공시서식 <표6>의 최대값이 결재·공시로 나가는 수치다.
    # `irrbb_worst_pct_tier1`이 같은 산출의 비율 뷰이지만 서식은 금액을 싣고
    # 부호 규약(감소액을 양수로)도 다르다. 3선이 서식 값을 직접 재계산하지
    # 않으면 부호 규약이 뒤집혀도 아무 데서도 걸리지 않는다.
    #
    # 여기에 "금리 EaR·금리 VaR·자기자본 대비 비율"을 넣지 않는다. 그 세
    # 수치는 [별표 9-1] 2014년 판의 지표이며 2019.11.29 개정으로 폐지됐다.
    # 산출하지 않는 값을 재계산 대상에 두면 3선이 매 회차 NULL을 확인하게 되고,
    # 폐지된 체계가 여전히 살아 있는 것처럼 보인다.
    ("kr_irrbb_table6_max_delta_eve",
     "[별표 9-1] <표6> 당기 최대 ΔEVE (감소액, 양수 표기)",
     "은행업감독업무시행세칙 [별표 9-1] 제22항 나 <표6> — 자체 조정 금지 양식"),
    ("kr_irrbb_table6_max_delta_nii",
     "[별표 9-1] <표6> 당기 최대 ΔNII (감소액, 양수 표기)",
     "은행업감독업무시행세칙 [별표 9-1] 제22항 나 <표6> · 제14항 목표관리기간 1년"),
    # LGD·CCF 실측검증 — 추정치가 실현치를 계속 밑돌면 IRB 자본이 과소산출된다.
    # 편의는 표본가중 평균이며, 관측중단 건수를 함께 넘겨 그 편의가 완결 표본만
    # 본 결과라는 사실을 3선이 판단할 수 있게 한다.
    ("lgd_backtest_bias",
     "LGD 실현−추정 편의 (세그먼트축 부도건수 가중)",
     "CRE36.83 사후검증 · BNK-CRM-010 — 표본은 완결 워크아웃이며 관측중단분은 "
     "제외된다(`lgd_backtest_n_censored`)"),
    ("lgd_backtest_n_censored", "LGD 표본의 관측중단 건수",
     "회수 진행 중인 부도건. 세지 않으면 실현 LGD가 낮게 나온다"),
    ("ccf_realised_mean",
     "CCF 실현치 (익스포저 유형·등급대 시설건수 가중 평균)",
     "CRE32.32 · CRE20.94 — 적용 CCF와의 차이가 EAD 과소산출로 직결된다"),
)


class IndependentValidationPending(Exception):
    """독립검증 응답 전 결재 상신 시도 — 게이트가 막는다."""


@dataclass(frozen=True)
class ValidationRequest:
    request_id: str
    run_id: str
    asof: str
    seed: int
    headline_digest: str
    portfolio_fingerprint: str
    requested_by: str
    requested_to: str
    branch: str
    reproduce: list[str]
    recalc_targets: list[dict]        # key, korean, value, citation
    self_validation: dict[str, int]   # PASS/WARN/FAIL 집계 — 3선의 출발점
    self_validation_failures: list[str]
    self_validation_warnings: list[dict]   # WARN 본문 (집계만으로는 못 읽는다)
    artefacts: list[str]
    known_assumptions: list[str]      # 3선이 반드시 도전해야 할 가정
    provenance: dict                  # 산출 근거 통계 — 문장이 아니라 수치로 넘긴다
    submission_digest: str            # 제출본(서식 전체) 지문 — 서식이 바뀌면 움직인다
    created_at: str

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(asdict(self), indent=indent, ensure_ascii=False)

    def write(self, directory: str | Path = DEFAULT_DIR) -> Path:
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        p = d / f"{self.run_id}.request.json"
        p.write_text(self.to_json(), encoding="utf-8")
        return p

    def response_path(self, directory: str | Path = DEFAULT_DIR) -> Path:
        return Path(directory) / f"{self.run_id}{RESPONSE_SUFFIX}"


@dataclass(frozen=True)
class Finding:
    finding_id: str
    severity: str                     # 적합 · 경부적합 · 중부적합
    target: str
    detail: str
    recomputed: float | None = None
    reported: float | None = None


@dataclass(frozen=True)
class ValidationResponse:
    request_id: str
    run_id: str
    verdict: str                      # 적합 · 경부적합 · 중부적합
    validated_by: str
    validated_at: str
    findings: list[Finding] = field(default_factory=list)
    recalc_matches: dict[str, bool] = field(default_factory=dict)

    @property
    def passes(self) -> bool:
        """기계 판정으로 무조건 통과하는 경우 — 판정 '적합' + 중부적합 0건.

        '경부적합'은 여기서 통과하지 않는다. 통과도 부적합도 아닌 세 번째
        상태이며 `conditional`이 True가 되어 게이트가 `조건부`로 넘긴다.
        조건부는 사람이 잔여위험·후속조건·이행기한을 기록해야 결재된다
        (독립검증 지적 F-207 — 이전 docstring은 '경부적합까지 조건부 통과'라고
        썼으나 구현에 그 경로가 없었다).
        """
        return self.verdict == "적합" and not any(
            f.severity == "중부적합" for f in self.findings)

    @property
    def conditional(self) -> bool:
        """조건부 승인 경로로 갈 수 있는가 — 판정 '경부적합' + 중부적합 0건."""
        return self.verdict == "경부적합" and not any(
            f.severity == "중부적합" for f in self.findings)

    @classmethod
    def read(cls, path: str | Path) -> "ValidationResponse":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        raw["findings"] = [Finding(**f) for f in raw.get("findings", [])]
        return cls(**raw)


@dataclass(frozen=True)
class ConditionalApproval:
    """경부적합 판정을 사람이 조건부로 인수한 기록.

    기계가 만들 수 없다 — 잔여위험을 누가 지고, 무엇을 언제까지 고치며, 그때까지
    어디에만 쓰는지는 결재 책임자의 판단이다.
    """
    approver: str                     # 인간 결재 책임자
    residual_risk: str                # 잔여위험 — 무엇을 안고 가는가
    conditions: tuple[str, ...]       # 후속조건 — 무엇을 고칠 것인가
    due_date: str                     # 이행기한 (YYYY-MM-DD)
    scope: str                        # 배포 범위 제한
    findings_accepted: tuple[str, ...] = ()   # 인수한 경부적합 finding_id

    def require_complete(self) -> None:
        missing = [n for n in ("approver", "residual_risk", "due_date", "scope")
                   if not str(getattr(self, n) or "").strip()]
        if not self.conditions:
            missing.append("conditions")
        if missing:
            raise IndependentValidationPending(
                f"조건부 승인 기록 미비 — 누락 항목: {', '.join(missing)}")


@dataclass(frozen=True)
class ValidationGate:
    status: str                       # 요청됨 · 응답대기 · 적합 · 조건부 · 부적합
    request: ValidationRequest
    response: ValidationResponse | None
    reason: str

    @property
    def approved(self) -> bool:
        return self.status == "적합"

    def require(self, conditional: ConditionalApproval | None = None) -> None:
        """결재 상신 직전에 호출한다. 통과하지 못하면 예외를 던진다.

        `조건부`(경부적합·중부적합 0건)일 때만 `conditional` 기록으로 통과할 수
        있다. 기록이 없거나 항목이 비면 통과하지 않는다 — fail-closed.
        """
        if self.approved:
            return
        if self.status == "조건부" and conditional is not None:
            conditional.require_complete()
            return
        raise IndependentValidationPending(
            f"독립검증 미완료 — {self.reason} "
            f"(요청 {self.request.request_id} → {VALIDATION_TEAM}/"
            f"{VALIDATION_TEAM_BRANCH})")


# ---------------------------------------------------------------- 요청 생성

def _digest(*parts: object) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode("utf-8"))
    return h.hexdigest()


# 요청 식별자의 지문에서 제외하는 필드. `request_id`는 지금 계산 중이고,
# `created_at`은 벽시계라 내용이 같아도 매번 달라진다.
_ID_EXCLUDED_FIELDS = frozenset({"request_id", "created_at"})


def request_identifier(request: "ValidationRequest") -> str:
    """요청 **전체**를 지문화한다 — 필드를 손으로 열거하지 않는다.

    지문 대상을 열거하면 열거에서 빠진 것이 조용히 stale 방어를 뚫는다. 지금까지
    두 번 그랬다: headline 수치만 넣었을 때는 공시 가정·자체검증 WARN이 뚫렸고
    (3차 시정), 여섯 항목을 열거했을 때는 `recalc_targets`의 `citation`이
    뚫렸다 — 규정 근거를 바꿔도 식별자가 불변이었다 (지적 F-301). 산출값이 안
    바뀌는 변경일수록 재검증이 필요한데 그때 정확히 뚫린다.

    그래서 대상은 `asdict(request)` 전부에서 위 두 필드만 뺀 것이다. 필드가
    늘어도 자동으로 덮인다 — F-102에서 세운 "목록을 손으로 적지 않는다"는 원칙을
    지문 설계에도 적용한 것이다.
    """
    payload = {k: v for k, v in asdict(request).items()
               if k not in _ID_EXCLUDED_FIELDS}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                           separators=(",", ":"), default=str)
    return "IVR-" + _digest(canonical)[:12].upper()


def _submission_digest(built_forms) -> str:
    """제출본 지문 — 서식 내용이 바뀌면 요청 식별자가 따라 움직여야 한다.

    요청 페이로드에 서식 내용이 하나도 없어서, 규정 인용 9건을 정정했는데도
    `request_id`가 불변이었다. 그 정정을 본 적 없는 이전 응답이 계속 승인으로
    통한다 — F-301과 같은 유형의 세 번째 반복이다.
    """
    from risk_lib.regulatory.forms import submission_digest
    return submission_digest(built_forms)


def _reserve_required(aq) -> float:
    """대손준비금 소요액 — **합계 기준**이 규정 금액이다 (지적 F-601).

    건별 미달액을 합산하면 초과적립분이 상계되지 못해 항상 과대해진다.
    """
    from risk_lib.datamodel.materialize_detail import reserve_requirement
    return float(reserve_requirement(aq)["required"])


def _irrbb_delta_nii(result) -> float | None:
    """평행충격 ΔNII 중 최악(최소). 원장이 비면 지어내지 않고 None."""
    nii = result.alm.get("nii") if isinstance(result.alm, dict) else None
    frame = getattr(nii, "result", None)
    if frame is None or not len(frame):
        return None
    return float(frame["delta_nii"].min())


def _survival_days(result) -> float | None:
    """기관고유 스트레스 생존일수 — **시계에서 우측절단**된 값.

    시계 안에서 반대매매가능자산이 소진되지 않으면 소진일이 없다. 그때 값을
    비우면 "산출하지 않았다"와 구분되지 않으므로 시계 길이를 적고, 그것이
    절단값이라는 사실을 `RECALC_SCOPE`의 근거란에 적는다. 시계는 원장
    (`alm_survival_path.day`)에서 읽는다 — 여기 숫자를 적으면 파이프라인이
    시계를 바꿔도 이 값이 따라오지 않는다.

    시나리오 자체가 산출되지 않았으면 None이다. 그 경우는 헤드라인이 비었다는
    뜻이고, 조용히 넘어가서는 안 된다.
    """
    sv = result.alm.get("survival") if isinstance(result.alm, dict) else None
    days = getattr(sv, "survival_days", None)
    if not days or "기관고유" not in days:
        return None
    breach = days["기관고유"]
    if breach is not None:
        return float(breach)
    path = sv.path
    hit = path[path["scenario"] == "기관고유"]
    return float(hit["day"].max()) if len(hit) else None


def _headline(result, tables: dict[str, pd.DataFrame] | None
              ) -> dict[str, float | None]:
    t = tables or {}
    sev = result.stress_path_trough
    sev = sev[sev["scenario"] == "severely_adverse"]
    aq = t.get("rdm_asset_quality")
    return {
        "rwa_final_total": float(result.rwa["final_total"]),
        "rwa_fund": float(result.rwa.get("fund", 0.0)),
        "rwa_securitisation": float(result.rwa.get("securitisation", 0.0)),
        "cet1_ratio": float(result.bis.cet1_ratio),
        "total_ratio": float(result.bis.total_ratio),
        "leverage_ratio": float(result.leverage.leverage_ratio),
        "ecl_total": float(result.ecl["total"]),
        "ecl_weighted_total": float(
            getattr(getattr(result, "macro_ecl", None), "weighted_total", 0.0)),
        "lcr": float(result.alm["lcr"].lcr),
        "nsfr": float(result.alm["nsfr"].nsfr),
        "irrbb_worst_pct_tier1": float(result.alm["irrbb"].worst_pct_tier1),
        "irrbb_delta_nii_parallel": _irrbb_delta_nii(result),
        "survival_days": _survival_days(result),
        "stress_trough_cet1": (float(sev["trough_cet1"].iloc[0])
                               if len(sev) else float("nan")),
        "reverse_critical_severity": float(
            result.reverse_stress.critical_severity),
        "reserve_shortfall": (_reserve_required(aq)
                              if aq is not None and len(aq) else 0.0),
        "kr_irrbb_table6_max_delta_eve": _table6_max(t, "ΔEVE"),
        "kr_irrbb_table6_max_delta_nii": _table6_max(t, "ΔNII"),
        "lgd_backtest_bias": _lgd_bias(t),
        "lgd_backtest_n_censored": _lgd_censored(t),
        "ccf_realised_mean": _ccf_realised(t),
    }


def _table6_max(tables: dict, measure: str) -> float | None:
    """<표6> 당기 최대값 행. 서식이 없거나 칸이 비면 지어내지 않고 None."""
    t6 = tables.get("disc_irrbb_table6")
    if t6 is None or not len(t6):
        return None
    hit = t6[(t6["row_code"] == "최대값") & (t6["measure"] == measure)
             & (t6["period"] == "당기")]
    if not len(hit) or pd.isna(hit["value"].iloc[0]):
        return None
    return float(hit["value"].iloc[0])


def _lgd_bias(tables: dict) -> float | None:
    """LGD 편의 — 세그먼트축 행만 쓰고 부도건수로 가중한다.

    세 축(등급·담보유형·세그먼트)이 같은 부도를 각각 다시 세므로 축을 섞어
    평균하면 같은 건이 세 번 들어간다. 세그먼트축 하나만 쓴다.
    """
    lgd = tables.get("crm_lgd_backtest")
    if lgd is None or not len(lgd):
        return None
    seg = lgd[(lgd["segment_axis"] == "segment") & lgd["bias"].notna()]
    w = seg["n_defaults"].astype(float)
    if not len(seg) or w.sum() <= 0:
        return None
    return float((seg["bias"].astype(float) * w).sum() / w.sum())


def _lgd_censored(tables: dict) -> float | None:
    """세그먼트축 관측중단 건수 합계."""
    lgd = tables.get("crm_lgd_backtest")
    if lgd is None or not len(lgd):
        return None
    seg = lgd[lgd["segment_axis"] == "segment"]
    return float(seg["n_censored"].fillna(0).sum()) if len(seg) else None


def _ccf_realised(tables: dict) -> float | None:
    """CCF 실현치 — 시설건수 가중 평균."""
    ccf = tables.get("crm_ccf_backtest")
    if ccf is None or not len(ccf):
        return None
    hit = ccf[ccf["ccf_realized_mean"].notna()]
    w = hit["n_facilities"].astype(float)
    if not len(hit) or w.sum() <= 0:
        return None
    return float((hit["ccf_realized_mean"].astype(float) * w).sum() / w.sum())


# 3선이 반드시 도전해야 하는 가정. 우리가 스스로 알고 있는 약한 고리를 숨기지
# 않고 넘기는 것이 독립검증의 출발점이다.
#
# **여기에 기계로 산출되는 수치를 적지 않는다.** 라인 수·실측 비중을 손으로 적어
# 두었더니 제출본(asof 2026-06-30)이 아니라 시험 고정일(2026-06-11) 실행의 값이
# 박혀 있었다 — 지적 F-501, 문서 수치가 코드 사실과 어긋난 네 번째 재발이다.
# 상수에는 숫자 없는 문장만 두고, 산출되는 값은 `build_request`가 실행 시점에
# 생성해 뒤에 덧붙인다 (`provenance_sentence`).
#
# 레지스트리 건수도 같다 — 마스터에서 센다. 282·117·165를 손으로 적어 두면
# `fss_master.BANK_FORMS`에 서식이 하나만 늘어도 조용히 낡고, 낡은 값은 바로
# 옆의 생성 문장("산출한 서식 N건")과 어긋나 3선이 어느 쪽을 믿을지 정하게
# 된다. 세는 방법이 있는 수치는 세서 쓴다.
_N_SUBMITTABLE = sum(1 for f in BANK_FORMS if f.applicable)   # 제출대상
_N_RISK_SCOPE = len(risk_scope())                             # 그중 리스크 소관
_N_OUT_OF_SCOPE = _N_SUBMITTABLE - _N_RISK_SCOPE              # 나머지

KNOWN_ASSUMPTIONS: tuple[str, ...] = (
    "자산건전성 분류는 연체일수 대용 규칙 — 감독규정 제27조는 채무상환능력 "
    "평가를 함께 요구한다 (risk_lib.datamodel.materialize_detail).",
    "파이프라인은 CRM 조정을 RWA에 반영하지 않는다 — 담보 배분은 정상화 "
    "후보로만 제시된다 (rwa_crm_allocation).",
    "시장리스크는 MAR40 간편표준방법이며 SBM 재산출이 아니다. 스트레스 시장 "
    "RWA는 위험계수 배수 근사다 (risk_lib.stress.multi_axis).",
    "트레이딩·스프레드 손익은 듀레이션 근사(3.0y/4.0y)로 산출한다.",
    "위기상황 충격 축 크기는 내부 관리값 — 기관 승인 시나리오로 교체 전제 "
    "(risk_lib.stress.axes).",
    "대주주 지정 원장이 없어 대주주 신용공여 사용액을 0으로 두었다 "
    "(risk_lib.prudential.ownership).",
    "업무보고서 서식번호는 내부 배정 코드 — 금감원 배포본과 대조 전이다 "
    "(risk_lib.regulatory.form_ids).",
    "합성 대차대조표에 통화 구분이 없어 외화 비중을 자산·부채 동일하게 가정했다.",
    # ---- 독립검증 IVR-E6BEA5DA0D5F 지적으로 추가된 항목.
    # 공시 기준이 방향에 따라 비대칭이면(보수적인 것만 공시) 공시가 아니다.
    "자본은 실제 원장이 아니라 **합성값**이다 — 고정 발행자본(자본금·AT1·T2 "
    "발행잔액 합계)에 이익잉여금(연간이익 × 4년)을 더한다. 뒤에 나오는 "
    "'규모와 무관한 축'은 이 중 기본자본분(자본금 + AT1)만 가리키므로 금액이 "
    "다르다 — 같은 용어의 두 범위를 구분해 읽어야 한다 (지적 F-603). RWA에서는 파생되지 않으므로 자본비율과 "
    "레버리지비율이 둘 다 반응한다. 실제 원장은 run_pipeline(capital_ledger=...)로 "
    "주입한다 (risk_lib.capital.bis.synthesise_capital · 지적 F-001 · F-101).",
    # ---- 독립검증 IVR-573F73DBBF35(3차) 지적으로 추가·정정된 항목.
    "합성 자본의 이익잉여금은 **익스포저의 함수다** — data_gen이 "
    "revenue = ead × spread로 수익을 만들므로 연간이익이 EAD를 따라간다"
    "(이익/EAD 변동계수 3.8%). CET1의 약 54%가 이 규모 비례분이며, 규모와 "
    "무관한 축은 고정 발행자본 6,400억뿐이다 (지적 F-201).",
    "합성기의 규모 독립성은 자산이 커지면 희석된다 — 레버리지비율이 "
    "4×margin/1.01로 수렴한다. 실측: EAD 10.4조 0.1171 → 104조 0.0625 → "
    "520조 0.0576. 합성기는 시험용이며 규모 민감도가 필요한 산출에는 실제 자본 "
    "원장을 주입해야 한다 (지적 F-202).",
    # ---- 금감원 업무보고서 93건 신설로 추가된 항목.
    "업무보고서 서식번호는 금감원 FINES 마스터와 대조해 배정했다. 이전 내부 코드 "
    "16건이 실재 서식과 한 글자 차이로 전혀 다른 서식을 가리키고 있었다 "
    "(risk_lib.regulatory.fss_master · form_ids).",
    "리스크 소관 제출대상 117건 중 8건(스트레스테스트·ICAAP·위기상황분석·"
    "적기시정조치·신용위험경감·운영손실·원화유동성비율·경영실태평가)은 대응하는 "
    "금감원 서식이 없는 **내부 관리보고**이며 제출 대상이 아니다. 7건(외은 "
    "국내지점·특수은행 근거법 전용)은 국내 일반은행 제출 대상이 아니다.",
    "FINES 가계·업무규제 서식이 요구하는 항목 중 원장이 없는 것은 기준일 고정 "
    "시드로 **파생**했다 — 지역·자금용도·상환방식·신규취급 여부·여신종별·"
    "채권재조정·변동표 기초잔액·자회사 명세·금융채권 발행이력·타은행주식·"
    "대출모집 위탁사·임직원 소액대출·일별 LCR 경로. 파생값의 **합계는 산출값에 "
    "앵커**했으므로 명세 대사는 난수끼리의 자기충족이 아니지만, 개별 배분은 "
    "실측이 아니다 (risk_lib.regulatory.forms_fss_*_data).",
    # ---- 리스크 소관 밖 서식 163건 신설로 추가된 항목.
    f"금감원 제출대상 서식 {_N_SUBMITTABLE}건을 전건 산출한다 "
    f"(risk_lib.regulatory.fss_master에서 센 값). 이 중 리스크 소관은 "
    f"{_N_RISK_SCOPE}건이고 나머지 {_N_OUT_OF_SCOPE}건(신용카드·해외점포·"
    "재무제표 상세·수익성·일반현황·휴면금융재산 등)은 리스크 산출과 멀어 "
    "**파생 의존이 높다**. 근거별 라인 수·비중은 이 목록 끝에 실행 시점 "
    "산출값으로 덧붙는다 (요청 패키지 `provenance` 필드).",
    "'혼합'은 합계를 산출값에 앵커하고 내부 배분만 파생한 라인이다 — 명세 대사가 "
    "난수끼리의 자기충족은 아니지만 개별 배분은 실측이 아니다. 실측으로 세면 "
    "과장이므로 별도 구분한다.",
    "신용카드 가맹점수수료율(B2824)은 분자가 연간수익·분모가 당월매출인 "
    "**혼합기준**이라 실제보다 12배 크다. 합성 카드수익이 회전율 가정의 매출 "
    "규모를 뒷받침하지 못하는 구조적 한계이며, 기간을 맞추면 우대수수료율 "
    "최저값에도 못 미쳐 협상요율이 음수가 된다. 서식에 공시했으나 해소되지 "
    "않았다 (risk_lib.regulatory.forms_fss_card).",
    "CVA 소요자기자본을 RWA로 12.5배 환산한다 (MAR50.2 · RBC20.6). 이전에는 "
    "K_BA를 RWA에 그대로 합산해 CVA가 12.5배 과소계상되고 있었다 — 서식 저작 중 "
    "적대적 검토에서 드러났다 (risk_lib.ccr.cva_rwa · 총 RWA +0.056%).",
    # 회차별 값을 손으로 나열했더니 CVA 12.5배 정정 때 이동한 값에서 계열이
    # 멈춰 낡았다 (지적 F-603). 값은 요청서 recalc_targets가 정본이고 git
    # 이력이 계열을 보존하므로, 여기에는 **성질만** 적는다.
    "역스트레스 임계 심도는 자본 수준에 민감해 자본 가정이 바뀌면 크게 움직인다 "
    "— 회차별 실측 진폭이 0.14에 이른다. 절대 수준보다 동일 자본 가정 하의 "
    "비교로 읽어야 하며, 회차별 값은 요청서 recalc_targets의 git 이력이 정본이다 "
    "(3선 권고 · 지적 F-603).",
    "레버리지 부외항목에 CCF 하한 10%를 일률 적용한다 — 약정 유형별 "
    "CCF(20/40/50/100%) 구분이 없어 가장 관대한 계수를 쓴 것이다 (지적 F-004).",
    "Stage 1 커버리지가 8.1%로 12개월 기대손실치고 높다. 합성 데이터의 PD "
    "스케일에서 비롯된 것이며 실무 수치로 읽으면 오해를 부른다 (지적 F-005).",
    "표준방법 RWA가 내부모형의 78% 수준이라 산출하한이 현 구성에서 구속되지 "
    "않는다. 통상 표준방법이 더 보수적인 점과 배치된다 (지적 F-006).",
)


def build_request(result, portfolio: pd.DataFrame,
                  tables: dict[str, pd.DataFrame] | None = None, *,
                  manifest=None, requested_by: str = "리스크관리 팀에이전트",
                  artefacts: list[str] | None = None,
                  extra_checks: list | None = None,
                  built_forms: list | None = None) -> ValidationRequest:
    """독립검증 요청 패키지 — 3선이 **다시 계산**할 수 있는 최소 집합."""
    asof = result.meta.get("asof", "1970-01-01")
    seed = int(result.meta.get("seed", 42))
    run_id = f"RUN-{asof.replace('-', '')}-{seed}"

    head = _headline(result, tables)
    digest = (getattr(manifest, "headline_digest", "") or
              _digest(sorted(head.items()))[:32])
    fingerprint = ""
    if manifest is not None:
        fingerprint = str(getattr(manifest, "portfolio", {}).get("sha256", ""))
    if not fingerprint:
        fingerprint = _digest(len(portfolio), tuple(portfolio.columns))[:32]

    # 자체검증 WARN은 집계만 넘기면 결재선이 내용을 읽지 못한다 — 본문을 싣는다
    # (독립검증 F-106 권고). FAIL이 0이어도 WARN이 규제 미달을 담을 수 있다.
    checks = tables.get("val_check") if tables else None
    if checks is not None and len(checks):
        summary = {k: int(v) for k, v in
                   checks["status"].value_counts().items()}
        failures = list(checks.loc[checks["status"] == "FAIL", "check_name"])
        warnings = [{"check": str(r["check_name"]), "detail": str(r["detail"])}
                    for _, r in checks[checks["status"] == "WARN"].iterrows()]
    else:
        summary = dict(result.validation.summary())
        failures = [c.name for c in result.validation.checks
                    if c.status == "FAIL"]
        warnings = [{"check": c.name, "detail": str(c.detail)}
                    for c in result.validation.checks if c.status == "WARN"]

    # 조립 시점에만 가능한 체크(문서 생성 구간 대조 등)는 파이프라인 산출에
    # 들어 있지 않다. 공유 상태를 변형하는 대신 여기서 합산한다 — 3선에 넘기는
    # 자체검증 집계는 실제로 돌린 전부여야 한다.
    for c in extra_checks or []:
        summary[c.status] = summary.get(c.status, 0) + 1
        if c.status == "FAIL":
            failures.append(c.name)
        elif c.status == "WARN":
            warnings.append({"check": c.name, "detail": str(c.detail)})

    # 산출 근거 통계는 **생성**한다 (지적 F-501). 3선은 구조화된 `provenance`를
    # 바로 대조하고, 같은 값에서 만든 문장이 가정 목록 끝에 붙는다 — 문장과
    # 필드가 어긋날 자리가 없다. 표가 없으면 빈 dict로 남겨 "미첨부"가 보이게
    # 한다. 0으로 채우면 대조를 통과한 것처럼 보인다.
    from risk_lib.regulatory.provenance import (
        provenance_sentence, provenance_stats_from_lines,
    )
    lines = tables.get("reg_form_line") if tables else None
    provenance = (provenance_stats_from_lines(lines)
                  if lines is not None and len(lines) else {})
    assumptions = list(KNOWN_ASSUMPTIONS)
    # 구조화 익스포저의 분모 통합 — 이번 회차의 가장 큰 변경이다. 총액만
    # 바뀐 것이 아니라 **모집단이 넓어졌다**. 겹치지 않는다는 주장이 이 회차의
    # 핵심 가정이므로 3선이 먼저 도전할 수 있도록 정면에 적는다.
    _str_total = float(result.rwa.get("structured_total", 0.0))
    if _str_total:
        assumptions.append(
            f"구조화 익스포저(집합투자증권 CRE60 · 유동화 CRE40) "
            f"{_str_total:,.0f}원을 위험가중자산 분모에 **신규 통합**했다 — "
            f"직전 회차까지는 원장에서 산출만 하고 분모에 넣지 않았다. "
            f"이중계상이 아니라는 근거는 두 원장이 은행계정 익스포저와 "
            f"모집단이 겹치지 않는다는 것이며(자산군 5종에 펀드·트렌치 없음), "
            f"이 주장 자체가 3선의 1차 도전 대상이다. output floor 표준 총계는 "
            f"SEC-IRBA를 제외한 계층(ERBA→SA)으로 세웠고, 레버리지 익스포저에도 "
            f"장부 익스포저를 함께 넣었다(LEV20.1). 결과로 총자본비율이 완충자본 "
            f"포함 요구치를 밑돈다 — 산출 결함이 아니라 산출 결과이며 "
            f"`bis_buffer_requirement` WARN 으로 남아 있다. 위기상황분석은 "
            f"구조화 RWA를 고정한다(등급 하락 시 ERBA 위험가중치 상승 미반영) — "
            f"`STRESS_MACRO` 모형의 알려진 한계로 등록했다.")
    if provenance:
        assumptions.append(provenance_sentence(provenance))
    # 검증의 세기도 생성한다 — 손으로 적은 수치는 이미 두 번 낡았다
    # (지적 F-501 · F-603).
    if built_forms:
        from risk_lib.regulatory.provenance import (
            check_strength, check_strength_sentence,
        )
        strength = check_strength(built_forms)
        assumptions.append(check_strength_sentence(strength))
        from risk_lib.regulatory.cross_form import coverage_sentence
        assumptions.append(coverage_sentence(built_forms))
        # 통제의 **한계**도 생성해 싣는다. docstring에 "요청서에 공시한다"고
        # 적어 놓고 실제로는 싣지 않아, 한계를 아는 사람과 모르는 사람이
        # 갈렸다 (지적 F-B01). 코드를 읽는 사람만 보는 곳에 적으면 공시가 아니다.
        from risk_lib.regulatory.structure import (
            coverage_sentence as _structure_coverage_sentence,
        )
        assumptions.append(_structure_coverage_sentence(built_forms))
        # 통제 6종 중 2종의 한계가 요청서에 없었다 — F-B01과 같은 상태였고
        # 3선이 지적하기 전에 자체 점검으로 찾았다. 한 건을 고칠 때 같은 유형이
        # 어디에 더 있는지 묻지 않으면 다음 회차에 또 나온다 (ADV-PROC-05).
        from risk_lib.regulatory.citations import (
            coverage_sentence as _citation_coverage_sentence,
        )
        from risk_lib.validation.doc_figures import (
            coverage_sentence as _doc_coverage_sentence,
        )
        assumptions.append(_citation_coverage_sentence(built_forms))
        # 요청 지문이 덮지 **않는** 것도 공시한다. F-D01 시정은 전부 산출물 Pack
        # 안에서 일어났는데 지문이 움직이지 않아, 그 결함을 지적한 응답이 여전히
        # 유효한 것처럼 게이트가 통과시킨다. 12차에 3선에 물은 "다음 계층" 질문이
        # 실현된 것이며, 설계 답을 받기 전에 성급히 고치면 F-C01 같은 상호작용을
        # 또 만든다 — 그래서 이번 회차는 **공시하고 묻는다**.
        assumptions.append(
            f"요청 지문은 산출값·서식·가정·자체검증을 덮지만 **산출물 Pack을 "
            f"덮지 않는다** — `artefacts` 필드가 비어 있다. Pack 안에서만 일어난 "
            f"변경(파일 신설·삭제·배선)은 `request_id`를 움직이지 않으므로, 그 "
            f"변경을 본 적 없는 이전 응답이 승인으로 통한다. 실제로 F-D01 시정이 "
            f"그랬다. 지문 대상을 넓히면 Pack이 요청서를 담고 요청서가 Pack "
            f"인벤토리를 담는 순환이 생기므로(F-C01 유형) 설계 판단이 필요하며, "
            f"3선에 도전 지점으로 올린다 (지적 F-301 · F-C01 · F-D01)."
        )
        assumptions.append(_doc_coverage_sentence(built_forms, asof))

    request = ValidationRequest(
        request_id="",                # 아래에서 요청 전체를 지문화해 채운다
        run_id=run_id, asof=asof, seed=seed,
        headline_digest=digest, portfolio_fingerprint=fingerprint,
        requested_by=requested_by, requested_to=VALIDATION_TEAM,
        branch=VALIDATION_TEAM_BRANCH,
        reproduce=[
            f"generate_portfolio(seed={seed})",
            f"run_pipeline(portfolio, seed={seed}, asof='{asof}')",
            "build_studio(result, portfolio)   # 정규 테이블 전체",
        ],
        recalc_targets=[
            {"key": k, "korean": ko, "value": head.get(k), "citation": cite}
            for k, ko, cite in RECALC_SCOPE
        ],
        self_validation=summary,
        self_validation_failures=failures,
        self_validation_warnings=warnings,
        artefacts=artefacts or [],
        known_assumptions=assumptions,
        submission_digest=(
            _submission_digest(built_forms) if built_forms else ""),
        provenance=provenance,
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    return replace(request, request_id=request_identifier(request))


# ---------------------------------------------------------------- 게이트

def check_gate(request: ValidationRequest,
               directory: str | Path = DEFAULT_DIR) -> ValidationGate:
    """응답 파일을 찾아 게이트 상태를 판정한다 (fail-closed)."""
    p = request.response_path(directory)
    if not p.exists():
        return ValidationGate("응답대기", request, None,
                              f"{VALIDATION_TEAM} 응답 없음 ({p})")
    try:
        resp = ValidationResponse.read(p)
    except Exception as exc:                      # noqa: BLE001
        return ValidationGate("부적합", request, None,
                              f"응답 파일을 읽을 수 없음: {exc}")
    if resp.run_id != request.run_id:
        # 다른 실행의 응답을 이 실행의 승인으로 쓰면 게이트가 무의미해진다.
        return ValidationGate("부적합", request, resp,
                              f"응답 run_id 불일치 ({resp.run_id} ≠ {request.run_id})")
    if resp.request_id != request.request_id:
        return ValidationGate("부적합", request, resp,
                              "응답 request_id 불일치 — 재요청 필요")
    mismatched = [k for k, ok in resp.recalc_matches.items() if not ok]
    if mismatched:
        # 재계산이 어긋나면 판정과 무관하게 부적합이다.
        return ValidationGate("부적합", request, resp,
                              f"독립 재계산 불일치: {', '.join(mismatched)}")
    if resp.passes:
        return ValidationGate("적합", request, resp, "독립 재계산 일치 · 판정 적합")
    if resp.conditional:
        minor = [f.finding_id for f in resp.findings if f.severity == "경부적합"]
        return ValidationGate(
            "조건부", request, resp,
            f"판정 경부적합 · 중부적합 0건 · 경부적합 {len(minor)}건"
            + (f" ({', '.join(minor)})" if minor else "")
            + " — 잔여위험·후속조건·이행기한을 기록해야 결재 가능")
    bad = [f.target for f in resp.findings if f.severity == "중부적합"]
    return ValidationGate("부적합", request, resp,
                          f"판정 {resp.verdict}"
                          + (f" · 중부적합 {', '.join(bad)}" if bad else ""))


def request_frames(request: ValidationRequest, gate: ValidationGate
                   ) -> dict[str, pd.DataFrame]:
    """PRD-VAL 정규 테이블로 실체화한다."""
    req = pd.DataFrame([{
        "request_id": request.request_id, "run_id": request.run_id,
        "asof": request.asof, "requested_by": request.requested_by,
        "requested_to": request.requested_to, "branch": request.branch,
        "headline_digest": request.headline_digest,
        "n_recalc_targets": len(request.recalc_targets),
        "n_self_fail": len(request.self_validation_failures),
        "n_self_warn": len(request.self_validation_warnings),
        "status": gate.status, "reason": gate.reason,
    }])
    rows = []
    resp = gate.response
    for t in request.recalc_targets:
        key = str(t["key"])
        matched = (resp.recalc_matches.get(key) if resp else None)
        rows.append({
            "request_id": request.request_id, "target": key,
            "korean": str(t["korean"]),
            "reported": float(t["value"]) if t["value"] is not None else None,
            "recomputed": None, "matched": matched,
            "citation": str(t["citation"]),
        })
    if resp:
        by_target = {f.target: f for f in resp.findings}
        for r in rows:
            f = by_target.get(r["target"])
            if f is not None and f.recomputed is not None:
                r["recomputed"] = float(f.recomputed)
    tgt = pd.DataFrame(rows)
    # 응답 전에는 전부 None이라 object dtype이 된다 — 스펙 dtype을 지켜야
    # "위반 0건일 때만 검증이 실패하는" 형태의 오류가 생기지 않는다.
    tgt["recomputed"] = pd.to_numeric(tgt["recomputed"], errors="coerce"
                                      ).astype("float64")
    tgt["matched"] = tgt["matched"].astype("boolean")
    return {"val_independent_request": req, "val_independent_target": tgt}
