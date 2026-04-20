from __future__ import annotations

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def _load_main():
    try:
        return importlib.import_module("uiux_rule_agent.cli").main
    except ModuleNotFoundError as exc:
        raise RuntimeError(f"无法从 {SRC} 加载 uiux_rule_agent.cli，请检查项目目录结构。") from exc


if __name__ == "__main__":
    raise SystemExit(_load_main()())
