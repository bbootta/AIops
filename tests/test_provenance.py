"""서식 라인의 산출 근거 분류 — 파생값이 실측으로 보고되지 않게 한다.

핵심 명제:
  1) 파생 어휘를 품은 라인이 조용히 실측으로 떨어지지 않는다.
  2) 실측이 아닌 라인은 **반드시** 어느 원장에 걸린다 — 걸리지 않으면
     "이걸 실측으로 바꾸려면 무엇이 필요한가"에 답할 수 없다.
  3) 동음이의(파생상품)를 파생값으로 오인하지 않는다.
"""

from __future__ import annotations

import pytest

from risk_lib.regulatory.forms import build_forms
from risk_lib.regulatory.provenance import (
    BASIS_DERIVED, BASIS_MEASURED, BASES, LEDGERS,
    basis_summary, ledger_impact_frame, line_basis, provenance_frame,
    unattributed, unclassified,
)


@pytest.fixture(scope="module")
def built(result, portfolio):
    from risk_lib.ui_studio.studio import build_studio
    studio = build_studio(result, portfolio)
    return build_forms(result, portfolio, studio.tables)


def test_every_line_gets_a_basis(built):
    prov = provenance_frame(built)
    assert len(prov) > 0
    assert set(prov["basis"]) <= set(BASES)


def test_no_line_is_left_unclassified(built):
    """파생 어휘를 품었는데 실측으로 떨어진 라인이 없어야 한다.

    분류가 조용히 실패하면 파생값이 실측으로 보고된다. 새 서식이 새 표현을
    쓰면 여기가 채워지므로 provenance의 규칙을 갱신하면 된다.
    """
    u = unclassified(built)
    assert len(u) == 0, u.to_string(index=False)


def test_every_open_line_maps_to_a_ledger(built):
    """실측이 아닌 라인은 전부 원장에 걸려야 한다 — 이행 계획의 전제다."""
    u = unattributed(built)
    assert len(u) == 0, (
        f"원장 미귀속 {len(u)}건\n"
        + u.groupby("form_id").size().to_string())


def test_derivative_is_not_mistaken_for_derived():
    """'파생상품'은 derivative이지 derived가 아니다."""
    from types import SimpleNamespace
    ln = SimpleNamespace(formula="온밸런스 + 파생 + SFT + 부외 환산",
                         text_value=None, value=1.0)
    assert line_basis(ln) == BASIS_MEASURED
    ln2 = SimpleNamespace(formula="월말 잔액 × exp(σ×z) — 파생값",
                          text_value=None, value=1.0)
    assert line_basis(ln2) == BASIS_DERIVED


def test_explicit_basis_wins_over_inference():
    from types import SimpleNamespace
    ln = SimpleNamespace(formula="파생값", text_value=None, value=1.0,
                         basis=BASIS_MEASURED)
    assert line_basis(ln) == BASIS_MEASURED


def test_ledger_ids_are_unique_and_documented():
    ids = [g.ledger_id for g in LEDGERS]
    assert len(ids) == len(set(ids))
    for g in LEDGERS:
        assert g.name and g.unlocks, g.ledger_id
        assert g.patterns or g.forms, f"{g.ledger_id}: 귀속 경로가 없다"


def test_measured_share_is_reported(built):
    """제출본이 얼마나 실측에 서 있는지 한 줄로 나와야 한다."""
    summ = basis_summary(built)
    assert abs(summ["share"].sum() - 1.0) < 1e-9
    measured = summ[summ["basis"] == BASIS_MEASURED]["share"].iloc[0]
    assert measured > 0.5, f"실측 비중 {measured:.1%} — 파생이 과반이면 제출본이 아니다"


def test_ledger_impact_covers_every_open_line(built):
    """원장별 영향 합계가 개방 라인 수를 덮는다 (중복 귀속 허용)."""
    impact = ledger_impact_frame(built)
    prov = provenance_frame(built)
    open_n = int((prov["basis"] != BASIS_MEASURED).sum()
                 - (prov["basis"] == "서술").sum())
    assert impact["n_lines"].sum() >= open_n
