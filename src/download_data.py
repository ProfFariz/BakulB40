from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from common import (
    basket_lookup_map,
    ensure_directories,
    get_paths,
    load_config,
    month_range,
    save_config,
)


def download_month(month: str, url_template: str, destination: Path, force: bool) -> pd.DataFrame:
    if destination.exists() and not force:
        print(f"Reuse {destination.name}")
        return pd.read_parquet(destination)

    url = url_template.format(month=month)
    print(f"Download {month} from {url}")
    frame = pd.read_parquet(url)
    frame["bulan"] = month
    frame.to_parquet(destination, index=False)
    print(f"Saved {destination.name} with {len(frame):,} rows")
    return frame


def download_lookup(url: str, destination: Path, force: bool) -> pd.DataFrame:
    if destination.exists() and not force:
        print(f"Reuse {destination.name}")
        return pd.read_parquet(destination)

    frame = pd.read_parquet(url)
    frame.to_parquet(destination, index=False)
    print(f"Saved {destination.name} with {len(frame):,} rows")
    return frame


def update_item_codes(config: dict, item_lookup: pd.DataFrame) -> None:
    lookup_map = basket_lookup_map(config)
    matched = item_lookup[item_lookup["item"].isin(lookup_map.keys())].copy()
    matched = matched.sort_values(["item", "item_code"]).drop_duplicates("item")

    code_by_name = dict(zip(matched["item"], matched["item_code"]))
    for item in config["basket"]["items"]:
        lookup_name = str(item.get("lookup_name") or item["name"])
        discovered = code_by_name.get(lookup_name)
        if discovered is not None:
            item["item_code"] = str(discovered)

    save_config(config)
    matched["basket_item_name"] = matched["item"].map(lookup_map)
    matched[["basket_item_name", "item", "item_code"]].to_csv(
        get_paths(config)["item_catalogue_csv"],
        index=False,
    )
    unresolved = [display_name for lookup_name, display_name in lookup_map.items() if lookup_name not in code_by_name]
    if unresolved:
        print(f"Warning: item codes not found for {', '.join(unresolved)}")


def build_combined_raw(month_frames: list[pd.DataFrame], destination: Path) -> None:
    combined = pd.concat(month_frames, ignore_index=True)
    combined.to_parquet(destination, index=False)
    print(f"Saved {destination.name} with {len(combined):,} rows")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download PriceCatcher and lookup data.")
    parser.add_argument("--force", action="store_true", help="Redownload files even if cached.")
    args = parser.parse_args()

    config = load_config()
    paths = get_paths(config)
    ensure_directories(
        paths["raw_dir"],
        paths["lookup_dir"],
        paths["processed_dir"],
        paths["cpi_dir"],
        paths["wages_dir"],
    )

    months = month_range(config)
    url_template = config["data_sources"]["pricecatcher_url_template"]

    month_frames = []
    for month in months:
        destination = paths["raw_dir"] / f"pricecatcher_{month}.parquet"
        month_frames.append(download_month(month, url_template, destination, args.force))

    build_combined_raw(month_frames, paths["raw_combined"])

    lookup_item = download_lookup(
        config["data_sources"]["lookup_item_url"],
        paths["lookup_dir"] / "lookup_item.parquet",
        args.force,
    )
    download_lookup(
        config["data_sources"]["lookup_premise_url"],
        paths["lookup_dir"] / "lookup_premise.parquet",
        args.force,
    )

    cpi_parquet_url = config["data_sources"].get("cpi_low_income_parquet_url")
    if cpi_parquet_url:
        download_lookup(
            cpi_parquet_url,
            paths["cpi_low_income_parquet"],
            args.force,
        )

    update_item_codes(config, lookup_item)
    print("Download step complete.")


if __name__ == "__main__":
    main()
