"""디캠프 9기 IR 덱 자동 버전관리·취합 실행기.

GitHub Actions가 주기적으로 실행한다. 한 번 실행할 때마다:
1. Slack에 봇 비공개 파일로 둔 상태(레지스트리)를 읽는다. 저장소가 공개라서 상태는 커밋하지 않는다.
2. 채널의 새 메시지를 시간순으로 읽는다(최근 스레드의 새 답글 포함).
3. 규칙 파일명(OLA_DCAMP9_Sxx_...pptx) 업로드는 버전으로 자동 등록한다.
4. `승인|반려|채택 Sxx vX.Y.Z` 명령을 처리한다(4-Eyes).
5. `취합` 또는 `취합 초안` 명령이 있으면 병합본 PPTX·PDF를 만들어 스레드에 올린다.
   봇·워크플로(취합 버튼) 메시지는 이 명령만 받는다. 업로드·승인은 사람 메시지만 받는다.
6. 현황 캔버스를 다시 그리고, 메인 캔버스의 `최신 취합본:` 줄을 갱신한다.
7. 바뀐 상태를 새 비공개 파일로 올리고 이전 상태 파일은 지운다.

환경변수: SLACK_BOT_TOKEN, IR_CHANNEL, IR_MAIN_CANVAS, IR_STATE_PATH(작업 사본 경로),
IR_PDF_READY(0이면 취합 명령 앞에서 멈춤), IR_BOOTSTRAP(1이면 상태 파일 없이 새로 시작), IR_START_TS
"""
from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ir_deck.merge import check_single, merge, to_pdf  # noqa: E402
from ir_deck.registry import FILE_RE, SLIDE_IDS, Build, Registry, is_build_command  # noqa: E402
from ir_deck.slack import Slack, SlackError  # noqa: E402

KST = timezone(timedelta(hours=9))
STATUS_TITLE = "디캠프 9기 IR 버전·취합 현황 (자동)"
STATE_NAME = "ir_deck_state.json"
CHANNEL = os.environ.get("IR_CHANNEL", "C0BK4SCJUBV")
# 워크플로 첫 단계는 0으로 돈다. 취합 명령을 만나면 멈추고, LibreOffice를 설치한 다음 단계가 이어서 처리한다.
PDF_READY = os.environ.get("IR_PDF_READY", "1") == "1"


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
    build = Build(bid, "초안" if draft else "제출", msg.get("user") or msg.get("bot_id", ""), msg["ts"],
                  [f"{v.slide_id}@v{v.version}:{v.file_id}:{v.sha256[:12]}" for v in picks])
    reg.builds.append(build)
    if problems:
        build.result = "중단: " + ", ".join(problems)
        return f"{bid} 취합 중단(직전 성공본 유지). 사유: " + ", ".join(problems)
    thread = msg.get("thread_ts", msg["ts"])
    try:  # 실패 빌드는 기록만 남기고 직전 성공본은 그대로 둔다
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            paths = []
            for v in picks:
                try:
                    _, data = sl.download(v.file_id)
                except Exception as e:
                    raise RuntimeError(f"{v.slide_id} v{v.version} 내려받기 실패({e})") from e
                if hashlib.sha256(data).hexdigest() != v.sha256:
                    build.result = f"중단: {v.slide_id} v{v.version} 파일 내용이 등록 시점과 다름"
                    return f"{bid} {build.result}"
                p = d / f"{v.slide_id}.pptx"
                p.write_bytes(data)
                paths.append(p)
            out = d / f"OLA_DCAMP9_IR_{'DRAFT' if draft else 'FINAL'}_{bid}.pptx"
            pages = merge(paths, out)
            pdf = to_pdf(out, d)
            note = "제출용 아님(초안 취합)" if draft else "S01~S20 채택본 취합"
            _, pptx_link = sl.upload(CHANNEL, thread, out.name, out.read_bytes(), f"{bid} PPTX · {note}")
            _, pdf_link = sl.upload(CHANNEL, thread, pdf.name, pdf.read_bytes(), f"{bid} PDF")
    except Exception as e:
        build.result = f"실패: {e}"
        return f"{bid} 취합 실패(직전 성공본 유지): {e}"
    build.pages, build.pptx_link, build.pdf_link, build.result = pages, pptx_link, pdf_link, "성공"
    return f"{bid} 취합 완료, {pages}장. 입력: " + ", ".join(i.split(":")[0] for i in build.inputs)


def handle(sl: Slack, reg: Registry, m: dict, replies: list[str]) -> None:
    """메시지 1건의 업로드·명령을 처리하고 답글을 `replies`에 쌓는다."""
    text, user = m.get("text", ""), m.get("user", "")
    human = not m.get("bot_id")  # 봇이 대신 올린 승인은 누가 했는지 알 수 없어 받지 않는다(4-Eyes)
    for f in m.get("files", []) if human else []:
        name = f.get("name") or sl.info(f["id"]).get("name", "")
        if not FILE_RE.match(name):
            continue
        info, data = sl.download(f["id"])
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / Path(name).name
            p.write_bytes(data)
            try:
                check_single(p)
            except Exception as e:
                replies.append(f"등록 거부, {e}")
                continue
        r = reg.register_upload(name, f["id"], hashlib.sha256(data).hexdigest(), user, m["ts"],
                                info.get("permalink", ""))
        if r:
            replies.append(r)
    r = reg.apply_command(text, user, m["ts"]) if human else ""
    if r:
        replies.append(r)
    is_build, draft = is_build_command(text)
    if is_build:
        replies.append(do_build(sl, reg, m, draft))


