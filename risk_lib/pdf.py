"""Minimal pure-Python PDF generator for the executive summary.

No external dependencies — writes a multi-page text-based PDF in raw spec.
Layout is intentionally simple (single-column with section headers, KPI
table, key tables) so the output is readable as an email-attachable
single-file deliverable.

The HTML report stays the canonical visual; PDF is the leave-behind copy.
"""

from __future__ import annotations

import io
import zlib
from dataclasses import dataclass
from typing import Any


# ---------------------------------------------------------------- PDF primitives

def _escape(s: str) -> str:
    """PDF string escaping for ASCII / latin-1 strings."""
    return (str(s).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)"))


class _PDFWriter:
    """Minimal PDF 1.4 producer.

    Korean text is shown via the standard Korean CJK encoding (UniKS-UTF16-H)
    with the Adobe-Korea1 character collection so the resulting file renders
    Hangul in Adobe Acrobat / browser PDF viewers without bundling a font.
    """

    PAGE_W = 595      # A4
    PAGE_H = 842
    MARGIN = 50

    def __init__(self):
        self.objects: list[bytes] = []          # 1-indexed; objects[0] is reserved
        self.objects.append(b"")
        self.pages: list[int] = []              # object ids of /Page objects
        self.content_streams: list[list[str]] = [[]]

    # ---- objects ----
    def _add(self, body: bytes) -> int:
        self.objects.append(body)
        return len(self.objects) - 1

    # ---- font ----
    def _ensure_font(self) -> dict[str, int]:
        if hasattr(self, "_font_ids"):
            return self._font_ids
        # CIDFont + Type 0 wrapper using HYSMyeongJo-Medium (built into Acrobat)
        descendant = self._add(
            b"<< /Type /Font /Subtype /CIDFontType0 "
            b"/BaseFont /HYSMyeongJo-Medium "
            b"/CIDSystemInfo << /Registry (Adobe) /Ordering (Korea1) /Supplement 1 >> "
            b">>"
        )
        kor = self._add(
            (f"<< /Type /Font /Subtype /Type0 /BaseFont /HYSMyeongJo-Medium "
             f"/Encoding /UniKS-UTF16-H /DescendantFonts [{descendant} 0 R] >>"
            ).encode("latin-1")
        )
        latin = self._add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        bold = self._add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>")
        self._font_ids = {"kor": kor, "lat": latin, "bold": bold}
        return self._font_ids

    # ---- drawing primitives ----
    def _stream(self) -> list[str]:
        return self.content_streams[-1]

    def _set_font(self, name: str, size: int):
        font_alias = {"kor": "/F1", "lat": "/F2", "bold": "/F3"}[name]
        self._stream().append(f"{font_alias} {size} Tf")

    def _text_at(self, x: float, y: float, s: str, *, font: str = "kor",
                 size: int = 11):
        self._set_font(font, size)
        if font == "kor":
            # Encode each char as UTF-16BE hex (UniKS-UTF16-H)
            hex_s = s.encode("utf-16-be").hex()
            self._stream().append(f"BT {x:.2f} {y:.2f} Td <{hex_s}> Tj ET")
        else:
            self._stream().append(f"BT {x:.2f} {y:.2f} Td ({_escape(s)}) Tj ET")

    def _rect(self, x, y, w, h, *, fill_gray: float | None = None,
              stroke: bool = True):
        if fill_gray is not None:
            self._stream().append(f"{fill_gray:.2f} g")
            self._stream().append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re f")
            self._stream().append("0 g")
        if stroke:
            self._stream().append(f"{x:.2f} {y:.2f} {w:.2f} {h:.2f} re S")

    def _line(self, x1, y1, x2, y2):
        self._stream().append(f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")

    # ---- page management ----
    def new_page(self):
        if self.content_streams[-1]:    # finalize previous page
            self._finalize_page()
        self.content_streams.append([])
        self.cursor_y = self.PAGE_H - self.MARGIN
        self._ensure_font()

    def _finalize_page(self):
        stream = "\n".join(self.content_streams[-1]).encode("latin-1")
        compressed = zlib.compress(stream)
        cid = self._add(
            f"<< /Length {len(compressed)} /Filter /FlateDecode >>\nstream\n"
            .encode("latin-1") + compressed + b"\nendstream"
        )
        fonts = self._ensure_font()
        page_obj = (f"<< /Type /Page /Parent {{PAGES_ID}} 0 R "
                    f"/MediaBox [0 0 {self.PAGE_W} {self.PAGE_H}] "
                    f"/Resources << /Font << /F1 {fonts['kor']} 0 R "
                    f"/F2 {fonts['lat']} 0 R /F3 {fonts['bold']} 0 R >> >> "
                    f"/Contents {cid} 0 R >>")
        self.pages.append(self._add(page_obj.encode("latin-1")))

    # ---- high-level layout helpers ----
    def heading(self, text: str, *, level: int = 1):
        size = {1: 18, 2: 13, 3: 11}.get(level, 11)
        self.cursor_y -= size + 4
        if self.cursor_y < self.MARGIN + 60:
            self.new_page(); self.cursor_y -= size + 4
        self._text_at(self.MARGIN, self.cursor_y, text, font="kor", size=size)
        if level == 1:
            self._line(self.MARGIN, self.cursor_y - 4,
                       self.PAGE_W - self.MARGIN, self.cursor_y - 4)
        self.cursor_y -= 6

    def para(self, text: str, *, size: int = 10):
        if not text: return
        line_h = size + 3
        # naive line wrap by character width (~size * 0.55 each — generous for CJK)
        max_chars = int((self.PAGE_W - 2 * self.MARGIN) / (size * 0.55))
        i = 0
        while i < len(text):
            chunk = text[i:i + max_chars]
            self.cursor_y -= line_h
            if self.cursor_y < self.MARGIN + 30: self.new_page()
            self._text_at(self.MARGIN, self.cursor_y, chunk, font="kor", size=size)
            i += max_chars
        self.cursor_y -= 4

    def bullet(self, text: str, *, size: int = 10):
        self.cursor_y -= size + 3
        if self.cursor_y < self.MARGIN + 30: self.new_page()
        self._text_at(self.MARGIN, self.cursor_y, "•  " + text, font="kor", size=size)

    def kv_row(self, label: str, value: str, *, size: int = 10):
        self.cursor_y -= size + 4
        if self.cursor_y < self.MARGIN + 30: self.new_page()
        self._text_at(self.MARGIN, self.cursor_y, label, font="kor", size=size)
        # right-align value
        val_x = self.PAGE_W - self.MARGIN - len(value) * size * 0.55
        self._text_at(val_x, self.cursor_y, value, font="kor", size=size)

    def table(self, headers: list[str], rows: list[list[str]], *, size: int = 9):
        col_w = (self.PAGE_W - 2 * self.MARGIN) / len(headers)
        row_h = size + 6
        # header bar
        self.cursor_y -= row_h
        if self.cursor_y < self.MARGIN + 50: self.new_page(); self.cursor_y -= row_h
        self._rect(self.MARGIN, self.cursor_y - 2,
                    self.PAGE_W - 2 * self.MARGIN, row_h,
                    fill_gray=0.92, stroke=False)
        for j, h in enumerate(headers):
            self._text_at(self.MARGIN + j * col_w + 3, self.cursor_y,
                          h, font="kor", size=size)
        # rows
        for row in rows:
            self.cursor_y -= row_h
            if self.cursor_y < self.MARGIN + 30:
                self.new_page(); self.cursor_y -= row_h
            for j, cell in enumerate(row):
                cell = str(cell)
                if len(cell) * size * 0.55 > col_w - 6:
                    cell = cell[: max(1, int((col_w - 8) / (size * 0.55)))]
                self._text_at(self.MARGIN + j * col_w + 3, self.cursor_y,
                              cell, font="kor", size=size)
        self.cursor_y -= 4

    # ---- finalize ----
    def write(self, path):
        if self.content_streams[-1]:
            self._finalize_page()
        pages_id = len(self.objects)
        kids = " ".join(f"{p} 0 R" for p in self.pages)
        self._add(f"<< /Type /Pages /Kids [{kids}] /Count {len(self.pages)} >>"
                  .encode("latin-1"))
        catalog_id = self._add(f"<< /Type /Catalog /Pages {pages_id} 0 R >>"
                                .encode("latin-1"))
        # patch placeholder PAGES_ID in each /Page object
        for pid in self.pages:
            self.objects[pid] = self.objects[pid].replace(b"{PAGES_ID}",
                                                          str(pages_id).encode())
        # assemble PDF
        buf = io.BytesIO()
        buf.write(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = [0]
        for i in range(1, len(self.objects)):
            offsets.append(buf.tell())
            buf.write(f"{i} 0 obj\n".encode("latin-1"))
            buf.write(self.objects[i])
            buf.write(b"\nendobj\n")
        xref_pos = buf.tell()
        buf.write(f"xref\n0 {len(self.objects)}\n".encode("latin-1"))
        buf.write(b"0000000000 65535 f \n")
        for off in offsets[1:]:
            buf.write(f"{off:010d} 00000 n \n".encode("latin-1"))
        buf.write(
            f"trailer\n<< /Size {len(self.objects)} /Root {catalog_id} 0 R >>\n"
            f"startxref\n{xref_pos}\n%%EOF\n".encode("latin-1"))
        from pathlib import Path
        Path(path).write_bytes(buf.getvalue())
        return path


# ---------------------------------------------------------------- builder

def build_executive_pdf(result, out_path, *, manifest=None) -> str:
    """One-page-ish executive PDF (cover + KRI scorecard + actions + KM1)."""
    from risk_lib.notifications import collect_alerts
    pdf = _PDFWriter()
    pdf.new_page()
    pdf.heading("리스크관리 종합 보고서 — 경영진 요약", level=1)
    pdf.para(f"산출시각 {result.meta.get('asof', '-')} · 시드 {result.meta.get('seed')} · "
             f"준거 Basel III + IFRS9 + 금감원 감독세칙")
    if manifest:
        pdf.para(f"포트폴리오 SHA-256 {manifest.portfolio['sha256'][:32]}...")
        pdf.para(f"Headline digest {manifest.headline_digest[:32]}...")

    # verdict
    v = result.validation; summ = v.summary()
    verdict = "결재 가능 (PASS)" if v.passes() else "결재 불가 (FAIL 존재)"
    pdf.heading("0. 종합 판정", level=2)
    pdf.para(f"{verdict} — 검증 PASS {summ.get('PASS',0)} / "
             f"WARN {summ.get('WARN',0)} / FAIL {summ.get('FAIL',0)}, "
             f"RAF 최악 {result.raf.worst()}")

    # KRI 스코어카드 (top 10)
    pdf.heading("1. RAF KRI 스코어카드 (상위 10)", level=2)
    rows = []
    for k in result.raf.kris[:12]:
        actual = (f"{k.actual*100:.2f}%" if k.fmt == "pct"
                  else (f"{k.actual:.3f}" if k.fmt == "ratio" else f"{k.actual:,.0f}"))
        board = (f"{k.threshold.board*100:.2f}%" if k.fmt == "pct"
                 else f"{k.threshold.board:.3f}")
        rows.append([k.category, k.name, actual, board, k.grade])
    pdf.table(["분류", "KRI", "실측", "board", "grade"], rows, size=9)

    # 자본·유동성 KPI
    bis = result.bis; lev = result.leverage
    lcr = result.alm["lcr"]; nsfr = result.alm["nsfr"]; irrbb = result.alm["irrbb"]
    pdf.heading("2. 자본·유동성 핵심 지표", level=2)
    kpis = [
        ["CET1 비율", f"{bis.cet1_ratio*100:.2f}%",
         f"요구 {bis.required['cet1']*100:.2f}%"],
        ["Tier1 비율", f"{bis.tier1_ratio*100:.2f}%", ""],
        ["총자본 비율", f"{bis.total_ratio*100:.2f}%", ""],
        ["레버리지 비율", f"{lev.leverage_ratio*100:.2f}%", "요구 3.00%"],
        ["LCR", f"{lcr.lcr*100:.1f}%", "기준 100%"],
        ["NSFR", f"{nsfr.nsfr*100:.1f}%", "기준 100%"],
        ["IRRBB ΔEVE/Tier1",
         f"{irrbb.worst_pct_tier1*100:.2f}%", "기준 ≤15%"],
        ["ICAAP 사용률",
         f"{result.icaap.utilisation*100:.1f}%", result.icaap.grade],
    ]
    pdf.table(["지표", "실측", "비고"], kpis, size=9)

    # 액션 리스트
    bundle = collect_alerts(result)
    if bundle.alerts:
        pdf.heading("3. CRO 액션 (상위 10건)", level=2)
        for a in bundle.alerts[:10]:
            pdf.bullet(f"[{a.severity}] {a.title} — {a.detail}", size=9)
    else:
        pdf.heading("3. CRO 액션", level=2)
        pdf.para("조치 필요 항목 없음 — 모든 KRI 정상.")

    # ALM 카드
    pdf.heading("4. ALM 요약", level=2)
    pdf.kv_row(f"LCR HQLA(캡 적용)", f"{lcr.hqla_total/1e12:,.2f} 조원")
    pdf.kv_row(f"30일 순현금유출", f"{lcr.net_outflow/1e12:,.2f} 조원")
    pdf.kv_row(f"NSFR ASF / RSF",
               f"{nsfr.asf_total/1e12:,.2f} / {nsfr.rsf_total/1e12:,.2f} 조원")
    pdf.kv_row(f"IRRBB 최악 시나리오", irrbb.worst_eve_scenario)

    pdf.heading("5. 재현성", level=2)
    pdf.para("동봉된 manifest.json 을 사용하면 누구나 같은 결과를 비트 단위로 재현할 수 있습니다.")
    pdf.para("python -m risk_lib.cli reproduce --manifest manifest.json")
    pdf.para("(상세 보고서는 동봉된 HTML 보고서 참조)")

    return pdf.write(out_path)
