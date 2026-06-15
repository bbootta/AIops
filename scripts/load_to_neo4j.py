#!/usr/bin/env python3
"""
load_to_neo4j.py

graphrag_output/ 의 nodes.json + edges.json 을 Neo4j에 적재한다.

사전 조건:
  pip install neo4j
  Neo4j 실행 중 (기본: bolt://localhost:7687)

  # Docker로 빠르게 시작하는 경우:
  docker run -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=none neo4j:latest

사용:
  python load_to_neo4j.py
  python load_to_neo4j.py --uri bolt://localhost:7687 --user neo4j --password <pw>
  python load_to_neo4j.py --input-dir <path> --wipe

Neo4j Browser: http://localhost:7474
"""

import argparse
import io
import json
import sys
import time
from pathlib import Path

# Windows 콘솔 인코딩 보정
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    from neo4j import GraphDatabase
    from neo4j.exceptions import ServiceUnavailable
except ImportError:
    print("neo4j 드라이버 없음. 설치: pip install neo4j", file=sys.stderr)
    sys.exit(1)

# ── 배치 크기 ──────────────────────────────────────────────────────────────
NODE_BATCH = 500
EDGE_BATCH = 1000


# ── 스키마 설정 ────────────────────────────────────────────────────────────

SCHEMA_QUERIES = [
    # 고유 제약 (중복 적재 방지 + 자동 인덱스)
    "CREATE CONSTRAINT note_id IF NOT EXISTS FOR (n:Note) REQUIRE n.id IS UNIQUE",
    # 추가 인덱스 (필터/집계 성능)
    "CREATE INDEX note_type   IF NOT EXISTS FOR (n:Note) ON (n.type)",
    "CREATE INDEX note_status IF NOT EXISTS FOR (n:Note) ON (n.status)",
    "CREATE INDEX note_folder IF NOT EXISTS FOR (n:Note) ON (n.folder)",
    # 전문 검색 인덱스 (title + content_preview)
    """CREATE FULLTEXT INDEX note_fulltext IF NOT EXISTS
       FOR (n:Note) ON EACH [n.title, n.content_preview]""",
]


def setup_schema(session) -> None:
    print("스키마 설정 중 …")
    for q in SCHEMA_QUERIES:
        session.run(q)
    print("  완료")


# ── 노드 적재 ──────────────────────────────────────────────────────────────

NODE_UPSERT = """
UNWIND $batch AS row
MERGE (n:Note {id: row.id})
SET
  n.title           = row.title,
  n.path            = row.path,
  n.folder          = row.folder,
  n.type            = row.type,
  n.status          = row.status,
  n.tags            = row.tags,
  n.aliases         = row.aliases,
  n.source_ids      = row.source_ids,
  n.created         = row.created,
  n.updated         = row.updated,
  n.content_preview = row.content_preview,
  n.char_count      = row.char_count,
  n.wikilink_count  = row.wikilink_count
"""

# type → 추가 레이블 매핑 (선택적, 쿼리 편의용)
TYPE_LABEL_MAP = {
    "concept": "Concept",
    "source": "Source",
    "source-note": "Source",
    "source_note": "Source",
    "source-extract": "Source",
    "map": "Map",
    "project": "Project",
    "workflow": "Workflow",
    "bridge": "Bridge",
    "index": "Index",
}

ADD_LABEL_TEMPLATE = "MATCH (n:Note {{id: $id}}) SET n:{label}"


def load_nodes(session, nodes: list[dict]) -> int:
    total = 0
    for i in range(0, len(nodes), NODE_BATCH):
        batch = nodes[i : i + NODE_BATCH]
        session.run(NODE_UPSERT, batch=batch)
        total += len(batch)
        print(f"  노드 {total:,}/{len(nodes):,}", end="\r")

    # 추가 레이블 부여
    for node in nodes:
        label = TYPE_LABEL_MAP.get(node.get("type", ""))
        if label:
            session.run(ADD_LABEL_TEMPLATE.format(label=label), id=node["id"])

    print(f"  노드 {total:,}개 적재 완료          ")
    return total


# ── 엣지 적재 ──────────────────────────────────────────────────────────────

EDGE_UPSERT = """
UNWIND $batch AS row
MATCH (src:Note {id: row.source})
MATCH (tgt:Note {id: row.target})
MERGE (src)-[r:LINKS_TO]->(tgt)
SET r.context      = row.context,
    r.source_path  = row.source_path,
    r.target_path  = row.target_path
"""


def load_edges(session, edges: list[dict]) -> int:
    total = 0
    skipped = 0
    for i in range(0, len(edges), EDGE_BATCH):
        batch = edges[i : i + EDGE_BATCH]
        result = session.run(EDGE_UPSERT, batch=batch)
        summary = result.consume()
        created = summary.counters.relationships_created
        total += created
        skipped += len(batch) - created
        print(f"  엣지 {total:,}/{len(edges):,}", end="\r")

    print(f"  엣지 {total:,}개 적재 완료 (노드 없어서 스킵: {skipped}개)          ")
    return total


