"""산출물 이력 보관 — 리스크관리 팀에이전트 경로 / 기준일자 / 수행일자·버전.

제출물은 **기준일자마다 여러 판(version)** 이 생긴다. 최초 제출본, 지적 시정본,
재제출본이 모두 같은 기준일을 갖되 다른 산출물이다. 규제 보고에서 "어느 판을
제출했는가"는 감사 대상이므로, 덮어쓰지 않고 나란히 쌓아 둔다.

    teams/risk-management/         ← 리스크관리 팀에이전트(2선)의 활동 경로
      deliverables/
        2026-06-30/                ← 기준일자 (asof) — 규제 보고 기준일
          20260729_v01/            ← 수행일자 + 판
            01_datamodel/ … 07_independent_validation/
            MANIFEST.txt           각 파일의 SHA-256
            버전정보.json           이 판의 식별자·지문·검증 상태
          20260729_v02/
        이력.csv                    전 판의 목록 — **스캔해서 생성한다**
        이력.md

## 왜 저장소 루트가 아니라 팀 경로인가

이 저장소에는 조직이 셋 있다 — 산출(1선)·자체검증(2선)을 하는 **리스크관리
팀에이전트**, 독립 재계산을 하는 **적합성검증 팀에이전트**
(`claude/validation-team-agent-Pw9F5`), 내부심사를 하는 AIMS 심사자. 산출물을
저장소 루트에 두면 **누가 만든 판인지가 경로에 남지 않는다**. 3선 산출물과
2선 산출물이 섞이면 "독립"이라는 말이 무의미해진다. 제출본은 리스크관리
팀에이전트가 만든 것이므로 그 팀 경로 아래에 둔다.

## 왜 버전을 기준일자 안에서 세는가

수행일자로만 세면 같은 날 두 번 만든 것이 구분되지 않고, 전역 일련번호로 세면
기준일이 다른 판이 뒤섞인다. 규제 보고의 단위는 기준일이므로 `2026-06-30`의
1판·2판이 자연스럽다. 수행일자는 폴더명에 남겨 "언제 만들었나"를 잃지 않는다.

## 이력은 생성한다

`이력.csv`를 손으로 적으면 낡는다 — 이 저장소에서 그 유형이 다섯 번 났다
(독립검증 F-103·F-201·F-401·F-501·F-B02). 각 판이 스스로 `버전정보.json`을
남기고, 이력은 그것들을 **스캔해서** 만든다. 판을 지우면 이력에서도 사라진다.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import pandas as pd

# 리스크관리 팀에이전트(2선)의 활동 경로. 산출물은 반드시 이 아래에 쌓인다 —
# 경로 자체가 "누가 만든 판인가"의 기록이다.
TEAM_HOME = Path("teams/risk-management")
ARCHIVE_ROOT = TEAM_HOME / "deliverables"
VERSION_INFO = "버전정보.json"


@dataclass(frozen=True)
class VersionInfo:
    """한 판의 정체 — 이력은 이 파일들을 모아 만든다."""
    asof: str                 # 기준일자
    run_date: str             # 수행일자 (YYYY-MM-DD)
    version: int              # 기준일자 안에서의 판 번호
    seed: int
    request_id: str           # 독립검증 요청 식별자
    headline_digest: str      # 산출값 지문
    submission_digest: str    # 제출본(서식 전체) 지문
    gate_status: str          # 응답대기 · 적합 · 조건부 · 부적합
    n_forms: int
    n_form_lines: int
    n_form_checks_failed: int
    n_tables: int
    self_validation: dict     # PASS/WARN/FAIL 집계
    git_revision: str         # 이 판을 만든 코드 리비전
    created_at: str

    @property
    def label(self) -> str:
        return f"{self.run_date.replace('-', '')}_v{self.version:02d}"


def _git_revision() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "HEAD"],
                             capture_output=True, text=True, timeout=10)
        rev = out.stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"],
                               capture_output=True, text=True, timeout=10).stdout
        return rev + ("+dirty" if dirty.strip() else "") if rev else "(unknown)"
    except Exception:                                  # noqa: BLE001
        return "(unknown)"


def asof_dir(asof: str, root: Path | str = ARCHIVE_ROOT) -> Path:
    return Path(root) / asof


def next_version(asof: str, root: Path | str = ARCHIVE_ROOT) -> int:
    """이 기준일자의 다음 판 번호. 기존 판을 스캔해서 정한다."""
    d = asof_dir(asof, root)
    if not d.exists():
        return 1
    used = []
    for p in d.iterdir():
        if p.is_dir() and "_v" in p.name:
            try:
                used.append(int(p.name.rsplit("_v", 1)[1]))
            except ValueError:
                continue
    return max(used, default=0) + 1


def version_path(asof: str, run_date: str, version: int,
                 root: Path | str = ARCHIVE_ROOT) -> Path:
    return asof_dir(asof, root) / f"{run_date.replace('-', '')}_v{version:02d}"


# ---------------------------------------------------------------- 보관

def archive(result, portfolio, *, asof: str, root: Path | str = ARCHIVE_ROOT,
            run_date: str | None = None, seed: int = 42,
            zip_name: str | None = None) -> VersionInfo:
    """산출물 Pack을 기준일자/수행일자·판 경로에 만들고 버전정보를 남긴다.

    수행일자는 벽시계다 — 폴더명은 재현 대상이 아니고 "언제 만들었나"의 기록이다.
    **내용**은 seed·asof·코드 리비전이 같으면 비트 단위로 같다.
    """
    from risk_lib.deliverables import build_deliverables

    run_date = run_date or date.today().isoformat()
    version = next_version(asof, root)
    out = version_path(asof, run_date, version, root)
    # ZIP은 판 디렉터리 **바깥**에 떨어지므로(build_deliverables 규약) 판별
    # 이름을 준다. 고정 이름이면 v01의 ZIP을 v02가 덮어써 이력이 사라진다.
    label = f"{run_date.replace('-', '')}_v{version:02d}"
    built = build_deliverables(result, portfolio, out,
                               zip_name=zip_name or f"{label}.zip")

    # 요청서에서 식별자·지문을 읽는다 — 여기서 다시 계산하면 두 벌이 갈라진다.
    req_path = out / "07_independent_validation" / f"RUN-{asof.replace('-', '')}-{seed}.request.json"
    req = json.loads(req_path.read_text(encoding="utf-8")) if req_path.exists() else {}

    info = VersionInfo(
        asof=asof, run_date=run_date, version=version, seed=seed,
        request_id=req.get("request_id", ""),
        headline_digest=req.get("headline_digest", ""),
        submission_digest=req.get("submission_digest", ""),
        gate_status=str(built.get("independent_validation_status", "")),
        n_forms=int(built.get("n_forms", 0)),
        n_form_lines=int(built.get("n_form_lines", 0)),
        n_form_checks_failed=int(built.get("n_form_checks_failed", 0)),
        n_tables=int(built.get("n_tables", 0)),
        self_validation=req.get("self_validation", {}),
        git_revision=_git_revision(),
        created_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    (out / VERSION_INFO).write_text(
        json.dumps(asdict(info), ensure_ascii=False, indent=2), encoding="utf-8")
    return info


# ---------------------------------------------------------------- 이력

def scan(root: Path | str = ARCHIVE_ROOT) -> list[VersionInfo]:
    """보관된 판을 전부 읽는다 — 목록을 손으로 적지 않는다."""
    r = Path(root)
    if not r.exists():
        return []
    out = []
    for p in sorted(r.glob(f"*/*/{VERSION_INFO}")):
        try:
            out.append(VersionInfo(**json.loads(p.read_text(encoding="utf-8"))))
        except Exception:                              # noqa: BLE001
            continue
    return sorted(out, key=lambda v: (v.asof, v.version))


def ledger(root: Path | str = ARCHIVE_ROOT) -> pd.DataFrame:
    """이력 표 — 기준일자·판별로 무엇을 만들었고 검증이 어디까지 갔는가."""
    rows = []
    for v in scan(root):
        sv = v.self_validation or {}
        rows.append({
            "기준일자": v.asof, "판": f"v{v.version:02d}", "수행일자": v.run_date,
            "요청식별자": v.request_id, "게이트": v.gate_status,
            "서식": v.n_forms, "라인": v.n_form_lines,
            "서식검증실패": v.n_form_checks_failed, "테이블": v.n_tables,
            "자체검증": f"PASS {sv.get('PASS', 0)} · WARN {sv.get('WARN', 0)} "
                        f"· FAIL {sv.get('FAIL', 0)}",
            "산출지문": v.headline_digest[:16],
            "제출본지문": v.submission_digest[:16],
            "코드리비전": v.git_revision[:12],
            "경로": str(version_path(v.asof, v.run_date, v.version, root)),
        })
    return pd.DataFrame(rows)


def write_ledger(root: Path | str = ARCHIVE_ROOT) -> dict[str, Path]:
    """이력을 CSV·MD로 남긴다. 스캔 결과이므로 판을 지우면 함께 사라진다."""
    r = Path(root)
    r.mkdir(parents=True, exist_ok=True)
    df = ledger(root)
    csv = r / "이력.csv"
    df.to_csv(csv, index=False, encoding="utf-8-sig")

    md = r / "이력.md"
    lines = [
        "# 산출물 이력",
        "",
        "**이 파일은 스캔 결과다.** 각 판의 `버전정보.json`을 모아 만들며 손으로",
        "적지 않는다 — 손으로 적은 표는 낡는다(독립검증 F-501 유형).",
        "",
        "재생성: `python3 -c \"from risk_lib.archive import write_ledger;"
        " write_ledger()\"`",
        "",
    ]
    if df.empty:
        lines.append("_보관된 판이 없다._")
    else:
        cols = ["기준일자", "판", "수행일자", "요청식별자", "게이트",
                "서식", "라인", "서식검증실패", "자체검증", "제출본지문", "코드리비전"]
        lines += ["| " + " | ".join(cols) + " |",
                  "|" + "|".join("---" for _ in cols) + "|"]
        lines += ["| " + " | ".join(str(row[c]) for c in cols) + " |"
                  for _, row in df.iterrows()]
        lines += ["", f"판 {len(df)}건 · 기준일자 {df['기준일자'].nunique()}종"]
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"csv": csv, "md": md}
