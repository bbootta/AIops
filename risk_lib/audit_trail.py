"""Audit trail & data lineage ledger — Top-IB grade.

Every published number must trace back to:
  - source data (input file path / row count / SHA-256 of canonical bytes)
  - code (file, function, git commit, line range)
  - parameters (regulatory constants, scenario assumptions, seed)
  - reviewer/approver (sign-off chain — owner / 1st line / 2nd line / risk)
  - regulatory citation(s)

This ledger is what auditors / FSS examiners ask for first when they
challenge a number. Without it, even correct numbers fail the review.

Reference: BCBS 239 (Risk data aggregation and reporting), SR 11-7 model
documentation requirements, EBA SREP IT supervision.
"""

from __future__ import annotations

import hashlib
import warnings
from dataclasses import dataclass, field, asdict
from typing import Any


# ----- single-figure ledger ------------------------------------------------

@dataclass
class LedgerEntry:
    """One reported figure's full provenance."""
    figure_id: str              # e.g. "rwa.final_total"
    label: str                  # human-readable label
    value: Any                  # the reported number
    unit: str = ""              # KRW / % / ratio / count
    # source data
    source_data: str = ""       # input file or table
    source_rows: int = 0
    source_sha256: str = ""
    # code provenance
    code_module: str = ""       # risk_lib.X.Y
    code_function: str = ""
    git_commit: str = ""
    # parameters
    parameters: dict[str, Any] = field(default_factory=dict)
    # regulatory citation
    citation: str = ""
    # approval chain
    owner: str = ""             # 1st line — desk / business
    reviewer: str = ""          # 2nd line — risk
    approver: str = ""          # CRO / Committee
    # 결재일시. 결재 원장에서 읽은 값만 들어간다. 없으면 None이고
    # approval_evidence_status가 '미확인'이 된다. 벽시계로 채우면 없는 결재를
    # 있다고 적는 것이므로 채우지 않는다.
    approval_dt: str | None = None
    approval_evidence_status: str = "미확인"
    # 산출 기준일. 다른 원장의 asof 규약과 같다. 예전에는 여기에 벽시계
    # 생성시각이 들어가, 같은 인자로 두 번 만든 감사원장이 서로 달랐다.
    asof: str = ""
    schema_version: str = "1.0"


@dataclass
class AuditLedger:
    """Append-only ledger of LedgerEntry records."""
    entries: list[LedgerEntry] = field(default_factory=list)

    def add(self, entry: LedgerEntry) -> None:
        self.entries.append(entry)

    def to_frame(self):
        import pandas as pd
        return pd.DataFrame([asdict(e) for e in self.entries])

    def export_json(self, path) -> str:
        import json
        from pathlib import Path
        Path(path).write_text(
            json.dumps([asdict(e) for e in self.entries],
                       indent=2, ensure_ascii=False, default=str),
            encoding="utf-8",
        )
        return str(Path(path).resolve())


# ----- automatic ledger from a PipelineResult ------------------------------

