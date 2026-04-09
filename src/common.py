from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "config.yaml"


def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def save_config(config: dict[str, Any]) -> None:
    with CONFIG_PATH.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(config, handle, allow_unicode=False, sort_keys=False)


def resolve_path(relative_path: str) -> Path:
    return PROJECT_ROOT / relative_path


def get_paths(config: dict[str, Any]) -> dict[str, Path]:
    paths = config["paths"]
    resolved = {
        "root": PROJECT_ROOT,
        "raw_dir": resolve_path(paths["raw_dir"]),
        "lookup_dir": resolve_path(paths["lookup_dir"]),
        "processed_dir": resolve_path(paths["processed_dir"]),
        "figures_dir": resolve_path(paths["figures_dir"]),
        "report_pdf": resolve_path(paths["report_pdf"]),
    }
    resolved["raw_combined"] = resolved["raw_dir"] / "pricecatcher_12bulan.parquet"
    resolved["clean_parquet"] = resolved["processed_dir"] / "pricecatcher_b40_12bulan.parquet"
    resolved["basket_cost_csv"] = resolved["processed_dir"] / "basket_cost.csv"
    resolved["basket_item_csv"] = resolved["processed_dir"] / "basket_item_monthly.csv"
    resolved["inflation_csv"] = resolved["processed_dir"] / "inflation_by_item.csv"
    resolved["volatility_csv"] = resolved["processed_dir"] / "volatility.csv"
    resolved["gap_csv"] = resolved["processed_dir"] / "urban_rural_gap.csv"
    resolved["ramadan_csv"] = resolved["processed_dir"] / "ramadan_effect.csv"
    resolved["kpi_json"] = resolved["processed_dir"] / "kpi_summary.json"
    resolved["insights_json"] = resolved["processed_dir"] / "insights.json"
    resolved["source_json"] = resolved["processed_dir"] / "source_metadata.json"
    resolved["item_catalogue_csv"] = resolved["processed_dir"] / "basket_item_codes.csv"
    return resolved


def ensure_directories(*paths: Path) -> None:
    for path in paths:
        path.mkdir(parents=True, exist_ok=True)


def month_range(config: dict[str, Any]) -> list[str]:
    analysis = config["analysis"]
    months = pd.date_range(
        f"{analysis['start_month']}-01",
        f"{analysis['end_month']}-01",
        freq="MS",
    )
    return months.strftime("%Y-%m").tolist()


def basket_items(config: dict[str, Any]) -> list[dict[str, Any]]:
    return config["basket"]["items"]


def basket_item_names(config: dict[str, Any]) -> list[str]:
    return [item["name"] for item in basket_items(config)]


def basket_quantities(config: dict[str, Any]) -> dict[str, float]:
    return {item["name"]: float(item["quantity"]) for item in basket_items(config)}


def quoted_sql_strings(values: list[str]) -> str:
    escaped = [value.replace("'", "''") for value in values]
    return ", ".join(f"'{value}'" for value in escaped)


def write_json(path: Path, payload: dict[str, Any] | list[Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)


def read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def classify_area_type(record: dict[str, Any]) -> str:
    state = str(record.get("state", "")).lower()
    if "kuala lumpur" in state:
        return "Urban"

    text_candidates = []
    for key in (
        "district",
        "premise",
        "premise_type",
        "premise_category",
        "premise_address",
        "address",
        "locality",
    ):
        value = record.get(key)
        if value is not None:
            text_candidates.append(str(value).lower())
    combined = " ".join(text_candidates)

    rural_tokens = ("kampung", "kg ", "felda", "mukim", "desa", "luar bandar", "rural", "pekan")
    urban_tokens = ("bandar", "urban", "city", "ipoh", "kuala lumpur", "kota kinabalu")

    if any(token in combined for token in rural_tokens):
        return "Rural"
    if any(token in combined for token in urban_tokens):
        return "Urban"
    return "Unknown"
