"""Files you hand Jarvis in the chat (or on Telegram): PDFs, Word documents,
images, and text or code files.

Jarvis reads the file once and keeps only the text it found in the
conversation, never the file itself (the same way screen snapshots work), so
the history stays small and any AI provider can use it.
"""

from __future__ import annotations

import io
import re
import zipfile
from typing import Callable

MAX_FILE_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 30_000
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/heic", "image/heif"}
TEXT_EXTENSIONS = {
    "txt", "md", "markdown", "csv", "tsv", "json", "xml", "yaml", "yml", "html", "htm", "log", "ini", "cfg",
    "toml", "py", "js", "ts", "tsx", "jsx", "css", "java", "c", "h", "cpp", "cs", "go", "rs", "rb", "php",
    "swift", "kt", "sql", "sh", "bat", "ps1", "srt", "vtt", "ics", "rtf",
}
EXTENSION_TYPES = {"pdf": "application/pdf", "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png",
                   "webp": "image/webp", "gif": "image/gif", "heic": "image/heic", "heif": "image/heif",
                   "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}

FILE_PROMPT = """You are the eyes of JARVIS, a personal assistant. The user sent this file
("{name}") and said: "{question}"
Write out what it contains so the assistant can answer them: transcribe the text (exactly,
where it matters: names, numbers, dates, amounts, totals), describe any pictures, charts or
tables, and note anything else relevant. Plain text, under 700 words."""

# look(data, mime, prompt) -> what the AI sees in the file
Looker = Callable[[bytes, str, str], str]


class FileError(ValueError):
    pass


def guess_type(name: str, mime: str = "") -> str:
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    mime = (mime or "").split(";")[0].strip().lower()
    if mime in ("", "application/octet-stream"):
        mime = EXTENSION_TYPES.get(ext, "text/plain" if ext in TEXT_EXTENSIONS else mime)
    return mime


def is_texty(name: str, mime: str) -> bool:
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    return mime.startswith("text/") or ext in TEXT_EXTENSIONS or mime in (
        "application/json", "application/xml", "application/x-yaml", "application/csv")


def _clip(text: str) -> str:
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) > MAX_TEXT_CHARS:
        return text[:MAX_TEXT_CHARS] + f"\n\n[… file cut here: only the first {MAX_TEXT_CHARS:,} characters were read]"
    return text


def pdf_text(data: bytes) -> tuple[str, int]:
    """(text, number of pages) of a PDF."""
    from pypdf import PdfReader

    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as exc:
                raise FileError("That PDF is password-protected.") from exc
        pages = []
        for number, page in enumerate(reader.pages, 1):
            pages.append(f"--- page {number} ---\n{(page.extract_text() or '').strip()}")
            if sum(len(p) for p in pages) > MAX_TEXT_CHARS * 1.2:
                break
        return "\n\n".join(pages), len(reader.pages)
    except FileError:
        raise
    except Exception as exc:
        raise FileError(f"I couldn't read that PDF ({exc}).") from exc


def docx_text(data: bytes) -> str:
    """Text of a Word (.docx) document, paragraph by paragraph (no extra packages)."""
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            xml = z.read("word/document.xml").decode("utf-8", "replace")
    except Exception as exc:
        raise FileError("I couldn't open that Word document.") from exc
    xml = re.sub(r"</w:p>", "\n", xml)
    xml = re.sub(r"<w:tab/>", "\t", xml)
    xml = re.sub(r"<w:br/>", "\n", xml)
    text = re.sub(r"<[^>]+>", "", xml)
    import html

    return html.unescape(text)


def decode_text(data: bytes) -> str:
    encoding = "utf-16" if data[:2] in (b"\xff\xfe", b"\xfe\xff") else "utf-8-sig"
    try:
        return data.decode(encoding)
    except UnicodeDecodeError:
        return data.decode("latin-1")


def read_file(name: str, data: bytes, mime: str, question: str, look: Looker | None) -> str:
    """What's in the file, as text for the conversation."""
    name = (name or "file").strip()[:120] or "file"
    if not data:
        raise FileError("That file is empty.")
    if len(data) > MAX_FILE_BYTES:
        raise FileError("That file is too large (10 MB max).")
    mime = guess_type(name, mime)
    ask = question[:500] or "What is this?"
    if mime in IMAGE_TYPES:
        if not look:
            raise FileError("I can't look at pictures right now.")
        return _clip(look(data, mime, FILE_PROMPT.format(name=name, question=ask)))
    if mime == "application/pdf":
        text, pages = pdf_text(data)
        if len(re.sub(r"--- page \d+ ---|\s", "", text)) < 25 * max(pages, 1) and look:
            # Little or no text: a scanned PDF. Let the AI read the pages instead.
            return _clip(look(data, mime, FILE_PROMPT.format(name=name, question=ask)))
        return _clip(f"({pages} page{'s' if pages != 1 else ''})\n{text}")
    if mime.endswith("wordprocessingml.document") or name.lower().endswith(".docx"):
        return _clip(docx_text(data))
    if is_texty(name, mime):
        return _clip(decode_text(data))
    raise FileError("I can read PDFs, Word documents, pictures and text or code files. "
                    "That type isn't supported yet.")


def with_file(text: str, name: str, content: str) -> str:
    """The user's message with the file's contents attached."""
    safe = re.sub(r'["<>\n]', "", name)[:120]
    return f'{text}\n\n<attached_file name="{safe}">\n{content}\n</attached_file>'
