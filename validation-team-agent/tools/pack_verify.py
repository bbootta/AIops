"""보고서 팩 재현성 자체검증 — "재현 가능" 주장을 실제로 증명한다.

CRO 요구사항은 *모든 산출값이 재현 가능*할 것이다. 지금까지 팩은 재현 방법
(입력 해시·정책 버전·재실행 명령)을 **기록**했지만, 그 기록이 실제로 맞는지는
아무도 검증하지 않았다. 본 도구가 그 마지막 고리를 채운다.

검증 단계:

1. **입력 재현 (fast)**: ``provenance.json`` 의 입력 조건(n/seed/stress 또는
   운영 추출 파일)으로 request 를 다시 만들어 df SHA-256 · 스칼라 SHA-256 이
   기록과 일치하는지 확인.
2. **정책 SSoT**: 현재 harness 정책 버전이 팩 생성 시점과 동일한지 확인
   (다르면 동일 입력이라도 판정이 달라질 수 있음 — 불일치는 경고가 아니라
   **검증 실패**로 취급).
3. **코드 리비전**: git rev 일치 여부.
4. **페이지 재빌드 (--deep)**: 팩 전체를 임시 디렉터리에 다시 만들어 페이지별
   SHA-256 을 대조. 생성 시각처럼 본질적으로 변하는 값은 정규화 후 비교.

운영 추출 파일 모드 팩은 원본 파일이 그대로 있어야 검증할 수 있다 (파일
SHA-256 으로 동일 파일 여부까지 확인). 파일이 없으면 해당 단계는 ``skipped``
로 보고하며 통과로 간주하지 않는다.

사용:
    python -m tools.pack_verify --pack reports/pack_1m_normal
    python -m tools.pack_verify --pack reports/pack_1m_normal --deep
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from pathlib import Path
from typing import Any

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

#: 재빌드 시 본질적으로 달라지는 값 — 페이지 해시 비교 전 정규화한다.
#: 입력(n/seed/stress)으로 결정되지 않는 값만 넣는다. 수치 결과를 여기에
#: 넣으면 검증이 무의미해지므로 추가 시 근거를 남길 것.
_VOLATILE = [
    (re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z"), "<TS>"),
    (re.compile(r"dirty=(yes|no)"), "dirty=<D>"),
    # 실행 시간 — 동일 입력이어도 머신 부하에 따라 달라지는 wall-clock
    (re.compile(r"<td>[\d.]+초</td>"), "<td><ELAPSED></td>"),
]

#: 누적 실행 로그(``logs/``)에서 파생되는 페이지. 선언된 입력이 아니라 그동안
#: 쌓인 로그에 의존하므로 재빌드 시 일치할 수 없다. 통과로 처리하지 않고
#: 별도 검사로 사유와 함께 보고한다.
LOG_DERIVED_PAGES = frozenset({
    "audit_timeseries.html",
    "findings_mapping.html",
    "governance_trend.html",
})


def normalize_page(html: str) -> str:
    """생성 시각 등 비결정 요소를 제거한 페이지 본문."""
    for pattern, replacement in _VOLATILE:
        html = pattern.sub(replacement, html)
    return html


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _check(name: str, passed: bool | None, detail: str) -> dict[str, Any]:
    status = "skipped" if passed is None else ("ok" if passed else "fail")
    return {"check": name, "status": status, "detail": detail}


def _rebuild_request(prov: dict) -> tuple[dict, list[dict]]:
    """provenance 입력 조건으로 request 재구성. (request, 추가 검사) 반환."""
    from tools.run_workflow_demo import build_request

    inputs = prov["inputs"]
    source = inputs.get("source")
    if not source:
        return build_request(inputs["n"], stress=inputs["stress"],
                             seed=inputs["seed"]), []

    from tools.provenance import file_sha256
    from tools.run_workflow_demo import build_request_from_file

    src_path = Path(source["input_file"])
    if not src_path.exists():
        raise FileNotFoundError(
            f"원천 파일 부재: {src_path} — 운영 추출 파일 모드 팩은 원본이 "
            "있어야 재현 검증이 가능하다")
    actual = file_sha256(src_path)
    file_check = _check(
        "원천 파일 SHA-256", actual == source["file_sha256"],
        f"{actual[:16]}… (기록 {source['file_sha256'][:16]}…)")
    salt = hashlib.sha256(
        f"vta-pack-salt-{inputs['seed']}".encode()).digest()
    request, _meta = build_request_from_file(
        src_path, source["mapping_file"], stress=inputs["stress"],
        pii_action=source["pii_action"], salt=salt)
    return request, [file_check]


def verify_pack(pack_dir: str | Path, *, deep: bool = False) -> dict[str, Any]:
    """팩의 재현성을 검증하고 검사별 결과를 반환한다."""
    from tools.provenance import git_info, policy_versions, request_fingerprint

    pack = Path(pack_dir)
    prov_path = pack / "provenance.json"
    if not prov_path.exists():
        return {
            "pack": str(pack), "passed": False,
            "checks": [_check("provenance.json 존재", False,
                              "팩에 기계 판독용 provenance 가 없다 — "
                              "R79 이전 팩이거나 provenance 없이 빌드됨")],
        }
    prov = json.loads(prov_path.read_text(encoding="utf-8"))
    checks: list[dict[str, Any]] = []

    # 1) 입력 재현
    try:
        request, extra = _rebuild_request(prov)
        checks.extend(extra)
    except FileNotFoundError as e:
        # 원천을 못 찾으면 재현성을 *증명할 수 없다* — 통과로 두지 않는다.
        checks.append(_check("입력 재현", False, str(e)))
        request = None
    if request is not None:
        fp_now = request_fingerprint(request)
        fp_rec = prov["inputs"]["fingerprint"]
        df_now = (fp_now.get("df") or {}).get("sha256", "-")
        df_rec = (fp_rec.get("df") or {}).get("sha256", "-")
        checks.append(_check(
            "입력 df SHA-256", df_now == df_rec,
            f"{df_now[:16]}… (기록 {df_rec[:16]}…)"))
        checks.append(_check(
            "입력 스칼라 SHA-256",
            fp_now["scalar_sha256"] == fp_rec["scalar_sha256"],
            f"{fp_now['scalar_sha256'][:16]}… "
            f"(기록 {fp_rec['scalar_sha256'][:16]}…)"))

    # 2) 정책 SSoT — 다르면 동일 입력이라도 판정이 달라진다
    pv_now = policy_versions()
    pv_rec = prov["policy_versions"]
    drifted = sorted(k for k in set(pv_now) | set(pv_rec)
                     if pv_now.get(k) != pv_rec.get(k))
    checks.append(_check(
        "정책 SSoT 버전", not drifted,
        "전부 일치" if not drifted else f"변경된 정책: {drifted}"))

    # 3) 코드 리비전
    git_now = git_info()
    git_rec = prov["git"]
    checks.append(_check(
        "git rev", git_now["rev"] == git_rec["rev"],
        f"{git_now['rev']} (기록 {git_rec['rev']})"))

    # 4) 페이지 재빌드 대조
    if deep and request is not None:
        checks.extend(_verify_pages(pack, prov, request))
    elif deep:
        checks.append(_check("페이지 재빌드 대조", None, "입력 재현 불가로 생략"))

    # fail 이 하나라도 있으면 실패. skipped 는 "설계상 검증 범위 밖"임을 사유와
    # 함께 밝힌 항목이므로 실패로 세지 않되, 요약에 건수를 드러낸다.
    return {
        "pack": str(pack),
        "passed": not any(c["status"] == "fail" for c in checks),
        "n_skipped": sum(1 for c in checks if c["status"] == "skipped"),
        "checks": checks,
    }


def _verify_pages(pack: Path, prov: dict, request: dict) -> list[dict[str, Any]]:
    """팩을 임시 디렉터리에 재빌드해 페이지별 정규화 해시를 대조.

    로그 파생 페이지는 선언된 입력으로 결정되지 않으므로 별도 검사로 분리해
    사유와 함께 보고한다 (통과로 처리하지 않는다).
    """
    from tools.report_pack import build_pack
    from tools.run_workflow_demo import run_demo

    inputs = prov["inputs"]
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        demo = run_demo(inputs["n"], inputs["stress"], inputs["seed"],
                        tmp_path / "logs", request=request)
        build_pack(demo, request, tmp_path / "pack", provenance=prov,
                   log_dir=tmp_path / "logs")
        mismatched: list[str] = []
        missing: list[str] = []
        deterministic = 0
        for original in sorted(pack.glob("*.html")):
            if original.name in LOG_DERIVED_PAGES:
                continue
            deterministic += 1
            rebuilt = tmp_path / "pack" / original.name
            if not rebuilt.exists():
                missing.append(original.name)
                continue
            a = _sha(normalize_page(original.read_text(encoding="utf-8")))
            b = _sha(normalize_page(rebuilt.read_text(encoding="utf-8")))
            if a != b:
                mismatched.append(original.name)

    present_log_pages = sorted(
        p.name for p in pack.glob("*.html") if p.name in LOG_DERIVED_PAGES)
    if missing or mismatched:
        main = _check(
            "페이지 재빌드 대조", False,
            f"입력 결정 {deterministic}개 중 불일치 {len(mismatched)}개 "
            f"{mismatched[:5]}, 미생성 {len(missing)}개 {missing[:5]}")
    else:
        main = _check(
            "페이지 재빌드 대조", True,
            f"입력 결정 {deterministic}개 페이지 전부 일치 "
            "(생성시각·실행시간 정규화 후)")
    log_check = _check(
        "로그 파생 페이지", None,
        f"{len(present_log_pages)}개 대조 제외 {present_log_pages} — "
        "누적 실행 로그에 의존하므로 선언된 입력(n/seed/stress)만으로는 "
        "재현되지 않는다. 재현이 필요하면 log_dir 스냅샷을 함께 보존할 것.")
    return [main, log_check]


def render_report(result: dict[str, Any]) -> str:
    lines = [f"재현성 검증: {result['pack']}", ""]
    mark = {"ok": "PASS", "fail": "FAIL", "skipped": "SKIP"}
    for c in result["checks"]:
        lines.append(f"[{mark[c['status']]}] {c['check']}: {c['detail']}")
    lines.append("")
    n_skip = result.get("n_skipped", 0)
    if result["passed"]:
        tail = (f"결과: 재현성 검증 통과 (검증 범위 밖 {n_skip}건 — SKIP 사유 확인)"
                if n_skip else "결과: 재현성 검증 통과")
    else:
        tail = "결과: 재현성 검증 실패 — 위 FAIL 항목 확인 필요"
    lines.append(tail)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="보고서 팩 재현성 자체검증 (입력 해시/정책/코드/페이지)")
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--deep", action="store_true",
                        help="팩을 재빌드해 페이지별 해시까지 대조 (느림)")
    parser.add_argument("--json", action="store_true",
                        help="결과를 JSON 으로 출력")
    args = parser.parse_args(argv)

    result = verify_pack(args.pack, deep=args.deep)
    if args.json:
        sys.stdout.write(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    else:
        sys.stdout.write(render_report(result) + "\n")
    return 0 if result["passed"] else 1


__all__ = ["verify_pack", "normalize_page", "render_report"]


if __name__ == "__main__":
    raise SystemExit(main())
