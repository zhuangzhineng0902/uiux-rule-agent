from __future__ import annotations

import re
from collections import defaultdict

from .css_parser import normalize_space
from .models import (
    COMPONENT_KEYWORDS,
    COMPONENT_PROPS,
    COMPONENT_STATE_REQUIREMENTS,
    FOUNDATION_PROPS,
    GLOBAL_PROPS,
    STATE_KEYWORDS,
    RuleRow,
    SourceDocument,
)

HEX_COLOR_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")
SIZE_RE = re.compile(r"\b\d+(?:\.\d+)?(?:px|rem|em|%)\b")
NEGATIVE_RE = re.compile(r"(禁止|不要|不得|避免|不可|不能|严禁|must not|avoid|do not|never)", re.I)
LAYOUT_SELECTOR_RE = re.compile(r"(layout|container|main|content|page|header|footer|sidebar|sider|toolbar|panel|shell)", re.I)

SYNTHETIC_STATE_DEFAULTS = {
    "hover": ("state_definition", "required"),
    "focus": ("state_definition", "required"),
    "active": ("state_definition", "required"),
    "disabled": ("state_definition", "required"),
    "error": ("state_definition", "required"),
    "open": ("state_definition", "required"),
    "selected": ("state_definition", "required"),
}


def split_lines(text: str) -> list[str]:
    return [normalize_space(line) for line in re.split(r"[\r\n]+", text or "") if normalize_space(line)]


def humanize(value: str) -> str:
    return normalize_space(re.sub(r"[_\-]+", " ", value))


def humanize_media_condition(condition: str) -> str:
    text = condition or ""
    text = re.sub(r"\(\s*max-width\s*:\s*([^)]+)\)", r"屏幕宽度 <= \1", text, flags=re.I)
    text = re.sub(r"\(\s*min-width\s*:\s*([^)]+)\)", r"屏幕宽度 >= \1", text, flags=re.I)
    text = re.sub(r"\(\s*max-height\s*:\s*([^)]+)\)", r"屏幕高度 <= \1", text, flags=re.I)
    text = re.sub(r"\(\s*min-height\s*:\s*([^)]+)\)", r"屏幕高度 >= \1", text, flags=re.I)
    text = text.replace("and", "且")
    return normalize_space(text)


def selector_subject(selector: str) -> str:
    value = re.sub(r":[\w\-]+(\([^)]+\))?", "", selector or "")
    value = re.sub(r"[^0-9A-Za-z\u4e00-\u9fa5_\-]+", " ", value)
    value = humanize(value)
    return value[:60] or "unnamed-subject"


def infer_component(value: str) -> str:
    lower = (value or "").lower()
    for component, keywords in COMPONENT_KEYWORDS.items():
        if any(keyword in lower for keyword in keywords):
            return component
    return ""


def infer_state(value: str) -> str:
    lower = (value or "").lower()
    for state, keywords in STATE_KEYWORDS.items():
        if any(keyword in lower for keyword in keywords):
            return state
    return "default"


def infer_page_type(doc: SourceDocument) -> tuple[str, str]:
    corpus = f"{doc.location} {doc.title} {doc.text}".lower()
    if any(token in corpus for token in ["审批", "审核", "approval", "approve", "review task"]):
        return "approval", "APV"
    if any(token in corpus for token in ["新建", "创建", "新增", "create", "new"]) and any(
        token in corpus for token in ["表单", "form", "submit", "保存"]
    ):
        return "create", "CRE"
    if any(token in corpus for token in ["列表", "table", "list", "search", "filter"]):
        return "list", "LST"
    if any(token in corpus for token in ["详情", "detail", "profile", "summary"]):
        return "detail", "DET"
    return "layout", "LAY"


def infer_foundation_property(label: str, value: str) -> str:
    text = f"{label} {value}".lower()
    if any(token in text for token in ["color", "颜色", "主色", "背景色", "文字色", "边框色"]):
        return "color"
    if any(token in text for token in ["font-size", "font size", "字号", "字体大小"]):
        return "font-size"
    if any(token in text for token in ["font-weight", "font weight", "字重"]):
        return "font-weight"
    if any(token in text for token in ["line-height", "line height", "行高"]):
        return "line-height"
    if any(token in text for token in ["font-family", "font family", "字体"]):
        return "font-family"
    if any(token in text for token in ["radius", "圆角"]):
        return "border-radius"
    if any(token in text for token in ["shadow", "阴影"]):
        return "box-shadow"
    if any(token in text for token in ["spacing", "space", "间距", "padding", "margin", "gap"]):
        return "gap"
    if HEX_COLOR_RE.search(value):
        return "color"
    if SIZE_RE.search(value):
        return "size"
    return ""