# ── 검증 쿼리 ──────────────────────────────────────────────────────────────

VERIFY_QUERIES = [
    ("전체 노드", "MATCH (n:Note) RETURN count(n) AS cnt"),
    ("전체 엣지", "MATCH ()-[r:LINKS_TO]->() RETURN count(r) AS cnt"),
    ("유형별 노드", "MATCH (n:Note) RETURN n.type AS type, count(n) AS cnt ORDER BY cnt DESC"),
    ("상위 허브 10개", """
        MATCH (n:Note)
        RETURN n.title AS title, n.type AS type, n.wikilink_count AS out_links
        ORDER BY out_links DESC LIMIT 10
    """),
]


def verify(session) -> None:
    print("\n── 검증 ──────────────────────────────────────────")
    for label, q in VERIFY_QUERIES:
        print(f"\n[{label}]")
        result = session.run(q)
        for row in result:
            print("  ", dict(row))


# ── 초기화 (선택) ──────────────────────────────────────────────────────────

WIPE_QUERY = "MATCH (n) DETACH DELETE n"


def wipe_db(session) -> None:
    print("  기존 데이터 전체 삭제 중 …")
    session.run(WIPE_QUERY)
    print("  완료")


# ── 메인 ───────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Obsidian GraphRAG 데이터를 Neo4j에 적재",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("--uri",      default="bolt://localhost:7687", help="Neo4j Bolt URI")
    parser.add_argument("--user",     default="neo4j",                 help="Neo4j 사용자명")
    parser.add_argument("--password", default="",                      help="Neo4j 비밀번호 (없으면 빈 문자열)")
    parser.add_argument(
        "--input-dir",
        default=r"C:\Users\bboot\AIops\codex\graphrag_output",
        help="nodes.json / edges.json 위치",
    )
    parser.add_argument(
        "--wipe",
        action="store_true",
        help="적재 전 DB 전체 삭제 (주의)",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="적재 후 검증 쿼리 생략",
    )
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    nodes_path = input_dir / "nodes.json"
    edges_path = input_dir / "edges.json"

    for p in (nodes_path, edges_path):
        if not p.exists():
            print(f"파일 없음: {p}\n먼저 parse_obsidian_to_graph.py를 실행하세요.", file=sys.stderr)
            sys.exit(1)

    print(f"데이터 로드 중 …")
    nodes = json.loads(nodes_path.read_text(encoding="utf-8"))
    edges = json.loads(edges_path.read_text(encoding="utf-8"))
    print(f"  nodes.json: {len(nodes):,}개")
    print(f"  edges.json: {len(edges):,}개")

    auth = (args.user, args.password) if args.password else ("", "")

    print(f"\nNeo4j 연결 중: {args.uri} …")
    try:
        driver = GraphDatabase.driver(args.uri, auth=auth)
        driver.verify_connectivity()
    except ServiceUnavailable:
        print(
            f"\n[연결 실패] Neo4j가 실행 중인지 확인하세요.\n"
            f"  Docker: docker run -p 7474:7474 -p 7687:7687 -e NEO4J_AUTH=none neo4j:latest\n"
            f"  또는 Neo4j Desktop 실행 후 재시도.",
            file=sys.stderr,
        )
        sys.exit(1)
    print("  연결 성공")

    t0 = time.time()
    with driver.session() as session:
        if args.wipe:
            wipe_db(session)

        setup_schema(session)

        print("\n노드 적재 중 …")
        load_nodes(session, nodes)

        print("\n엣지 적재 중 …")
        load_edges(session, edges)

        if not args.no_verify:
            verify(session)

    elapsed = time.time() - t0
    print(f"\n완료 ({elapsed:.1f}초)")
    print("Neo4j Browser: http://localhost:7474")
    print("\n── 유용한 시작 쿼리 ───────────────────────────────")
    print("  // 가장 많이 연결된 노드 20개")
    print("  MATCH (n:Note)-[r:LINKS_TO]->() RETURN n.title, count(r) AS deg ORDER BY deg DESC LIMIT 20")
    print()
    print("  // 두 노드 간 최단 경로")
    print("  MATCH p=shortestPath((a:Note {title:'Language Modeling'})-[:LINKS_TO*]-(b:Note {title:'Transformer'}))")
    print("  RETURN p")
    print()
    print("  // 타입별 클러스터 탐색")
    print("  MATCH (n:Concept)-[:LINKS_TO]->(m:Concept) RETURN n.title, m.title LIMIT 50")
    print()
    print("  // 특정 태그 노드와 이웃")
    print("  MATCH (n:Note)-[:LINKS_TO]->(m) WHERE 'rag' IN n.tags RETURN n, m")

    driver.close()


if __name__ == "__main__":
    main()
