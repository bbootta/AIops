#!/usr/bin/env python3
"""Validate Obsidian wikilinks and source IDs in knowledge graph nodes."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GRAPH_DIR = ROOT / "knowledge_graph"
REGISTRY_PATH = GRAPH_DIR / "SOURCE_REGISTRY.md"

WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
SOURCE_ROW_RE = re.compile(r"^\| ([A-Z0-9-]+) \|", re.MULTILINE)
SOURCE_REF_RE = re.compile(r"source_refs:\n((?:  - [A-Z0-9-]+\n)+)")


def load_registry_ids() -> set[str]:
    text = REGISTRY_PATH.read_text(encoding="utf-8")
    ids = set(SOURCE_ROW_RE.findall(text))
    assert ids, "SOURCE_REGISTRY.md must contain source IDs"
    return ids


def parse_source_refs(text: str) -> list[str]:
    match = SOURCE_REF_RE.search(text)
    if not match:
        return []
    return [line.replace("  - ", "").strip() for line in match.group(1).splitlines()]


def main() -> None:
    assert GRAPH_DIR.exists(), "knowledge_graph directory is missing"
    registry_ids = load_registry_ids()
    nodes = {path.stem: path for path in GRAPH_DIR.glob("*.md")}
    assert "INDEX" in nodes and "SOURCE_REGISTRY" in nodes

    missing_links: list[str] = []
    missing_sources: list[str] = []
    sparse_nodes: list[str] = []

    for path in sorted(nodes.values()):
        text = path.read_text(encoding="utf-8")
        links = WIKILINK_RE.findall(text)
        for link in links:
            if link not in nodes:
                missing_links.append(f"{path.name} -> [[{link}]]")

        if path.stem not in {"INDEX", "SOURCE_REGISTRY"}:
            refs = parse_source_refs(text)
            if not refs:
                missing_sources.append(f"{path.name} has no source_refs")
            for ref in refs:
                if ref not in registry_ids:
                    missing_sources.append(f"{path.name} -> {ref}")
            if len(set(links)) < 3:
                sparse_nodes.append(f"{path.name} has fewer than 3 unique wikilinks")

    assert not missing_links, "Missing wikilink targets: " + "; ".join(missing_links)
    assert not missing_sources, "Missing or invalid source refs: " + "; ".join(missing_sources)
    assert not sparse_nodes, "Sparse graph nodes: " + "; ".join(sparse_nodes)
    print(f"validated {len(nodes)} knowledge graph nodes and {len(registry_ids)} source IDs")


if __name__ == "__main__":
    main()

