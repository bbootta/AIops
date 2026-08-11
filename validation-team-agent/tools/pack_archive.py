"""보고서 팩 archiving — 분기별 누적 보존 + latest auto-prev resolve.

각 분기마다 새 팩을 생성할 때 다음을 자동화한다:

- ``<archive_root>/<label>/`` 형태로 보존 (label 기본: ``YYYY-MM-DDTHHMMSS``).
- ``<archive_root>/manifest.json`` 에 분기 인덱스 유지 (label / timestamp /
  팩 디렉터리 / 페이지 수 / SHA-256 등 메타데이터).
- N 개 초과 시 오래된 팩 자동 prune (FIFO).
- ``latest()`` API 로 가장 최근 팩 디렉터리 반환 — ``build_pack`` 의
  ``prev_pack_dir`` 자동 지정에 사용.

본 모듈은 read/write — 운영 데이터에 접근하지 않으며, 로컬 reports/
디렉터리만 다룬다. 저장된 팩은 인간 검증자가 직접 삭제할 수 있다 (CLAUDE.md
§5: 운영 시스템 파일 삭제는 안 함, 본 archive 는 reports/ 하위).
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

_INDEX_FILENAME = "manifest.json"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _default_label() -> str:
    """기본 archive label — UTC ISO 압축형."""
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _index_path(archive_root: Path) -> Path:
    return archive_root / _INDEX_FILENAME


def load_index(archive_root: str | Path) -> dict:
    """archive 인덱스 로드. 부재 시 빈 구조 반환."""
    p = _index_path(Path(archive_root))
    if not p.exists():
        return {"schema_version": "1.0", "entries": []}
    return json.loads(p.read_text(encoding="utf-8"))


def _save_index(archive_root: Path, index: dict) -> None:
    archive_root.mkdir(parents=True, exist_ok=True)
    _index_path(archive_root).write_text(
        json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_pack_metadata(pack_dir: Path) -> dict:
    """팩의 pack_manifest.json 에서 메타데이터 추출 (없으면 추정)."""
    pm = pack_dir / "pack_manifest.json"
    if pm.exists():
        data = json.loads(pm.read_text(encoding="utf-8"))
        return {
            "n_pages": data.get("n_pages"),
            "all_have_watermark": data.get("all_have_watermark"),
            "all_have_provenance": data.get("all_have_provenance"),
            "by_domain": data.get("by_domain", {}),
        }
    # 추정: HTML 페이지 수
    n_html = sum(1 for _ in pack_dir.glob("*.html"))
    return {"n_pages": n_html, "all_have_watermark": None,
            "all_have_provenance": None, "by_domain": {}}


def add(
    archive_root: str | Path,
    pack_dir: str | Path,
    *,
    label: str | None = None,
    stress: bool = False,
    notes: str | None = None,
    move: bool = False,
    keep: int | None = None,
) -> dict:
    """팩을 archive 에 등록 (복사 또는 이동).

    Args:
        archive_root: archive 디렉터리 (예: reports/archive)
        pack_dir: 등록할 팩 디렉터리 (index.html 등 포함)
        label: 폴더 이름 (기본: UTC ISO 압축)
        stress: 메타데이터 플래그
        notes: 자유 메모
        move: True 면 원본을 archive 로 이동, False 면 복사
        keep: 최근 N 개만 유지 — 초과 시 오래된 항목 prune

    반환: 새로 등록된 entry dict.
    """
    archive_root = Path(archive_root)
    pack_dir = Path(pack_dir)
    if not pack_dir.is_dir():
        raise FileNotFoundError(f"pack_dir not found: {pack_dir}")
    label = label or _default_label()
    target = archive_root / label
    if target.exists():
        raise FileExistsError(f"archive label already exists: {target}")

    archive_root.mkdir(parents=True, exist_ok=True)
    if move:
        shutil.move(str(pack_dir), str(target))
    else:
        shutil.copytree(str(pack_dir), str(target))

    meta = _read_pack_metadata(target)
    entry = {
        "label": label,
        "stored_at_utc": _utc_now_iso(),
        "path": str(target),
        "stress": bool(stress),
        "notes": notes,
        "meta": meta,
    }
    index = load_index(archive_root)
    index.setdefault("entries", []).append(entry)
    # 시간 역순 (latest first). 같은 timestamp 면 label 역순 tiebreak.
    index["entries"].sort(
        key=lambda e: (e["stored_at_utc"], e["label"]), reverse=True)
    _save_index(archive_root, index)
    if keep is not None and keep >= 0:
        _prune(archive_root, keep=keep)
    return entry


def _prune(archive_root: Path, *, keep: int) -> list[dict]:
    """오래된 항목을 keep 개수만 남기고 삭제. 반환: 삭제된 entry 목록."""
    index = load_index(archive_root)
    entries = index.get("entries", [])
    if len(entries) <= keep:
        return []
    # entries 는 latest first 이므로 [keep:] 가 오래된 것
    to_remove = entries[keep:]
    survivors = entries[:keep]
    for e in to_remove:
        p = Path(e["path"])
        if p.exists() and p.is_dir() and archive_root.resolve() in p.resolve().parents:
            shutil.rmtree(p)
    index["entries"] = survivors
    _save_index(archive_root, index)
    return to_remove


def latest(archive_root: str | Path,
           *, stress: bool | None = None) -> dict | None:
    """가장 최근 archive entry 반환. stress 필터 가능."""
    index = load_index(archive_root)
    for e in index.get("entries", []):
        if stress is None or e.get("stress") == stress:
            return e
    return None


def latest_pack_dir(archive_root: str | Path,
                    *, stress: bool | None = None) -> Path | None:
    e = latest(archive_root, stress=stress)
    if e is None:
        return None
    return Path(e["path"])


def list_entries(archive_root: str | Path) -> list[dict]:
    return load_index(archive_root).get("entries", [])


def main(argv: list[str] | None = None) -> int:
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="보고서 팩 archive 관리 — add/list/latest/prune")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="팩을 archive 에 등록")
    p_add.add_argument("--archive", type=Path, required=True)
    p_add.add_argument("--pack", type=Path, required=True)
    p_add.add_argument("--label", default=None)
    p_add.add_argument("--stress", action="store_true")
    p_add.add_argument("--notes", default=None)
    p_add.add_argument("--move", action="store_true")
    p_add.add_argument("--keep", type=int, default=None,
                       help="최근 N 개만 유지 (FIFO prune)")

    p_list = sub.add_parser("list", help="archive 의 entry 목록")
    p_list.add_argument("--archive", type=Path, required=True)
    p_list.add_argument("--json", action="store_true")

    p_lat = sub.add_parser("latest", help="가장 최근 entry 경로 출력")
    p_lat.add_argument("--archive", type=Path, required=True)
    p_lat.add_argument("--stress", action="store_true")

    p_prune = sub.add_parser("prune", help="최근 N 개만 남기고 prune")
    p_prune.add_argument("--archive", type=Path, required=True)
    p_prune.add_argument("--keep", type=int, required=True)

    args = parser.parse_args(argv)

    if args.cmd == "add":
        e = add(args.archive, args.pack, label=args.label,
                stress=args.stress, notes=args.notes,
                move=args.move, keep=args.keep)
        sys.stdout.write(json.dumps(e, ensure_ascii=False, indent=2) + "\n")
        return 0
    if args.cmd == "list":
        entries = list_entries(args.archive)
        if args.json:
            sys.stdout.write(json.dumps(entries, ensure_ascii=False, indent=2))
            sys.stdout.write("\n")
        else:
            sys.stdout.write("# Archive Entries\n\n")
            for e in entries:
                sys.stdout.write(
                    f"- {e['label']} ({e['stored_at_utc']}) "
                    f"stress={e['stress']} pages={e['meta'].get('n_pages', '?')}"
                    f" → {e['path']}\n")
        return 0
    if args.cmd == "latest":
        path = latest_pack_dir(args.archive,
                               stress=args.stress if args.stress else None)
        if path is None:
            sys.stderr.write("(no entries)\n")
            return 1
        sys.stdout.write(str(path) + "\n")
        return 0
    if args.cmd == "prune":
        removed = _prune(Path(args.archive), keep=args.keep)
        sys.stdout.write(f"pruned {len(removed)} entries\n")
        return 0
    return 2


__all__ = [
    "load_index", "add", "latest", "latest_pack_dir", "list_entries",
]


if __name__ == "__main__":
    raise SystemExit(main())
