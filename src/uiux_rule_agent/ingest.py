from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

from .css_parser import normalize_space, parse_css_rules
from .models import COMPONENT_KEYWORDS, MARKDOWN_BUCKET_ALIASES, SourceDocument

MARKDOWN_SUFFIXES = {".md", ".mdx", ".markdown"}


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


def load_markdown_docs(path_value: str) -> list[SourceDocument]:
    root = Path(path_value)
    if not root.exists():
        raise FileNotFoundError(f"输入路径不存在：{path_value}")
    if root.is_file() and root.suffix.lower() not in MARKDOWN_SUFFIXES:
        raise ValueError(f"仅支持 Markdown 文件输入：{path_value}")

    files = [root] if root.is_file() else sorted(list(root.rglob("*.md")) + list(root.rglob("*.mdx")) + list(root.rglob("*.markdown")))
    if not files:
        raise ValueError(f"目录中未找到 Markdown 文件：{path_value}")
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


def load_documents(input_value: str) -> list[SourceDocument]:
    parsed = urlparse(input_value)
    if parsed.scheme in {"http", "https"}:
        raise ValueError("当前版本仅支持本地 Markdown 文件或目录，不支持网站 URL。")
    return load_markdown_docs(input_value)