def explode_declaration(name: str, value: str) -> list[tuple[str, str]]:
    prop = normalize_space(name.lower())
    raw = normalize_space(value)

    if prop in {"padding", "margin"}:
        parts = raw.split()
        if len(parts) == 1:
            top = right = bottom = left = parts[0]
        elif len(parts) == 2:
            top = bottom = parts[0]
            right = left = parts[1]
        elif len(parts) == 3:
            top = parts[0]
            right = left = parts[1]
            bottom = parts[2]
        elif len(parts) >= 4:
            top, right, bottom, left = parts[:4]
        else:
            return []

        return [
            (f"{prop}-top", top),
            (f"{prop}-right", right),
            (f"{prop}-bottom", bottom),
            (f"{prop}-left", left),
        ]

    if prop == "border":
        rules: list[tuple[str, str]] = []
        width = re.search(r"\b\d+(?:\.\d+)?px\b", raw)
        color = HEX_COLOR_RE.search(raw)
        style = next((token for token in raw.split() if token in {"solid", "dashed", "dotted", "none"}), "")
        if width:
            rules.append(("border-width", width.group(0)))
        if style:
            rules.append(("border-style", style))
        if color:
            rules.append(("border-color", color.group(0)))
        return rules or [(prop, raw)]

    if prop == "background":
        color = HEX_COLOR_RE.search(raw)
        return [("background-color", color.group(0))] if color else [(prop, raw)]

    return [(prop, raw)]


def preferred_pattern(layer: str) -> str:
    if layer == "foundation":
        return "优先使用设计令牌或 CSS 变量统一引用，避免组件级硬编码"
    if layer == "component":
        return "为每个组件状态分别声明单一属性值，确保规则原子化"
    return "把动态行为写成可测试的 If-Then-Else 逻辑断言"


def component_anti_pattern(component: str, state: str, prop: str) -> str:
    if state == "focus":
        return "禁止移除焦点指示且没有等价替代反馈"
    if state == "disabled":
        return "禁止 disabled 态仍保留可点击暗示"
    if state == "error":
        return "禁止仅改文案而不提供错误态视觉反馈"
    return f"禁止 {component} 在 {state} 态混用多个 {prop} 取值"


def make_rule(
    prefix: str,
    layer: str,
    page_type: str,
    subject: str,
    component: str,
    state: str,
    property_name: str,
    condition_if: str,
    then_clause: str,
    else_clause: str,
    default_value: str,
    preferred: str,
    anti_pattern: str,
    evidence: str,
    source_ref: str,
) -> RuleRow:
    return RuleRow(
        prefix=prefix,
        layer=layer,
        page_type=page_type,
        subject=subject,
        component=component,
        state=state,
        property_name=property_name,
        condition_if=condition_if,
        then_clause=then_clause,
        else_clause=else_clause,
        default_value=default_value,
        preferred_pattern=preferred,
        anti_pattern=anti_pattern,
        evidence=evidence,
        source_ref=source_ref,
    )


def extract_if_then_else_rules(doc: SourceDocument, page_type: str, prefix: str) -> list[RuleRow]:
    rows: list[RuleRow] = []

    patterns = [
        re.compile(r"如果\s*(.+?)\s*[，,]\s*则\s*(.+?)(?:\s*[，,]\s*否则\s*(.+))?$"),
        re.compile(r"If\s+(.+?),\s*then\s+(.+?)(?:,\s*else\s+(.+))?$", re.I),
    ]

    for line in split_lines(doc.text):
        for pattern in patterns:
            match = pattern.search(line)
            if not match:
                continue
            condition = normalize_space(match.group(1))
            then_clause = normalize_space(match.group(2))
            else_clause = normalize_space(match.group(3) if match.lastindex and match.lastindex >= 3 else "") or "Else 保持默认规则"
            rows.append(
                make_rule(
                    prefix=prefix,
                    layer="global",
                    page_type=page_type,
                    subject="explicit-if-then-else",
                    component="",
                    state="default",
                    property_name="logical-assertion",
                    condition_if=f"If {condition}",
                    then_clause=f"Then {then_clause}",
                    else_clause=else_clause if else_clause.startswith("Else ") else f"Else {else_clause}",
                    default_value=then_clause,
                    preferred=preferred_pattern("global"),
                    anti_pattern="禁止将条件规则写成无法测试的模糊描述",
                    evidence=line,
                    source_ref=doc.location,
                )
            )
            break

    return rows


