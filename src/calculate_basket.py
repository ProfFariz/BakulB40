from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import plotly.express as px

from common import (
    basket_quantities,
    ensure_directories,
    get_paths,
    load_config,
    read_json,
    write_json,
)


def build_monthly_item_basket(clean: pd.DataFrame, config: dict) -> pd.DataFrame:
    grouped = (
        clean.groupby(["bulan", "state", "district", "area_type", "item"], dropna=False)
        .agg(
            harga_purata=("price", "mean"),
            harga_median=("price", "median"),
            sampel_harga=("price", "size"),
        )
        .reset_index()
    )
    grouped["qty"] = grouped["item"].map(basket_quantities(config))
    grouped["cost_item"] = grouped["harga_purata"] * grouped["qty"]
    grouped["cost_item"] = grouped["cost_item"].round(2)
    grouped["harga_purata"] = grouped["harga_purata"].round(4)
    grouped["harga_median"] = grouped["harga_median"].round(4)
    return grouped


def build_total_basket(item_monthly: pd.DataFrame, income_rm: float) -> pd.DataFrame:
    totals = (
        item_monthly.groupby(["bulan", "state", "district", "area_type"], dropna=False)
        .agg(
            cost_item=("cost_item", "sum"),
            item_count=("item", "nunique"),
            total_observation=("sampel_harga", "sum"),
        )
        .reset_index()
    )
    totals["cost_item"] = totals["cost_item"].round(2)
    totals["household_income_rm"] = income_rm
    totals["burden_pct"] = (totals["cost_item"] / income_rm * 100).round(2)
    return totals


def build_inflation_table(item_monthly: pd.DataFrame) -> pd.DataFrame:
    national = (
        item_monthly.groupby(["bulan", "item"], dropna=False)["harga_purata"]
        .mean()
        .reset_index()
        .sort_values(["item", "bulan"])
    )
    national["monthly_change_pct"] = (
        national.groupby("item")["harga_purata"].pct_change().mul(100).round(2)
    )
    first_price = national.groupby("item")["harga_purata"].transform("first")
    national["price_index"] = (national["harga_purata"] / first_price * 100).round(2)
    return national


def build_volatility_table(total_basket: pd.DataFrame) -> pd.DataFrame:
    volatility = (
        total_basket.groupby(["state", "district"], dropna=False)["cost_item"]
        .agg(["mean", "std", "min", "max"])
        .reset_index()
        .rename(
            columns={
                "mean": "avg_cost",
                "std": "std_dev",
                "min": "min_cost",
                "max": "max_cost",
            }
        )
    )
    volatility["std_dev"] = volatility["std_dev"].fillna(0).round(2)
    volatility["avg_cost"] = volatility["avg_cost"].round(2)
    volatility["min_cost"] = volatility["min_cost"].round(2)
    volatility["max_cost"] = volatility["max_cost"].round(2)
    return volatility.sort_values("std_dev", ascending=False)


def build_gap_table(total_basket: pd.DataFrame) -> pd.DataFrame:
    usable = total_basket[total_basket["area_type"].isin(["Urban", "Rural"])].copy()
    if usable.empty:
        return pd.DataFrame(columns=["bulan", "area_type", "avg_cost"])
    grouped = usable.groupby(["bulan", "area_type"], dropna=False)["cost_item"].mean().reset_index()
    grouped = grouped.rename(columns={"cost_item": "avg_cost"})
    grouped["avg_cost"] = grouped["avg_cost"].round(2)
    return grouped


def build_ramadan_table(total_basket: pd.DataFrame, config: dict) -> pd.DataFrame:
    ramadan_months = set(config["analysis"]["ramadan_months"])
    frame = total_basket.copy()
    frame["ramadan_flag"] = frame["bulan"].apply(lambda value: "Ramadan" if value in ramadan_months else "Non-Ramadan")
    grouped = frame.groupby("ramadan_flag", dropna=False)["cost_item"].mean().reset_index()
    grouped = grouped.rename(columns={"cost_item": "avg_cost"})
    grouped["avg_cost"] = grouped["avg_cost"].round(2)
    return grouped


