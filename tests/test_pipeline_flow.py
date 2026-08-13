"""기초데이터에서 업무보고서까지의 원장 흐름도 (tools/gen_pipeline_flow.py).

이 그림은 상자에 이름만 적는다. 이름이 잘리거나 상자가 하나 빠지면 그 원장은
사실상 그림에서 사라지는데, 나머지가 멀쩡해 보여서 눈으로는 모른다. 그래서

1. 원장 266장이 전부 어느 단계·묶음에 들어간다. 새 접두어가 생기면 여기서 운다.
2. 상자가 겹치지 않고, 한 묶음이 두 열에 걸리지 않는다.
3. 스펙의 엣지가 전부 선이 된다. 되돌아가는 선도 지우지 않고 센다.
4. 가장 긴 이름이 상자에 들어간다. 안 들어가면 말줄임표로 잘려 다른 표와
   구별되지 않는다.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

import gen_pipeline_flow as pf                            # noqa: E402
from risk_lib.datamodel import lineage as lin             # noqa: E402

# 크로미움 실측. 10.5px ui-monospace 로 alm_early_redemption_observation(32자)이
# 202.296875px 였다. 글자당 6.3218px 이고, 여기서는 올려 잡는다.
PX_PER_CHAR = 6.33


@pytest.fixture(scope="module")
def graph():
    return lin.build_lineage()


@pytest.fixture(scope="module")
def blk(graph):
    return {s.name: lin.block_of(s) for s in graph.specs}


@pytest.fixture(scope="module")
def laid(graph, blk):
    return pf.layout(graph, blk)


# ------------------------------------------------------------ 빠짐 없음

def test_every_ledger_lands_in_a_stage(graph):
    """접두어가 어디에도 안 걸리는 원장이 있으면 그림에서 통째로 빠진다."""
    missing = [s.name for s in graph.specs if pf._assign(s.name) is None]
    assert not missing, f"단계 미배정 {len(missing)}장: {missing[:10]}"


def test_every_ledger_gets_a_box(graph, laid):
    _members, nodes, _forms, _cols, _w, _h = laid
    assert len(nodes) == len(graph.specs)


def test_every_form_module_gets_a_box(graph, laid):
    _members, _nodes, forms, _cols, _w, _h = laid
    assert set(forms) == set(graph.forms)


def test_every_edge_becomes_a_line(graph, blk, laid):
    """스펙의 엣지 수와 그린 선 수가 같다.

    feeds·fk 는 같은 쌍이 여러 함수에서 나올 수 있어 중복을 접는다. 접은 뒤의
    수와 그린 수를 맞춘다. 어느 한쪽만 세면 빠진 선을 못 잡는다.
    """
    _members, nodes, _forms, _cols, _w, _h = laid
    want = {(e.src, e.dst, e.kind) for e in graph.edges
            if e.kind in ("feeds", "fk") and e.src in nodes and e.dst in nodes}
    want |= {(t, m, "reports") for m, ts in graph.forms.items()
             for t in ts if t in nodes}
    body, meta = pf.build(graph, blk)
    assert meta["stats"]["edges"] == len(want)
    assert body.count("<path id=\"e") == len(want)


def test_backward_lines_are_counted_not_hidden(graph, blk):
    """단계를 거스르는 선이 있다. 지우면 흐름이 한 방향으로만 보인다."""
    _body, meta = pf.build(graph, blk)
    assert meta["stats"]["back"] > 0, "되돌아가는 선이 0이면 이 검사가 무의미하다"
    body, _ = pf.build(graph, blk)
    assert body.count("e back") == meta["stats"]["back"]


# ------------------------------------------------------------ 겹침 없음

def test_boxes_do_not_overlap(laid):
    _members, nodes, forms, _cols, _w, _h = laid
    pos = sorted(list(nodes.values()) + list(forms.values()))
    for i, (x1, y1) in enumerate(pos):
        for x2, y2 in pos[i + 1:]:
            assert not (abs(x1 - x2) < pf.BOX_W
                        and abs(y1 - y2) < pf.ROW_H - 1), \
                f"상자 겹침 ({x1},{y1}) ({x2},{y2})"


def test_a_group_is_never_split_across_columns(laid):
    """한 묶음이 두 열에 걸리면 묶음 이름이 두 번 찍혀 어느 쪽이 진짜인지 모른다."""
    members, nodes, _forms, _cols, _w, _h = laid
    for key, names in members.items():
        xs = {nodes[n][0] for n in names}
        assert len(xs) == 1, f"{key} 묶음이 열 {len(xs)}개에 걸쳤다"


def test_stage_columns_run_left_to_right(laid):
    """단계 순서가 화면 순서다. 뒤집히면 그림이 흐름을 거짓으로 말한다."""
    members, nodes, forms, _cols, _w, _h = laid
    xs = {}
    for (stage, _grp), names in members.items():
        xs.setdefault(stage, []).extend(nodes[n][0] for n in names)
    order = [s for s, _, _ in pf.STAGES]
    lefts = [min(xs[s]) for s in order if s in xs]
    assert lefts == sorted(lefts)
    assert min(f[0] for f in forms.values()) > max(lefts)


# ------------------------------------------------------------ 이름이 들어간다

def test_longest_name_fits_the_box(graph):
    """이름이 잘리면 그 원장은 다른 원장과 구별되지 않는다."""
    longest = max((s.name for s in graph.specs), key=len)
    need = len(longest) * PX_PER_CHAR + 14      # 좌우 안쪽 여백
    assert pf.BOX_W >= need, (
        f"{longest} ({len(longest)}자) 가 {need:.0f}px 를 쓰는데 "
        f"상자는 {pf.BOX_W}px 다")


def test_longest_form_module_name_fits(graph):
    longest = max(graph.forms, key=len)
    assert pf.BOX_W >= len(longest) * PX_PER_CHAR + 14


# ------------------------------------------------------------ 눌렀을 때

def test_every_box_has_column_data(graph, blk, laid):
    """이름을 눌러도 컬럼이 안 나오는 상자가 있으면 안 된다."""
    _members, nodes, forms, _cols, _w, _h = laid
    _body, meta = pf.build(graph, blk)
    have = meta["data"]["cols"]
    for n in list(nodes) + list(forms):
        assert n in have, f"{n} 의 컬럼 자료가 없다"
    for n in nodes:
        assert have[n]["c"], f"{n} 의 컬럼이 비었다"


def test_column_data_marks_pk_and_fk_from_the_spec(graph, blk):
    _body, meta = pf.build(graph, blk)
    sp = graph.spec_by_name["crm_ccf_backtest"]
    got = {c[0]: c[3] for c in meta["data"]["cols"]["crm_ccf_backtest"]["c"]}
    for c in sp.primary_key:
        assert got[c] == "PK"
    fk = {c for f in sp.foreign_keys for c in f.columns}
    assert fk, "이 표에 FK 가 없으면 검사가 무의미하다"
    for c in fk - set(sp.primary_key):
        assert got[c] == "FK"


# ------------------------------------------------------------ 재현

def test_output_is_deterministic(graph, blk):
    assert pf.build(graph, blk)[0] == pf.build(graph, blk)[0]


def test_no_long_dash(graph, blk):
    body, _ = pf.build(graph, blk)
    assert "—" not in body and "–" not in body
