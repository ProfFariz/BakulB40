from __future__ import annotations

import pandas as pd
import duckdb

from common import (
    basket_item_names,
    classify_area_type,
    ensure_directories,
    get_paths,
    load_config,
    quoted_sql_strings,
)


def resolve_selected_items(config: dict, item_lookup: pd.DataFrame) -> pd.DataFrame:
    configured_names = basket_item_names(config)
    configured_codes = [item.get("item_code") for item in config["basket"]["items"] if item.get("item_code")]

    selected = item_lookup[item_lookup["item"].isin(configured_names)].copy()
    if configured_codes:
        selected = item_lookup[item_lookup["item_code"].astype(str).isin(configured_codes)].copy()

    if selected.empty:
        raise ValueError("No matching basket items found in lookup_item.parquet.")

    columns = [column for column in ("item_code", "item", "unit", "item_group") if column in selected.columns]
    return selected[columns].drop_duplicates("item_code")


def filter_price_data(raw_parquet: str, item_codes: list[str]) -> pd.DataFrame:
    connection = duckdb.connect()
    code_list = quoted_sql_strings(item_codes)
    query = f"""
        SELECT
            CAST(date AS DATE) AS date,
            COALESCE(bulan, strftime(CAST(date AS DATE), '%Y-%m')) AS bulan,
            CAST(item_code AS VARCHAR) AS item_code,
            CAST(premise_code AS VARCHAR) AS premise_code,
            CAST(price AS DOUBLE) AS price
        FROM read_parquet('{raw_parquet}')
        WHERE CAST(item_code AS VARCHAR) IN ({code_list})
          AND price > 0
          AND price < 100
    """
    return connection.execute(query).fetch_df()


def enrich_premise_columns(premise_lookup: pd.DataFrame) -> pd.DataFrame:
    frame = premise_lookup.copy()
    rename_candidates = {
        "premise": "premise",
        "premise_name": "premise",
        "premise_type": "premise_type",
        "type": "premise_type",
        "category": "premise_category",
        "premise_category": "premise_category",
        "address": "premise_address",
        "premise_address": "premise_address",
        "locality": "locality",
    }
    available = {key: value for key, value in rename_candidates.items() if key in frame.columns}
    frame = frame.rename(columns=available)
    return frame


def main() -> None:
    config = load_config()
    paths = get_paths(config)
    ensure_directories(paths["processed_dir"])

    item_lookup = pd.read_parquet(paths["lookup_dir"] / "lookup_item.parquet")
    premise_lookup = pd.read_parquet(paths["lookup_dir"] / "lookup_premise.parquet")
    premise_lookup = enrich_premise_columns(premise_lookup)

    selected_items = resolve_selected_items(config, item_lookup)
    item_codes = selected_items["item_code"].astype(str).tolist()
    price = filter_price_data(paths["raw_combined"].as_posix(), item_codes)

    clean = price.merge(selected_items, on="item_code", how="left")
    clean = clean.merge(premise_lookup, on="premise_code", how="left")
    clean = clean[clean["state"].isin(config["analysis"]["focus_states"])].copy()

    clean["area_type"] = clean.apply(lambda row: classify_area_type(row.to_dict()), axis=1)
    clean["price"] = clean["price"].round(4)
    clean = clean.sort_values(["bulan", "state", "district", "item", "date"]).reset_index(drop=True)

    clean.to_parquet(paths["clean_parquet"], index=False)
    print(f"Saved clean parquet with {len(clean):,} rows")


if __name__ == "__main__":
    main()