def build_kpis(total_basket: pd.DataFrame, volatility: pd.DataFrame, config: dict, data_mode: str) -> dict:
    latest_month = total_basket["bulan"].max()
    earliest_month = total_basket["bulan"].min()
    focus_district = config["analysis"]["focus_district"]
    income_rm = config["analysis"]["household_monthly_income_rm"]

    latest_focus = total_basket[
        (total_basket["district"] == focus_district) & (total_basket["bulan"] == latest_month)
    ]
    baseline_focus = total_basket[
        (total_basket["district"] == focus_district) & (total_basket["bulan"] == earliest_month)
    ]

    latest_focus_cost = float(latest_focus["cost_item"].iloc[0]) if not latest_focus.empty else 0.0
    latest_focus_burden = float(latest_focus["burden_pct"].iloc[0]) if not latest_focus.empty else 0.0
    focus_change = 0.0
    if not latest_focus.empty and not baseline_focus.empty and float(baseline_focus["cost_item"].iloc[0]) > 0:
        start_cost = float(baseline_focus["cost_item"].iloc[0])
        focus_change = round((latest_focus_cost - start_cost) / start_cost * 100, 2)

    latest_state = (
        total_basket[total_basket["bulan"] == latest_month]
        .groupby("state", dropna=False)["burden_pct"]
        .mean()
        .sort_values(ascending=False)
    )
    latest_pressure_state = latest_state.index[0] if not latest_state.empty else "N/A"
    latest_pressure_value = round(float(latest_state.iloc[0]), 2) if not latest_state.empty else 0.0

    most_volatile = volatility.iloc[0].to_dict() if not volatility.empty else {"district": "N/A", "std_dev": 0.0}
    return {
        "data_mode": data_mode,
        "latest_month": latest_month,
        "latest_focus_district": focus_district,
        "latest_focus_cost_rm": round(latest_focus_cost, 2),
        "latest_focus_burden_pct": round(latest_focus_burden, 2),
        "focus_district_12m_change_pct": focus_change,
        "reference_income_rm": float(income_rm),
        "highest_pressure_state": latest_pressure_state,
        "highest_pressure_state_burden_pct": latest_pressure_value,
        "most_volatile_district": most_volatile.get("district", "N/A"),
        "most_volatile_std_dev_rm": round(float(most_volatile.get("std_dev", 0.0)), 2),
    }


def build_insights(
    item_monthly: pd.DataFrame,
    total_basket: pd.DataFrame,
    inflation: pd.DataFrame,
    gap: pd.DataFrame,
    ramadan: pd.DataFrame,
    kpis: dict,
) -> list[dict]:
    latest_month = kpis["latest_month"]

    latest_state = (
        total_basket[total_basket["bulan"] == latest_month]
        .groupby("state", dropna=False)["burden_pct"]
        .mean()
        .sort_values(ascending=False)
    )
    latest_item = (
        inflation[inflation["bulan"] == latest_month]
        .sort_values("monthly_change_pct", ascending=False)
        .head(1)
    )
    urban_gap = 0.0
    if not gap.empty and latest_month in set(gap["bulan"]):
        latest_gap = gap[gap["bulan"] == latest_month].set_index("area_type")["avg_cost"].to_dict()
        urban_gap = round(float(latest_gap.get("Urban", 0.0) - latest_gap.get("Rural", 0.0)), 2)

    ramadan_delta = 0.0
    if set(ramadan["ramadan_flag"]) == {"Ramadan", "Non-Ramadan"}:
        ramadan_map = ramadan.set_index("ramadan_flag")["avg_cost"].to_dict()
        ramadan_delta = round(float(ramadan_map["Ramadan"] - ramadan_map["Non-Ramadan"]), 2)

    top_state = latest_state.index[0] if not latest_state.empty else "N/A"
    top_state_burden = round(float(latest_state.iloc[0]), 2) if not latest_state.empty else 0.0

    top_item = latest_item.iloc[0].to_dict() if not latest_item.empty else {"item": "N/A", "monthly_change_pct": 0.0}
    return [
        {
            "title": "Beban gaji",
            "detail": (
                f"Kos bakul {kpis['latest_focus_district']} pada {latest_month} ialah "
                f"RM{kpis['latest_focus_cost_rm']:.2f}, bersamaan {kpis['latest_focus_burden_pct']:.2f}% "
                f"daripada pendapatan rujukan RM{kpis['reference_income_rm']:.0f}."
            ),
        },
        {
            "title": "Negeri paling tertekan",
            "detail": f"{top_state} merekodkan purata beban tertinggi pada {top_state_burden:.2f}% dalam bulan terkini.",
        },
        {
            "title": "Inflasi item",
            "detail": f"Item dengan kenaikan bulanan paling tinggi dalam snapshot terkini ialah {top_item['item']} pada {float(top_item['monthly_change_pct'] or 0.0):.2f}%.",
        },
        {
            "title": "Jurang bandar-luar bandar",
            "detail": f"Jurang purata kos bakul Urban berbanding Rural dalam bulan terkini ialah RM{urban_gap:.2f}.",
        },
        {
            "title": "Kesan Ramadan",
            "detail": f"Purata kos bakul semasa Ramadan berubah sebanyak RM{ramadan_delta:.2f} berbanding bulan bukan Ramadan.",
        },
    ]