def build_ledger_from_result(result, *, git_commit: str = "",
                              owner: str = "산출 담당자",
                              reviewer: str = "리스크 2선",
                              approver: str = "CRO",
                              asof: str | None = None,
                              approval_dt: str | None = None) -> AuditLedger:
    """Walk through standard headline figures and create ledger entries.

    `asof`를 넘기지 않으면 `result.meta['asof']`를 쓴다. 같은 인자로 두 번
    만들면 같은 원장이 나와야 보관본을 재실행으로 대조할 수 있다.

    `approval_dt`는 결재 원장에서 읽은 값만 넣는다. 넘기지 않으면 None이며
    `approval_evidence_status='미확인'`으로 남는다.
    """
    led = AuditLedger()
    if asof is None:
        asof = str(getattr(result, "meta", {}).get("asof", "") or "")
    if not asof:
        warnings.warn(
            "감사원장에 산출 기준일이 없다. result.meta['asof']가 비어 있고 "
            "asof 인자도 넘어오지 않았다. asof를 빈 값으로 남긴다",
            stacklevel=2)

    common = dict(
        git_commit=git_commit,
        owner=owner, reviewer=reviewer, approver=approver,
        approval_dt=approval_dt,
        approval_evidence_status="결재원장" if approval_dt else "미확인",
        asof=asof,
    )

    # RWA
    led.add(LedgerEntry(
        figure_id="rwa.sa", label="신용 RWA (SA)",
        value=float(result.rwa["sa"]), unit="KRW",
        source_data="portfolio sa_book", source_rows=0,
        code_module="risk_lib.capital.rwa_sa", code_function="compute_rwa_sa",
        parameters={"sa_rw_tables": "CRE20"},
        citation="Basel III CRE20 / 감독세칙 별표", **common))
    led.add(LedgerEntry(
        figure_id="rwa.irb", label="신용 RWA (IRB)",
        value=float(result.rwa["irb"]), unit="KRW",
        source_data="portfolio irb_book",
        code_module="risk_lib.capital.rwa_irb", code_function="compute_rwa_irb",
        parameters={"confidence": 0.999, "pd_floor": 0.0003,
                    "maturity_cap": 5.0},
        citation="Basel III CRE31.5 (Vasicek ASRF) + CRE32 PD/LGD floors",
        **common))
    led.add(LedgerEntry(
        figure_id="rwa.market", label="시장리스크 RWA",
        value=float(result.rwa["market"]), unit="KRW",
        code_module="risk_lib.capital.market_risk",
        code_function="compute_market_risk_rwa",
        parameters={"method": "simplified standardised"},
        citation="Basel III MAR40 (간편표준방법)", **common))
    led.add(LedgerEntry(
        figure_id="rwa.op", label="운영리스크 RWA",
        value=float(result.rwa["op"]), unit="KRW",
        code_module="risk_lib.capital.op_risk", code_function="compute_op_risk_rwa",
        parameters={"method": "SMA (BIC x ILM)"},
        citation="Basel III OPE25 (신표준방법)", **common))
    led.add(LedgerEntry(
        figure_id="rwa.standardised_total", label="전부표준방법 RWA (floor 산정용)",
        value=float(result.rwa["standardised_total"]), unit="KRW",
        code_module="risk_lib.capital.output_floor", code_function="apply_output_floor",
        citation="Basel III RBC30 (floor 비교 기준)", **common))
    led.add(LedgerEntry(
        figure_id="rwa.final_total", label="최종 RWA (output floor 적용 후)",
        value=float(result.rwa["final_total"]), unit="KRW",
        code_module="risk_lib.capital.output_floor", code_function="apply_output_floor",
        parameters={"floor": 0.725},
        citation="Basel III RBC30.1 (output floor 72.5%)",
        **common))

    # BIS
    bis = result.bis
    for key, label in (("cet1","CET1 비율"), ("tier1","Tier1 비율"),
                       ("total","총자본 비율")):
        led.add(LedgerEntry(
            figure_id=f"bis.{key}", label=label,
            value=float(getattr(bis, f"{key}_ratio")), unit="ratio",
            code_module="risk_lib.capital.bis", code_function="compute_bis_ratios",
            parameters={"required": bis.required.get(key)},
            citation="Basel III CRE10.4 / 감독세칙 자본적정성",
            **common))

    # Leverage
    lev = result.leverage
    led.add(LedgerEntry(
        figure_id="leverage", label="레버리지 비율",
        value=float(lev.leverage_ratio), unit="ratio",
        code_module="risk_lib.capital.leverage", code_function="compute_leverage_ratio",
        parameters={"required": 0.03},
        citation="Basel III LEV10.6", **common))

    # ECL
    led.add(LedgerEntry(
        figure_id="ecl.ttc_total", label="총 ECL (TTC)",
        value=float(result.ecl["total"]), unit="KRW",
        code_module="risk_lib.provisioning.ecl", code_function="compute_ecl",
        citation="IFRS 9 5.5.3 (12M) + 5.5.5 (lifetime)", **common))
    led.add(LedgerEntry(
        figure_id="ecl.pit_weighted", label="확률가중 PIT ECL",
        value=float(result.macro_ecl.weighted_total), unit="KRW",
        code_module="risk_lib.provisioning.macro", code_function="macro_ecl",
        parameters={"scenarios": "baseline/downside/severe"},
        citation="IFRS 9 B5.5.42 (multiple scenarios)", **common))

    # ALM
    led.add(LedgerEntry(
        figure_id="alm.lcr", label="LCR",
        value=float(result.alm["lcr"].lcr), unit="ratio",
        code_module="risk_lib.alm.lcr", code_function="compute_lcr",
        citation="Basel III LCR20.1 (≥100%)", **common))
    led.add(LedgerEntry(
        figure_id="alm.nsfr", label="NSFR",
        value=float(result.alm["nsfr"].nsfr), unit="ratio",
        code_module="risk_lib.alm.nsfr", code_function="compute_nsfr",
        citation="Basel III NSF20.1 (≥100%)", **common))
    led.add(LedgerEntry(
        figure_id="alm.irrbb_worst_pct_tier1",
        label="IRRBB worst ΔEVE/Tier1",
        value=float(result.alm["irrbb"].worst_pct_tier1), unit="ratio",
        code_module="risk_lib.alm.irrbb", code_function="compute_irrbb",
        parameters={"shocks": "6 standard scenarios"},
        citation="Basel SRP31.90 IRRBB (2016) / outlier test SRP31.92",
        **common))

    # ICAAP
    if result.icaap is not None:
        led.add(LedgerEntry(
            figure_id="icaap.utilisation", label="ICAAP 사용률",
            value=float(result.icaap.utilisation), unit="ratio",
            code_module="risk_lib.icaap.economic_capital",
            code_function="compute_icaap",
            citation="Basel SRP20 / 감독세칙 ICAAP", **common))

    # Reverse stress
    led.add(LedgerEntry(
        figure_id="reverse_stress.severity",
        label="역스트레스 임계 심도",
        value=float(result.reverse_stress.critical_severity), unit="",
        code_module="risk_lib.stress.reverse",
        code_function="reverse_stress",
        citation="감독세칙 스트레스테스트 가이드라인", **common))

    # Stress path trough (worst scenario minimum CET1 over the horizon)
    trough = result.stress_path_trough
    worst = trough.loc[trough["trough_cet1"].idxmin()]
    led.add(LedgerEntry(
        figure_id="stress.trough_cet1",
        label=f"스트레스 경로 최저 CET1 ({worst['scenario']}, {worst['trough_quarter']})",
        value=float(worst["trough_cet1"]), unit="ratio",
        code_module="risk_lib.stress.path", code_function="run_stress_path / path_trough_summary",
        parameters={"scenario": str(worst["scenario"]),
                    "trough_quarter": str(worst["trough_quarter"])},
        citation="BCBS Stress testing principles (2018) / Pillar 2", **common))

    # Concentration (worst normalised HHI dimension)
    conc = result.concentration
    top = conc.loc[conc["normalised_hhi"].idxmax()]
    led.add(LedgerEntry(
        figure_id="concentration.worst_hhi",
        label=f"집중리스크 최대 HHI ({top['dimension']})",
        value=float(top["hhi"]), unit="",
        code_module="risk_lib.limits.concentration", code_function="concentration_report",
        parameters={"dimension": str(top["dimension"]),
                    "top1_share": float(top["top1_share"])},
        citation="BCBS 283 / 감독규정 집중리스크", **common))

    # CCR / CVA
    if getattr(result, "ccr", None) is not None:
        led.add(LedgerEntry(
            figure_id="ccr.cva_charge", label="CVA 자본부과 (BA-CVA)",
            value=float(result.ccr.cva_charge), unit="KRW",
            code_module="risk_lib.ccr", code_function="compute_ccr",
            parameters={"ead_total": float(result.ccr.ead_total),
                        "n_counterparties": int(result.ccr.n_counterparties)},
            citation="Basel III CRE52 (SA-CCR) + MAR50 (BA-CVA)", **common))

    # Operational loss distribution
    if getattr(result, "op_loss", None) is not None:
        led.add(LedgerEntry(
            figure_id="op_loss.var_99_9", label="운영손실 VaR 99.9%",
            value=float(result.op_loss.var_99_9), unit="KRW",
            code_module="risk_lib.op_loss", code_function="compute_op_loss",
            parameters={"annual_total": float(result.op_loss.annual_total)},
            citation="Basel III OPE25 (SMA 비교) / LDA 내부 산출", **common))

    # Climate (worst transition scenario ECL uplift)
    if getattr(result, "climate", None) is not None:
        cl = result.climate
        wt = next(l for l in cl.transition if l.scenario == cl.worst_transition)
        led.add(LedgerEntry(
            figure_id="climate.worst_transition_uplift",
            label=f"기후 전환리스크 최대 ECL uplift ({wt.scenario})",
            value=float(wt.uplift), unit="KRW",
            code_module="risk_lib.climate", code_function="run_climate",
            parameters={"scenario": str(wt.scenario)},
            citation="NGFS Phase 4 / TCFD", **common))

    # RAF worst grade
    if getattr(result, "raf", None) is not None:
        led.add(LedgerEntry(
            figure_id="raf.worst", label="RAF 최악 KRI 등급",
            value=result.raf.worst(), unit="grade",
            code_module="risk_lib.appetite", code_function="build_raf",
            parameters={"n_kris": len(result.raf.kris)},
            citation="FSB Principles / 감독세칙 RAF 가이드라인", **common))

    return led
