from __future__ import annotations

import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import AppConfig, DEFAULT_LLM_MODEL
from .models import RuleRow, SourceDocument

PAGE_TYPE_TO_PREFIX = {
    "layout": "LAY",
    "detail": "DET",
    "list": "LST",
    "create": "CRE",
    "approval": "APV",
}
SUPPORTED_OPENAI_API_STYLES = {"auto", "responses", "chat_completions"}


class LLMExtractorError(RuntimeError):
    """当基于 OpenAI 的抽取流程无法完成时抛出。"""


class OpenAIAPIHTTPError(LLMExtractorError):
    """当 OpenAI 风格接口返回 HTTP 错误时抛出。"""

    def __init__(self, endpoint: str, status_code: int, detail: str) -> None:
        self.endpoint = endpoint
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"OpenAI API 请求失败，接口={endpoint}，HTTP {status_code}: {detail}")


def can_use_openai_llm(config: AppConfig) -> bool:
    return bool(config.openai.api_key)


def resolve_llm_model(config: AppConfig, value: str | None = None) -> str:
    return value or config.openai.model or DEFAULT_LLM_MODEL


def resolve_openai_api_style(config: AppConfig) -> str:
    style = (config.openai.api_style or "").strip() or "auto"
    if style not in SUPPORTED_OPENAI_API_STYLES:
        raise LLMExtractorError(
            f"不支持的 OpenAI 接口类型：{style}。可选值为 auto、responses、chat_completions。"
        )
    return style


def extract_rules_with_llm(docs: list[SourceDocument], config: AppConfig, model: str | None = None) -> list[RuleRow]:
    if not can_use_openai_llm(config):
        raise LLMExtractorError(f"当 extractor=llm 时，必须在 {config.config_path} 中配置 OpenAI API key。")

    selected_model = resolve_llm_model(config, model)
    selected_api_style = resolve_openai_api_style(config)
    rows: list[RuleRow] = []

    for doc in docs:
        payload = _extract_doc_payload(doc, config, selected_model, selected_api_style)
        rows.extend(_rows_from_payload(payload, doc))

    return rows


def _extract_doc_payload(doc: SourceDocument, config: AppConfig, model: str, api_style: str) -> dict[str, object]:
    if api_style == "responses":
        return _extract_doc_payload_via_responses(doc, config, model)
    if api_style == "chat_completions":
        return _extract_doc_payload_via_chat_completions(doc, config, model)
    if api_style == "auto":
        try:
            return _extract_doc_payload_via_responses(doc, config, model)
        except LLMExtractorError:
            return _extract_doc_payload_via_chat_completions(doc, config, model)
    raise LLMExtractorError(f"不支持的 OpenAI 接口类型：{api_style}")


def _extract_doc_payload_via_responses(doc: SourceDocument, config: AppConfig, model: str) -> dict[str, object]:
    request_payload = {
        "model": model,
        "store": False,
        "instructions": _build_instructions(),
        "input": _build_doc_input(doc),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "uiux_rules",
                "strict": True,
                "schema": _rule_schema(),
            }
        },
    }
    raw = _request_openai_json(request_payload, config, endpoint="responses")
    output_text = _extract_output_text_from_responses(raw)
    return _parse_structured_output_json(output_text)


def _extract_doc_payload_via_chat_completions(doc: SourceDocument, config: AppConfig, model: str) -> dict[str, object]:
    try:
        request_payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": _build_instructions()},
                {"role": "user", "content": _build_doc_input(doc)},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "uiux_rules",
                    "strict": True,
                    "schema": _rule_schema(),
                },
            },
        }
        raw = _request_openai_json(request_payload, config, endpoint="chat/completions")
        output_text = _extract_output_text_from_chat_completions(raw)
        return _parse_structured_output_json(output_text)
    except LLMExtractorError as structured_error:
        if "模型拒绝执行抽取" in str(structured_error):
            raise
        try:
            return _extract_doc_payload_via_chat_completions_plain_json(doc, config, model)
        except LLMExtractorError as plain_error:
            raise LLMExtractorError(
                f"Chat Completions 抽取失败。结构化模式错误：{structured_error}；纯文本 JSON 兜底错误：{plain_error}"
            ) from plain_error


def _extract_doc_payload_via_chat_completions_plain_json(
    doc: SourceDocument,
    config: AppConfig,
    model: str,
) -> dict[str, object]:
    request_payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": _build_plain_json_instructions()},
            {"role": "user", "content": _build_doc_input(doc)},
        ],
    }
    raw = _request_openai_json(request_payload, config, endpoint="chat/completions")
    output_text = _extract_output_text_from_chat_completions(raw)
    return _parse_structured_output_json(output_text)


