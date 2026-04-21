from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib

DEFAULT_CONFIG_PATH = "config/ai.toml"
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_LLM_MODEL = "gpt-5.4-mini"
DEFAULT_OPENAI_API_STYLE = "auto"
DEFAULT_EXTRACTOR = "auto"
DEFAULT_INPUT_SOURCE = ""
DEFAULT_OUTPUT_DIR = "data"


@dataclass(slots=True)
class OpenAIConfig:
    api_key: str = ""
    base_url: str = DEFAULT_OPENAI_BASE_URL
    model: str = DEFAULT_LLM_MODEL
    api_style: str = DEFAULT_OPENAI_API_STYLE


@dataclass(slots=True)
class ExtractionConfig:
    strategy: str = DEFAULT_EXTRACTOR


@dataclass(slots=True)
class InputConfig:
    sources: list[str]


@dataclass(slots=True)
class OutputConfig:
    directory: str = DEFAULT_OUTPUT_DIR


@dataclass(slots=True)
class AppConfig:
    openai: OpenAIConfig
    extraction: ExtractionConfig
    input: InputConfig
    output: OutputConfig
    config_path: str


def load_app_config(config_path: str | None = None) -> AppConfig:
    resolved = Path(config_path or DEFAULT_CONFIG_PATH)
    payload = _read_toml_file(resolved)

    openai_payload = payload.get("openai", {})
    extraction_payload = payload.get("extraction", {})
    input_payload = payload.get("input", {})
    output_payload = payload.get("output", {})

    openai = OpenAIConfig(
        api_key=str(openai_payload.get("api_key", "")).strip(),
        base_url=str(openai_payload.get("base_url", DEFAULT_OPENAI_BASE_URL)).strip() or DEFAULT_OPENAI_BASE_URL,
        model=str(openai_payload.get("model", DEFAULT_LLM_MODEL)).strip() or DEFAULT_LLM_MODEL,
        api_style=str(openai_payload.get("api_style", DEFAULT_OPENAI_API_STYLE)).strip() or DEFAULT_OPENAI_API_STYLE,
    )
    extraction = ExtractionConfig(
        strategy=str(extraction_payload.get("strategy", DEFAULT_EXTRACTOR)).strip() or DEFAULT_EXTRACTOR,
    )
    input_config = InputConfig(
        sources=_coerce_sources(input_payload),
    )
    output_config = OutputConfig(
        directory=str(output_payload.get("directory", DEFAULT_OUTPUT_DIR)).strip() or DEFAULT_OUTPUT_DIR,
    )

    return AppConfig(
        openai=openai,
        extraction=extraction,
        input=input_config,
        output=output_config,
        config_path=str(resolved),
    )


def _read_toml_file(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("rb") as handle:
        data = tomllib.load(handle)
    return data if isinstance(data, dict) else {}


def _coerce_sources(payload: dict) -> list[str]:
    array_value = payload.get("sources")
    if isinstance(array_value, list):
        sources = [str(item).strip() for item in array_value if str(item).strip()]
        if sources:
            return sources

    single_value = str(payload.get("source", DEFAULT_INPUT_SOURCE)).strip()
    return [single_value] if single_value else []
