"""Bounded source acquisition and page-aware, non-inferential extraction."""
import csv
import io
import json
from html.parser import HTMLParser
from urllib.parse import urlparse
from urllib.request import Request, urlopen

MAX_BYTES = 30 * 1024 * 1024
ALLOWED_FORMATS = {"pdf", "html", "csv", "json"}


def fetch_source(url, opener=urlopen):
    """Fetch a configured public source with a hard size limit and timeout."""
    if urlparse(url).scheme not in ("http", "https"):
        raise ValueError("Only HTTP(S) source URLs are supported")
    request = Request(url, headers={"User-Agent": "VietGreenResearch/1.0 (evidence capture)"})
    with opener(request, timeout=60) as response:
        if urlparse(response.geturl()).scheme not in ("http", "https"):
            raise ValueError("Invalid redirected source URL")
        length = response.headers.get("Content-Length")
        if length and int(length) > MAX_BYTES:
            raise ValueError("Source exceeds maximum allowed size")
        body = response.read(MAX_BYTES + 1)
        if len(body) > MAX_BYTES:
            raise ValueError("Source exceeds maximum allowed size")
        if not body:
            raise ValueError("Source is empty")
        return body, response.headers.get("Content-Type", "application/octet-stream").split(";")[0], response.geturl()


class TextExtractor(HTMLParser):
    """Collect visible HTML text without executing scripts."""
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


def extract_document(body, source_format):
    """Return page records and an extraction status; never infer environmental metrics."""
    if source_format not in ALLOWED_FORMATS:
        raise ValueError("Unsupported source format: " + str(source_format))
    pages = []
    if source_format == "pdf":
        if not body.startswith(b"%PDF-"):
            raise ValueError("Configured PDF does not contain a PDF signature")
        import pdfplumber
        with pdfplumber.open(io.BytesIO(body)) as pdf:
            for index, page in enumerate(pdf.pages, start=1):
                pages.append({"page_number": index, "text": page.extract_text() or "", "tables": page.extract_tables() or []})
        if not pages:
            raise ValueError("PDF has no pages")
        status = "text_extracted" if any(p["text"].strip() for p in pages) else "needs_ocr"
    elif source_format == "html":
        parser = TextExtractor()
        parser.feed(body.decode("utf-8-sig"))
        pages = [{"page_number": 1, "text": "\n".join(parser.parts), "tables": []}]
        status = "text_extracted"
    else:
        data = body.decode("utf-8-sig")
        if source_format == "json":
            parsed = json.loads(data)
        else:
            parsed = list(csv.DictReader(io.StringIO(data)))
            if not parsed:
                raise ValueError("CSV contains no data rows")
        pages = [{"page_number": 1, "text": json.dumps(parsed, ensure_ascii=False), "tables": []}]
        status = "structured_extracted"
    return pages, status
