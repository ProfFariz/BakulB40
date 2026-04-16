from __future__ import annotations

import argparse
from pathlib import Path

import duckdb
import pandas as pd

from common import ensure_directories, get_paths, load_config, month_range, save_config


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
    matched = item_lookup.sort_values(["item", "item_code"]).drop_duplicates("item")
    code_by_name = dict(zip(matched["item"], matched["item_code"]))
    catalogue_rows: list[dict[str, object]] = []
    unresolved: list[str] = []

    for item in config["basket"]["items"]:
        state_proxies = item.get("state_proxies") or {}
        if state_proxies:
            for state, proxy in state_proxies.items():
                lookup_name = str(proxy.get("lookup_name") or item.get("lookup_name") or item["name"])
                discovered = code_by_name.get(lookup_name)
                if discovered is not None:
                    proxy["item_code"] = str(discovered)
                else:
                    unresolved.append(f"{item['name']} [{state}]")
                catalogue_rows.append(
                    {
                        "basket_item_name": item["name"],
                        "state": state,
                        "lookup_name": lookup_name,
                        "item_code": proxy.get("item_code"),
                    }
                )
            continue

        lookup_name = str(item.get("lookup_name") or item["name"])
        discovered = code_by_name.get(lookup_name)
        if discovered is not None:
            item["item_code"] = str(discovered)
        else:
            unresolved.append(str(item["name"]))
        catalogue_rows.append(
            {
                "basket_item_name": item["name"],
                "state": "ALL_FOCUS_STATES",
                "lookup_name": lookup_name,
                "item_code": item.get("item_code"),
            }
        )

    save_config(config)
    pd.DataFrame(catalogue_rows).to_csv(get_paths(config)["item_catalogue_csv"], index=False)
    if unresolved:
        print(f"Warning: item codes not found for {', '.join(unresolved)}")


def build_combined_raw(month_files: list[Path], destination: Path) -> None:
    if not month_files:
        return

    parquet_list = ", ".join(f"'{path.as_posix()}'" for path in month_files)
    connection = duckdb.connect()
    query = f"""
        COPY (
            SELECT
                CAST(date AS DATE) AS date,
                COALESCE(bulan, strftime(CAST(date AS DATE), '%Y-%m')) AS bulan,
                *
            EXCLUDE (date, bulan)
            FROM read_parquet([{parquet_list}])
        ) TO '{destination.as_posix()}' (FORMAT PARQUET);
    """
    connection.execute(query)
    print(f"Saved {destination.name}")


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

    month_files = []
    for month in months:
        destination = paths["raw_dir"] / f"pricecatcher_{month}.parquet"
        download_month(month, url_template, destination, args.force)
        month_files.append(destination)

    try:
        build_combined_raw(month_files, paths["raw_combined"])
    except Exception as error:
        print(f"Warning: skipped combined parquet snapshot because of: {error}")

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
