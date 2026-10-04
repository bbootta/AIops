"""디캠프 9기 IR 덱 실행기: 버전 레지스트리, PPTX 병합, Slack 처리 흐름."""
import hashlib
import sys
from pathlib import Path

import pytest

pptx = pytest.importorskip("pptx")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pptx import Presentation  # noqa: E402
from pptx.chart.data import CategoryChartData  # noqa: E402
from pptx.enum.chart import XL_CHART_TYPE  # noqa: E402
from pptx.util import Inches  # noqa: E402

from ir_deck import run  # noqa: E402
from ir_deck.merge import MergeError, merge  # noqa: E402
from ir_deck.registry import SLIDE_IDS, Registry, is_build_command  # noqa: E402

FN = "OLA_DCAMP9_S09_BusinessModel_v0.1.0_20261004_JJ.pptx"


def _slide(path, title, layout=1, chart=False, notes=None, width=Inches(13.333), theme_tag=None):
    p = Presentation()
    p.slide_width, p.slide_height = width, Inches(7.5)
    s = p.slides.add_slide(p.slide_layouts[layout])
    s.shapes.title.text = title
    if chart:
        cd = CategoryChartData()
        cd.categories = ["A", "B"]
        cd.add_series("S", (1, 2))
        s.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(5), Inches(2), Inches(4), Inches(3), cd)
    if notes:
        s.notes_slide.notes_text_frame.text = notes
    if theme_tag:  # 다른 템플릿을 흉내 내려고 마스터 내용을 바꾼다
        p.slide_masters[0].name = theme_tag
    p.save(path)
    return Path(path)


# ---------- 레지스트리 ----------

def test_filename_version_and_auto_patch():
    r = Registry()
    assert "S09 v0.1.0 초안" in r.register_upload(FN, "F1", "a", "U1", "1")
    msg = r.register_upload("OLA_DCAMP9_S09_BM.pptx", "F2", "b", "U1", "2")
    assert "v0.1.1" in msg and "자동 부여" in msg
    assert r.register_upload("deck.pptx", "F3", "c", "U1", "3") == ""


def test_same_version_different_content_rejected():
    r = Registry()
    r.register_upload(FN, "F1", "a", "U1", "1")
    assert "거부" in r.register_upload(FN, "F2", "b", "U1", "2")
    assert "같아" in r.register_upload(FN, "F3", "a", "U1", "3")
    assert len(r.versions) == 1


def test_four_eyes_and_adopt_requires_approval():
    r = Registry()
    r.register_upload(FN, "F1", "a", "U1", "1")
    assert "채택할 수" in r.apply_command("채택 S09 v0.1.0", "U2", "2")
    assert "본인" in r.apply_command("승인 S09 v0.1.0", "U1", "3")
    assert "승인 기록" in r.apply_command("승인 S09 v0.1.0", "U2", "4")
    assert "채택" in r.apply_command("채택 S09 v0.1.0", "U2", "5")
    assert r.adopted("S09").reviewer == "U2"
    r.register_upload(FN.replace("v0.1.0", "v0.2.0"), "F2", "b", "U1", "6")
    r.apply_command("승인 S09 v0.2.0", "U3", "7")
    r.apply_command("채택 S09 v0.2.0", "U3", "8")
    assert r.find("S09", "0.1.0").status == "대체"
    assert r.adopted("S09").version == "0.2.0"


def test_plan_fail_closed_and_draft():
    r = Registry()
    r.register_upload(FN, "F1", "a", "U1", "1")
    picks, problems = r.plan(draft=False)
    assert len(problems) == 20 and not picks
    picks, problems = r.plan(draft=True)
    assert [v.slide_id for v in picks] == ["S09"] and not problems
    assert is_build_command("취합") == (True, False)
    assert is_build_command(" 취합 초안 ") == (True, True)
    assert is_build_command("취합해줘") == (False, False)


def test_registry_roundtrip(tmp_path):
    r = Registry()
    r.register_upload(FN, "F1", "a", "U1", "1", link="https://x")
    r.save(tmp_path / "r.json")
    assert Registry.load(tmp_path / "r.json").versions[0].link == "https://x"


# ---------- 병합 ----------

