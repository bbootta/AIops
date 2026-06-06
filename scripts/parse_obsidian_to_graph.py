#!/usr/bin/env python3
"""
parse_obsidian_to_graph.py

Obsidian 볼트를 파싱해 GraphRAG / Neo4j 적재용 JSON을 생성한다.

출력 (--output-dir):
  nodes.json       — 노드 1개 = .md 파일 1개 (frontmatter + 본문 미리보기)
  edges.json       — 엣지 1개 = 해석된 [[wikilink]] 1개 (중복 제거)
  unresolved.json  — 대상 파일을 찾지 못한 깨진 링크
  stats.json       — 요약 통계

사용:
  pip install pyyaml
  python parse_obsidian_to_graph.py
  python parse_obsidian_to_graph.py --vault <path> --output-dir <path>
"""

import argparse
import io
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Windows 콘솔 cp949 인코딩 오류 방지
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

try:
    import yaml
except ImportError:
    print("PyYAML 없음. 설치: pip install pyyaml", file=sys.stderr)
    sys.exit(1)


# ── 정규식 ─────────────────────────────────────────────────────────────────

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

# [[Link]], [[Link|Display]], [[Link#Section]], [[Link#Section|Display]] 전부 처리
WIKILINK_RE = re.compile(r"\[\[([^\]|#]+?)(?:#[^\]|]*)??(?:\|[^\]]+)?\]\]")


# ── 유틸 ───────────────────────────────────────────────────────────────────

def slugify(name: str) -> str:
    """노트 제목/파일명을 안정적인 ID로 변환."""
    for ch in r'\/:*?"<>|':
        name = name.replace(ch, "")
    return name.strip().lower().replace(" ", "-")


def as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    return [str(value)]


def date_str(value) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.date().isoformat()
    return str(value)


def count_by(records: list[dict], key: str) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for r in records:
        counts[r.get(key) or ""] += 1
    return dict(sorted(counts.items(), key=lambda x: -x[1]))


# ── 파싱 ───────────────────────────────────────────────────────────────────

