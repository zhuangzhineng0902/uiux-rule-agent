from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from io import BytesIO
from unittest.mock import patch
from pathlib import Path
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from uiux_rule_agent.cli import run
from uiux_rule_agent.config import load_app_config
from uiux_rule_agent.ingest import load_documents
from uiux_rule_agent.llm_extractor import (
    LLMExtractorError,
    _build_instructions,
    _coerce_rule,
    extract_rules_with_llm,
)
from uiux_rule_agent.models import RuleRow, SourceDocument
from uiux_rule_agent.writer import CSV_FILE_ENCODING


class FakeJSONResponse:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    def __enter__(self) -> "FakeJSONResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


class PipelineTest(unittest.TestCase):
    def _build_llm_structured_payload(self, subject: str = "LLM 主色") -> dict:
        return {
            "foundation_rules": [
                {
                    "page_type": "foundation",
                    "subject": subject,
                    "component": "",
                    "state": "default",
                    "property_name": "color",
                    "condition_if": "If 语义令牌 = 品牌主色",
                    "then_clause": "Then color 必须为 #1677FF",
                    "else_clause": "Else 保持默认规则",
                    "default_value": "#1677FF",
                    "preferred_pattern": "使用统一品牌主色 token",
                    "anti_pattern": "不要混用多个接近的主色蓝",
                    "evidence": "mocked chat completions evidence",
                    "source_ref": "memory://doc",
                }
            ],
            "component_rules": [],
            "global_rules": [],
        }

    def _build_llm_payload_with_dropped_rule(self) -> dict:
        payload = self._build_llm_structured_payload(subject="可写入主色")
        payload["foundation_rules"].append(
            {
                "page_type": "foundation",
                "subject": "",
                "component": "",
                "state": "default",
                "property_name": "color",
                "condition_if": "If 语义令牌 = 无效主色",
                "then_clause": "Then color 必须为 #FF4D4F",
                "else_clause": "Else 保持默认规则",
                "default_value": "",
                "preferred_pattern": "使用统一 token",
                "anti_pattern": "不要直接写死无效规则",
                "evidence": "mocked invalid rule",
                "source_ref": "memory://doc",
            }
        )
        return payload

    def test_llm_prompt_contains_required_extraction_constraints(self) -> None:
        instructions = _build_instructions()

        self.assertIn("颜色值、像素值", instructions)
        self.assertIn("必须、禁止、避免、建议、应该、最多只能、当...时、少于或等于、不超过、间距、等分", instructions)
        self.assertIn("Markdown 表格", instructions)
        self.assertIn("规则内容必须使用中文描述", instructions)

    def test_llm_rule_can_infer_default_value_from_then_clause(self) -> None:
        doc = SourceDocument(
            source_type="markdown",
            location="memory://doc",
            title="测试文档",
            text="",
        )
        item = {
            "page_type": "foundation",
            "subject": "品牌主色",
            "component": "",
            "state": "default",
            "property_name": "color",
            "condition_if": "If 语义令牌 = 品牌主色",
            "then_clause": "Then color 必须为 #1677FF",
            "else_clause": "Else 保持默认规则",
            "default_value": "",
            "preferred_pattern": "使用统一品牌主色 token",
            "anti_pattern": "不要混用多个接近的主色蓝",
            "evidence": "mocked evidence",
            "source_ref": "memory://doc",
        }

        row = _coerce_rule(item, doc, "foundation", "FDN")

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row.default_value, "#1677FF")

    def test_llm_rule_can_be_kept_when_default_value_is_empty(self) -> None:
        doc = SourceDocument(
            source_type="markdown",
            location="memory://doc",
            title="测试文档",
            text="",
        )
        item = {
            "page_type": "component",
            "subject": "按钮",
            "component": "button",
            "state": "default",
            "property_name": "loading-feedback",
            "condition_if": "If 按钮进入 loading 状态",
            "then_clause": "Then 需要提供清晰的 loading 反馈",
            "else_clause": "Else 保持默认按钮样式",
            "default_value": "",
            "preferred_pattern": "使用统一 loading 反馈",
            "anti_pattern": "不要让按钮进入 loading 后无反馈",
            "evidence": "mocked evidence",
            "source_ref": "memory://doc",
        }

        row = _coerce_rule(item, doc, "component", "CMP")

        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row.default_value, "")
        self.assertEqual(row.then_clause, "Then 需要提供清晰的 loading 反馈")

    def test_llm_rule_is_dropped_when_required_fields_are_missing(self) -> None:
        doc = SourceDocument(
            source_type="markdown",
            location="memory://doc",
            title="测试文档",
            text="",
        )
        item = {
            "page_type": "foundation",
            "subject": "",
            "component": "",
            "state": "default",
            "property_name": "color",
            "condition_if": "",
            "then_clause": "Then color 必须为 #1677FF",
            "else_clause": "",
            "default_value": "",
            "preferred_pattern": "",
            "anti_pattern": "",
            "evidence": "",
            "source_ref": "",
        }

        row = _coerce_rule(item, doc, "foundation", "FDN")

        self.assertIsNone(row)

    def test_output_directory_can_be_loaded_from_config_and_used(self) -> None:
        fixture = Path(__file__).resolve().parents[1] / "examples" / "sample-guidelines.md"

        with tempfile.TemporaryDirectory() as temp_dir:
            configured_output_dir = Path(temp_dir) / "configured-out"
            config_path = Path(temp_dir) / "ai.toml"
            config_path.write_text(
                f'[input]\nsources = ["{fixture}"]\nmax_pages = 3\n\n'
                f'[output]\ndirectory = "{configured_output_dir}"\n\n'
                '[openai]\napi_key = ""\nbase_url = "https://api.openai.com/v1"\nmodel = "gpt-5.4-mini"\n\n'
                '[extraction]\nstrategy = "heuristic"\n',
                encoding="utf-8",
            )

            result = run(None, output_dir=None, config_path=str(config_path))

            self.assertEqual(result["output_dir"], str(configured_output_dir))
            self.assertTrue((configured_output_dir / "foundation-rules.csv").exists())
            self.assertTrue((configured_output_dir / "component-rules.csv").exists())
            self.assertTrue((configured_output_dir / "global-layout-rules.csv").exists())

    def test_input_sources_can_be_loaded_from_config(self) -> None:
        fixture = Path(__file__).resolve().parents[1] / "examples" / "sample-guidelines.md"

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "out"
            config_path = Path(temp_dir) / "ai.toml"
            config_path.write_text(
                f'[input]\nsources = ["{fixture}"]\nmax_pages = 3\n\n'
                '[openai]\napi_key = ""\nbase_url = "https://api.openai.com/v1"\nmodel = "gpt-5.4-mini"\n\n'
                '[extraction]\nstrategy = "heuristic"\n',
                encoding="utf-8",
            )

            result = run(None, output_dir=str(output_dir), config_path=str(config_path))

            self.assertGreater(result["foundation_rules"], 0)
            self.assertGreater(result["component_rules"], 0)
            self.assertGreater(result["global_rules"], 0)
            self.assertTrue((output_dir / "foundation-rules.csv").exists())

    def test_root_directory_name_can_force_component_bucket(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            component_root = Path(temp_dir) / "component-rules"
            component_root.mkdir()
            (component_root / "button.md").write_text(
                "# 按钮\n\n```css\n.button { height: 32px; background-color: #0067D1; }\n.button:hover { background-color: #2E86DE; }\n.button[disabled] { opacity: 0.6; }\n```\n",
                encoding="utf-8",
            )

            output_dir = Path(temp_dir) / "out"
            result = run(str(component_root), output_dir=str(output_dir), max_pages=1)

            self.assertEqual(result["foundation_rules"], 0)
            self.assertGreater(result["component_rules"], 0)
            self.assertEqual(result["global_rules"], 0)

            with (output_dir / "component-rules.csv").open(encoding=CSV_FILE_ENCODING) as handle:
                component_rows = list(csv.DictReader(handle))
            with (output_dir / "foundation-rules.csv").open(encoding=CSV_FILE_ENCODING) as handle:
                foundation_rows = list(csv.DictReader(handle))
            with (output_dir / "global-layout-rules.csv").open(encoding=CSV_FILE_ENCODING) as handle:
                global_rows = list(csv.DictReader(handle))

            self.assertTrue(any(row["subject"] == "button" and row["state"] == "hover" for row in component_rows))
            self.assertEqual(foundation_rows, [])
            self.assertEqual(global_rows, [])

    def test_unbucketed_markdown_still_routes_by_semantics_when_bucketed_docs_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "docs"
            root.mkdir()
            component_dir = root / "component-rules"
            component_dir.mkdir()

            (component_dir / "button.md").write_text(
                "# Button\n\n```css\n.button { height: 32px; background-color: #0067D1; }\n.button:hover { background-color: #2E86DE; }\n.button[disabled] { opacity: 0.6; }\n```\n",
                encoding="utf-8",
            )
            (root / "mixed.md").write_text(
                "# Mixed\n\n- Primary color: #0067D1\n\n如果 屏幕宽度 < 600px，则 底部操作栏 必须 撑满全屏（100% width），否则 保持桌面端悬浮宽度。\n",
                encoding="utf-8",
            )

            output_dir = root / "out"
            result = run(str(root), output_dir=str(output_dir), max_pages=1)

            self.assertGreater(result["foundation_rules"], 0)
            self.assertGreater(result["component_rules"], 0)
            self.assertGreater(result["global_rules"], 0)

            with (output_dir / "foundation-rules.csv").open(encoding=CSV_FILE_ENCODING) as handle:
                foundation_rows = list(csv.DictReader(handle))
            with (output_dir / "component-rules.csv").open(encoding=CSV_FILE_ENCODING) as handle:
                component_rows = list(csv.DictReader(handle))
            with (output_dir / "global-layout-rules.csv").open(encoding=CSV_FILE_ENCODING) as handle:
                global_rows = list(csv.DictReader(handle))

            self.assertTrue(any(row["subject"] == "Primary color" for row in foundation_rows))
            self.assertTrue(any(row["subject"] == "button" for row in component_rows))
            self.assertTrue(any("屏幕宽度 < 600px" in row["condition_if"] for row in global_rows))

    def test_chat_completions_api_style_can_extract_rules(self) -> None:
        doc = SourceDocument(
            source_type="markdown",
            location="memory://doc",
            title="测试文档",
            text="主色: #1677FF",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "ai.toml"
            config_path.write_text(
                '[openai]\napi_key = "test-key"\nbase_url = "https://example.com/v1"\nmodel = "gpt-5.4-mini"\napi_style = "chat_completions"\n\n'
                '[extraction]\nstrategy = "llm"\n',
                encoding="utf-8",
            )
            config = load_app_config(str(config_path))
            captured_requests: list[tuple[str, dict]] = []

            def fake_urlopen(request, timeout=120):
                captured_requests.append((request.full_url, json.loads(request.data.decode("utf-8"))))
                payload = {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(self._build_llm_structured_payload())
                            }
                        }
                    ]
                }
                return FakeJSONResponse(payload)

            with patch("uiux_rule_agent.llm_extractor.urlopen", side_effect=fake_urlopen):
                rows = extract_rules_with_llm([doc], config=config)

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].subject, "LLM 主色")
            self.assertEqual(len(captured_requests), 1)
            self.assertTrue(captured_requests[0][0].endswith("/chat/completions"))
            self.assertIn("response_format", captured_requests[0][1])

    def test_auto_api_style_can_fallback_to_chat_completions(self) -> None:
        doc = SourceDocument(
            source_type="markdown",
            location="memory://doc",
            title="测试文档",
            text="主色: #1677FF",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "ai.toml"
            config_path.write_text(
                '[openai]\napi_key = "test-key"\nbase_url = "https://example.com/v1"\nmodel = "gpt-5.4-mini"\napi_style = "auto"\n\n'
                '[extraction]\nstrategy = "llm"\n',
                encoding="utf-8",
            )
            config = load_app_config(str(config_path))
            request_urls: list[str] = []

            def fake_urlopen(request, timeout=120):
                request_urls.append(request.full_url)
                if request.full_url.endswith("/responses"):
                    raise HTTPError(
                        request.full_url,
                        404,
                        "Not Found",
                        hdrs=None,
                        fp=BytesIO(b'{"error":"unknown endpoint"}'),
                    )
                payload = {
                    "choices": [
                        {
                            "message": {
                                "content": json.dumps(self._build_llm_structured_payload(subject="回退主色"))
                            }
                        }
                    ]
                }
                return FakeJSONResponse(payload)

            with patch("uiux_rule_agent.llm_extractor.urlopen", side_effect=fake_urlopen):
                rows = extract_rules_with_llm([doc], config=config)

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].subject, "回退主色")
            self.assertEqual(
                request_urls,
                [
                    "https://example.com/v1/responses",
                    "https://example.com/v1/chat/completions",
                ],
            )

    def test_chat_completions_can_fallback_to_plain_text_json(self) -> None:
        doc = SourceDocument(
            source_type="markdown",
            location="memory://doc",
            title="测试文档",
            text="主色: #1677FF",
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "ai.toml"
            config_path.write_text(
                '[openai]\napi_key = "test-key"\nbase_url = "https://example.com/v1"\nmodel = "gpt-5.4-mini"\napi_style = "chat_completions"\n\n'
                '[extraction]\nstrategy = "llm"\n',
                encoding="utf-8",
            )
            config = load_app_config(str(config_path))
            captured_payloads: list[dict] = []

            def fake_urlopen(request, timeout=120):
                payload = json.loads(request.data.decode("utf-8"))
                captured_payloads.append(payload)
                if "response_format" in payload:
                    raise HTTPError(
                        request.full_url,
                        400,
                        "Bad Request",
                        hdrs=None,
                        fp=BytesIO(b'{"error":"response_format unsupported"}'),
                    )
                plain_json = json.dumps(self._build_llm_structured_payload(subject="纯文本回退主色"), ensure_ascii=False)
                return FakeJSONResponse(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": f"```json\n{plain_json}\n```"
                                }
                            }
                        ]
                    }
                )

            with patch("uiux_rule_agent.llm_extractor.urlopen", side_effect=fake_urlopen):
                rows = extract_rules_with_llm([doc], config=config)

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].subject, "纯文本回退主色")
            self.assertEqual(len(captured_payloads), 2)
            self.assertIn("response_format", captured_payloads[0])
            self.assertNotIn("response_format", captured_payloads[1])

    def test_cli_llm_run_writes_debug_artifacts_for_dropped_rules(self) -> None:
        fixture = Path(__file__).resolve().parents[1] / "examples" / "sample-guidelines.md"

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "out"
            config_path = Path(temp_dir) / "ai.toml"
            config_path.write_text(
                f'[input]\nsources = ["{fixture}"]\nmax_pages = 1\n\n'
                f'[output]\ndirectory = "{output_dir}"\n\n'
                '[openai]\napi_key = "test-key"\nbase_url = "https://example.com/v1"\nmodel = "gpt-5.4-mini"\napi_style = "chat_completions"\n\n'
                '[extraction]\nstrategy = "llm"\n',
                encoding="utf-8",
            )

            def fake_urlopen(request, timeout=120):
                return FakeJSONResponse(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps(self._build_llm_payload_with_dropped_rule(), ensure_ascii=False)
                                }
                            }
                        ]
                    }
                )

            with patch("uiux_rule_agent.llm_extractor.urlopen", side_effect=fake_urlopen):
                result = run(None, config_path=str(config_path))

            self.assertEqual(result["foundation_rules"], 1)

            debug_dir = output_dir / "debug" / "llm" / "doc-001"
            self.assertTrue((debug_dir / "meta.json").exists())
            self.assertTrue((debug_dir / "request.json").exists())
            self.assertTrue((debug_dir / "raw-response.json").exists())
            self.assertTrue((debug_dir / "payload.json").exists())
            self.assertTrue((debug_dir / "dropped-rules.json").exists())
            self.assertTrue((debug_dir / "output-text.txt").exists())

            meta = json.loads((debug_dir / "meta.json").read_text(encoding="utf-8"))
            dropped = json.loads((debug_dir / "dropped-rules.json").read_text(encoding="utf-8"))

            self.assertEqual(meta["kept_rule_count"], 1)
            self.assertEqual(meta["dropped_rule_count"], 1)
            self.assertEqual(len(dropped["dropped_rules"]), 1)
            self.assertIn("缺少 subject", dropped["dropped_rules"][0])

    def test_remote_url_from_config_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "out"
            config_path = Path(temp_dir) / "ai.toml"
            config_path.write_text(
                '[input]\n'
                'sources = ["https://example.com/spec"]\n'
                'max_pages = 2\n\n'
                '[openai]\napi_key = ""\nbase_url = "https://api.openai.com/v1"\nmodel = "gpt-5.4-mini"\n\n'
                '[extraction]\nstrategy = "heuristic"\n',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "仅支持本地 Markdown 文件或目录，不支持网站 URL"):
                run(None, output_dir=str(output_dir), config_path=str(config_path))

    def test_multiple_local_markdown_files_can_be_used_as_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir) / "docs"
            docs_dir.mkdir()
            file_one = docs_dir / "tokens.md"
            file_two = docs_dir / "layout.md"

            file_one.write_text(
                "# Tokens\n\n- Primary color: #0067D1\n",
                encoding="utf-8",
            )
            file_two.write_text(
                "# Layout\n\n如果 屏幕宽度 < 600px，则 底部操作栏 必须 撑满全屏（100% width），否则 保持桌面端悬浮宽度。\n",
                encoding="utf-8",
            )

            output_dir = Path(temp_dir) / "out"
            result = run([str(file_one), str(file_two)], output_dir=str(output_dir))

            self.assertEqual(result["documents"], 2)
            self.assertGreater(result["foundation_rules"], 0)
            self.assertGreater(result["global_rules"], 0)

            with (output_dir / "foundation-rules.csv").open(encoding=CSV_FILE_ENCODING) as handle:
                foundation_rows = list(csv.DictReader(handle))
            with (output_dir / "global-layout-rules.csv").open(encoding=CSV_FILE_ENCODING) as handle:
                global_rows = list(csv.DictReader(handle))

            self.assertTrue(any(row["subject"] == "Primary color" for row in foundation_rows))
            self.assertTrue(any("屏幕宽度 < 600px" in row["condition_if"] for row in global_rows))

    def test_overlapping_directory_and_file_inputs_are_deduplicated(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            docs_dir = Path(temp_dir) / "docs"
            docs_dir.mkdir()
            nested_file = docs_dir / "tokens.md"
            nested_file.write_text("# Tokens\n\n- Primary color: #0067D1\n", encoding="utf-8")

            output_dir = Path(temp_dir) / "out"
            result = run([str(docs_dir), str(nested_file)], output_dir=str(output_dir))

            self.assertEqual(result["documents"], 1)

    def test_cli_input_overrides_configured_input_source(self) -> None:
        fixture = Path(__file__).resolve().parents[1] / "examples" / "sample-guidelines.md"

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "out"
            alternative_dir = Path(temp_dir) / "alternative-docs"
            alternative_dir.mkdir()
            (alternative_dir / "other.md").write_text("# Other\n\n- Secondary color: #999999\n", encoding="utf-8")
            config_path = Path(temp_dir) / "ai.toml"
            config_path.write_text(
                f'[input]\nsources = ["{alternative_dir}"]\nmax_pages = 2\n\n'
                '[openai]\napi_key = ""\nbase_url = "https://api.openai.com/v1"\nmodel = "gpt-5.4-mini"\n\n'
                '[extraction]\nstrategy = "heuristic"\n',
                encoding="utf-8",
            )

            result = run(str(fixture), output_dir=str(output_dir), config_path=str(config_path))

            self.assertGreater(result["foundation_rules"], 0)
            self.assertTrue((output_dir / "foundation-rules.csv").exists())

    def test_load_documents_rejects_remote_url(self) -> None:
        with self.assertRaisesRegex(ValueError, "仅支持本地 Markdown 文件或目录，不支持网站 URL"):
            load_documents("https://example.com/spec")

    def test_markdown_pipeline_generates_three_csvs(self) -> None:
        fixture = Path(__file__).resolve().parents[1] / "examples" / "sample-guidelines.md"

        with tempfile.TemporaryDirectory() as temp_dir:
            result = run(str(fixture), output_dir=temp_dir, max_pages=1)
            target = Path(temp_dir)

            foundation = target / "foundation-rules.csv"
            component = target / "component-rules.csv"
            global_rules = target / "global-layout-rules.csv"

            self.assertTrue(foundation.exists())
            self.assertTrue(component.exists())
            self.assertTrue(global_rules.exists())
            self.assertGreater(result["foundation_rules"], 0)
            self.assertGreater(result["component_rules"], 0)
            self.assertGreater(result["global_rules"], 0)

            with foundation.open(encoding=CSV_FILE_ENCODING) as handle:
                foundation_rows = list(csv.DictReader(handle))
            with component.open(encoding=CSV_FILE_ENCODING) as handle:
                component_rows = list(csv.DictReader(handle))
            with global_rules.open(encoding=CSV_FILE_ENCODING) as handle:
                global_rows = list(csv.DictReader(handle))

            self.assertTrue(any(row["rule_id"].startswith("FDN-") for row in foundation_rows))
            self.assertTrue(any(row["state"] == "hover" for row in component_rows))
            self.assertTrue(any("If 屏幕宽度 < 600px" in row["condition_if"] for row in global_rows))

    def test_structured_markdown_subdirectories_route_to_matching_csv(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            foundation_dir = root / "foundation-rules"
            component_dir = root / "component-rules"
            global_dir = root / "global-layout-rules"
            foundation_dir.mkdir()
            component_dir.mkdir()
            global_dir.mkdir()

            (foundation_dir / "tokens.md").write_text(
                "# Tokens\n\n- Primary color: #0067D1\n- Card radius: 8px\n",
                encoding="utf-8",
            )
            (component_dir / "button.md").write_text(
                "# Button\n\n```css\n.button { height: 32px; background-color: #0067D1; }\n.button:hover { background-color: #2E86DE; }\n.button[disabled] { opacity: 0.6; }\n```\n",
                encoding="utf-8",
            )
            (global_dir / "layout.md").write_text(
                "# Layout\n\n```css\n@media (max-width: 600px) { .bottom-action-bar { width: 100%; } }\n```\n\n如果 屏幕宽度 < 600px，则 底部操作栏 必须 撑满全屏（100% width），否则 保持桌面端悬浮宽度。\n",
                encoding="utf-8",
            )

            output_dir = root / "out"
            result = run(str(root), output_dir=str(output_dir), max_pages=1)

            self.assertGreater(result["foundation_rules"], 0)
            self.assertGreater(result["component_rules"], 0)
            self.assertGreater(result["global_rules"], 0)

            with (output_dir / "foundation-rules.csv").open(encoding=CSV_FILE_ENCODING) as handle:
                foundation_rows = list(csv.DictReader(handle))
            with (output_dir / "component-rules.csv").open(encoding=CSV_FILE_ENCODING) as handle:
                component_rows = list(csv.DictReader(handle))
            with (output_dir / "global-layout-rules.csv").open(encoding=CSV_FILE_ENCODING) as handle:
                global_rows = list(csv.DictReader(handle))

            self.assertTrue(any(row["subject"] == "Primary color" for row in foundation_rows))
            self.assertFalse(any(row["subject"] == "button" for row in foundation_rows))
            self.assertTrue(any(row["subject"] == "button" and row["state"] == "hover" for row in component_rows))
            self.assertFalse(any(row["prefix"] == "CMP" for row in global_rows))
            self.assertTrue(any("屏幕宽度 < 600px" in row["condition_if"] for row in global_rows))

    def test_non_markdown_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            plain_text = Path(temp_dir) / "notes.txt"
            plain_text.write_text("not markdown", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "仅支持 Markdown 文件输入"):
                load_documents(str(plain_text))

    def test_directory_without_markdown_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            empty_dir = Path(temp_dir) / "empty-docs"
            empty_dir.mkdir()

            with self.assertRaisesRegex(ValueError, "目录中未找到 Markdown 文件"):
                load_documents(str(empty_dir))

    def test_llm_extractor_can_be_selected_explicitly(self) -> None:
        fixture = Path(__file__).resolve().parents[1] / "examples" / "sample-guidelines.md"
        llm_rows = [
            RuleRow(
                prefix="FDN",
                layer="foundation",
                page_type="foundation",
                subject="LLM 主字号",
                component="",
                state="default",
                property_name="font-size",
                condition_if="If 文本角色 = body",
                then_clause="Then font-size 必须为 14px",
                else_clause="Else 保持默认规则",
                default_value="14px",
                preferred_pattern="使用 LLM 归纳后的 token",
                anti_pattern="不要混用多个正文主字号",
                evidence="mocked llm evidence",
                source_ref=str(fixture),
            )
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "ai.toml"
            config_path.write_text(
                '[openai]\napi_key = "test-key"\nbase_url = "https://api.openai.com/v1"\nmodel = "gpt-5.4-mini"\n\n[extraction]\nstrategy = "auto"\n',
                encoding="utf-8",
            )

            with patch("uiux_rule_agent.cli.extract_rules_with_llm", return_value=llm_rows):
                result = run(
                    str(fixture),
                    output_dir=temp_dir,
                    max_pages=1,
                    extractor="llm",
                    llm_model="gpt-5.4-mini",
                    config_path=str(config_path),
                )

            self.assertEqual(result["foundation_rules"], 1)
            self.assertEqual(result["component_rules"], 0)
            self.assertEqual(result["global_rules"], 0)

            with (Path(temp_dir) / "foundation-rules.csv").open(encoding=CSV_FILE_ENCODING) as handle:
                foundation_rows = list(csv.DictReader(handle))

            self.assertEqual(foundation_rows[0]["subject"], "LLM 主字号")

    def test_auto_extractor_falls_back_to_heuristic_when_llm_fails(self) -> None:
        fixture = Path(__file__).resolve().parents[1] / "examples" / "sample-guidelines.md"

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "ai.toml"
            config_path.write_text(
                '[openai]\napi_key = "test-key"\nbase_url = "https://api.openai.com/v1"\nmodel = "gpt-5.4-mini"\n\n[extraction]\nstrategy = "auto"\n',
                encoding="utf-8",
            )

            with patch(
                "uiux_rule_agent.cli.extract_rules_with_llm",
                side_effect=LLMExtractorError("llm unavailable"),
            ):
                result = run(str(fixture), output_dir=temp_dir, max_pages=1, extractor="auto", config_path=str(config_path))
            self.assertGreater(result["foundation_rules"], 0)
            self.assertGreater(result["component_rules"], 0)
            self.assertGreater(result["global_rules"], 0)

    def test_ai_config_file_is_loaded_from_toml(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "ai.toml"
            config_path.write_text(
                '[input]\nsources = ["./docs"]\nmax_pages = 8\n\n'
                '[output]\ndirectory = "./exports"\n\n'
                '[openai]\napi_key = "demo-key"\nbase_url = "https://example.com/v1"\nmodel = "gpt-5.4-mini"\napi_style = "chat_completions"\n\n'
                '[extraction]\nstrategy = "llm"\n',
                encoding="utf-8",
            )

            config = load_app_config(str(config_path))

            self.assertEqual(config.input.sources, ["./docs"])
            self.assertEqual(config.input.max_pages, 8)
            self.assertEqual(config.output.directory, "./exports")
            self.assertEqual(config.openai.api_key, "demo-key")
            self.assertEqual(config.openai.base_url, "https://example.com/v1")
            self.assertEqual(config.openai.model, "gpt-5.4-mini")
            self.assertEqual(config.openai.api_style, "chat_completions")
            self.assertEqual(config.extraction.strategy, "llm")

    def test_legacy_single_input_source_is_still_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "ai.toml"
            config_path.write_text(
                '[input]\nsource = "./docs"\nmax_pages = 4\n\n'
                '[openai]\napi_key = ""\nbase_url = "https://api.openai.com/v1"\nmodel = "gpt-5.4-mini"\n\n'
                '[extraction]\nstrategy = "auto"\n',
                encoding="utf-8",
            )

            config = load_app_config(str(config_path))

            self.assertEqual(config.input.sources, ["./docs"])
            self.assertEqual(config.input.max_pages, 4)

    def test_generated_csv_uses_utf8_bom_for_excel_compatibility(self) -> None:
        fixture = Path(__file__).resolve().parents[1] / "examples" / "sample-guidelines.md"

        with tempfile.TemporaryDirectory() as temp_dir:
            run(str(fixture), output_dir=temp_dir, max_pages=1)
            raw = (Path(temp_dir) / "foundation-rules.csv").read_bytes()

            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))


if __name__ == "__main__":
    unittest.main()