def test_merge_keeps_order_media_chart_notes_and_masters(tmp_path):
    a = _slide(tmp_path / "a.pptx", "S01", notes="노트1")
    b = _slide(tmp_path / "b.pptx", "S02", layout=5, chart=True, notes="노트2")
    c = _slide(tmp_path / "c.pptx", "S03", theme_tag="다른 템플릿")
    out = tmp_path / "out.pptx"
    assert merge([a, b, c], out) == 3
    p = Presentation(str(out))
    assert [s.shapes.title.text for s in p.slides] == ["S01", "S02", "S03"]
    assert any(sh.has_chart for sh in p.slides[1].shapes)
    assert p.slides[1].notes_slide.notes_text_frame.text == "노트2"
    assert len(p.slide_masters) == 2  # 같은 템플릿은 재사용, 다른 템플릿만 추가
    ids = [int(e.get("id")) for m in p.slide_masters for e in m._element.iter(
        "{http://schemas.openxmlformats.org/presentationml/2006/main}sldLayoutId")]
    assert len(ids) == len(set(ids))
    import zipfile
    names = zipfile.ZipFile(out).namelist()
    assert len(names) == len(set(names))  # 파트 이름 중복 없음


def test_merge_rejects_multi_slide_and_size_mismatch(tmp_path):
    a = _slide(tmp_path / "a.pptx", "S01")
    wide43 = _slide(tmp_path / "b.pptx", "S02", width=Inches(10))
    with pytest.raises(MergeError, match="화면 크기"):
        merge([a, wide43], tmp_path / "o.pptx")
    two = Presentation(str(a))
    two.slides.add_slide(two.slide_layouts[0])
    two.save(str(tmp_path / "two.pptx"))
    with pytest.raises(MergeError, match="1장"):
        merge([tmp_path / "two.pptx"], tmp_path / "o.pptx")


# ---------- Slack 처리 흐름 ----------

class FakeSlack:
    def __init__(self, messages, files):
        self.messages, self.files, self.posts, self.uploads = messages, files, [], []

    def history(self, channel, oldest):
        return [m for m in self.messages if float(m["ts"]) > float(oldest)]

    def download(self, file_id):
        return {"permalink": f"https://files/{file_id}"}, self.files[file_id]

    def post(self, channel, text, thread_ts=None):
        self.posts.append(text)

    def upload(self, channel, thread_ts, filename, data, comment):
        self.uploads.append(filename)
        return "FX", f"https://files/{filename}"


def test_process_end_to_end_draft_build(tmp_path, monkeypatch):
    files, msgs = {}, []
    for i, sid in enumerate(["S01", "S02"], start=1):
        path = _slide(tmp_path / f"{sid}.pptx", sid)
        files[f"F{i}"] = path.read_bytes()
        msgs.append({"ts": f"{i}.0", "user": "U1", "text": "",
                     "files": [{"id": f"F{i}", "name": f"OLA_DCAMP9_{sid}_X_v0.1.0.pptx"}]})
    msgs += [{"ts": "3.0", "user": "U1", "text": "승인 S01 v0.1.0"},
             {"ts": "4.0", "user": "U2", "text": "승인 S01 v0.1.0"},
             {"ts": "5.0", "user": "U2", "text": "취합"},
             {"ts": "6.0", "user": "U2", "text": "취합 초안"}]
    monkeypatch.setattr(run, "to_pdf", lambda p, d: p)  # LibreOffice 없이 흐름만 확인
    sl, reg = FakeSlack(msgs, files), Registry()
    assert run.process(sl, reg)
    assert reg.cursor == "6.0"
    assert any("본인" in p for p in sl.posts)
    assert reg.builds[0].result.startswith("중단") and "S02 채택본 없음" in reg.builds[0].result
    assert reg.builds[1].result == "성공" and reg.builds[1].pages == 2
    assert len(sl.uploads) == 2 and "DRAFT" in sl.uploads[0]
    assert reg.find("S01", "0.1.0").sha256 == hashlib.sha256(files["F1"]).hexdigest()
    md = run.render_status(reg, lambda u: u)
    assert "최신 취합본: **" in md and all(s in md for s in SLIDE_IDS)
    assert "—" not in md and "–" not in md


def test_pdf_conversion_when_libreoffice_available(tmp_path):
    """CI(IR_REQUIRE_PDF=1)에서는 LibreOffice로 실제 PDF 장수까지 확인한다."""
    import os
    import subprocess

    from ir_deck.merge import to_pdf

    out = tmp_path / "out.pptx"
    merge([_slide(tmp_path / "a.pptx", "S01"), _slide(tmp_path / "b.pptx", "S02", chart=True),
           _slide(tmp_path / "c.pptx", "S03", theme_tag="T2")], out)
    try:
        pdf = to_pdf(out, tmp_path)
    except (MergeError, OSError, subprocess.SubprocessError):
        if os.environ.get("IR_REQUIRE_PDF"):
            raise
        pytest.skip("LibreOffice 변환 불가 환경")
    info = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True).stdout
    assert "Pages:          3" in info
