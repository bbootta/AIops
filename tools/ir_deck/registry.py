"""장표 버전 레지스트리: 업로드 자동 등록, 승인·반려·채택 명령, 취합 계획.

결정 원칙
- 버전은 파일명에서 읽고, 없으면 해당 장표의 다음 patch 버전을 자동 부여한다.
- 같은 장표·버전에 내용(sha256)이 다른 파일이 오면 거부한다. 기존 기록은 바뀌지 않는다.
- 승인은 업로더가 아닌 사람만 할 수 있다(4-Eyes). 채택은 승인된 버전만 가능하다.
- `취합`은 S01~S20 전부에 승인·채택본이 있어야 진행한다(fail-closed).
  `취합 초안`은 장표별 최신 비반려 버전으로 만들고 제출용이 아님을 표시한다.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

SLIDE_IDS = [f"S{i:02d}" for i in range(1, 21)]
FILE_RE = re.compile(r"^OLA_DCAMP9_(S\d{2})_.*\.pptx$", re.I)
VER_RE = re.compile(r"_v(\d+)\.(\d+)\.(\d+)(?=[_.])")
CMD_RE = re.compile(r"^\s*(승인|반려|채택)\s+(S\d{2})\s+v?(\d+\.\d+\.\d+)\s*(.*)$")
BUILD_RE = re.compile(r"^\s*취합(\s+초안)?\s*$")


@dataclass
class Version:
    slide_id: str
    version: str
    file_id: str
    filename: str
    sha256: str
    author: str
    uploaded_ts: str
    status: str = "초안"  # 초안 | 승인 | 반려 | 채택 | 대체
    reviewer: str = ""
    reviewed_ts: str = ""
    note: str = ""
    link: str = ""


@dataclass
class Build:
    build_id: str
    kind: str  # 제출 | 초안
    requested_by: str
    ts: str
    inputs: list[str]  # "S01@v1.0.0:F123:sha12"
    pptx_link: str = ""
    pdf_link: str = ""
    pages: int = 0
    result: str = ""


@dataclass
class Registry:
    cursor: str = "0"
    status_canvas: str = ""
    versions: list[Version] = field(default_factory=list)
    builds: list[Build] = field(default_factory=list)

    # ---------- 저장 ----------
    @classmethod
    def load(cls, path: Path) -> "Registry":
        if not path.exists():
            return cls()
        d = json.loads(path.read_text(encoding="utf-8"))
        return cls(d.get("cursor", "0"), d.get("status_canvas", ""),
                   [Version(**v) for v in d.get("versions", [])],
                   [Build(**b) for b in d.get("builds", [])])

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # ---------- 조회 ----------
    def of(self, slide_id: str) -> list[Version]:
        return [v for v in self.versions if v.slide_id == slide_id]

    def find(self, slide_id: str, version: str) -> Version | None:
        return next((v for v in self.of(slide_id) if v.version == version), None)

    def adopted(self, slide_id: str) -> Version | None:
        return next((v for v in self.of(slide_id) if v.status == "채택"), None)

    # ---------- 업로드 ----------
    def register_upload(self, filename: str, file_id: str, sha256: str, author: str, ts: str,
                        link: str = "") -> str:
        """업로드 1건을 등록하고 결과 메시지를 반환한다. 대상이 아니면 빈 문자열."""
        m = FILE_RE.match(filename)
        if not m:
            return ""
        sid = m.group(1).upper()
        if sid not in SLIDE_IDS:
            return f"{filename}: 장표 ID {sid}는 S01~S20 범위 밖이라 등록하지 않았습니다."
        if any(v.file_id == file_id for v in self.versions):
            return ""
        vm = VER_RE.search(filename)
        if vm:
            ver = ".".join(str(int(x)) for x in vm.groups())
            auto = ""
        else:
            ver = _next_patch([v.version for v in self.of(sid)])
            auto = " (파일명에 버전이 없어 자동 부여)"
        same = self.find(sid, ver)
        if same:
            if same.sha256 == sha256:
                return f"{sid} v{ver}: 이미 등록된 파일과 내용이 같아 새 버전을 만들지 않았습니다."
            return f"{sid} v{ver}: 같은 버전에 다른 내용이 있어 거부했습니다. 버전을 올려 다시 올려주세요."
        self.versions.append(Version(sid, ver, file_id, filename, sha256, author, ts, link=link))
        return f"{sid} v{ver} 초안으로 등록{auto}. 업로더가 아닌 검토자가 `승인 {sid} v{ver}`으로 승인합니다."

    # ---------- 명령 ----------
    def apply_command(self, text: str, user: str, ts: str) -> str:
        m = CMD_RE.match(text)
        if not m:
            return ""
        cmd, sid, ver, note = m.group(1), m.group(2).upper(), m.group(3), m.group(4).strip()
        v = self.find(sid, ver)
        if v is None:
            return f"{sid} v{ver}: 등록된 버전이 없습니다."
        if cmd in ("승인", "반려"):
            if user == v.author:
                return f"{sid} v{ver}: 업로더 본인은 {cmd}할 수 없습니다(4-Eyes)."
            if v.status not in ("초안", "반려", "승인"):
                return f"{sid} v{ver}: 현재 상태 {v.status}에서는 {cmd}할 수 없습니다."
            v.status, v.reviewer, v.reviewed_ts, v.note = cmd, user, ts, note
            return f"{sid} v{ver} {cmd} 기록."
        # 채택
        if v.status not in ("승인", "채택"):
            return f"{sid} v{ver}: 승인된 버전만 채택할 수 있습니다(현재 {v.status})."
        for other in self.of(sid):
            if other.status == "채택" and other is not v:
                other.status = "대체"
        v.status = "채택"
        return f"{sid} v{ver} 채택. 이전 채택본은 대체로 바뀌었습니다."

    # ---------- 취합 계획 ----------
    def plan(self, draft: bool) -> tuple[list[Version], list[str]]:
        """(입력 목록, 중단 사유) 반환. 제출용은 사유가 하나라도 있으면 빌드하지 않는다."""
        picks, problems = [], []
        for sid in SLIDE_IDS:
            if draft:
                cands = [v for v in self.of(sid) if v.status != "반려"]
                if cands:
                    picks.append(max(cands, key=lambda v: _vkey(v.version)))
            else:
                v = self.adopted(sid)
                if v is None:
                    problems.append(f"{sid} 채택본 없음")
                else:
                    picks.append(v)
        if draft and not picks:
            problems.append("등록된 장표가 없음")
        return picks, problems


def is_build_command(text: str) -> tuple[bool, bool]:
    """(취합 명령 여부, 초안 여부)."""
    m = BUILD_RE.match(text)
    return (bool(m), bool(m and m.group(1)))


def _vkey(ver: str) -> tuple[int, ...]:
    return tuple(int(x) for x in ver.split("."))


def _next_patch(existing: list[str]) -> str:
    if not existing:
        return "0.1.0"
    a, b, c = max(_vkey(v) for v in existing)
    return f"{a}.{b}.{c + 1}"
