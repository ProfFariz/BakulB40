from __future__ import annotations

from datetime import date

import pandas as pd

from calculate_basket import run_analysis
import generate_report
from common import (
    basket_items,
    ensure_directories,
    get_paths,
    load_config,
    month_range,
    write_json,
)


DISTRICTS = [
    {"state": "Perak", "district": "Tapah", "area_type": "Rural", "district_factor": 1.00},
    {"state": "Perak", "district": "Ipoh", "area_type": "Urban", "district_factor": 1.05},
    {"state": "W.P. Kuala Lumpur", "district": "Kuala Lumpur", "area_type": "Urban", "district_factor": 1.12},
    {"state": "Sabah", "district": "Kota Kinabalu", "area_type": "Urban", "district_factor": 1.17},
]

BASE_PRICES = {
    "Beras putih": 32.00,
    "Ayam": 10.20,
    "Telur": 13.50,
    "Minyak masak": 3.30,
    "Gula": 2.90,
    "Tepung": 2.60,
    "Susu pekat": 4.30,
    "Kicap": 4.50,
    "Bawang": 4.80,
    "Cili": 13.50,
    "Ikan kembung": 17.00,
    "Sayur sawi": 4.20,
    "Roti": 3.40,
    "Mee segera": 9.20,
    "Sabun": 13.80,
}


def build_demo_clean_dataset(config: dict) -> pd.DataFrame:
    rows = []
    months = month_range(config)
    basket = basket_items(config)

    for month_index, month in enumerate(months):
        year, month_number = map(int, month.split("-"))
        month_date = date(year, month_number, 1)
        seasonal_factor = 1 + (month_index * 0.011)
        ramadan_factor = 1.018 if month in set(config["analysis"]["ramadan_months"]) else 1.0

        for district_index, district in enumerate(DISTRICTS):
            district_adj = district["district_factor"]
            for item_index, item in enumerate(basket):
                base_price = BASE_PRICES[item["name"]]
                item_factor = 1 + (item_index * 0.012)
                for sample_index in range(4):
                    noise = 1 + ((sample_index - 1.5) * 0.003) + (district_index * 0.001)
                    price = round(base_price * seasonal_factor * ramadan_factor * district_adj * item_factor * noise, 4)
                    rows.append(
                        {
                            "date": month_date,
                            "bulan": month,
                            "state": district["state"],
                            "district": district["district"],
                            "area_type": district["area_type"],
                            "item_code": item.get("item_code") or f"DEMO-{item_index + 1:02d}",
                            "item": item["name"],
                            "unit": item["quantity_unit"],
                            "item_group": "Makanan Asas",
                            "price": price,
                            "premise_code": f"P-{district_index + 1:02d}",
                            "premise": f"Premise {district['district']}",
                            "premise_type": "Supermarket" if district["area_type"] == "Urban" else "Kedai Runcit",
                            "premise_category": district["area_type"],
                            "premise_address": district["district"],
                        }
                    )
    return pd.DataFrame(rows)


def main() -> None:
    config = load_config()
    paths = get_paths(config)
    ensure_directories(paths["processed_dir"], paths["figures_dir"])

    clean = build_demo_clean_dataset(config)
    clean.to_parquet(paths["clean_parquet"], index=False)

    write_json(
        paths["source_json"],
        {
            "data_mode": "demo",
            "note": "Bundled demo snapshot for a fast first run. Replace by running the full PriceCatcher pipeline.",
        },
    )

    run_analysis(data_mode="demo")
    generate_report.main()
    print("Demo bootstrap complete.")


if __name__ == "__main__":
    main()
