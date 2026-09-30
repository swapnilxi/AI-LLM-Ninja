"""PDF / DOCX / registry utilities, tested with real files generated on the fly."""
import io
import zipfile

import pytest

from app.utils import docx, filetypes, pdf


def make_pdf(pages: list[str]) -> bytes:
    """Minimal valid PDF with one text line per '\\n' in each page string (Helvetica, no dependencies)."""
    objs: list[bytes] = []
    n = len(pages)
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(n))
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(f"<< /Type /Pages /Kids [{kids}] /Count {n} >>".encode())
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    for i, text in enumerate(pages):
        lines = "".join(f"({ln.replace('(', '[').replace(')', ']')}) Tj T* " for ln in text.split("\n"))
        stream = f"BT /F1 12 Tf 14 TL 50 750 Td {lines}ET".encode()
        objs.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {5 + 2 * i} 0 R "
                    f"/Resources << /Font << /F1 3 0 R >> >> >>".encode())
        objs.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    out, offsets = bytearray(b"%PDF-1.4\n"), []
    for i, o in enumerate(objs, start=1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n".encode() + o + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode()
    out += b"".join(f"{o:010d} 00000 n \n".encode() for o in offsets)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode()
    return bytes(out)


def make_docx() -> bytes:
    ns = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
    body = (
        '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Returns policy</w:t></w:r></w:p>'
        "<w:p><w:r><w:t>Items can be returned within 30 days.</w:t></w:r></w:p>"
        "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Item</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Days</w:t></w:r></w:p></w:tc></w:tr>"
        "<w:tr><w:tc><w:p><w:r><w:t>Shoes</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>45</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
    )
    core = ('<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Policy</dc:title><dc:creator>Ada</dc:creator></cp:coreProperties>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", f'<w:document {ns}><w:body>{body}</w:body></w:document>')
        z.writestr("docProps/core.xml", core)
    return buf.getvalue()


PAGES = [f"ACME Confidential\nChapter {i}: the infor-\nmation about topic{i}.\nPage {i} of 4" for i in range(1, 5)]


# ------------------------------------------------------------------ pdf
def test_pdf_extract_keeps_page_numbers_and_cleans_noise():
    pages = pdf.extract_pages(make_pdf(PAGES))
    assert [n for n, _ in pages] == [1, 2, 3, 4]
    text = pages[1][1]
    assert "ACME Confidential" not in text          # repeated header removed
    assert "Page 2 of 4" not in text                # page number removed
    assert "information about topic2" in text       # hyphenation repaired
    raw = pdf.extract_pages(make_pdf(PAGES), clean=False)
    assert "ACME Confidential" in raw[0][1]


def test_pdf_validate_info_and_scanned_detection():
    data = make_pdf(PAGES)
    info = pdf.validate(data)
    assert info.pages == 4 and not info.encrypted
    with pytest.raises(pdf.PdfError, match="PDF header"):
        pdf.validate(b"just text")
    with pytest.raises(pdf.PdfError, match="limit"):
        pdf.validate(data, max_pages=2)
    assert not pdf.looks_scanned(data)
    assert pdf.looks_scanned(make_pdf(["", "", ""]))  # no text layer


def test_pdf_split_range_merge(tmp_path):
    src = tmp_path / "book.pdf"
    src.write_bytes(make_pdf(PAGES))
    parts = pdf.split(src, tmp_path / "parts", pages_per_file=3)
    assert [p.name for p in parts] == ["book_part01.pdf", "book_part02.pdf"]
    assert pdf.read_info(parts[0]).pages == 3 and pdf.read_info(parts[1]).pages == 1
    one = pdf.extract_range(src, 2, 3, tmp_path / "mid.pdf")
    assert pdf.read_info(one).pages == 2
    with pytest.raises(pdf.PdfError):
        pdf.extract_range(src, 3, 9, tmp_path / "bad.pdf")
    merged = pdf.merge(parts, tmp_path / "all.pdf")
    assert pdf.read_info(merged).pages == 4


# ------------------------------------------------------------------ docx
def test_docx_extract_structure_and_validate():
    data = make_docx()
    text = docx.extract_text(data)
    assert text.startswith("# Returns policy") and "Shoes | 45" in text
    info = docx.validate(data)
    assert (info.title, info.author, info.tables) == ("Policy", "Ada", 1)
    with pytest.raises(docx.DocxError):
        docx.validate(b"PK\x03\x04 not really a zip")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/workbook.xml", "<x/>")
    with pytest.raises(docx.DocxError, match="Word document"):
        docx.validate(buf.getvalue())


# ------------------------------------------------------------------ registry / upload validation
def test_validate_upload_rules():
    ok = filetypes.validate_upload("../my report.pdf", make_pdf(PAGES))
    assert ok == "my report.pdf"
    with pytest.raises(filetypes.FileValidationError, match="not a real PDF"):
        filetypes.validate_upload("fake.pdf", b"hello, i am text")
    with pytest.raises(filetypes.FileValidationError, match="Unsupported"):
        filetypes.validate_upload("run.exe", b"MZ")
    with pytest.raises(filetypes.FileTooLarge):
        filetypes.validate_upload("big.txt", b"x" * (2 * 1024 * 1024), max_mb=1)
    with pytest.raises(filetypes.FileValidationError, match="empty"):
        filetypes.validate_upload("a.txt", b"")
    assert {".pdf", ".docx", ".md", ".csv", ".json", ".html", ".txt"} <= filetypes.SUPPORTED


def test_scanned_pdf_gives_actionable_error(tmp_path):
    p = tmp_path / "scan.pdf"
    p.write_bytes(make_pdf(["", "", ""]))
    with pytest.raises(pdf.PdfError, match="OCR"):
        filetypes.extract(p)


# ------------------------------------------------------------------ through the API (upload -> index -> cite page)
def test_api_upload_pdf_docx_and_cite_pages(client):
    c, docs = client, client.data / "acme"
    c.post("/api/profiles", json={"name": "Acme"})
    up = "/api/profiles/acme/documents"
    bad = c.post(up, files={"files": ("fake.pdf", b"not a pdf", "application/pdf")})
    assert bad.status_code == 400 and "not a real PDF" in bad.json()["detail"]
    assert not (docs / "fake.pdf").exists()

    good = c.post(up, files=[
        ("files", ("manual.pdf", make_pdf(PAGES), "application/pdf")),
        ("files", ("policy.docx", make_docx(), "application/octet-stream")),
    ], data={"folder": "guides/2024"})
    assert good.status_code == 200 and sorted(good.json()["saved"]) == ["guides/2024/manual.pdf", "guides/2024/policy.docx"]
    st = c.wait()
    assert st["state"] == "done" and not st["result"]["errors"], st

    r = c.post("/api/query-context", json={"profile_id": "acme", "query": "topic3 information", "limit": 1}).json()
    src = r["sources"][0]
    assert src["source"] == "guides/2024/manual.pdf" and src["page"] == 3   # page-level citation

    base = f"/api/profiles/acme/documents/{src['document_id']}"
    info = c.get(f"{base}/info").json()
    assert info["pages"] == 4 and info["type"] == "PDF" and info["scanned"] is False
    by_name = {d["filename"]: d["id"] for d in c.get(up).json()["documents"]}
    assert c.get(f"/api/profiles/acme/documents/{by_name['policy.docx']}/info").json()["author"] == "Ada"
    f = c.get(f"{base}/file")
    assert f.headers["content-type"] == "application/pdf" and f.content.startswith(b"%PDF")
    assert c.get("/api/profiles/acme/documents/nope/file").status_code == 404