def save_figures(
    item_monthly: pd.DataFrame,
    total_basket: pd.DataFrame,
    inflation: pd.DataFrame,
    gap: pd.DataFrame,
    ramadan: pd.DataFrame,
    figures_dir: Path,
) -> None:
    ensure_directories(figures_dir)

    figures = [
        (
            px.line(
                total_basket,
                x="bulan",
                y="cost_item",
                color="district",
                markers=True,
                title="Kos Bakul Bulanan Mengikut Daerah",
            ),
            figures_dir / "01_kos_bakul_bulanan.png",
        ),
        (
            px.bar(
                total_basket[total_basket["bulan"] == total_basket["bulan"].max()]
                .groupby("state", dropna=False)["burden_pct"]
                .mean()
                .reset_index(),
                x="state",
                y="burden_pct",
                color="state",
                title="Beban Gaji Bulan Terkini Mengikut Negeri",
            ),
            figures_dir / "02_beban_gaji_negeri.png",
        ),
        (
            px.line(
                inflation,
                x="bulan",
                y="price_index",
                color="item",
                markers=True,
                title="Indeks Harga Item Asas",
            ),
            figures_dir / "03_inflasi_item.png",
        ),
        (
            px.bar(
                gap,
                x="bulan",
                y="avg_cost",
                color="area_type",
                barmode="group",
                title="Jurang Kos Bakul Bandar-Luar Bandar",
            ),
            figures_dir / "04_jurang_bandar_luar_bandar.png",
        ),
        (
            px.bar(
                ramadan,
                x="ramadan_flag",
                y="avg_cost",
                color="ramadan_flag",
                title="Purata Kos Bakul Ramadan vs Bukan Ramadan",
            ),
            figures_dir / "05_kesan_ramadan.png",
        ),
    ]

    for figure, destination in figures:
        figure.update_layout(template="plotly_white")
        figure.write_image(destination, width=1280, height=720, scale=2)


def run_analysis(data_mode: str = "real") -> None:
    config = load_config()
    paths = get_paths(config)
    ensure_directories(paths["processed_dir"], paths["figures_dir"])

    clean = pd.read_parquet(paths["clean_parquet"])
    income_rm = float(config["analysis"]["household_monthly_income_rm"])

    item_monthly = build_monthly_item_basket(clean, config)
    total_basket = build_total_basket(item_monthly, income_rm)
    inflation = build_inflation_table(item_monthly)
    volatility = build_volatility_table(total_basket)
    gap = build_gap_table(total_basket)
    ramadan = build_ramadan_table(total_basket, config)
    kpis = build_kpis(total_basket, volatility, config, data_mode)
    insights = build_insights(item_monthly, total_basket, inflation, gap, ramadan, kpis)

    item_monthly.to_csv(paths["basket_item_csv"], index=False)
    total_basket.to_csv(paths["basket_cost_csv"], index=False)
    inflation.to_csv(paths["inflation_csv"], index=False)
    volatility.to_csv(paths["volatility_csv"], index=False)
    gap.to_csv(paths["gap_csv"], index=False)
    ramadan.to_csv(paths["ramadan_csv"], index=False)
    write_json(paths["kpi_json"], kpis)
    write_json(paths["insights_json"], insights)

    source_metadata = read_json(paths["source_json"], default={})
    source_metadata["data_mode"] = data_mode
    write_json(paths["source_json"], source_metadata)

    save_figures(item_monthly, total_basket, inflation, gap, ramadan, paths["figures_dir"])
    print("Analysis outputs saved.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate basket metrics and derived outputs.")
    parser.add_argument(
        "--data-mode",
        choices=["real", "demo"],
        default="real",
        help="Label the generated outputs as real or demo data.",
    )
    args = parser.parse_args()
    run_analysis(data_mode=args.data_mode)


if __name__ == "__main__":
    main()