def _request_openai_json(request_payload: dict[str, object], config: AppConfig, endpoint: str) -> dict[str, object]:
    base_url = config.openai.base_url.rstrip("/")
    api_key = config.openai.api_key
    body = json.dumps(request_payload).encode("utf-8")
    request = Request(
        f"{base_url}/{endpoint}",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=120) as response:
            data = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        exc.close()
        raise OpenAIAPIHTTPError(endpoint, exc.code, detail) from exc
    except URLError as exc:
        raise LLMExtractorError(f"OpenAI API 请求失败，接口={endpoint}：{exc}") from exc

    try:
        return json.loads(data)
    except json.JSONDecodeError as exc:
        raise LLMExtractorError(f"OpenAI 响应 JSON 解析失败，接口={endpoint}：{exc}") from exc


def _parse_structured_output_json(output_text: str) -> dict[str, object]:
    candidate = _extract_json_candidate(output_text)
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise LLMExtractorError(f"结构化输出 JSON 解析失败：{exc}") from exc


def _extract_output_text_from_responses(response: dict[str, object]) -> str:
    if isinstance(response.get("output_text"), str) and response["output_text"]:
        return str(response["output_text"])

    for item in response.get("output", []):
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") == "output_text" and isinstance(content.get("text"), str):
                return str(content["text"])
            if content.get("type") == "refusal" and isinstance(content.get("refusal"), str):
                raise LLMExtractorError(f"模型拒绝执行抽取：{content['refusal']}")

    raise LLMExtractorError("OpenAI 响应中未包含结构化输出文本。")


def _extract_output_text_from_chat_completions(response: dict[str, object]) -> str:
    choices = response.get("choices", [])
    if not isinstance(choices, list) or not choices:
        raise LLMExtractorError("Chat Completions 响应中未包含 choices。")

    message = choices[0].get("message", {}) if isinstance(choices[0], dict) else {}
    if not isinstance(message, dict):
        raise LLMExtractorError("Chat Completions 响应中的 message 结构无效。")

    refusal = message.get("refusal")
    if isinstance(refusal, str) and refusal:
        raise LLMExtractorError(f"模型拒绝执行抽取：{refusal}")

    content = message.get("content")
    if isinstance(content, str) and content.strip():
        return content
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            if item.get("type") in {"text", "output_text"} and isinstance(item.get("text"), str):
                text_parts.append(str(item["text"]))
        if text_parts:
            return "\n".join(text_parts)

    raise LLMExtractorError("Chat Completions 响应中未包含可解析的结构化输出文本。")


def _build_instructions() -> str:
    return (
        "你是一个 UI/UX 规范规则抽取器。"
        "请从输入内容中提炼结构化规则，并遵守以下要求："
        "1. 规则必须原子化，每条规则只描述一个属性。"
        "2. 规则分为 foundation、component、global 三层。"
        "3. 如果规则有条件，condition_if / then_clause / else_clause 必须使用 If / Then / Else 结构。"
        "4. component 规则要覆盖不同交互状态的视觉参数。"
        "5. global 规则要把动态行为转成逻辑断言，例如触发条件、关闭逻辑、反馈位置。"
        "6. 必须寻找禁止项，并写入 anti_pattern。"
        "7. 仅输出有明确证据支持的规则；没有证据就不要猜。"
        "8. 所有字段都必须返回字符串；不适用时返回空字符串。"
        "9. source_ref 必须使用输入文档的 location；evidence 必须是简短证据摘要，不要长段复制。"
        "10. 如果输入文档限定了层级，只输出该层级数组，其余层级返回空数组。"
    )


def _build_plain_json_instructions() -> str:
    return (
        _build_instructions()
        + "11. 你必须只返回一个合法的 JSON 对象，不要附加解释。"
        + "12. 不要输出 Markdown 代码块，不要输出前后说明文字。"
        + "13. 顶层字段必须为 foundation_rules、component_rules、global_rules。"
    )


def _build_doc_input(doc: SourceDocument) -> str:
    text = _trim(doc.text, 12000)
    css = "\n\n".join(doc.css_blocks[:3])
    css = _trim(css, 6000)
    allowed_layers = _allowed_layers(doc)
    parts = [
        f"location: {doc.location}",
        f"title: {doc.title}",
        f"source_type: {doc.source_type}",
        f"source_bucket: {doc.source_bucket or 'unrestricted'}",
        f"allowed_layers: {', '.join(allowed_layers)}",
        "",
        "[text]",
        text or "(empty)",
    ]
    if css:
        parts.extend(["", "[css]", css])
    return "\n".join(parts)


def _allowed_layers(doc: SourceDocument) -> list[str]:
    if doc.source_bucket in {"foundation", "component", "global"}:
        return [doc.source_bucket]
    return ["foundation", "component", "global"]


def _trim(value: str, max_chars: int) -> str:
    cleaned = (value or "").strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[:max_chars].rstrip() + "\n...[truncated]"


