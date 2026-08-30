import asyncio

from app.paper_integrations.models import Paper
from app.paper_integrations.zotero import PdfLinkParser, _known_pdf_url_variants, _pdf_request_headers, _resolve_pdf_for_paper


class FakeResponse:
    def __init__(self, content: bytes, content_type: str, url: str = "https://example.org/item"):
        self.content = content
        self.headers = {"Content-Type": content_type}
        self.url = url

    @property
    def text(self) -> str:
        return self.content.decode("utf-8")

    def raise_for_status(self) -> None:
        return None


class FakeClient:
    def __init__(self, responses: dict[str, FakeResponse]):
        self.responses = responses
        self.requested: list[str] = []

    async def get(self, url: str, headers: dict | None = None):
        self.requested.append(url)
        return self.responses[url]


def test_pdf_link_parser_discovers_meta_and_relative_links():
    parser = PdfLinkParser("https://example.org/papers/item")
    parser.feed('''
      <html><head>
        <meta name="citation_pdf_url" content="/papers/item.pdf">
      </head><body>
        <a href="supplement.pdf">Download PDF</a>
      </body></html>
    ''')

    assert parser.urls == [
        "https://example.org/papers/item.pdf",
        "https://example.org/papers/supplement.pdf",
    ]


def test_known_pdf_url_variants_cover_common_hosts():
    variants = _known_pdf_url_variants("https://arxiv.org/abs/2401.12345")
    assert "https://arxiv.org/pdf/2401.12345.pdf" in variants

    variants = _known_pdf_url_variants("https://openreview.net/forum?id=abc123")
    assert "https://openreview.net/pdf?id=abc123" in variants

    variants = _known_pdf_url_variants("https://ieeexplore.ieee.org/document/1234567")
    assert "https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=1234567" in variants
    assert "https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?tp=&arnumber=1234567" in variants


def test_resolve_pdf_for_paper_discovers_pdf_from_homepage_meta():
    paper = Paper(
        id="paper-1",
        title="A Test Paper",
        url="https://example.org/papers/item",
        is_oa=False,
    )
    client = FakeClient({
        "https://example.org/papers/item": FakeResponse(
            b'<meta name="citation_pdf_url" content="https://cdn.example.org/item.pdf">',
            "text/html",
        ),
        "https://cdn.example.org/item.pdf": FakeResponse(b"%PDF-1.7 test", "application/pdf"),
    })

    resolved = asyncio.run(_resolve_pdf_for_paper(client, paper))

    assert resolved.content.startswith(b"%PDF")
    assert resolved.content_type == "application/pdf"
    assert resolved.url == "https://cdn.example.org/item.pdf"
    assert resolved.status == "AVAILABLE"


def test_resolve_pdf_for_paper_discovers_pdf_from_homepage_link_text():
    paper = Paper(
        id="paper-2",
        title="Another Test Paper",
        url="https://example.org/articles/42",
        is_oa=False,
    )
    client = FakeClient({
        "https://example.org/articles/42": FakeResponse(
            b'<a href="/articles/42/fulltext.pdf">Full text PDF</a>',
            "text/html",
        ),
        "https://example.org/articles/42/fulltext.pdf": FakeResponse(b"%PDF-1.7 test", "application/pdf"),
    })

    resolved = asyncio.run(_resolve_pdf_for_paper(client, paper))

    assert resolved.content is not None
    assert resolved.url == "https://example.org/articles/42/fulltext.pdf"

def test_resolve_pdf_for_paper_rejects_html_returned_from_pdf_url():
    paper = Paper(
        id="paper-3",
        title="HTML Instead of PDF",
        pdf_url="https://example.org/not-really.pdf",
        is_oa=True,
    )
    client = FakeClient({
        "https://example.org/not-really.pdf": FakeResponse(b"<html>not found</html>", "text/html"),
    })

    resolved = asyncio.run(_resolve_pdf_for_paper(client, paper))

    assert resolved.content is None
    assert resolved.error_code == "BROWSER_REQUIRED"

def test_pdf_link_parser_discovers_embedded_pdf():
    parser = PdfLinkParser("https://example.org/papers/item")
    parser.feed('<iframe src="/viewer/paper.pdf"></iframe><object data="/object/fulltext.pdf"></object>')

    assert parser.urls == [
        "https://example.org/viewer/paper.pdf",
        "https://example.org/object/fulltext.pdf",
    ]


def test_resolve_pdf_for_paper_discovers_download_link_without_pdf_suffix():
    paper = Paper(
        id="paper-4",
        title="Download Link Paper",
        url="https://example.org/articles/99",
        is_oa=False,
    )
    client = FakeClient({
        "https://example.org/articles/99": FakeResponse(
            b'<a href="/articles/99/download?format=fulltext">Download</a>',
            "text/html",
        ),
        "https://example.org/articles/99/download?format=fulltext": FakeResponse(b"%PDF-1.7 test", "application/pdf"),
    })

    resolved = asyncio.run(_resolve_pdf_for_paper(client, paper))

    assert resolved.content is not None
    assert resolved.url == "https://example.org/articles/99/download?format=fulltext"

def test_ieee_pdf_request_headers_include_referer():
    headers = _pdf_request_headers("https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?tp=&arnumber=11247714&ref=")

    assert "Mozilla/5.0" in headers["User-Agent"]
    assert headers["Referer"] == "https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=11247714"



def test_resolve_pdf_for_paper_rejects_fake_pdf_content_type_without_magic_header():
    paper = Paper(
        id="paper-5",
        title="Fake PDF Header",
        pdf_url="https://example.org/fake.pdf",
        is_oa=True,
    )
    client = FakeClient({
        "https://example.org/fake.pdf": FakeResponse(b"not really a pdf", "application/pdf"),
    })

    resolved = asyncio.run(_resolve_pdf_for_paper(client, paper))

    assert resolved.content is None
    assert resolved.error_code == "INVALID_PDF_RESPONSE"


def test_restricted_publisher_without_oa_url_requires_browser():
    paper = Paper(
        id="paper-6",
        title="IEEE Paper",
        url="https://ieeexplore.ieee.org/document/1234567",
        is_oa=False,
    )
    client = FakeClient({
        "https://ieeexplore.ieee.org/document/1234567": FakeResponse(b"<html>Sign in</html>", "text/html"),
        "https://ieeexplore.ieee.org/stamp/stamp.jsp?tp=&arnumber=1234567": FakeResponse(b"<html>Sign in</html>", "text/html"),
        "https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?tp=&arnumber=1234567": FakeResponse(b"<html>Sign in</html>", "text/html"),
        "https://ieeexplore.ieee.org/stampPDF/getPDF.jsp?tp=&arnumber=1234567&ref=": FakeResponse(b"<html>Sign in</html>", "text/html"),
    })

    resolved = asyncio.run(_resolve_pdf_for_paper(client, paper))

    assert resolved.content is None
    assert resolved.status == "AUTH_REQUIRED"
