#!/usr/bin/env python3
"""
explore_graph.py

Neo4j 없이 graphrag_output/ 의 nodes.json + edges.json 을
NetworkX 로 불러와 즉석 탐색한다.

사용:
  pip install networkx
  python explore_graph.py
  python explore_graph.py --query hub          # 허브 노드 상위 20개
  python explore_graph.py --query neighbors --title "RAG Systems"
  python explore_graph.py --query path --from "Language Modeling" --to "Transformer"
  python explore_graph.py --query community    # 커뮤니티 탐지 (leiden 없이 louvain 대체)
  python explore_graph.py --query stats        # 전체 통계
"""

import argparse
import io
import json
import sys
from collections import Counter
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    import networkx as nx
except ImportError:
    print("networkx 없음. 설치: pip install networkx", file=sys.stderr)
    sys.exit(1)

INPUT_DIR = Path(r"C:\Users\bboot\AIops\codex\graphrag_output")


# ── 그래프 로드 ────────────────────────────────────────────────────────────

def load_graph(input_dir: Path) -> tuple[nx.DiGraph, dict]:
    nodes = json.loads((input_dir / "nodes.json").read_text(encoding="utf-8"))
    edges = json.loads((input_dir / "edges.json").read_text(encoding="utf-8"))

    G = nx.DiGraph()
    node_map: dict[str, dict] = {}

    for n in nodes:
        G.add_node(n["id"], **{k: v for k, v in n.items() if k != "content_preview"})
        node_map[n["id"]] = n
        # title → id 역매핑도 추가 (title로 노드 찾기 편의)
        node_map[n["title"].lower()] = n

    for e in edges:
        G.add_edge(e["source"], e["target"], context=e.get("context", ""))

    return G, node_map


def find_node(node_map: dict, query: str) -> dict | None:
    """제목 또는 id로 노드 찾기 (대소문자 무시)."""
    q = query.strip().lower()
    return node_map.get(q)


# ── 쿼리 함수들 ────────────────────────────────────────────────────────────

def query_stats(G: nx.DiGraph, node_map: dict) -> None:
    print(f"\n{'='*50}")
    print("전체 그래프 통계")
    print(f"{'='*50}")
    print(f"  노드 수:       {G.number_of_nodes():>6,}")
    print(f"  엣지 수:       {G.number_of_edges():>6,}")
    print(f"  평균 out-deg:  {sum(d for _, d in G.out_degree()) / max(G.number_of_nodes(), 1):.2f}")
    print(f"  평균 in-deg:   {sum(d for _, d in G.in_degree()) / max(G.number_of_nodes(), 1):.2f}")
    print(f"  약한 연결 컴포넌트: {nx.number_weakly_connected_components(G)}")

    # 노드 유형 분포
    types = Counter(d.get("type", "") for _, d in G.nodes(data=True))
    print("\n  노드 유형 분포:")
    for t, cnt in types.most_common():
        print(f"    {(t or '(없음)'):<30} {cnt:>5,}")

    # 폴더 분포
    folders = Counter(d.get("folder", "") for _, d in G.nodes(data=True))
    print("\n  폴더별 노드 수:")
    for f, cnt in folders.most_common():
        print(f"    {f:<40} {cnt:>5,}")


def query_hub(G: nx.DiGraph, top_n: int = 20) -> None:
    print(f"\n{'='*50}")
    print(f"허브 노드 상위 {top_n}개 (out-degree 기준)")
    print(f"{'='*50}")
    ranked = sorted(G.nodes(data=True), key=lambda x: G.out_degree(x[0]), reverse=True)
    print(f"  {'순위':>4}  {'제목':<40} {'유형':<15} {'out':>5} {'in':>5}")
    print(f"  {'-'*75}")
    for i, (node_id, data) in enumerate(ranked[:top_n], 1):
        title = (data.get("title") or node_id)[:38]
        ntype = (data.get("type") or "")[:13]
        out = G.out_degree(node_id)
        inp = G.in_degree(node_id)
        print(f"  {i:>4}  {title:<40} {ntype:<15} {out:>5} {inp:>5}")


def query_neighbors(G: nx.DiGraph, node_map: dict, title: str, depth: int = 1) -> None:
    node = find_node(node_map, title)
    if not node:
        print(f"노드를 찾을 수 없음: '{title}'")
        return

    node_id = node["id"]
    print(f"\n{'='*50}")
    print(f"이웃 노드: {node['title']} ({node.get('type', '')})")
    print(f"{'='*50}")

    # 나가는 링크
    out_neighbors = list(G.successors(node_id))
    print(f"\n  → 나가는 링크 ({len(out_neighbors)}개):")
    for nb in sorted(out_neighbors, key=lambda n: G.nodes[n].get("title", n))[:30]:
        nb_data = G.nodes[nb]
        ctx = G.edges[node_id, nb].get("context", "")[:60]
        print(f"    [{nb_data.get('type', ''):<10}] {nb_data.get('title', nb):<35} | {ctx}")

    # 들어오는 링크
    in_neighbors = list(G.predecessors(node_id))
    print(f"\n  ← 들어오는 링크 ({len(in_neighbors)}개):")
    for nb in sorted(in_neighbors, key=lambda n: G.nodes[n].get("title", n))[:20]:
        nb_data = G.nodes[nb]
        print(f"    [{nb_data.get('type', ''):<10}] {nb_data.get('title', nb)}")


