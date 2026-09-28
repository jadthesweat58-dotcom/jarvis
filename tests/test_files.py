import base64
import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from jarvis import files
from jarvis.brain import Brain
from jarvis.server import create_app
from tests.conftest import FakeClaude, response, text


def make_pdf(*pages: str) -> bytes:
    """A minimal valid PDF with one line of text per page."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", None,
               "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for body in pages:
        stream = f"BT /F1 12 Tf 72 720 Td ({body}) Tj ET".encode() if body else b""
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
        content_id = len(objects)
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                       f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>")
        kids.append(f"{len(objects)} 0 R")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    out, offsets = io.BytesIO(), []
    out.write(b"%PDF-1.4\n")
    for n, obj in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(f"{n} 0 obj\n".encode() + (obj if isinstance(obj, bytes) else obj.encode()) + b"\nendobj\n")
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF".encode())
    return out.getvalue()


def make_docx(*paragraphs: str) -> bytes:
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", f'<w:document xmlns:w="x"><w:body>{body}</w:body></w:document>')
    return buf.getvalue()


def no_look(*_):
    raise AssertionError("shouldn't need the AI's eyes")


def test_pdf_text():
    out = files.read_file("report.pdf", make_pdf("Revenue grew 12 percent in Q3 across all regions", "Page two has more words on it"),
                          "application/pdf", "summarise", no_look)
    assert out.startswith("(2 pages)") and "Revenue grew 12 percent" in out and "Page two" in out


def test_scanned_pdf_is_read_by_the_ai():
    seen = {}

    def look(data, mime, prompt):
        seen.update(mime=mime, prompt=prompt)
        return "An invoice for 450 AED from DEWA."

    out = files.read_file("scan.pdf", make_pdf(""), "", "what is this bill?", look)
    assert out == "An invoice for 450 AED from DEWA."
    assert seen["mime"] == "application/pdf" and "scan.pdf" in seen["prompt"] and "what is this bill?" in seen["prompt"]


def test_images_docx_and_text():
    assert files.read_file("pic.png", b"\x89PNG...", "image/png", "q", lambda d, m, p: f"saw {m}") == "saw image/png"
    assert files.read_file("notes.docx", make_docx("Hello &amp; welcome", "Line two"), "", "q", no_look) \
        == "Hello & welcome\nLine two"
    assert files.read_file("data.csv", "a,b\n1,2\n".encode(), "", "q", no_look) == "a,b\n1,2"
    assert files.read_file("utf16.txt", "héllo".encode("utf-16"), "text/plain", "q", no_look) == "héllo"


def test_long_files_are_cut_and_odd_ones_refused():
    out = files.read_file("big.txt", b"x" * (files.MAX_TEXT_CHARS + 500), "text/plain", "q", no_look)
    assert len(out) < files.MAX_TEXT_CHARS + 200 and "file cut here" in out
    with pytest.raises(files.FileError, match="isn't supported"):
        files.read_file("archive.zip", b"PK\x03\x04", "application/zip", "q", no_look)
    with pytest.raises(files.FileError, match="too large"):
        files.read_file("huge.txt", b"x" * (files.MAX_FILE_BYTES + 1), "text/plain", "q", no_look)
    with pytest.raises(files.FileError, match="empty"):
        files.read_file("empty.txt", b"", "text/plain", "q", no_look)


def test_with_file_escapes_the_name():
    assert files.with_file("hi", 'a"<b>\n.txt', "body") == 'hi\n\n<attached_file name="ab.txt">\nbody\n</attached_file>'


def data_url(data: bytes, mime: str) -> str:
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def test_chat_with_a_file_over_http(ctx):
    claude = FakeClaude(response(text("It's a quarterly report.")), response(text("Here you go.")))
    app = create_app(ctx, brain_factory=lambda **kw: Brain(ctx, client=claude, **kw))
    client = TestClient(app, base_url="http://localhost", client=("127.0.0.1", 5000))
    pdf = make_pdf("Quarterly report: revenue up 12 percent year on year")
    out = client.post("/api/chat", json={"text": "", "file": {"name": "q3.pdf", "data": data_url(pdf, "application/pdf")}})
    assert out.status_code == 200 and out.json()["reply"] == "It's a quarterly report."
    sent = claude.requests[0]["messages"][-1]["content"][-1]["text"]
    assert "summary" in sent and '<attached_file name="q3.pdf">' in sent and "revenue up 12 percent" in sent
    # Only the text is kept: no file bytes in the saved conversation.
    assert "JVBER" not in str(ctx.db.load_conversation("main"))

    bad = client.post("/api/chat", json={"text": "x", "file": {"name": "a.zip", "data": data_url(b"PK..", "application/zip")}})
    assert bad.status_code == 400 and "isn't supported" in bad.json()["detail"]
    assert client.post("/api/chat", json={"text": "x", "file": {"name": "a.txt", "data": "not a data url"}}).status_code == 400
    big = data_url(b"x" * (11 * 1024 * 1024), "text/plain")
    assert client.post("/api/chat", json={"text": "x", "file": {"name": "a.txt", "data": big}}).status_code == 413
    assert client.post("/api/chat", json={"text": "  "}).status_code == 400
    # The conversation still works after the failed uploads.
    assert client.post("/api/chat", json={"text": "thanks"}).json()["reply"] == "Here you go."
