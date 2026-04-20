from __future__ import annotations

import re
import ssl
from collections import deque
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import URLError
from urllib.parse import urldefrag, urljoin, urlparse
from urllib.request import Request, urlopen

from .css_parser import normalize_space, parse_css_rules
from .models import COMPONENT_KEYWORDS, MARKDOWN_BUCKET_ALIASES, SourceDocument


def infer_component(value: str) -> str:
    lower = (value or "").lower()
    for component, keywords in COMPONENT_KEYWORDS.items():
        if any(keyword in lower for keyword in keywords):
            return component
    return ""


def strip_code_fences(text: str) -> str:
    return re.sub(r"```.*?```", "", text or "", flags=re.S)


def infer_markdown_bucket(file: Path, root: Path) -> str:
    root_bucket = _infer_root_bucket(root)
    if root_bucket:
        return root_bucket

    try:
        relative = file.relative_to(root) if root.is_dir() else Path(file.name)
    except ValueError:
        relative = file

    for part in relative.parts:
        bucket = MARKDOWN_BUCKET_ALIASES.get(part.lower())
        if bucket:
            return bucket
    return ""


def _infer_root_bucket(root: Path) -> str:
    candidates: list[str] = []
    if root.is_dir():
        candidates.append(root.name)
    elif root.is_file() and root.parent != root:
        candidates.append(root.parent.name)

    for candidate in candidates:
        bucket = MARKDOWN_BUCKET_ALIASES.get(candidate.lower())
        if bucket:
            return bucket
    return ""


def fetch_text(url: str, timeout: int = 10) -> str:
    request = Request(url, headers={"User-Agent": "uiux-rule-agent/0.1"})
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except URLError as exc:
        reason = getattr(exc, "reason", None)
        if isinstance(reason, ssl.SSLCertVerificationError):
            unverified = ssl._create_unverified_context()
            with urlopen(request, timeout=timeout, context=unverified) as response:
                raw = response.read()
        else:
            raise
    return raw.decode("utf-8", errors="ignore")


def should_follow(path: str) -> bool:
    suffix = Path(path).suffix.lower()
    return suffix in {"", ".html", ".htm", ".php", ".jsp", ".aspx"}


class SiteParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.in_style = False
        self.in_script = False
        self.in_title = False
        self.title_chunks: list[str] = []
        self.text_chunks: list[str] = []
        self.style_chunks: list[str] = []
        self.inline_styles: list[str] = []
        self.stylesheet_links: set[str] = set()
        self.page_links: set[str] = set()
        self.element_hints: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key.lower(): (value or "") for key, value in attrs}

        if tag == "style":
            self.in_style = True
        elif tag == "script":
            self.in_script = True
        elif tag == "title":
            self.in_title = True

        if tag == "a" and attrs_map.get("href"):
            self.page_links.add(attrs_map["href"])

        if tag == "link" and "stylesheet" in attrs_map.get("rel", "").lower() and attrs_map.get("href"):
            self.stylesheet_links.add(attrs_map["href"])

        if attrs_map.get("style"):
            self.inline_styles.append(f"{tag}[data-inline-style] {{{attrs_map['style']}}}")

        hint_source = " ".join(
            [
                tag,
                attrs_map.get("class", ""),
                attrs_map.get("id", ""),
                attrs_map.get("role", ""),
                attrs_map.get("aria-label", ""),
            ]
        )
        component = infer_component(hint_source)
        if component:
            self.element_hints.add(component)

    def handle_endtag(self, tag: str) -> None:
        if tag == "style":
            self.in_style = False
        elif tag == "script":
            self.in_script = False
        elif tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        text = normalize_space(data)
        if not text:
            return
        if self.in_style:
            self.style_chunks.append(data)
        elif self.in_title:
            self.title_chunks.append(text)
        elif not self.in_script:
            self.text_chunks.append(text)


def load_markdown_docs(path_value: str) -> list[SourceDocument]:
    root = Path(path_value)
    files = [root] if root.is_file() else sorted(list(root.rglob("*.md")) + list(root.rglob("*.mdx")) + list(root.rglob("*.markdown")))
    documents: list[SourceDocument] = []

    for file in files:
        text = file.read_text(encoding="utf-8", errors="ignore")
        title = next(
            (normalize_space(line.lstrip("#").strip()) for line in text.splitlines() if line.strip().startswith("#")),
            file.stem,
        )
        css_blocks = re.findall(r"```css(.*?)```", text, flags=re.S | re.I)
        document = SourceDocument(
            source_type="markdown",
            location=str(file),
            title=title,
            text=strip_code_fences(text),
            source_bucket=infer_markdown_bucket(file, root),
            css_blocks=css_blocks,
        )
        document.css_rules = [rule for css in document.css_blocks for rule in parse_css_rules(css)]
        documents.append(document)

    return documents


def crawl_website(start_url: str, max_pages: int) -> list[SourceDocument]:
    origin = urlparse(start_url).netloc
    queue = deque([start_url])
    seen: set[str] = set()
    documents: list[SourceDocument] = []

    while queue and len(documents) < max_pages:
        current = urldefrag(queue.popleft())[0]
        if current in seen:
            continue
        seen.add(current)

        parsed_current = urlparse(current)
        if parsed_current.netloc != origin:
            continue

        try:
            html = fetch_text(current)
        except Exception:
            continue

        parser = SiteParser()
        parser.feed(html)

        css_blocks = list(parser.style_chunks) + list(parser.inline_styles)
        for href in list(parser.stylesheet_links)[:10]:
            css_url = urljoin(current, href)
            if urlparse(css_url).netloc != origin:
                continue
            try:
                css_blocks.append(fetch_text(css_url))
            except Exception:
                continue

        document = SourceDocument(
            source_type="website",
            location=current,
            title=normalize_space(" ".join(parser.title_chunks)) or current,
            text="\n".join(parser.text_chunks),
            css_blocks=css_blocks,
            element_hints=set(parser.element_hints),
        )
        document.css_rules = [rule for css in document.css_blocks for rule in parse_css_rules(css)]
        documents.append(document)

        for href in parser.page_links:
            next_url = urldefrag(urljoin(current, href))[0]
            parsed_next = urlparse(next_url)
            if parsed_next.scheme in {"http", "https"} and parsed_next.netloc == origin and should_follow(parsed_next.path):
                queue.append(next_url)

    return documents


def load_documents(input_value: str, max_pages: int) -> list[SourceDocument]:
    parsed = urlparse(input_value)
    if parsed.scheme in {"http", "https"}:
        return crawl_website(input_value, max_pages=max_pages)
    return load_markdown_docs(input_value)
