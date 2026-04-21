from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path

from .models import CSV_COLUMNS, RuleRow

CSV_FILE_ENCODING = "utf-8-sig"


def assign_rule_ids(rows: list[RuleRow]) -> None:
    counters: dict[str, int] = defaultdict(int)
    for row in rows:
        counters[row.prefix] += 1
        row.rule_id = f"{row.prefix}-{counters[row.prefix]:03d}"


def write_csvs(rows: list[RuleRow], output_dir: str) -> None:
    target = Path(output_dir)
    target.mkdir(parents=True, exist_ok=True)

    file_map = {
        "foundation-rules.csv": [row for row in rows if row.prefix == "FDN"],
        "component-rules.csv": [row for row in rows if row.prefix == "CMP"],
        "global-layout-rules.csv": [row for row in rows if row.prefix not in {"FDN", "CMP"}],
    }

    for filename, subset in file_map.items():
        with (target / filename).open("w", newline="", encoding=CSV_FILE_ENCODING) as handle:
            writer = csv.DictWriter(handle, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            for row in subset:
                writer.writerow(row.to_row())