def extract_foundation_rules(docs: list[SourceDocument]) -> list[RuleRow]:
    rows: list[RuleRow] = []

    for doc in docs:
        for line in split_lines(doc.text):
            if "：" not in line and ":" not in line:
                continue
            label, value = re.split(r"[:：]", line, maxsplit=1)
            label = humanize(label)
            value = normalize_space(value).rstrip(";")
            if not label or not value or len(label) > 40 or len(value) > 80:
                continue
            prop = infer_foundation_property(label, value)
            if not prop:
                continue
            rows.append(
                make_rule(
                    prefix="FDN",
                    layer="foundation",
                    page_type="foundation",
                    subject=label,
                    component="",
                    state="default",
                    property_name=prop,
                    condition_if=f"If 语义令牌 = {label}",
                    then_clause=f"Then {prop} 必须为 {value}",
                    else_clause=f"Else 禁止使用未登记的 {prop} 取值",
                    default_value=value,
                    preferred=preferred_pattern("foundation"),
                    anti_pattern=f"禁止在组件中硬编码与 {label} 相近但不一致的 {prop}",
                    evidence=line,
                    source_ref=doc.location,
                )
            )

        for css_rule in doc.css_rules:
            selector = css_rule.selector.lower()
            is_foundation_selector = selector in {":root", "html", "body", "h1", "h2", "h3", "h4", "h5", "h6"}

            for name, value in css_rule.declarations.items():
                if name.startswith("--"):
                    prop = infer_foundation_property(name, value)
                    if not prop:
                        continue
                    subject = humanize(name[2:])
                    rows.append(
                        make_rule(
                            prefix="FDN",
                            layer="foundation",
                            page_type="foundation",
                            subject=subject,
                            component="",
                            state="default",
                            property_name=prop,
                            condition_if=f"If 语义令牌 = {subject}",
                            then_clause=f"Then {prop} 必须为 {value}",
                            else_clause=f"Else 禁止使用未收敛的 {prop} 临时值",
                            default_value=value,
                            preferred=preferred_pattern("foundation"),
                            anti_pattern=f"禁止跳过令牌层直接在组件里硬编码 {value}",
                            evidence=f"{css_rule.selector} -> {name}: {value}",
                            source_ref=doc.location,
                        )
                    )
                    continue

                if not is_foundation_selector:
                    continue

                for atomic_prop, atomic_value in explode_declaration(name, value):
                    if atomic_prop not in FOUNDATION_PROPS:
                        continue
                    subject = selector_subject(css_rule.selector)
                    rows.append(
                        make_rule(
                            prefix="FDN",
                            layer="foundation",
                            page_type="foundation",
                            subject=subject,
                            component="",
                            state="default",
                            property_name=atomic_prop,
                            condition_if=f"If 基础对象 = {subject}",
                            then_clause=f"Then {atomic_prop} 必须为 {atomic_value}",
                            else_clause="Else 禁止出现未登记的基础样式值",
                            default_value=atomic_value,
                            preferred=preferred_pattern("foundation"),
                            anti_pattern=f"禁止 {subject} 在同一层级混用多个 {atomic_prop}",
                            evidence=f"{css_rule.selector} -> {name}: {value}",
                            source_ref=doc.location,
                        )
                    )

    return rows


