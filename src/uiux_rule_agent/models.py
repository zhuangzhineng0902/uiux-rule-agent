from __future__ import annotations

from dataclasses import dataclass, field

MARKDOWN_BUCKET_ALIASES = {
    "foundation-rules": "foundation",
    "foundation-rules.csv": "foundation",
    "component-rules": "component",
    "component-rules.csv": "component",
    "global-layout-rules": "global",
    "global-layout-rules.csv": "global",
}

CSV_COLUMNS = [
    "rule_id",
    "prefix",
    "layer",
    "page_type",
    "subject",
    "component",
    "state",
    "property_name",
    "condition_if",
    "then_clause",
    "else_clause",
    "default_value",
    "preferred_pattern",
    "anti_pattern",
    "evidence",
    "source_ref",
]

COMPONENT_KEYWORDS = {
    "button": ["button", ".btn", " btn", "cta"],
    "input": ["input", "textfield", "form-control", "field"],
    "textarea": ["textarea"],
    "select": ["select", "dropdown", "combobox"],
    "table": ["table", "datatable", "grid"],
    "toolbar": ["toolbar", "action-bar", "topbar"],
    "modal": ["modal", "dialog"],
    "drawer": ["drawer", "sheet", "sidepanel"],
    "tabs": ["tabs", "tab", "segmented"],
    "toast": ["toast", "snackbar", "message"],
    "card": ["card"],
    "pagination": ["pagination", "pager"],
    "form": ["form"],
}

STATE_KEYWORDS = {
    "hover": [":hover", "hovered", "is-hover"],
    "focus": [":focus", ":focus-visible", "focused", "is-focus"],
    "active": [":active", ".active", ".is-active", "selected", 'aria-selected="true"'],
    "disabled": [":disabled", "[disabled]", ".disabled", ".is-disabled", 'aria-disabled="true"'],
    "open": [".open", ".is-open", "[open]", 'aria-expanded="true"'],
    "error": [".error", ".is-error", ":invalid", "invalid", 'aria-invalid="true"'],
    "loading": [".loading", ".is-loading", "spinner"],
    "selected": [".selected", ".is-selected", 'aria-current="page"'],
}

COMPONENT_STATE_REQUIREMENTS = {
    "button": ["default", "hover", "focus", "active", "disabled"],
    "input": ["default", "focus", "disabled", "error"],
    "textarea": ["default", "focus", "disabled", "error"],
    "select": ["default", "focus", "open", "disabled", "error"],
    "tabs": ["default", "hover", "focus", "active", "selected"],
    "modal": ["default", "open"],
    "drawer": ["default", "open"],
    "table": ["default", "hover", "selected"],
}

FOUNDATION_PROPS = {
    "color",
    "background-color",
    "font-size",
    "font-weight",
    "line-height",
    "font-family",
    "border-radius",
    "box-shadow",
    "gap",
    "padding-top",
    "padding-right",
    "padding-bottom",
    "padding-left",
    "margin-top",
    "margin-right",
    "margin-bottom",
    "margin-left",
}

COMPONENT_PROPS = FOUNDATION_PROPS | {
    "border-color",
    "border-width",
    "border-style",
    "opacity",
    "width",
    "height",
    "outline",
}

GLOBAL_PROPS = {
    "width",
    "max-width",
    "min-width",
    "padding-top",
    "padding-right",
    "padding-bottom",
    "padding-left",
    "margin-top",
    "margin-right",
    "margin-bottom",
    "margin-left",
    "gap",
    "grid-template-columns",
    "top",
    "right",
    "bottom",
    "left",
    "z-index",
}


@dataclass(slots=True)
class CSSRule:
    selector: str
    declarations: dict[str, str]
    condition: str = ""


@dataclass(slots=True)
class SourceDocument:
    source_type: str
    location: str
    title: str
    text: str
    source_bucket: str = ""
    css_blocks: list[str] = field(default_factory=list)
    css_rules: list[CSSRule] = field(default_factory=list)
    element_hints: set[str] = field(default_factory=set)


@dataclass(slots=True)
class RuleRow:
    prefix: str
    layer: str
    page_type: str
    subject: str
    component: str
    state: str
    property_name: str
    condition_if: str
    then_clause: str
    else_clause: str
    default_value: str
    preferred_pattern: str
    anti_pattern: str
    evidence: str
    source_ref: str
    rule_id: str = ""

    def to_row(self) -> dict[str, str]:
        return {column: getattr(self, column) for column in CSV_COLUMNS}
