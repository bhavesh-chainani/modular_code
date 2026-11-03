"""Turn a source (URL, file path, or raw text) into plain text for the LLM."""

import io
from pathlib import Path

import httpx
from pypdf import PdfReader

from modkit.observability import observation


def load_text(source: str | Path) -> str:
    """Return text from an http(s) URL, a local file (.pdf or any text format), or the input itself."""
    s = str(source)
    is_url = s.startswith(("http://", "https://"))
    path = None if is_url else _as_file(s)
    if not is_url and path is None:
        return s  # raw text: nothing to load, so nothing to trace

    with observation("load-document", as_type="retriever", input={"source": s}) as obs:
        text = _load_url(s) if is_url else _load_file(path)
        obs.update(
            output={"chars": len(text), "preview": text[:500]},
            level=None if text.strip() else "WARNING",
            status_message=None if text.strip() else "no text extracted (scanned PDF?)",
        )
    return text


def _load_url(url: str) -> str:
    response = httpx.get(url, follow_redirects=True, timeout=30)
    response.raise_for_status()
    if "pdf" in response.headers.get("content-type", ""):
        return _pdf_text(io.BytesIO(response.content))
    return response.text


def _load_file(path: Path) -> str:
    if path.suffix.lower() == ".pdf":
        return _pdf_text(path)
    return path.read_text(encoding="utf-8", errors="replace")


def _as_file(s: str) -> Path | None:
    if "\n" in s or len(s) > 1024:
        return None
    try:
        path = Path(s).expanduser()
        return path if path.is_file() else None
    except OSError:
        return None


def _pdf_text(fp) -> str:
    return "\n\n".join(page.extract_text() or "" for page in PdfReader(fp).pages)