def extract_component_rules(docs: list[SourceDocument]) -> list[RuleRow]:
    raw_rules: list[tuple[SourceDocument, str, str, str, str, str, str]] = []
    rows: list[RuleRow] = []
    detected_components: set[str] = set()
    seen_states: dict[str, set[str]] = defaultdict(set)
    default_values: dict[tuple[str, str], str] = {}

    for doc in docs:
        detected_components.update(doc.element_hints)

        for css_rule in doc.css_rules:
            component = infer_component(css_rule.selector)
            if not component:
                continue

            state = infer_state(css_rule.selector)
            detected_components.add(component)
            seen_states[component].add(state)

            for name, value in css_rule.declarations.items():
                for atomic_prop, atomic_value in explode_declaration(name, value):
                    if atomic_prop not in COMPONENT_PROPS:
                        continue
                    if state == "default" and (component, atomic_prop) not in default_values:
                        default_values[(component, atomic_prop)] = atomic_value
                    raw_rules.append((doc, css_rule.selector, css_rule.condition, component, state, atomic_prop, atomic_value))

    for doc, selector, condition, component, state, prop, value in raw_rules:
        parts = []
        if condition:
            parts.append(humanize_media_condition(condition))
        parts.append(f"组件 = {component}")
        parts.append(f"状态 = {state}")
        fallback = default_values.get((component, prop), "")
        else_clause = f"Else 恢复 default 状态的 {prop} = {fallback}" if state != "default" and fallback else f"Else 禁止出现未定义的 {prop} 变化"

        rows.append(
            make_rule(
                prefix="CMP",
                layer="component",
                page_type="component",
                subject=component,
                component=component,
                state=state,
                property_name=prop,
                condition_if="If " + " and ".join(parts),
                then_clause=f"Then {prop} 必须为 {value}",
                else_clause=else_clause,
                default_value=value,
                preferred=preferred_pattern("component"),
                anti_pattern=component_anti_pattern(component, state, prop),
                evidence=f"{selector} -> {prop}: {value}",
                source_ref=doc.location,
            )
        )

    for component in sorted(detected_components):
        for required_state in COMPONENT_STATE_REQUIREMENTS.get(component, []):
            if required_state == "default" or required_state in seen_states[component]:
                continue
            property_name, default_value = SYNTHETIC_STATE_DEFAULTS.get(required_state, ("state_definition", "required"))
            rows.append(
                make_rule(
                    prefix="CMP",
                    layer="component",
                    page_type="component",
                    subject=component,
                    component=component,
                    state=required_state,
                    property_name=property_name,
                    condition_if=f"If 组件 = {component} and 状态 = {required_state}",
                    then_clause=f"Then {property_name} 必须被显式定义",
                    else_clause=f"Else 禁止 {component} 缺失 {required_state} 态规则",
                    default_value=default_value,
                    preferred=preferred_pattern("component"),
                    anti_pattern=f"禁止 {component} 缺失 {required_state} 态导致状态不完整",
                    evidence="synthetic:state-completeness",
                    source_ref="agent:state-completeness",
                )
            )

    return rows


