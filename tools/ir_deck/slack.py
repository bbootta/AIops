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

    def call(self, method: str, **params) -> dict:
        body = json.dumps(params).encode()
        req = urllib.request.Request(API + method, data=body, headers={
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json; charset=utf-8"})
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

    def get(self, method: str, **params) -> dict:
        """조회용 메서드는 form 인코딩 GET이 필요한 경우가 있다."""
        url = API + method + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.token}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read())
        if not data.get("ok"):
            raise SlackError(f"{method}: {data.get('error')}")
        return data

    def history(self, channel: str, oldest: str) -> list[dict]:
        """`oldest` 이후 최상위 메시지와 스레드 답글을 시간순으로 반환한다."""
        msgs, cursor = [], None
        while True:
            p = {"channel": channel, "oldest": oldest, "limit": 200}
            if cursor:
                p["cursor"] = cursor
            d = self.get("conversations.history", **p)
            msgs += d["messages"]
            cursor = d.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
        out = []
        for m in msgs:
            out.append(m)
            if m.get("reply_count"):
                r = self.get("conversations.replies", channel=channel, ts=m["ts"], oldest=oldest)
                out += [x for x in r["messages"] if x["ts"] != m["ts"] and float(x["ts"]) > float(oldest)]
        return sorted(out, key=lambda m: float(m["ts"]))

    def download(self, file_id: str) -> tuple[dict, bytes]:
        info = self.get("files.info", file=file_id)["file"]
        req = urllib.request.Request(info["url_private_download"],
                                     headers={"Authorization": f"Bearer {self.token}"})
        with urllib.request.urlopen(req, timeout=120) as r:
            return info, r.read()

    def upload(self, channel: str, thread_ts: str, filename: str, data: bytes,
               comment: str) -> tuple[str, str]:
        """파일을 스레드에 올리고 (file_id, permalink)를 반환한다."""
        u = self.get("files.getUploadURLExternal", filename=filename, length=len(data))
        req = urllib.request.Request(u["upload_url"], data=data, method="POST")
        urllib.request.urlopen(req, timeout=300).read()
        self.call("files.completeUploadExternal", files=[{"id": u["file_id"], "title": filename}],
                  channel_id=channel, thread_ts=thread_ts, initial_comment=comment)
        return u["file_id"], self.get("files.info", file=u["file_id"])["file"]["permalink"]

    def post(self, channel: str, text: str, thread_ts: str | None = None) -> None:
        p = {"channel": channel, "text": text}
        if thread_ts:
            p["thread_ts"] = thread_ts
        self.call("chat.postMessage", **p)

    def name(self, user_id: str) -> str:
        if user_id not in self._names:
            try:
                u = self.get("users.info", user=user_id)["user"]
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
