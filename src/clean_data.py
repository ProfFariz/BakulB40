from __future__ import annotations

import pandas as pd
import duckdb

from common import (
    basket_proxy_rows,
    classify_area_type,
    ensure_directories,
    get_paths,
    load_config,
    quoted_sql_strings,
    raw_month_paths,
)


def normalize_code(series: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    normalized = series.astype(str).str.strip()
    normalized = normalized.mask(numeric.notna(), numeric.dropna().astype("Int64").astype(str))
    return normalized


def resolve_selected_items(config: dict, item_lookup: pd.DataFrame) -> pd.DataFrame:
    lookup = item_lookup.copy()
    lookup["item_code"] = normalize_code(lookup["item_code"])

    resolved_rows: list[dict[str, object]] = []
    unresolved: list[str] = []

    for proxy in basket_proxy_rows(config):
        match = pd.DataFrame()
        item_code = proxy.get("item_code")
        lookup_name = str(proxy["lookup_name"])
        if item_code:
            match = lookup[lookup["item_code"] == str(item_code)].copy()
        if match.empty:
            match = lookup[lookup["item"] == lookup_name].copy()
        if match.empty:
            unresolved.append(f"{proxy['name']} [{proxy['state']}] -> {lookup_name}")
            continue

        row = match.sort_values("item_code").iloc[0]
        resolved_rows.append(
            {
                "state": str(proxy["state"]),
                "item_code": str(row["item_code"]),
                "item": str(proxy["name"]),
                "unit": row.get("unit"),
                "item_group": row.get("item_group"),
            }
        )

    if unresolved:
        raise ValueError("No matching basket items found for: " + "; ".join(unresolved))

    selected = pd.DataFrame(resolved_rows)
    if selected.empty:
        raise ValueError("No matching basket items found in lookup_item.parquet.")

    columns = [column for column in ("state", "item_code", "item", "unit", "item_group") if column in selected.columns]
    return selected[columns].drop_duplicates(["state", "item_code"])


def filter_price_data(raw_parquets: list[str], item_codes: list[str]) -> pd.DataFrame:
    connection = duckdb.connect()
    code_list = quoted_sql_strings(item_codes)
    parquet_list = ", ".join(f"'{path}'" for path in raw_parquets)
    query = f"""
        SELECT
            CAST(date AS DATE) AS date,
            COALESCE(bulan, strftime(CAST(date AS DATE), '%Y-%m')) AS bulan,
            CAST(item_code AS VARCHAR) AS item_code,
            CAST(premise_code AS VARCHAR) AS premise_code,
            CAST(price AS DOUBLE) AS price
        FROM read_parquet([{parquet_list}])
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
    if "premise_code" in frame.columns:
        frame["premise_code"] = normalize_code(frame["premise_code"])
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
    month_files = [path.as_posix() for path in raw_month_paths(config) if path.exists()]
    if not month_files:
        raise FileNotFoundError("No monthly PriceCatcher parquet files found in data/raw. Run download_data.py first.")
    price = filter_price_data(month_files, item_codes)

    clean = price.merge(premise_lookup, on="premise_code", how="left")
    clean = clean[clean["state"].isin(config["analysis"]["focus_states"])].copy()
    clean = clean.merge(selected_items, on=["state", "item_code"], how="inner")

    clean["area_type"] = clean.apply(lambda row: classify_area_type(row.to_dict()), axis=1)
    clean["price"] = clean["price"].round(4)
    clean = clean.sort_values(["bulan", "state", "district", "item", "date"]).reset_index(drop=True)

    clean.to_parquet(paths["clean_parquet"], index=False)
    print(f"Saved clean parquet with {len(clean):,} rows")


if __name__ == "__main__":
    main()