def extract_global_rules(docs: list[SourceDocument]) -> list[RuleRow]:
    rows: list[RuleRow] = []

    for doc in docs:
        page_type, prefix = infer_page_type(doc)
        rows.extend(extract_if_then_else_rules(doc, page_type, prefix))

        for css_rule in doc.css_rules:
            if not css_rule.condition and not LAYOUT_SELECTOR_RE.search(css_rule.selector):
                continue

            for name, value in css_rule.declarations.items():
                for atomic_prop, atomic_value in explode_declaration(name, value):
                    if atomic_prop not in GLOBAL_PROPS:
                        continue

                    parts = []
                    if css_rule.condition:
                        parts.append(humanize_media_condition(css_rule.condition))
                    parts.append(f"对象 = {selector_subject(css_rule.selector)}")

                    rows.append(
                        make_rule(
                            prefix=prefix,
                            layer="global",
                            page_type=page_type,
                            subject=selector_subject(css_rule.selector),
                            component="",
                            state="default",
                            property_name=atomic_prop,
                            condition_if="If " + " and ".join(parts),
                            then_clause=f"Then {atomic_prop} 必须为 {atomic_value}",
                            else_clause="Else 保持非当前断点或非当前布局场景的既定规则",
                            default_value=atomic_value,
                            preferred=preferred_pattern("global"),
                            anti_pattern=f"禁止 {selector_subject(css_rule.selector)} 在同一场景下出现多个冲突的 {atomic_prop}",
                            evidence=f"{css_rule.selector} -> {name}: {value}",
                            source_ref=doc.location,
                        )
                    )

        for line in split_lines(doc.text):
            lower = line.lower()

            if re.search(r"(点击|单击).*(遮罩|蒙层).*(不关闭|不得关闭|不要关闭).*(弹窗|模态|对话框|抽屉|下拉)", line, re.I):
                rows.append(
                    make_rule(
                        prefix=prefix,
                        layer="global",
                        page_type=page_type,
                        subject="overlay-dismiss",
                        component="modal",
                        state="open",
                        property_name="dismiss-on-overlay-click",
                        condition_if="If 用户点击遮罩层",
                        then_clause="Then 弹层不得关闭",
                        else_clause="Else 保持当前阻断式交互并提供明确关闭入口",
                        default_value="false",
                        preferred=preferred_pattern("global"),
                        anti_pattern="禁止阻断式弹层在点击遮罩后无确认直接关闭",
                        evidence=line,
                        source_ref=doc.location,
                    )
                )
            elif re.search(r"(点击|单击).*(遮罩|蒙层).*(关闭|收起).*(弹窗|模态|对话框|抽屉|下拉)", line, re.I):
                rows.append(
                    make_rule(
                        prefix=prefix,
                        layer="global",
                        page_type=page_type,
                        subject="overlay-dismiss",
                        component="modal",
                        state="open",
                        property_name="dismiss-on-overlay-click",
                        condition_if="If 用户点击遮罩层",
                        then_clause="Then 弹层必须关闭",
                        else_clause="Else 保持弹层打开并提供明确关闭入口",
                        default_value="true",
                        preferred=preferred_pattern("global"),
                        anti_pattern="禁止遮罩层可点击但关闭行为不明确",
                        evidence=line,
                        source_ref=doc.location,
                    )
                )

            if re.search(r"(报错|错误信息|错误提示)", line):
                position = ""
                if "下方" in line or "下边" in line or "字段下" in line:
                    position = "below"
                elif "右侧" in line:
                    position = "right"
                elif "顶部" in line:
                    position = "top"
                elif "toast" in lower or "消息" in line or "提示条" in line:
                    position = "toast"
                if position:
                    rows.append(
                        make_rule(
                            prefix=prefix,
                            layer="global",
                            page_type=page_type,
                            subject="error-feedback",
                            component="form",
                            state="error",
                            property_name="feedback-position",
                            condition_if="If 表单校验失败",
                            then_clause=f"Then 错误信息必须出现在 {position}",
                            else_clause="Else 禁止错误反馈位置在同类场景中漂移",
                            default_value=position,
                            preferred=preferred_pattern("global"),
                            anti_pattern="禁止错误信息位置不固定导致扫描成本增加",
                            evidence=line,
                            source_ref=doc.location,
                        )
                    )

            if re.search(r"(成功|已保存|提交成功|操作成功)", line) and re.search(r"(toast|提示|消息)", line, re.I):
                rows.append(
                    make_rule(
                        prefix=prefix,
                        layer="global",
                        page_type=page_type,
                        subject="success-feedback",
                        component="toast",
                        state="success",
                        property_name="feedback-channel",
                        condition_if="If 操作成功",
                        then_clause="Then 成功反馈必须通过 toast 或消息提示出现",
                        else_clause="Else 禁止成功反馈缺失或与错误反馈混淆",
                        default_value="toast",
                        preferred=preferred_pattern("global"),
                        anti_pattern="禁止成功操作无反馈",
                        evidence=line,
                        source_ref=doc.location,
                    )
                )

            if re.search(r"(加载|loading|提交中)", line, re.I) and re.search(r"(骨架|skeleton|spinner|转圈)", line, re.I):
                channel = "skeleton" if re.search(r"(骨架|skeleton)", line, re.I) else "spinner"
                rows.append(
                    make_rule(
                        prefix=prefix,
                        layer="global",
                        page_type=page_type,
                        subject="loading-feedback",
                        component="",
                        state="loading",
                        property_name="feedback-channel",
                        condition_if="If 页面或操作进入 loading 状态",
                        then_clause=f"Then 必须展示 {channel}",
                        else_clause="Else 禁止用户在无反馈状态下等待",
                        default_value=channel,
                        preferred=preferred_pattern("global"),
                        anti_pattern="禁止 loading 态无可见反馈",
                        evidence=line,
                        source_ref=doc.location,
                    )
                )

            if re.search(r"(未保存|脏数据|内容变更)", line) and re.search(r"(离开|返回|关闭)", line) and re.search(r"(确认|提示|二次确认)", line):
                rows.append(
                    make_rule(
                        prefix=prefix,
                        layer="global",
                        page_type=page_type,
                        subject="unsaved-confirmation",
                        component="modal",
                        state="warning",
                        property_name="leave-guard",
                        condition_if="If 用户尝试离开未保存页面",
                        then_clause="Then 必须触发二次确认",
                        else_clause="Else 禁止直接丢失未保存内容",
                        default_value="confirm-before-leave",
                        preferred=preferred_pattern("global"),
                        anti_pattern="禁止未保存内容在离开时被静默丢弃",
                        evidence=line,
                        source_ref=doc.location,
                    )
                )

            if re.search(r"(删除|移除|作废|驳回|拒绝)", line) and re.search(r"(确认|二次确认|弹窗)", line):
                rows.append(
                    make_rule(
                        prefix=prefix,
                        layer="global",
                        page_type=page_type,
                        subject="destructive-confirmation",
                        component="modal",
                        state="warning",
                        property_name="confirmation-required",
                        condition_if="If 用户触发破坏性操作",
                        then_clause="Then 必须先二次确认",
                        else_clause="Else 禁止直接执行不可逆操作",
                        default_value="true",
                        preferred=preferred_pattern("global"),
                        anti_pattern="禁止破坏性操作无确认直接提交",
                        evidence=line,
                        source_ref=doc.location,
                    )
                )

    return rows


