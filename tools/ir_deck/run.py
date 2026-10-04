"""디캠프 9기 IR 덱 자동 버전관리·취합 실행기.

GitHub Actions가 주기적으로 실행한다. 한 번 실행할 때마다:
1. 채널의 새 메시지를 시간순으로 읽는다.
2. 규칙 파일명(OLA_DCAMP9_Sxx_...pptx) 업로드는 버전으로 자동 등록한다.
3. `승인|반려|채택 Sxx vX.Y.Z` 명령을 처리한다(4-Eyes).
4. `취합` 또는 `취합 초안` 명령이 있으면 병합본 PPTX·PDF를 만들어 스레드에 올린다.
5. 현황 캔버스를 다시 그리고, 메인 캔버스의 `최신 취합본:` 줄을 갱신한다.
6. 레지스트리(JSON)를 저장한다. 워크플로가 저장소에 커밋한다.

환경변수: SLACK_BOT_TOKEN, IR_CHANNEL, IR_MAIN_CANVAS, IR_REGISTRY
"""
from __future__ import annotations

import hashlib
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ir_deck.merge import check_single, merge, to_pdf  # noqa: E402
from ir_deck.registry import SLIDE_IDS, Build, Registry, is_build_command  # noqa: E402
from ir_deck.slack import Slack  # noqa: E402

KST = timezone(timedelta(hours=9))
STATUS_TITLE = "디캠프 9기 IR 버전·취합 현황 (자동)"


def kst(ts: str) -> str:
    return datetime.fromtimestamp(float(ts), KST).strftime("%Y-%m-%d %H:%M")