def process(sl: Slack, reg: Registry, me: frozenset[str] = frozenset()) -> tuple[bool, bool]:
    """새 메시지를 처리한다. (상태 변경 여부, PDF 도구가 없어 취합 명령 앞에서 멈췄는지)를 반환한다."""
    changed = False
    for m in sl.new_messages(CHANNEL, reg.cursor):
        mine = m.get("user") in me or m.get("bot_id") in me
        if not mine and not PDF_READY and is_build_command(m.get("text", ""))[0]:
            return changed, True
        reg.cursor, changed = m["ts"], True
        if mine:  # 실행기 자신의 답글·업로드
            continue
        replies: list[str] = []
        try:
            handle(sl, reg, m, replies)
        except Exception as e:  # 한 메시지의 오류가 나머지 메시지 처리와 상태 저장을 막지 않게 한다
            replies.append(f"처리 중 오류로 건너뛰었습니다. 다시 올리거나 명령을 다시 보내 주세요: {e}")
        for r in replies:
            sl.post(CHANNEL, r, thread_ts=m.get("thread_ts", m["ts"]))
    return changed, False


def state_files(sl: Slack, bot_user: str) -> list[str]:
    """봇이 올린 상태 파일 ID, 최신순."""
    fs = [f for f in sl.form("files.list", user=bot_user, count=100)["files"] if f.get("name") == STATE_NAME]
    return [f["id"] for f in sorted(fs, key=lambda f: f.get("created", 0), reverse=True)]


def main() -> int:
    sl = Slack(os.environ["SLACK_BOT_TOKEN"])
    auth = sl.form("auth.test")
    me = frozenset(x for x in (auth.get("user_id"), auth.get("bot_id")) if x)
    path = Path(os.environ.get("IR_STATE_PATH", STATE_NAME))
    olds = state_files(sl, auth["user_id"])
    if not path.exists():  # 같은 실행의 두 번째 단계는 첫 단계가 남긴 작업 사본을 이어 쓴다
        if olds:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(sl.download(olds[0])[1])
        elif os.environ.get("IR_BOOTSTRAP") != "1":
            print("Slack에서 상태 파일을 찾지 못했습니다. 첫 실행이면 Run workflow에서 bootstrap을 켜세요.",
                  file=sys.stderr)
            return 1
    saved = path.read_bytes() if path.exists() else b""
    reg = Registry.load(path)
    if reg.cursor == "0":  # 첫 실행: 과거 메시지는 처리하지 않는다
        reg.cursor = os.environ.get("IR_START_TS", f"{datetime.now(timezone.utc).timestamp():.6f}")
    before = reg.builds[-1].build_id if reg.builds else ""
    deferred = False
    try:
        changed, deferred = process(sl, reg, me)
        if not reg.status_canvas:
            reg.status_canvas = sl.canvas_create(STATUS_TITLE, render_status(reg, sl.name))
            sl.call("canvases.access.set", canvas_id=reg.status_canvas, access_level="read",
                    channel_ids=[CHANNEL])
            sl.post(CHANNEL, f"버전·취합 현황 캔버스를 만들었습니다: {sl.info(reg.status_canvas)['permalink']}")
        elif changed:
            sl.canvas_replace_all(reg.status_canvas, render_status(reg, sl.name))
        main_canvas = os.environ.get("IR_MAIN_CANVAS")
        if main_canvas and (reg.builds[-1].build_id if reg.builds else "") != before:
            try:
                if not sl.canvas_replace_section(main_canvas, "최신 취합본:", latest_line(reg)):
                    print("메인 캔버스에서 '최신 취합본:' 줄을 찾지 못함", file=sys.stderr)
            except SlackError as e:  # 메인 캔버스 편집 권한이 없으면 현황 캔버스만 갱신된다
                print(f"메인 캔버스 갱신 실패: {e}", file=sys.stderr)
    finally:
        reg.save(path)
        if path.read_bytes() != saved or not olds:
            sl.upload(None, None, STATE_NAME, path.read_bytes())
            for fid in olds:
                try:
                    sl.form("files.delete", file=fid)
                except SlackError as e:  # 남은 이전 파일은 최신순 선택이라 동작에 영향 없음
                    print(f"이전 상태 파일 삭제 실패: {e}", file=sys.stderr)
    if not olds:  # 처음 올린 상태 파일을 다음 실행이 찾을 수 있는지 확인한다
        for _ in range(5):
            if state_files(sl, auth["user_id"]):
                break
            time.sleep(3)
        else:
            print("올린 상태 파일이 files.list에 보이지 않아 다음 실행이 상태를 잇지 못합니다.", file=sys.stderr)
            return 1
    if deferred and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as f:
            f.write("needs_pdf=true\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