def extract_prohibition_rules(docs: list[SourceDocument]) -> list[RuleRow]:
    rows: list[RuleRow] = []

    for doc in docs:
        page_type, prefix = infer_page_type(doc)

        for line in split_lines(doc.text):
            if not NEGATIVE_RE.search(line):
                continue

            component = infer_component(line)
            lower = line.lower()

            if doc.source_bucket == "foundation":
                row_prefix = "FDN"
                layer = "foundation"
                derived_page_type = "foundation"
                subject = component or "foundation-prohibition"
            elif doc.source_bucket == "component":
                row_prefix = "CMP"
                layer = "component"
                derived_page_type = "component"
                subject = component or "component-prohibition"
            elif doc.source_bucket == "global":
                row_prefix = prefix
                layer = "global"
                derived_page_type = page_type
                subject = component or "global-prohibition"
            elif any(token in lower for token in ["颜色", "字体", "字号", "间距", "圆角", "阴影", "color", "font", "spacing", "radius", "shadow"]):
                row_prefix = "FDN"
                layer = "foundation"
                derived_page_type = "foundation"
                subject = component or "foundation-prohibition"
            elif component:
                row_prefix = "CMP"
                layer = "component"
                derived_page_type = "component"
                subject = component
            else:
                row_prefix = prefix
                layer = "global"
                derived_page_type = page_type
                subject = "global-prohibition"

            rows.append(
                make_rule(
                    prefix=row_prefix,
                    layer=layer,
                    page_type=derived_page_type,
                    subject=subject,
                    component=component,
                    state="default",
                    property_name="prohibition",
                    condition_if="If 命中该显式禁止场景",
                    then_clause="Then 该行为不得发生",
                    else_clause="Else 保持当前安全且一致的交互行为",
                    default_value="forbidden",
                    preferred="把禁止项写成可测试断言，并给出唯一替代实现",
                    anti_pattern=line,
                    evidence=line,
                    source_ref=doc.location,
                )
            )

    return rows


def dedupe_rules(rows: list[RuleRow]) -> list[RuleRow]:
    seen: set[tuple[str, str, str, str, str, str, str, str]] = set()
    output: list[RuleRow] = []

    for row in rows:
        key = (
            row.prefix,
            row.subject,
            row.component,
            row.state,
            row.property_name,
            row.condition_if,
            row.default_value,
            row.anti_pattern,
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(row)

    return output


def generate_rules(docs: list[SourceDocument]) -> list[RuleRow]:
    has_bucketed_markdown = any(doc.source_type == "markdown" and doc.source_bucket for doc in docs)
    if has_bucketed_markdown:
        foundation_docs = [doc for doc in docs if doc.source_type != "markdown" or doc.source_bucket == "foundation"]
        component_docs = [doc for doc in docs if doc.source_type != "markdown" or doc.source_bucket == "component"]
        global_docs = [doc for doc in docs if doc.source_type != "markdown" or doc.source_bucket == "global"]
    else:
        foundation_docs = docs
        component_docs = docs
        global_docs = docs

    rows: list[RuleRow] = []
    rows.extend(extract_foundation_rules(foundation_docs))
    rows.extend(extract_component_rules(component_docs))
    rows.extend(extract_global_rules(global_docs))
    rows.extend(extract_prohibition_rules(docs))
    return dedupe_rules(rows)
