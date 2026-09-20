"""AI 리스크관리 업무요건 문서 세트(zip)에서 요건 76건(BR-NNN)을 추출해
risk_lib/regulatory/requirements_air.py 를 생성한다.

세트 안의 requirements.json 이 구조화 원장이라 HTML 을 긁지 않는다. 문서
세트는 저장소에 넣지 않고(고객 제공 문서) zip 과 구성 파일의 SHA-256 만 박는다.
v9.6.0 BRD(tools/gen_requirements.py)·기후(tools/gen_climate_requirements.py)와
같은 규약이다.

사용: python3 tools/gen_ai_risk_requirements.py <AI_Risk_Requirements_Package.zip>
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import zipfile
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "risk_lib/regulatory/requirements_air.py"
N_REQ = 76


def _title(rule: str) -> str:
    """규칙 첫 문장을 제목으로 쓴다. 세트에 짧은 제목 필드가 없다."""
    first = re.split(r"(?<=[.。])\s", rule.strip(), maxsplit=1)[0].rstrip(".。")
    return first if len(first) <= 70 else first[:69] + "…"


def _tables(sql: str) -> list[tuple[str, int]]:
    out = []
    for m in re.finditer(r"CREATE TABLE\s+([a-z_]+)\s*\((.*?)\n\);", sql, re.S | re.I):
        cols = [ln for ln in m.group(2).splitlines()
                if ln.strip() and not re.match(
                    r"\s*(CONSTRAINT|PRIMARY|FOREIGN|UNIQUE|CHECK|--)", ln, re.I)]
        out.append((m.group(1), len(cols)))
    return out


def main(src: str) -> None:
    raw = Path(src).read_bytes()
    with zipfile.ZipFile(src) as z:
        names = {n.split("/")[-1]: n for n in z.namelist() if not n.endswith("/")}
        read = lambda n: z.read(names[n])                         # noqa: E731
        reqs = json.loads(read("requirements.json"))
        manifest = json.loads(read("document_manifest.json"))
        sql = (read("ai_risk_schema.sql") + b"\n" + read("ai_risk_extensions.sql")).decode("utf-8")
        titles = {}
        for n in ("AI_Risk_Requirements_Overview.html", "AI_Risk_Practitioner_Manual.html"):
            m = re.search(r"<title>(.*?)</title>", read(n).decode("utf-8"), re.S)
            titles[n] = re.sub(r"\s+", " ", m.group(1)).strip()
        shas = {n: hashlib.sha256(read(n)).hexdigest() for n in names}

    assert len(reqs) == N_REQ, f"요건 {len(reqs)}건, {N_REQ}건이어야 한다 (세트가 바뀌었나?)"
    assert manifest["requirements"] == N_REQ
    tables = _tables(sql)
    assert len(tables) == manifest["entity_tables"], (len(tables), manifest["entity_tables"])

    chapters = sorted({r["chapter"] for r in reqs})
    chap = [(c.split(".", 1)[0].strip(), c.split(".", 1)[1].strip()) for c in chapters]

    lines = [
        '"""AI 리스크관리 업무요건 레지스터, tools/gen_ai_risk_requirements.py 생성.',
        "",
        "손으로 고치지 않는다. 원문 세트가 바뀌면 생성기를 다시 돌린다.",
        "요건은 세트의 requirements.json 에서 나오고, 개요·해설서 HTML 과 SQL·OpenAPI",
        "계약은 같은 세트의 구성 파일이라 함께 지문을 남긴다.",
        '"""',
        "",
        "# (역할, 파일 또는 문서 제목, SHA-256)",
        "SOURCES = (",
        f'    ("package", {Path(src).name.split("-", 1)[-1]!r}, "{hashlib.sha256(raw).hexdigest()}"),',
        f'    ("register", "requirements.json", "{shas["requirements.json"]}"),',
        f'    ("overview", {titles["AI_Risk_Requirements_Overview.html"]!r}, "{shas["AI_Risk_Requirements_Overview.html"]}"),',
        f'    ("manual", {titles["AI_Risk_Practitioner_Manual.html"]!r}, "{shas["AI_Risk_Practitioner_Manual.html"]}"),',
        f'    ("schema", "ai_risk_schema.sql + ai_risk_extensions.sql", "{shas["ai_risk_schema.sql"]}"),',
        f'    ("openapi", "ai_risk_openapi.json", "{shas["ai_risk_openapi.json"]}"),',
        ")",
        "SOURCE = SOURCES[3][1]",
        "SOURCE_SHA256 = SOURCES[3][2]",
        f'AS_OF = {manifest["as_of"]!r}',
        f'VERSION = {manifest["version"]!r}',
        f'N_API_PATHS = {int(manifest["api_paths"])}',
        "",
        "# (장 번호, 제목). 요건이 있는 장만 있다. 해설서의 나머지 장은 부록·계약이다.",
        "CHAPTERS = (",
    ]
    lines += [f"    ({no!r}, {t!r})," for no, t in chap]
    lines += [")", "", "# (id, 제목(규칙 첫 문장), 업권, 우선순위, 수용기준 수 = 샘플 인수조건 수)",
              "REQUIREMENTS = ("]
    for r in reqs:
        lines.append(f'    ({r["requirement_id"]!r}, {_title(r["rule"])!r}, \'공통\', '
                     f'{r["priority"]!r}, {1 if r.get("sample_acceptance") else 0}),')
    lines += [")", "", "# 요건 → 장 번호. 요건 ID 에 장이 없어 따로 둔다.", "CHAPTER_OF = {"]
    lines += [f'    {r["requirement_id"]!r}: {r["chapter"].split(".", 1)[0].strip()!r},' for r in reqs]
    lines += ["}", "", "# 참조 데이터 구조(엔티티 테이블 43장, 이름·컬럼 수). 이 하네스의 카탈로그에는",
              "# 아직 한 장도 없다. 등재 여부는 req_trace_air 가 판정한다.", "TABLES = ("]
    lines += [f"    ({n!r}, {k})," for n, k in tables]
    lines += [")", ""]
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"{OUT}: 요건 {len(reqs)}건 · 장 {len(chap)}개 · 원장 {len(tables)}장")


if __name__ == "__main__":
    main(sys.argv[1])