def query_path(G: nx.DiGraph, node_map: dict, src_title: str, tgt_title: str) -> None:
    src = find_node(node_map, src_title)
    tgt = find_node(node_map, tgt_title)
    if not src:
        print(f"시작 노드를 찾을 수 없음: '{src_title}'")
        return
    if not tgt:
        print(f"끝 노드를 찾을 수 없음: '{tgt_title}'")
        return

    print(f"\n{'='*50}")
    print(f"최단 경로: {src['title']} → {tgt['title']}")
    print(f"{'='*50}")

    # 유향 최단 경로
    try:
        path = nx.shortest_path(G, source=src["id"], target=tgt["id"])
        print(f"\n  방향 경로 (길이 {len(path)-1}):")
        for step, nid in enumerate(path):
            nd = G.nodes[nid]
            arrow = "  →  " if step > 0 else "  시작"
            print(f"  {arrow} [{nd.get('type',''):<10}] {nd.get('title', nid)}")
    except nx.NetworkXNoPath:
        print("  유향 경로 없음. 무향 최단 경로 시도 …")
        try:
            UG = G.to_undirected()
            path = nx.shortest_path(UG, source=src["id"], target=tgt["id"])
            print(f"  무향 경로 (길이 {len(path)-1}):")
            for step, nid in enumerate(path):
                nd = G.nodes[nid]
                arrow = "  --  " if step > 0 else "  시작"
                print(f"  {arrow} [{nd.get('type',''):<10}] {nd.get('title', nid)}")
        except nx.NetworkXNoPath:
            print("  경로 없음 (연결되지 않은 컴포넌트)")


def query_community(G: nx.DiGraph, top_n: int = 15) -> None:
    print(f"\n{'='*50}")
    print("커뮤니티 탐지 (Greedy Modularity, 무향 변환)")
    print(f"{'='*50}")

    try:
        from networkx.algorithms.community import greedy_modularity_communities
    except ImportError:
        print("  networkx 버전이 낮거나 community 모듈 없음")
        return

    UG = G.to_undirected()
    # 큰 컴포넌트만 분석
    largest = max(nx.connected_components(UG), key=len)
    sub = UG.subgraph(largest).copy()

    print(f"  분석 대상: {sub.number_of_nodes():,}개 노드 (최대 컴포넌트)")
    print("  커뮤니티 탐지 중 … (수 초 소요)")

    communities = list(greedy_modularity_communities(sub))
    communities.sort(key=len, reverse=True)

    print(f"  발견된 커뮤니티: {len(communities)}개\n")
    print(f"  {'순위':>4}  {'크기':>5}  대표 노드 (상위 5개)")
    print(f"  {'-'*70}")

    for i, comm in enumerate(communities[:top_n], 1):
        # 커뮤니티 내 가장 많이 연결된 노드 선택
        top_nodes = sorted(comm, key=lambda n: sub.degree(n), reverse=True)[:5]
        titles = [G.nodes[n].get("title", n)[:20] for n in top_nodes]
        print(f"  {i:>4}  {len(comm):>5}  {' / '.join(titles)}")


def query_search(G: nx.DiGraph, keyword: str, input_dir: Path, top_n: int = 20) -> None:
    """제목 또는 content_preview에서 키워드 검색."""
    kw = keyword.lower()
    results = []
    nodes_json = json.loads(
        (input_dir / "nodes.json").read_text(encoding="utf-8")
    )
    for n in nodes_json:
        score = 0
        if kw in (n.get("title") or "").lower():
            score += 10
        if kw in (n.get("content_preview") or "").lower():
            score += 1
        if any(kw in t.lower() for t in (n.get("tags") or [])):
            score += 5
        if score:
            results.append((score, n))

    results.sort(reverse=True)
    print(f"\n{'='*50}")
    print(f"키워드 검색: '{keyword}' — {len(results)}개 결과")
    print(f"{'='*50}")
    print(f"  {'점수':>5}  {'제목':<40} {'유형':<12} {'링크수':>6}")
    print(f"  {'-'*70}")
    for score, n in results[:top_n]:
        title = (n.get("title") or "")[:38]
        ntype = (n.get("type") or "")[:10]
        wc = n.get("wikilink_count", 0)
        print(f"  {score:>5}  {title:<40} {ntype:<12} {wc:>6}")


# ── 진입점 ─────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Obsidian 그래프 즉석 탐색 (Neo4j 불필요)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--query",
        choices=["stats", "hub", "neighbors", "path", "community", "search"],
        default="stats",
        help="실행할 쿼리 유형",
    )
    parser.add_argument("--title",  help="--query neighbors: 노드 제목")
    parser.add_argument("--from",   dest="src", help="--query path: 시작 노드 제목")
    parser.add_argument("--to",     dest="tgt", help="--query path: 끝 노드 제목")
    parser.add_argument("--keyword", help="--query search: 검색 키워드")
    parser.add_argument("--top",    type=int, default=20, help="결과 표시 수")
    parser.add_argument(
        "--input-dir",
        default=str(INPUT_DIR),
        help="nodes.json / edges.json 위치",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)

    print("그래프 로드 중 …")
    G, node_map = load_graph(input_dir)
    print(f"  완료: {G.number_of_nodes():,}개 노드, {G.number_of_edges():,}개 엣지")

    if args.query == "stats":
        query_stats(G, node_map)
    elif args.query == "hub":
        query_hub(G, top_n=args.top)
    elif args.query == "neighbors":
        if not args.title:
            print("--title 필요", file=sys.stderr); sys.exit(1)
        query_neighbors(G, node_map, args.title)
    elif args.query == "path":
        if not args.src or not args.tgt:
            print("--from 과 --to 모두 필요", file=sys.stderr); sys.exit(1)
        query_path(G, node_map, args.src, args.tgt)
    elif args.query == "community":
        query_community(G, top_n=args.top)
    elif args.query == "search":
        if not args.keyword:
            print("--keyword 필요", file=sys.stderr); sys.exit(1)
        query_search(G, args.keyword, input_dir, top_n=args.top)


if __name__ == "__main__":
    main()
