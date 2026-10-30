"""최소 Slack Web API 클라이언트 (표준 라이브러리만 사용)."""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

API = "https://slack.com/api/"


class SlackError(RuntimeError):
    pass


class Slack:
    def __init__(self, token: str):
        self.token = token
        self._names: dict[str, str] = {}

    def _send(self, req: urllib.request.Request, method: str) -> dict:
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=60) as r:
                    data = json.loads(r.read())
            except urllib.error.HTTPError as e:
                if e.code == 429 and attempt < 3:
                    time.sleep(int(e.headers.get("Retry-After", "5")))
                    continue
                raise
            if not data.get("ok"):
                raise SlackError(f"{method}: {data.get('error')}")
            return data
        raise SlackError(f"{method}: rate limited")

    def call(self, method: str, **params) -> dict:
        """쓰기 메서드: JSON 본문."""
        req = urllib.request.Request(API + method, data=json.dumps(params).encode(), headers={
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json; charset=utf-8"})
        return self._send(req, method)

    def form(self, method: str, **params) -> dict:
        """조회 메서드: JSON 본문을 받지 않는 메서드가 있어 form 인코딩으로 보낸다."""
        req = urllib.request.Request(API + method, data=urllib.parse.urlencode(params).encode(), headers={
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/x-www-form-urlencoded"})
        return self._send(req, method)

    def _messages(self, method: str, **params) -> list[dict]:
        out, cursor = [], ""
        while True:
            d = self.form(method, **params, **({"cursor": cursor} if cursor else {}))
            out += d["messages"]
            cursor = d.get("response_metadata", {}).get("next_cursor", "")
            if not cursor:
                return out

    def new_messages(self, channel: str, after: str, lookback_days: int = 14) -> list[dict]:
        """`after` 이후 메시지를 시간순으로 반환한다.

        최상위 메시지와 함께, 최근 `lookback_days`일 안에 시작된 스레드에 새로 달린 답글도 넣는다.
        채널에도 보내기 한 답글은 양쪽에 나오므로 ts로 한 번만 남긴다.
        """
        oldest = f"{float(after) - lookback_days * 86400:.6f}"
        tops = self._messages("conversations.history", channel=channel, oldest=oldest, limit=200)
        found = {m["ts"]: m for m in tops if float(m["ts"]) > float(after)}
        for m in tops:
            if float(m.get("latest_reply", 0)) > float(after):
                for r in self._messages("conversations.replies", channel=channel, ts=m["ts"],
                                        oldest=after, limit=200):
                    if float(r["ts"]) > float(after):
                        found.setdefault(r["ts"], r)
        return sorted(found.values(), key=lambda m: float(m["ts"]))

    def info(self, file_id: str) -> dict:
        return self.form("files.info", file=file_id)["file"]

    def download(self, file_id: str) -> tuple[dict, bytes]:
        info = self.info(file_id)
        req = urllib.request.Request(info["url_private_download"],
                                     headers={"Authorization": f"Bearer {self.token}"})
        with urllib.request.urlopen(req, timeout=120) as r:
            if r.headers.get_content_type() == "text/html":  # 권한이 없으면 로그인 페이지가 온다
                raise SlackError(f"{info.get('name', file_id)}: 내려받기 권한 없음(봇이 채널에 있는지 확인)")
            return info, r.read()

    def upload(self, channel: str | None, thread_ts: str | None, filename: str, data: bytes,
               comment: str = "") -> tuple[str, str]:
        """파일을 올리고 (file_id, permalink)를 반환한다. 채널을 주지 않으면 봇만 보는 비공개 파일이 된다."""
        u = self.form("files.getUploadURLExternal", filename=filename, length=len(data))
        req = urllib.request.Request(u["upload_url"], data=data, method="POST",
                                     headers={"Content-Type": "application/octet-stream"})
        urllib.request.urlopen(req, timeout=300).read()
        share = {"channel_id": channel, "thread_ts": thread_ts, "initial_comment": comment}
        self.call("files.completeUploadExternal", files=[{"id": u["file_id"], "title": filename}],
                  **{k: v for k, v in share.items() if v})
        return u["file_id"], self.info(u["file_id"])["permalink"]

    def post(self, channel: str, text: str, thread_ts: str | None = None) -> None:
        p = {"channel": channel, "text": text}
        if thread_ts:
            p["thread_ts"] = thread_ts
        self.call("chat.postMessage", **p)

    def name(self, user_id: str) -> str:
        if user_id not in self._names:
            try:
                u = self.form("users.info", user=user_id)["user"]
                self._names[user_id] = u["profile"].get("display_name") or u.get("real_name") or user_id
            except SlackError:
                self._names[user_id] = user_id
        return self._names[user_id]

    def canvas_create(self, title: str, markdown: str) -> str:
        return self.call("canvases.create", title=title, document_content={
            "type": "markdown", "markdown": markdown})["canvas_id"]

    def canvas_replace_all(self, canvas_id: str, markdown: str) -> None:
        self.call("canvases.edit", canvas_id=canvas_id, changes=[{
            "operation": "replace", "document_content": {"type": "markdown", "markdown": markdown}}])

    def canvas_replace_section(self, canvas_id: str, contains_text: str, markdown: str) -> bool:
        d = self.call("canvases.sections.lookup", canvas_id=canvas_id,
                      criteria={"contains_text": contains_text})
        if not d.get("sections"):
            return False
        self.call("canvases.edit", canvas_id=canvas_id, changes=[{
            "operation": "replace", "section_id": d["sections"][0]["id"],
            "document_content": {"type": "markdown", "markdown": markdown}}])
        return True
