# UI/UX 规范规则生成 Agent

`uiux-rule-agent` 用来读取网站 URL 或本地 Markdown 文件目录，并把抽取出的原子化 UI/UX 规范写入 `data/` 目录下的 CSV 文件。

## 生成结果

生成后的 CSV 是唯一事实来源：

| 文件 | 覆盖范围 | 前缀 |
| --- | --- | --- |
| `data/foundation-rules.csv` | 基础令牌规范，如颜色、字体、间距、圆角、阴影等 | `FDN` |
| `data/component-rules.csv` | 组件规范，包含 hover、focus、active、disabled、error、open、selected 等状态完整性 | `CMP` |
| `data/global-layout-rules.csv` | 全局布局与交互断言，包含响应式行为和页面类型前缀 | `LAY` / `DET` / `LST` / `CRE` / `APV` |

CSV 中每一行都必须是原子规则，只描述一个属性。

## 输出字段

每条 CSV 规则包含以下字段：

- `rule_id`
- `prefix`
- `layer`
- `page_type`
- `subject`
- `component`
- `state`
- `property_name`
- `condition_if`
- `then_clause`
- `else_clause`
- `default_value`
- `preferred_pattern`
- `anti_pattern`
- `evidence`
- `source_ref`

和需求直接对应的关键字段有：

- `rule_id`
- `default_value`
- `preferred_pattern`
- `anti_pattern`

## 主要能力

- 支持远程 `http/https` 网站 URL，或本地 Markdown 文件 / 目录作为输入。
- 对已知的官方规范页支持内置适配器，当前已接入 Ant Design 的 `colors-cn` 和 `font-cn`。
- 支持混合抽取流程：Python 负责编排与落盘，未知输入可按需调用 OpenAI 模型做语义抽取。
- 当 Markdown 输入目录中包含 `foundation-rules/`、`component-rules/`、`global-layout-rules/` 子目录时，会自动路由到对应 CSV。
- 会把 `padding`、`margin`、`border` 等 CSS 简写自动展开为原子规则。
- 会把规则分层为 foundation、component、global 三层。
- 会从选择器中识别组件状态，并在必要时补出缺失状态规则。
- 会把显式条件文本和响应式媒体查询转换成 `If / Then / Else` 断言。
- 会识别 `禁止`、`不得`、`avoid`、`must not` 等禁止项表达，并写入 `anti_pattern`。

## 快速开始

```bash
python3 ./agent.py --input ./examples/sample-guidelines.md --output-dir ./data
```

所有运行时配置都集中在 [config/ai.toml](/Users/zhuangzhineng/Documents/ai_workspace/uiux-rule-agent/config/ai.toml:1) 中，包括输入源、输出目录、抽取策略和 OpenAI 设置。

最小配置示例：

```toml
[input]
sources = ["./examples/sample-guidelines.md"]
max_pages = 5

[output]
directory = "./data"

[openai]
api_key = ""
base_url = "https://api.openai.com/v1"
model = "gpt-5.4-mini"
api_style = "auto"

[extraction]
strategy = "auto"
```

当 `config/ai.toml` 里已经配置好 `input.sources` 和 `output.directory` 后，可以直接无参运行：

```bash
python3 ./agent.py
```

`[openai].api_style` 当前支持以下枚举值：

- `auto`
  默认值。优先尝试 `Responses API`；如果当前服务端不支持该接口，或只兼容 OpenAI 的 `Chat Completions API`，则自动切换到 `chat/completions`。在 `chat/completions` 下，会先尝试 `response_format + json_schema`，失败后再自动回退到纯文本 JSON 模式。
- `responses`
  强制使用 `Responses API`，请求路径为 `/responses`。
- `chat_completions`
  强制使用兼容 OpenAI 的 `Chat Completions API`，请求路径为 `/chat/completions`。会先尝试结构化 `json_schema` 输出，若服务端不支持，则自动再试一次纯文本 JSON 兜底。

`[extraction].strategy` 当前支持以下枚举值：

- `auto`
  优先尝试 LLM 抽取；当 `config/ai.toml` 中存在非空 `openai.api_key` 时，会调用 OpenAI 结构化抽取；如果未配置 key，或 LLM 抽取失败，则自动回退到内置启发式抽取。
- `heuristic`
  强制使用内置启发式抽取，不调用 LLM，适合离线、低成本或追求可复现性的场景。
- `llm`
  强制使用 LLM 抽取；如果没有配置 `openai.api_key`，或调用失败，会直接报错，不会自动回退。

## 输入模式

多网页输入示例：

```toml
[input]
sources = [
  "https://ant.design/docs/spec/colors-cn",
  "https://ant.design/docs/spec/font-cn",
]
max_pages = 5
```

输入规则有以下约束：

- 可以一次传入多个远程 `http/https` URL。
- 或者一次传入一个本地 Markdown 文件，或一个本地 Markdown 目录。
- 同一次运行中不能混用远程 URL 和本地路径。

## 常用运行方式

安装为本地可执行命令：

```bash
python3 -m pip install -e .
uiux-rule-agent --input ./examples/sample-guidelines.md --output-dir ./data
```

以网站为输入：

```bash
uiux-rule-agent --input https://example.com --output-dir ./data --max-pages 5
```

从命令行传入多个网页 URL：

```bash
python3 ./agent.py \
  --input https://ant.design/docs/spec/colors-cn \
  --input https://ant.design/docs/spec/font-cn \
  --config ./config/ai.toml
```

显式使用 LLM 抽取：

```bash
python3 ./agent.py \
  --config ./config/ai.toml \
  --extractor llm \
  --llm-model gpt-5.4-mini
```

如果保持 `auto` 模式，那么只有当 `config/ai.toml` 中存在非空的 `openai.api_key` 时，才会优先走 LLM 抽取；否则会自动回退到内置启发式抽取：

```bash
python3 ./agent.py
```

结构化 Markdown 目录示例：

```text
docs/
  foundation-rules/
    tokens.md
  component-rules/
    button.md
  global-layout-rules/
    layout.md
```

## 说明

- 网站抓取默认是保守模式，只会在同域内跟进有限数量的页面。
- `--input`、`--output-dir`、`--max-pages` 都是可选覆盖项；如果不传，会从 `config/ai.toml` 中读取 `input.sources`、`output.directory`、`input.max_pages`。
- 为了兼容旧配置，`input.source` 仍然可用，但推荐统一使用 `input.sources`。
- 在 `auto` 模式下，如果 `config/ai.toml` 中配置了 `openai.api_key`，会优先使用 OpenAI Responses API 的结构化输出；否则自动回退到启发式抽取器。
- `openai.api_style = "auto"` 时，会优先走 `Responses API`，失败后自动尝试兼容 OpenAI 的 `Chat Completions API`。
- OpenAI 集成同时支持 `Responses API` 和兼容 OpenAI 的 `Chat Completions API`；其中 `chat_completions` 模式会在 `json_schema` 不可用时自动回退到纯文本 JSON。
- 当前版本不会执行浏览器中的 JavaScript，动态行为主要通过文本、CSS 状态选择器和交互描述进行推断。
- `examples/` 目录自带一个最小示例 Markdown，便于端到端验证整条流水线。