def _extract_json_candidate(output_text: str) -> str:
    text = (output_text or "").strip()
    if not text:
        raise LLMExtractorError("模型未返回可解析的 JSON 文本。")

    direct_candidate = _try_parse_json_candidate(text)
    if direct_candidate is not None:
        return direct_candidate

    fenced_match = re.search(r"```(?:json)?\s*(.*?)```", text, flags=re.S | re.I)
    if fenced_match:
        fenced_candidate = fenced_match.group(1).strip()
        parsed_fenced = _try_parse_json_candidate(fenced_candidate)
        if parsed_fenced is not None:
            return parsed_fenced

    balanced_candidate = _find_balanced_json_object(text)
    if balanced_candidate is not None:
        return balanced_candidate

    raise LLMExtractorError("模型返回了文本，但其中未找到可解析的 JSON 对象。")


def _try_parse_json_candidate(candidate: str) -> str | None:
    try:
        json.loads(candidate)
        return candidate
    except json.JSONDecodeError:
        return None


def _find_balanced_json_object(text: str) -> str | None:
    start_index = text.find("{")
    while start_index != -1:
        depth = 0
        in_string = False
        escaped = False
        for index in range(start_index, len(text)):
            char = text[index]
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start_index : index + 1]
                    if _try_parse_json_candidate(candidate) is not None:
                        return candidate
                    break
        start_index = text.find("{", start_index + 1)
    return None


def _rule_schema() -> dict[str, object]:
    rule_object = {
        "type": "object",
        "additionalProperties": False,
        "required": [
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
        ],
        "properties": {
            "page_type": {"type": "string"},
            "subject": {"type": "string"},
            "component": {"type": "string"},
            "state": {"type": "string"},
            "property_name": {"type": "string"},
            "condition_if": {"type": "string"},
            "then_clause": {"type": "string"},
            "else_clause": {"type": "string"},
            "default_value": {"type": "string"},
            "preferred_pattern": {"type": "string"},
            "anti_pattern": {"type": "string"},
            "evidence": {"type": "string"},
            "source_ref": {"type": "string"},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["foundation_rules", "component_rules", "global_rules"],
        "properties": {
            "foundation_rules": {"type": "array", "items": rule_object},
            "component_rules": {"type": "array", "items": rule_object},
            "global_rules": {"type": "array", "items": rule_object},
        },
    }


def _rows_from_payload(payload: dict[str, object], doc: SourceDocument) -> list[RuleRow]:
    rows: list[RuleRow] = []
    layer_specs = [
        ("foundation_rules", "foundation", "FDN"),
        ("component_rules", "component", "CMP"),
        ("global_rules", "global", ""),
    ]

    for payload_key, layer, fixed_prefix in layer_specs:
        for item in payload.get(payload_key, []):
            if not isinstance(item, dict):
                continue
            row = _coerce_rule(item, doc, layer, fixed_prefix)
            if row is not None:
                rows.append(row)

    return rows


def _coerce_rule(item: dict[str, object], doc: SourceDocument, layer: str, fixed_prefix: str) -> RuleRow | None:
    page_type = _normalize_page_type(str(item.get("page_type", "")).strip(), layer)
    subject = str(item.get("subject", "")).strip()
    component = str(item.get("component", "")).strip()
    state = str(item.get("state", "")).strip() or "default"
    property_name = str(item.get("property_name", "")).strip()
    default_value = str(item.get("default_value", "")).strip()

    if not subject or not property_name or not default_value:
        return None

    condition_if = _ensure_prefix(str(item.get("condition_if", "")).strip(), "If ", fallback=f"If 对象 = {subject}")
    then_clause = _ensure_prefix(str(item.get("then_clause", "")).strip(), "Then ", fallback=f"Then {property_name} 必须为 {default_value}")
    else_clause = _ensure_prefix(str(item.get("else_clause", "")).strip(), "Else ", fallback="Else 保持默认规则")

    prefix = fixed_prefix or PAGE_TYPE_TO_PREFIX.get(page_type, "LAY")
    source_ref = str(item.get("source_ref", "")).strip() or doc.location

    return RuleRow(
        prefix=prefix,
        layer=layer,
        page_type=page_type,
        subject=subject,
        component=component or (subject if layer == "component" else ""),
        state=state,
        property_name=property_name,
        condition_if=condition_if,
        then_clause=then_clause,
        else_clause=else_clause,
        default_value=default_value,
        preferred_pattern=str(item.get("preferred_pattern", "")).strip(),
        anti_pattern=str(item.get("anti_pattern", "")).strip(),
        evidence=str(item.get("evidence", "")).strip(),
        source_ref=source_ref,
    )


def _normalize_page_type(value: str, layer: str) -> str:
    if layer == "foundation":
        return "foundation"
    if layer == "component":
        return "component"
    return value if value in PAGE_TYPE_TO_PREFIX else "layout"


def _ensure_prefix(value: str, prefix: str, fallback: str) -> str:
    if not value:
        return fallback
    return value if value.startswith(prefix) else f"{prefix}{value}"
