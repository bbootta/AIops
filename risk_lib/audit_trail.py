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
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
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
    approval_dt: str = ""
    # versioning
    asof: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
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
                              approval_dt: str | None = None) -> AuditLedger:
    """Walk through standard headline figures and create ledger entries."""
    led = AuditLedger()
    ts = approval_dt or datetime.now(timezone.utc).isoformat(timespec="seconds")

    common = dict(
        git_commit=git_commit,
        owner=owner, reviewer=reviewer, approver=approver,
        approval_dt=ts,
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

    return led
