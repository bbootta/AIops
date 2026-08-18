"""블록별 ERD 생성기 (tools/gen_erd.py).

ERD 는 그림이라 틀려도 그럴듯해 보인다. 상자 하나가 빠지거나 화살표 하나가
사라져도 나머지가 멀쩡하면 눈으로는 알 수 없다. 그래서 눈이 아니라 수로 잡는다.

지키는 것은 세 가지다.

1. 스펙에 있는 FK 가 전부 그림에 있다. 블록 안 FK 는 화살표로, 블록 밖 FK 는
   목록으로 나오며 둘을 더하면 스펙의 FK 수와 정확히 같다. 어느 쪽으로도 새지
   않아야 한다.
2. 상자가 겹치지 않는다. 겹치면 밑에 깔린 표는 없는 표가 된다.
3. PK·FK 표시가 스펙에서 온다. 손으로 붙인 표시가 없어야 한다.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import gen_erd as erd                                    # noqa: E402
from risk_lib.datamodel import lineage as lin            # noqa: E402


@pytest.fixture(scope="module")
def graph():
    return lin.build_lineage()


@pytest.fixture(scope="module")
def blk(graph):
    return {s.name: lin.block_of(s) for s in graph.specs}


@pytest.fixture(scope="module")
def page(graph, blk):
    return erd.diagrams(graph, blk)


def _svgs(page_html: str) -> list[str]:
    return re.findall(r"<svg .*?</svg>", page_html, re.S)


# ------------------------------------------------------------ 빠짐 없음

def test_every_intra_block_fk_becomes_an_arrow(graph, blk, page):
    """블록 안 FK 수와 화살표 수가 같다.

    배치가 어떤 표를 좌표에 올리지 못하면 그 표로 가는 화살표도 조용히 빠진다.
    그림은 여전히 그럴듯하다. 그것을 여기서 잡는다.
    """
    inner = sum(1 for e in graph.edges_of("fk")
                if blk.get(e.src) == blk.get(e.dst))
    drawn = sum(s.count("marker-end=") for s in _svgs(page))
    assert drawn == inner, f"FK {inner}건 중 {drawn}건만 그려졌다"


def test_every_participating_table_becomes_a_box(graph, blk, page):
    """FK 에 참여하는 표는 전부 상자가 된다."""
    fks = graph.edges_of("fk")
    joined = {e.src for e in fks} | {e.dst for e in fks}
    inner = {n for n in joined
             if any(blk.get(e.src) == blk.get(e.dst)
                    and n in (e.src, e.dst) for e in fks)}
    for n in inner:
        assert f">{n}</text>" in page, f"{n} 상자가 없다"


def test_cross_block_fks_are_listed_not_dropped(graph, blk, page):
    """블록 경계를 넘는 FK 는 선이 안 그려지므로 목록으로 남는다.

    화살표 + 목록 = 스펙의 FK. 어느 쪽에도 없는 FK 가 있으면 실패한다.
    """
    fks = graph.edges_of("fk")
    cross = [e for e in fks if blk.get(e.src) != blk.get(e.dst)]
    for e in cross:
        assert f"{e.src} → {e.dst}" in page, f"{e.src}→{e.dst} 가 어디에도 없다"
    drawn = sum(s.count("marker-end=") for s in _svgs(page))
    assert drawn + len(cross) == len(fks)


def test_fk_less_ledgers_are_named(graph, blk, page):
    """FK 가 없어 그림에 못 들어간 원장도 이름은 남긴다."""
    fks = graph.edges_of("fk")
    joined = {e.src for e in fks} | {e.dst for e in fks}
    lone = [s.name for s in graph.specs
            if s.name not in joined and blk.get(s.name) in erd.BLOCK_ORDER]
    assert lone, "FK 없는 원장이 하나도 없다면 이 검사가 무의미하다"
    for n in lone:
        assert f">{n}</span>" in page, f"{n} 이 목록에서 빠졌다"


# ------------------------------------------------------------ 겹침 없음

def _boxes(graph, blk, block):
    """한 블록의 상자 좌표. 그리기와 같은 경로로 뽑는다."""
    fks = graph.edges_of("fk")
    joined = {e.src for e in fks} | {e.dst for e in fks}
    names = {n for n, v in blk.items() if v == block} & joined
    specs = [s for s in graph.specs if s.name in names]
    if not specs:
        return []
    svg, _, _ = erd.block_erd(block, specs, fks, "#000", "t")
    return [tuple(float(v) for v in m)
            for m in re.findall(
                r'<rect x="(-?\d+)" y="(-?\d+)" width="(\d+)" height="(\d+)"',
                svg)]


@pytest.mark.parametrize("block", erd.BLOCK_ORDER)
def test_boxes_do_not_overlap(graph, blk, block):
    """겹친 상자는 밑에 깔린 표를 지운다."""
    bs = _boxes(graph, blk, block)
    for i, (x1, y1, w1, h1) in enumerate(bs):
        for x2, y2, w2, h2 in bs[i + 1:]:
            assert not (x1 < x2 + w2 and x2 < x1 + w1
                        and y1 < y2 + h2 and y2 < y1 + h1), \
                f"{block} 상자 겹침 ({x1},{y1}) ({x2},{y2})"


@pytest.mark.parametrize("block", erd.BLOCK_ORDER)
def test_no_block_is_a_narrow_column(graph, blk, block):
    """세로 기둥이 되면 ERD 로 읽히지 않는다.

    계층을 옆으로 접지 않으면 신용 블록은 폭 708 에 높이 3682 가 된다. 접기가
    풀리면 이 검사가 먼저 운다.
    """
    bs = _boxes(graph, blk, block)
    if len(bs) < 10:                      # 작은 블록은 애초에 기둥이 아니다
        return
    w = max(x + bw for x, _, bw, _ in bs)
    h = max(y + bh for _, y, _, bh in bs)
    assert h / w < 2.0, f"{block} 가 {w:.0f}×{h:.0f} 로 기둥이다"


# ------------------------------------------------------------ 표시의 출처

def test_pk_and_fk_marks_come_from_the_spec(graph):
    """상자에 찍히는 PK·FK 는 스펙이 정한다."""
    sp = graph.spec_by_name["crm_ccf_backtest"]
    fk_cols = {c for fk in sp.foreign_keys for c in fk.columns}
    cols = erd._box_cols(sp, fk_cols)
    got = {name: (pk, fk) for name, pk, fk in cols}
    for c in sp.primary_key:
        assert got.get(c, (False, False))[0], f"{c} 가 PK 로 안 찍혔다"
    for c in fk_cols & set(got):
        assert got[c][1], f"{c} 가 FK 로 안 찍혔다"
    assert fk_cols, "이 표에 FK 가 없으면 검사가 무의미하다"


def test_truncated_box_says_how_many_it_hid(graph, blk, page):
    """칸을 자른 상자는 몇 칸을 숨겼는지 적는다. 안 적으면 그 표는 작아 보인다."""
    wide = [s for s in graph.specs if len(s.columns) > erd.MAX_COLS + 3]
    assert wide, "자를 만큼 넓은 표가 없으면 검사가 무의미하다"
    assert "외 " in page


# ------------------------------------------------------------ 재현

def test_output_is_deterministic(graph, blk):
    assert erd.diagrams(graph, blk) == erd.diagrams(graph, blk)


def test_no_long_dash_in_output(page):
    assert "—" not in page and "–" not in page
