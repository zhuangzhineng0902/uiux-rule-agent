from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from .config import DEFAULT_CONFIG_PATH, load_app_config
from .extractors import dedupe_rules, generate_rules
from .ingest import load_documents
from .llm_extractor import LLMExtractorError, can_use_openai_llm, extract_rules_with_llm, resolve_llm_model
from .official_specs import match_official_spec_rules
from .writer import assign_rule_ids, write_csvs


class ChineseArgumentParser(argparse.ArgumentParser):
    def format_help(self) -> str:
        help_text = super().format_help()
        help_text = help_text.replace("usage:", "用法：", 1)
        help_text = help_text.replace("\noptions:\n", "\n参数说明：\n", 1)
        help_text = help_text.replace("show this help message and exit", "显示帮助信息并退出")
        return help_text


def run(
    input_value: str | list[str] | None = None,
    output_dir: str | None = None,
    max_pages: int | None = None,
    extractor: str | None = None,
    llm_model: str | None = None,
    config_path: str | None = None,
) -> dict[str, int]:
    app_config = load_app_config(config_path)
    selected_inputs = _resolve_input_values(input_value, app_config)
    selected_output_dir = (output_dir or "").strip() or app_config.output.directory
    selected_max_pages = max_pages if max_pages is not None else app_config.input.max_pages
    selected_extractor = extractor or app_config.extraction.strategy

    documents = []
    rules = []

    for source in selected_inputs:
        official_rules = match_official_spec_rules(source)
        if official_rules is not None:
            rules.extend(official_rules)
            continue
        documents.extend(load_documents(source, max_pages=selected_max_pages))

    if documents:
        rules.extend(
            _generate_non_official_rules(
                documents,
                extractor=selected_extractor,
                llm_model=llm_model,
                app_config=app_config,
                output_dir=selected_output_dir,
            )
        )
    rules = dedupe_rules(rules)
    assign_rule_ids(rules)
    write_csvs(rules, selected_output_dir)

    counter = Counter(row.prefix for row in rules)
    return {
        "documents": len(documents) + sum(1 for source in selected_inputs if match_official_spec_rules(source) is not None),
        "foundation_rules": counter.get("FDN", 0),
        "component_rules": counter.get("CMP", 0),
        "global_rules": sum(count for prefix, count in counter.items() if prefix not in {"FDN", "CMP"}),
        "output_dir": selected_output_dir,
    }


def _resolve_input_values(input_value: str | list[str] | None, app_config) -> list[str]:
    if isinstance(input_value, list):
        selected_inputs = [item.strip() for item in input_value if item and item.strip()]
    elif isinstance(input_value, str):
        selected_inputs = [input_value.strip()] if input_value.strip() else []
    else:
        selected_inputs = list(app_config.input.sources)

    if not selected_inputs:
        raise ValueError(
            "缺少输入源。请通过 --input 传入，或在配置文件中设置 [input].sources。"
        )

    local_sources = [source for source in selected_inputs if not _is_remote_source(source)]
    remote_sources = [source for source in selected_inputs if _is_remote_source(source)]
    if local_sources and remote_sources:
        raise ValueError("同一次运行中不能混用远程 URL 和本地路径。")
    if len(local_sources) > 1:
        raise ValueError("每次运行只支持一个本地 Markdown 文件或一个本地目录。")

    return selected_inputs


def _is_remote_source(value: str) -> bool:
    return value.startswith("http://") or value.startswith("https://")


def _generate_non_official_rules(
    documents: list,
    extractor: str,
    llm_model: str | None,
    app_config,
    output_dir: str,
):
    if extractor not in {"auto", "heuristic", "llm"}:
        raise ValueError(f"不支持的抽取器类型：{extractor}")

    if extractor == "heuristic":
        return generate_rules(documents)

    if extractor == "llm":
        return extract_rules_with_llm(
            documents,
            config=app_config,
            model=resolve_llm_model(app_config, llm_model),
            debug_dir=str(Path(output_dir) / "debug"),
        )

    if can_use_openai_llm(app_config):
        try:
            return extract_rules_with_llm(
                documents,
                config=app_config,
                model=resolve_llm_model(app_config, llm_model),
                debug_dir=str(Path(output_dir) / "debug"),
            )
        except LLMExtractorError:
            return generate_rules(documents)

    return generate_rules(documents)


def build_parser() -> argparse.ArgumentParser:
    parser = ChineseArgumentParser(description="从网站或本地 Markdown 目录中生成原子化 UI/UX 规范规则。")
    parser.add_argument(
        "--input",
        action="append",
        default=None,
        help="可选输入源。可传网站 URL 或本地 Markdown 文件/目录；如需多个远程 URL，可重复使用该参数。默认读取配置文件中的 [input].sources。",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="可选输出目录覆盖项。默认读取配置文件中的 [output].directory。",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="可选网站抓取页数上限覆盖项。默认读取配置文件中的 [input].max_pages。",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help="应用配置 TOML 文件路径。",
    )
    parser.add_argument(
        "--extractor",
        choices=["auto", "heuristic", "llm"],
        default=None,
        help="可选抽取器覆盖项。默认读取配置文件中的抽取策略。",
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help="可选 OpenAI 模型覆盖项。默认读取配置文件中的模型配置。",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    result = run(
        args.input,
        args.output_dir,
        args.max_pages,
        extractor=args.extractor,
        llm_model=args.llm_model,
        config_path=args.config,
    )
    print(f"documents={result['documents']}")
    print(f"foundation_rules={result['foundation_rules']}")
    print(f"component_rules={result['component_rules']}")
    print(f"global_rules={result['global_rules']}")
    print(f"output_dir={result['output_dir']}")
    return 0