def parse_frontmatter(text: str) -> tuple[dict, str]:
    """YAML frontmatter와 본문을 분리. (meta, body) 반환."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        meta = {}
    return meta, text[m.end():]


def extract_wikilinks(body: str) -> list[tuple[str, str]]:
    """
    본문에서 [[wikilink]] 전체를 추출.
    반환: [(raw_target, context_snippet), ...]
    context_snippet = 링크 전후 80자
    """
    results = []
    for m in WIKILINK_RE.finditer(body):
        target = m.group(1).strip()
        if not target:
            continue
        start = max(0, m.start() - 40)
        end = min(len(body), m.end() + 40)
        ctx = body[start:end].replace("\n", " ").strip()
        results.append((target, ctx))
    return results


# ── 인덱스 빌드 ────────────────────────────────────────────────────────────

def build_name_index(vault_dir: Path, include_dirs: list[str]) -> dict[str, str]:
    """
    lowercase_stem → relative_path 매핑 생성.
    aliases frontmatter도 포함. 충돌 시 먼저 발견된 것 우선.
    """
    index: dict[str, str] = {}
    alias_map: dict[str, str] = {}

    for sub in include_dirs:
        sub_dir = vault_dir / sub
        if not sub_dir.exists():
            continue
        for path in sub_dir.rglob("*.md"):
            rel = path.relative_to(vault_dir).as_posix()
            key = path.stem.strip().lower()
            if key not in index:
                index[key] = rel

            # aliases 처리
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            meta, _ = parse_frontmatter(text)
            for alias in as_list(meta.get("aliases")):
                akey = alias.strip().lower()
                if akey and akey not in alias_map and akey not in index:
                    alias_map[akey] = rel

    index.update(alias_map)
    return index


def resolve_link(raw_target: str, index: dict[str, str]) -> str | None:
    """wikilink 대상 → rel_path. 못 찾으면 None."""
    # 섹션 앵커 제거
    target = raw_target.split("#")[0].strip()
    if not target:
        return None
    return index.get(target.lower())


# ── 메인 파싱 ──────────────────────────────────────────────────────────────

def parse_vault(
    vault_dir: Path,
    include_dirs: list[str],
    max_content_chars: int = 2000,
) -> tuple[list[dict], list[dict], list[dict]]:

    print(f"\n볼트: {vault_dir}")
    print("이름 인덱스 생성 중 …")
    name_index = build_name_index(vault_dir, include_dirs)
    print(f"  → {len(name_index):,}개 노트명 인덱싱 완료")

    nodes: list[dict] = []
    edges: list[dict] = []
    unresolved: list[dict] = []

    for sub in include_dirs:
        sub_dir = vault_dir / sub
        if not sub_dir.exists():
            print(f"  [SKIP] {sub}/ 없음", file=sys.stderr)
            continue

        md_files = sorted(sub_dir.rglob("*.md"))
        print(f"\n  {sub}/ — {len(md_files):,}개 파일 파싱 중 …")

        for path in md_files:
            rel = path.relative_to(vault_dir).as_posix()
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                print(f"    [ERR] {rel}: {e}", file=sys.stderr)
                continue

            meta, body = parse_frontmatter(text)

            # 폴더 버킷 (10 Maps, 20 Concepts, …)
            parts = Path(rel).parts
            folder = parts[1] if len(parts) > 2 else parts[0]

            node_id = slugify(path.stem)

            raw_links = extract_wikilinks(body)

            node = {
                "id": node_id,
                "title": meta.get("title") or path.stem,
                "path": rel,
                "folder": folder,
                "type": meta.get("type") or "",
                "status": meta.get("status") or "",
                "tags": as_list(meta.get("tags")),
                "aliases": as_list(meta.get("aliases")),
                "source_ids": as_list(meta.get("source_ids")),
                "created": date_str(meta.get("created")),
                "updated": date_str(meta.get("updated")),
                "content_preview": body[:max_content_chars].strip(),
                "char_count": len(body),
                "wikilink_count": len(raw_links),
            }
            nodes.append(node)

            for raw_target, ctx in raw_links:
                target_path = resolve_link(raw_target, name_index)
                if target_path:
                    edges.append({
                        "source": node_id,
                        "target": slugify(Path(target_path).stem),
                        "source_path": rel,
                        "target_path": target_path,
                        "context": ctx,
                    })
                else:
                    unresolved.append({
                        "source": node_id,
                        "source_path": rel,
                        "raw_target": raw_target,
                        "context": ctx,
                    })

    return nodes, edges, unresolved


# ── 출력 ───────────────────────────────────────────────────────────────────

def write_outputs(
    output_dir: Path,
    nodes: list[dict],
    edges: list[dict],
    unresolved: list[dict],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    # 엣지 중복 제거 (동일 source-target 쌍)
    seen: set[tuple[str, str]] = set()
    deduped: list[dict] = []
    for e in edges:
        key = (e["source"], e["target"])
        if key not in seen:
            seen.add(key)
            deduped.append(e)

    resolve_rate = len(edges) / max(len(edges) + len(unresolved), 1)

    stats = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "nodes": len(nodes),
        "edges_raw": len(edges),
        "edges_deduped": len(deduped),
        "unresolved_links": len(unresolved),
        "resolve_rate": f"{resolve_rate:.1%}",
        "node_types": count_by(nodes, "type"),
        "node_statuses": count_by(nodes, "status"),
        "folders": count_by(nodes, "folder"),
    }

    def write_json(name: str, data) -> None:
        (output_dir / name).write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    write_json("nodes.json", nodes)
    write_json("edges.json", deduped)
    write_json("unresolved.json", unresolved)
    write_json("stats.json", stats)

    print("\n── 결과 ───────────────────────────────────────────")
    print(f"  nodes.json      {len(nodes):>6,}개 노드")
    print(f"  edges.json      {len(deduped):>6,}개 엣지 (원본 {len(edges):,}개 중복 제거)")
    print(f"  unresolved.json {len(unresolved):>6,}개 깨진 링크")
    print(f"  resolve rate    {resolve_rate:.1%}")
    print(f"\n  출력 위치: {output_dir}")
    print("\n── 노드 유형 분포 ─────────────────────────────────")
    for k, v in stats["node_types"].items():
        label = k or "(없음)"
        print(f"  {label:<25} {v:>5,}")
    print("\n── 폴더별 노드 수 ─────────────────────────────────")
    for k, v in stats["folders"].items():
        print(f"  {k:<35} {v:>5,}")


# ── 진입점 ─────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Obsidian 볼트 → GraphRAG 노드/엣지 JSON 변환",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--vault",
        default=r"C:\Users\bboot\AIops\codex\karpathy-llm-wiki",
        help="Obsidian 볼트 루트 경로",
    )
    parser.add_argument(
        "--dirs",
        nargs="+",
        default=["wiki", "sources"],
        help="파싱할 하위 디렉토리",
    )
    parser.add_argument(
        "--output-dir",
        default=r"C:\Users\bboot\AIops\codex\graphrag_output",
        help="JSON 출력 디렉토리",
    )
    parser.add_argument(
        "--max-content-chars",
        type=int,
        default=2000,
        help="content_preview 최대 글자 수",
    )
    args = parser.parse_args()

    vault_dir = Path(args.vault)
    if not vault_dir.exists():
        print(f"볼트 없음: {vault_dir}", file=sys.stderr)
        sys.exit(1)

    nodes, edges, unresolved = parse_vault(
        vault_dir,
        args.dirs,
        max_content_chars=args.max_content_chars,
    )
    write_outputs(Path(args.output_dir), nodes, edges, unresolved)


if __name__ == "__main__":
    main()
