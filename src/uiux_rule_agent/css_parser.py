from __future__ import annotations

import re

from .models import CSSRule

CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)


def normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def parse_declarations(block: str) -> dict[str, str]:
    declarations: dict[str, str] = {}
    for chunk in block.split(";"):
        if ":" not in chunk:
            continue
        name, value = chunk.split(":", 1)
        name = normalize_space(name)
        value = normalize_space(value)
        if name and value:
            declarations[name] = value
    return declarations


def parse_css_rules(css_text: str, condition: str = "") -> list[CSSRule]:
    css = CSS_COMMENT_RE.sub("", css_text or "")
    rules: list[CSSRule] = []
    cursor = 0

    while cursor < len(css):
        start = css.find("{", cursor)
        if start == -1:
            break

        selector = normalize_space(css[cursor:start])
        depth = 1
        end = start + 1

        while end < len(css) and depth:
            if css[end] == "{":
                depth += 1
            elif css[end] == "}":
                depth -= 1
            end += 1

        body = css[start + 1 : end - 1]

        if selector.startswith("@media"):
            next_condition = normalize_space(selector[len("@media") :])
            merged = f"{condition} and {next_condition}" if condition else next_condition
            rules.extend(parse_css_rules(body, merged))
        elif selector and not selector.startswith("@"):
            declarations = parse_declarations(body)
            if declarations:
                rules.append(CSSRule(selector=selector, declarations=declarations, condition=condition))

        cursor = end

    return rules