def render_status(reg: Registry, name) -> str:
    rows = ["| 장표 | 채택 버전 | 최신 버전·상태 | 업로더 | 승인자 |", "| --- | --- | --- | --- | --- |"]
    for sid in SLIDE_IDS:
        a = reg.adopted(sid)
        vs = reg.of(sid)
        last = max(vs, key=lambda v: tuple(map(int, v.version.split(".")))) if vs else None
        rows.append("| {} | {} | {} | {} | {} |".format(
            sid,
            f"[v{a.version}]({a.link})" if a and a.link else (f"v{a.version}" if a else "없음"),
            f"v{last.version} · {last.status}" if last else "미등록",
            name(last.author) if last else "없음",
            name(a.reviewer) if a else "없음"))
    hist = ["| 장표 | 버전 | 파일명·ID | sha256 | 업로더·시각 | 검토자·시각 | 상태·비고 |",
            "| --- | --- | --- | --- | --- | --- | --- |"]
    for v in sorted(reg.versions, key=lambda v: (v.slide_id, tuple(map(int, v.version.split("."))))):
        hist.append(f"| {v.slide_id} | v{v.version} | {v.filename}<br>{v.file_id} | {v.sha256[:12]} | "
                    f"{name(v.author)}<br>{kst(v.uploaded_ts)} | "
                    f"{name(v.reviewer) if v.reviewer else '없음'}<br>{kst(v.reviewed_ts) if v.reviewed_ts else ''} | "
                    f"{v.status}{(' · ' + v.note) if v.note else ''} |")
    builds = ["| 빌드 ID | 구분 | 요청자·시각 | 입력(장표@버전) | PPTX | PDF | 장수 | 결과 |",
              "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for b in reversed(reg.builds):
        builds.append(f"| {b.build_id} | {b.kind} | {name(b.requested_by)}<br>{kst(b.ts)} | "
                      f"{'<br>'.join(i.split(':')[0] for i in b.inputs) or '없음'} | "
                      f"{f'[PPTX]({b.pptx_link})' if b.pptx_link else '없음'} | "
                      f"{f'[PDF]({b.pdf_link})' if b.pdf_link else '없음'} | {b.pages} | {b.result} |")
    return "\n".join([
        "이 캔버스는 실행기가 매 실행마다 다시 씁니다. 직접 수정한 내용은 덮어써집니다.",
        "",
        "## 최신 취합본",
        "",
        latest_line(reg),
        "",
        "## 사용 방법",
        "",
        "- 업로드: 채널에 `OLA_DCAMP9_S09_BusinessModel_v0.2.0_20261005_JJ.pptx` 형식 1슬라이드 파일 업로드, 자동으로 초안 등록",
        "- 버전 미기재 파일: 해당 장표의 다음 patch 버전 자동 부여",
        "- 승인·반려: `승인 S09 v0.2.0` / `반려 S09 v0.2.0 사유`, 업로더 본인은 불가",
        "- 채택: `채택 S09 v0.2.0`, 승인된 버전만 가능, 이전 채택본은 대체 처리",
        "- 취합: `취합` (S01~S20 채택본 전부 필요, 누락 시 중단) / `취합 초안` (장표별 최신 비반려본, 제출용 아님)",
        "- 반영 주기: 약 10분마다 실행, 결과는 명령 메시지의 스레드에 답글",
        "",
        "## 장표별 채택 현황",
        "",
        *rows,
        "",
        "## 버전 이력",
        "",
        *(hist if len(hist) > 2 else hist + ["| 없음 | | | | | | |"]),
        "",
        "## 취합본 빌드 이력",
        "",
        *(builds if len(builds) > 2 else builds + ["| 없음 | | | | | | | |"]),
    ])


def latest_line(reg: Registry) -> str:
    ok = [b for b in reg.builds if b.pptx_link]
    if not ok:
        return "최신 취합본: 아직 없음"
    b = ok[-1]
    return (f"최신 취합본: **{b.build_id}** ({b.kind}, {kst(b.ts)} KST, {b.pages}장) · "
            f"[PPTX 다운로드]({b.pptx_link}) · [PDF 다운로드]({b.pdf_link or b.pptx_link})")


def do_build(sl: Slack, reg: Registry, msg: dict, draft: bool) -> str:
    picks, problems = reg.plan(draft)
    stem = f"B{datetime.fromtimestamp(float(msg['ts']), KST):%Y%m%d-%H%M}"
    bid = f"{stem}-{sum(1 for b in reg.builds if b.build_id.startswith(stem)) + 1}"
    build = Build(bid, "초안" if draft else "제출", msg.get("user", ""), msg["ts"],
                  [f"{v.slide_id}@v{v.version}:{v.file_id}:{v.sha256[:12]}" for v in picks])
    reg.builds.append(build)
    if problems:
        build.result = "중단: " + ", ".join(problems)
        return f"{bid} 취합 중단(직전 성공본 유지). 사유: " + ", ".join(problems)
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        paths = []
        for v in picks:
            _, data = sl.download(v.file_id)
            if hashlib.sha256(data).hexdigest() != v.sha256:
                build.result = f"중단: {v.slide_id} v{v.version} 파일 내용이 등록 시점과 다름"
                return f"{bid} {build.result}"
            p = d / f"{v.slide_id}.pptx"
            p.write_bytes(data)
            paths.append(p)
        tag = "DRAFT" if draft else "FINAL"
        out = d / f"OLA_DCAMP9_IR_{tag}_{bid}.pptx"
        try:
            build.pages = merge(paths, out)
            pdf = to_pdf(out, d)
        except Exception as e:  # 실패 빌드는 기록만 남기고 직전 성공본은 그대로 둔다
            build.result = f"실패: {e}"
            return f"{bid} 취합 실패(직전 성공본 유지): {e}"
        note = "제출용 아님(초안 취합)" if draft else "S01~S20 채택본 취합"
        _, build.pptx_link = sl.upload(CHANNEL, msg["ts"], out.name, out.read_bytes(), f"{bid} PPTX · {note}")
        _, build.pdf_link = sl.upload(CHANNEL, msg["ts"], pdf.name, pdf.read_bytes(), f"{bid} PDF")
    build.result = "성공"
    return f"{bid} 취합 완료, {build.pages}장. 입력: " + ", ".join(i.split(":")[0] for i in build.inputs)


def process(sl: Slack, reg: Registry) -> bool:
    changed = False
    for m in sl.history(CHANNEL, reg.cursor):
        reg.cursor = m["ts"]
        changed = True
        if m.get("bot_id"):
            continue
        replies = []
        for f in m.get("files", []):
            name = f.get("name", "")
            if not name.lower().endswith(".pptx") or not name.upper().startswith("OLA_DCAMP9_"):
                continue
            info, data = sl.download(f["id"])
            with tempfile.NamedTemporaryFile(suffix=".pptx") as t:
                t.write(data)
                t.flush()
                try:
                    check_single(Path(t.name))
                except Exception as e:
                    replies.append(f"{name}: 등록 거부, {e}")
                    continue
            r = reg.register_upload(name, f["id"], hashlib.sha256(data).hexdigest(),
                                    m.get("user", ""), m["ts"], info.get("permalink", ""))
            if r:
                replies.append(r)
        text = m.get("text", "")
        r = reg.apply_command(text, m.get("user", ""), m["ts"])
        if r:
            replies.append(r)
        is_build, draft = is_build_command(text)
        if is_build:
            replies.append(do_build(sl, reg, m, draft))
        for r in replies:
            sl.post(CHANNEL, r, thread_ts=m.get("thread_ts", m["ts"]))
    return changed


def main() -> int:
    sl = Slack(os.environ["SLACK_BOT_TOKEN"])
    path = Path(os.environ.get("IR_REGISTRY", "deliverables/ir_deck/dcamp9/registry.json"))
    reg = Registry.load(path)
    if reg.cursor == "0":  # 첫 실행: 과거 메시지는 처리하지 않는다
        reg.cursor = os.environ.get("IR_START_TS", f"{datetime.now(timezone.utc).timestamp():.6f}")
    before = reg.builds[-1].build_id if reg.builds else ""
    changed = process(sl, reg)
    md = render_status(reg, sl.name)
    if not reg.status_canvas:
        reg.status_canvas = sl.canvas_create(STATUS_TITLE, md)
        sl.call("canvases.access.set", canvas_id=reg.status_canvas, access_level="read",
                channel_ids=[CHANNEL])
        link = sl.get("files.info", file=reg.status_canvas)["file"]["permalink"]
        sl.post(CHANNEL, f"버전·취합 현황 캔버스를 만들었습니다: {link}")
    elif changed:
        sl.canvas_replace_all(reg.status_canvas, md)
    after = reg.builds[-1].build_id if reg.builds else ""
    if after != before and os.environ.get("IR_MAIN_CANVAS"):
        if not sl.canvas_replace_section(os.environ["IR_MAIN_CANVAS"], "최신 취합본:", latest_line(reg)):
            print("메인 캔버스에서 '최신 취합본:' 줄을 찾지 못함", file=sys.stderr)
    reg.save(path)
    return 0


CHANNEL = os.environ.get("IR_CHANNEL", "C0BK4SCJUBV")

if __name__ == "__main__":
    sys.exit(main())
