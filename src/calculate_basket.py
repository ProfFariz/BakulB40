from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

import pandas as pd
import plotly.express as px

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
except Exception:  # pragma: no cover - fallback import is environment dependent
    plt = None

from common import (
    basket_quantities,
    ensure_directories,
    get_paths,
    load_config,
    month_range,
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


def load_cpi_low_income(cpi_parquet: Path, months: list[str]) -> pd.DataFrame:
    empty = pd.DataFrame(
        columns=[
            "date",
            "bulan",
            "division",
            "cpi_index",
            "cpi_mom_change_pct",
            "cpi_yoy_change_pct",
        ]
    )
    if not cpi_parquet.exists():
        return empty

    frame = pd.read_parquet(cpi_parquet)
    required_columns = {"date", "division", "index"}
    if not required_columns.issubset(frame.columns):
        return empty

    frame = frame[list(required_columns)].copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["division"] = frame["division"].astype(str).str.strip()
    frame["cpi_index"] = pd.to_numeric(frame["index"], errors="coerce")
    frame = frame.drop(columns=["index"]).dropna(subset=["date", "division", "cpi_index"])
    frame["bulan"] = frame["date"].dt.strftime("%Y-%m")
    frame = frame[frame["bulan"].isin(months)].copy()
    if frame.empty:
        return empty

    overall = frame[frame["division"].str.lower() == "overall"].copy()
    frame = overall if not overall.empty else frame
    frame = frame.sort_values(["division", "date"]).reset_index(drop=True)
    frame["cpi_mom_change_pct"] = frame.groupby("division")["cpi_index"].pct_change().mul(100).round(2)
    frame["cpi_yoy_change_pct"] = frame.groupby("division")["cpi_index"].pct_change(12).mul(100).round(2)
    return frame


def load_state_wages(wages_csv: Path) -> pd.DataFrame:
    if not wages_csv.exists():
        return pd.DataFrame(columns=["state", "year", "median_monthly_wage_rm"])

    frame = pd.read_csv(wages_csv)
    required_columns = {"state", "year", "median_monthly_wage_rm"}
    if not required_columns.issubset(frame.columns):
        return pd.DataFrame(columns=["state", "year", "median_monthly_wage_rm"])

    frame = frame[list(required_columns)].copy()
    frame["state"] = frame["state"].astype(str).str.strip()
    frame["year"] = pd.to_numeric(frame["year"], errors="coerce")
    frame["median_monthly_wage_rm"] = pd.to_numeric(frame["median_monthly_wage_rm"], errors="coerce")
    frame = frame.dropna(subset=["state", "year", "median_monthly_wage_rm"])
    frame = frame[frame["median_monthly_wage_rm"] > 0].copy()
    frame["year"] = frame["year"].astype(int)
    return frame.sort_values(["state", "year"]).reset_index(drop=True)


def attach_income_reference(
    total_basket: pd.DataFrame,
    wages: pd.DataFrame,
    fallback_income_rm: float,
) -> pd.DataFrame:
    frame = total_basket.copy()
    frame["year"] = frame["bulan"].str.slice(0, 4).astype(int)
    frame["household_income_rm"] = fallback_income_rm
    frame["income_reference_method"] = "config_fallback"

    if wages.empty:
        frame["income_reference_year"] = pd.NA
        frame["burden_pct"] = (frame["cost_item"] / frame["household_income_rm"] * 100).round(2)
        return frame

    malaysia_reference = wages[wages["state"] == "Malaysia"].sort_values("year")
    enriched_parts: list[pd.DataFrame] = []

    for state, group in frame.groupby("state", dropna=False):
        state_rows = group.sort_values("year").copy()
        state_reference = wages[wages["state"] == state].sort_values("year")
        reference = state_reference if not state_reference.empty else malaysia_reference
        reference = reference[["year", "median_monthly_wage_rm"]].rename(columns={"year": "income_reference_year"})

        merged = pd.merge_asof(
            state_rows,
            reference,
            left_on="year",
            right_on="income_reference_year",
            direction="backward",
        )

        merged["household_income_rm"] = merged["median_monthly_wage_rm"].fillna(fallback_income_rm)
        merged["income_reference_method"] = merged["median_monthly_wage_rm"].apply(
            lambda value: "state_median_wage" if pd.notna(value) else "config_fallback"
        )
        merged = merged.drop(columns=["median_monthly_wage_rm"])
        enriched_parts.append(merged)

    enriched = pd.concat(enriched_parts, ignore_index=True)
    enriched["household_income_rm"] = enriched["household_income_rm"].round(2)
    enriched["burden_pct"] = (enriched["cost_item"] / enriched["household_income_rm"] * 100).round(2)
    return enriched.sort_values(["bulan", "state", "district", "area_type"]).reset_index(drop=True)


def build_total_basket(item_monthly: pd.DataFrame, wages: pd.DataFrame, fallback_income_rm: float) -> pd.DataFrame:
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
    return attach_income_reference(totals, wages, fallback_income_rm)


def build_basket_vs_cpi_table(total_basket: pd.DataFrame, cpi_low_income: pd.DataFrame) -> pd.DataFrame:
    monthly_basket = (
        total_basket.groupby("bulan", dropna=False)["cost_item"]
        .mean()
        .reset_index()
        .rename(columns={"cost_item": "national_avg_basket_cost_rm"})
        .sort_values("bulan")
    )
    if monthly_basket.empty:
        return pd.DataFrame(
            columns=[
                "bulan",
                "national_avg_basket_cost_rm",
                "basket_index",
                "low_income_cpi_index",
                "low_income_cpi_rebased",
                "cpi_mom_change_pct",
                "cpi_yoy_change_pct",
                "basket_vs_cpi_gap",
            ]
        )

    base_basket = float(monthly_basket["national_avg_basket_cost_rm"].iloc[0])
    monthly_basket["basket_index"] = (monthly_basket["national_avg_basket_cost_rm"] / base_basket * 100).round(2)

    if cpi_low_income.empty:
        monthly_basket["low_income_cpi_index"] = pd.NA
        monthly_basket["low_income_cpi_rebased"] = pd.NA
        monthly_basket["cpi_mom_change_pct"] = pd.NA
        monthly_basket["cpi_yoy_change_pct"] = pd.NA
        monthly_basket["basket_vs_cpi_gap"] = pd.NA
        return monthly_basket

    cpi_series = (
        cpi_low_income.sort_values("bulan")[["bulan", "cpi_index", "cpi_mom_change_pct", "cpi_yoy_change_pct"]]
        .drop_duplicates("bulan")
        .rename(columns={"cpi_index": "low_income_cpi_index"})
    )
    comparison = monthly_basket.merge(cpi_series, on="bulan", how="left")
    first_cpi = comparison["low_income_cpi_index"].dropna()
    if first_cpi.empty:
        comparison["low_income_cpi_rebased"] = pd.NA
        comparison["basket_vs_cpi_gap"] = pd.NA
    else:
        comparison["low_income_cpi_rebased"] = (
            comparison["low_income_cpi_index"] / float(first_cpi.iloc[0]) * 100
        ).round(2)
        comparison["basket_vs_cpi_gap"] = (
            comparison["basket_index"] - comparison["low_income_cpi_rebased"]
        ).round(2)
    comparison["national_avg_basket_cost_rm"] = comparison["national_avg_basket_cost_rm"].round(2)
    return comparison


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


def build_kpis(
    total_basket: pd.DataFrame,
    volatility: pd.DataFrame,
    basket_vs_cpi: pd.DataFrame,
    config: dict,
    data_mode: str,
) -> dict:
    latest_month = total_basket["bulan"].max()
    earliest_month = total_basket["bulan"].min()
    focus_district = config["analysis"]["focus_district"]

    latest_focus = total_basket[
        (total_basket["district"] == focus_district) & (total_basket["bulan"] == latest_month)
    ]
    baseline_focus = total_basket[
        (total_basket["district"] == focus_district) & (total_basket["bulan"] == earliest_month)
    ]

    latest_focus_cost = float(latest_focus["cost_item"].iloc[0]) if not latest_focus.empty else 0.0
    latest_focus_burden = float(latest_focus["burden_pct"].iloc[0]) if not latest_focus.empty else 0.0
    reference_income_rm = float(latest_focus["household_income_rm"].iloc[0]) if not latest_focus.empty else 0.0
    reference_income_year = (
        int(latest_focus["income_reference_year"].iloc[0])
        if not latest_focus.empty and pd.notna(latest_focus["income_reference_year"].iloc[0])
        else None
    )
    latest_focus_state = str(latest_focus["state"].iloc[0]) if not latest_focus.empty else "N/A"
    reference_income_method = (
        str(latest_focus["income_reference_method"].iloc[0]) if not latest_focus.empty else "config_fallback"
    )
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

    latest_cpi_row = pd.DataFrame()
    if not basket_vs_cpi.empty:
        latest_cpi_row = basket_vs_cpi[basket_vs_cpi["low_income_cpi_index"].notna()].sort_values("bulan").tail(1)
    latest_low_income_cpi_month = (
        str(latest_cpi_row["bulan"].iloc[0]) if not latest_cpi_row.empty else None
    )
    latest_low_income_cpi_index = (
        round(float(latest_cpi_row["low_income_cpi_index"].iloc[0]), 2)
        if not latest_cpi_row.empty and pd.notna(latest_cpi_row["low_income_cpi_index"].iloc[0])
        else None
    )
    latest_low_income_cpi_yoy_pct = (
        round(float(latest_cpi_row["cpi_yoy_change_pct"].iloc[0]), 2)
        if not latest_cpi_row.empty and pd.notna(latest_cpi_row["cpi_yoy_change_pct"].iloc[0])
        else None
    )
    latest_basket_vs_cpi_gap = (
        round(float(latest_cpi_row["basket_vs_cpi_gap"].iloc[0]), 2)
        if not latest_cpi_row.empty and pd.notna(latest_cpi_row["basket_vs_cpi_gap"].iloc[0])
        else None
    )

    most_volatile = volatility.iloc[0].to_dict() if not volatility.empty else {"district": "N/A", "std_dev": 0.0}
    return {
        "data_mode": data_mode,
        "latest_month": latest_month,
        "latest_focus_district": focus_district,
        "latest_focus_cost_rm": round(latest_focus_cost, 2),
        "latest_focus_burden_pct": round(latest_focus_burden, 2),
        "focus_district_series_change_pct": focus_change,
        "focus_district_12m_change_pct": focus_change,
        "latest_focus_state": latest_focus_state,
        "reference_income_rm": round(reference_income_rm, 2),
        "reference_income_year": reference_income_year,
        "reference_income_method": reference_income_method,
        "latest_low_income_cpi_month": latest_low_income_cpi_month,
        "latest_low_income_cpi_index": latest_low_income_cpi_index,
        "latest_low_income_cpi_yoy_pct": latest_low_income_cpi_yoy_pct,
        "latest_basket_vs_cpi_gap": latest_basket_vs_cpi_gap,
        "highest_pressure_state": latest_pressure_state,
        "highest_pressure_state_burden_pct": latest_pressure_value,
        "most_volatile_district": most_volatile.get("district", "N/A"),
        "most_volatile_std_dev_rm": round(float(most_volatile.get("std_dev", 0.0)), 2),
    }


def build_insights(
    item_monthly: pd.DataFrame,
    total_basket: pd.DataFrame,
    inflation: pd.DataFrame,
    basket_vs_cpi: pd.DataFrame,
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
    income_year = kpis.get("reference_income_year")
    income_year_text = f" (rujukan gaji {income_year})" if income_year else ""
    latest_cpi = {}
    if not basket_vs_cpi.empty:
        latest_cpi_rows = basket_vs_cpi[basket_vs_cpi["low_income_cpi_index"].notna()].sort_values("bulan")
        if not latest_cpi_rows.empty:
            latest_cpi = latest_cpi_rows.iloc[-1].to_dict()
    cpi_detail = "CPI Low-Income keseluruhan belum tersedia untuk bulan ini."
    if latest_cpi and pd.notna(latest_cpi.get("low_income_cpi_rebased")):
        cpi_gap = float(latest_cpi["basket_vs_cpi_gap"])
        cpi_direction = "lebih pantas" if cpi_gap > 0 else "lebih perlahan"
        cpi_month = latest_cpi.get("bulan", latest_month)
        cpi_detail = (
            f"Pada {cpi_month}, indeks bakul bergerak {abs(cpi_gap):.2f} mata {cpi_direction} "
            f"berbanding CPI Low-Income keseluruhan (rebase=100)."
        )
    return [
        {
            "title": "Beban gaji",
            "detail": (
                f"Kos bakul {kpis['latest_focus_district']} pada {latest_month} ialah "
                f"RM{kpis['latest_focus_cost_rm']:.2f}, bersamaan {kpis['latest_focus_burden_pct']:.2f}% "
                f"daripada pendapatan rujukan negeri RM{kpis['reference_income_rm']:.0f}{income_year_text}."
            ),
        },
        {
            "title": "Rujukan CPI B40",
            "detail": cpi_detail,
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
    basket_vs_cpi: pd.DataFrame,
    gap: pd.DataFrame,
    ramadan: pd.DataFrame,
    figures_dir: Path,
) -> None:
    ensure_directories(figures_dir)

    figures = [
        (
            "monthly_basket",
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
            "state_burden",
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
            "inflation_item",
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
            "urban_rural_gap",
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
            "ramadan",
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

    if not basket_vs_cpi.empty and basket_vs_cpi["low_income_cpi_rebased"].notna().any():
        figures.append(
            (
                "basket_vs_cpi",
                px.line(
                    basket_vs_cpi.melt(
                        id_vars="bulan",
                        value_vars=["basket_index", "low_income_cpi_rebased"],
                        var_name="series",
                        value_name="index_value",
                    ),
                    x="bulan",
                    y="index_value",
                    color="series",
                    markers=True,
                    title="Indeks Bakul vs CPI Low-Income (Rebase=100)",
                ),
                figures_dir / "06_bakul_vs_cpi_lowincome.png",
            )
        )

    for chart_key, figure, destination in figures:
        figure.update_layout(template="plotly_white")
        exported = export_figure_with_timeout(
            figure,
            destination,
            width=1280,
            height=720,
            scale=2,
        )
        if not exported:
            export_matplotlib_fallback(
                chart_key,
                destination,
                item_monthly=item_monthly,
                total_basket=total_basket,
                inflation=inflation,
                basket_vs_cpi=basket_vs_cpi,
                gap=gap,
                ramadan=ramadan,
            )


def export_figure_with_timeout(
    figure,
    destination: Path,
    width: int,
    height: int,
    scale: int,
    timeout_seconds: int = 45,
) -> bool:
    payload = json.dumps(
        {
            "figure_json": figure.to_json(),
            "destination": str(destination),
            "width": width,
            "height": height,
            "scale": scale,
        }
    )
    script = """
import json
import sys
from pathlib import Path

import plotly.io as pio

payload = json.load(sys.stdin)
figure = pio.from_json(payload["figure_json"])
destination = Path(payload["destination"])
destination.parent.mkdir(parents=True, exist_ok=True)
figure.write_image(
    destination,
    width=payload["width"],
    height=payload["height"],
    scale=payload["scale"],
)
"""

    try:
        subprocess.run(
            [sys.executable, "-c", script],
            input=payload,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=True,
        )
        return True
    except subprocess.TimeoutExpired:
        print(f"Warning: skipped figure export after {timeout_seconds}s timeout: {destination.name}")
    except subprocess.CalledProcessError as error:
        stderr = error.stderr.strip() if error.stderr else "unknown image export error"
        print(f"Warning: failed to export {destination.name}: {stderr}")
    return False


def export_matplotlib_fallback(
    chart_key: str,
    destination: Path,
    *,
    item_monthly: pd.DataFrame,
    total_basket: pd.DataFrame,
    inflation: pd.DataFrame,
    basket_vs_cpi: pd.DataFrame,
    gap: pd.DataFrame,
    ramadan: pd.DataFrame,
) -> None:
    if plt is None:
        print(f"Warning: matplotlib fallback unavailable for {destination.name}")
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(12.8, 7.2), dpi=100)

    if chart_key == "monthly_basket":
        data = (
            total_basket.groupby(["bulan", "district"], dropna=False)["cost_item"]
            .mean()
            .reset_index()
        )
        for district, group in data.groupby("district", dropna=False):
            ax.plot(group["bulan"], group["cost_item"], marker="o", linewidth=1.5, label=str(district))
        ax.set_title("Kos Bakul Bulanan Mengikut Daerah")
        ax.set_ylabel("RM")
        ax.legend(loc="upper left", fontsize=8, ncol=2)
    elif chart_key == "state_burden":
        data = (
            total_basket[total_basket["bulan"] == total_basket["bulan"].max()]
            .groupby("state", dropna=False)["burden_pct"]
            .mean()
            .reset_index()
            .sort_values("burden_pct", ascending=False)
        )
        ax.bar(data["state"], data["burden_pct"], color="#2563eb")
        ax.set_title("Beban Gaji Bulan Terkini Mengikut Negeri")
        ax.set_ylabel("%")
    elif chart_key == "inflation_item":
        for item, group in inflation.groupby("item", dropna=False):
            ax.plot(group["bulan"], group["price_index"], marker="o", linewidth=1.5, label=str(item))
        ax.set_title("Indeks Harga Item Asas")
        ax.set_ylabel("Index")
        ax.legend(loc="upper left", fontsize=8, ncol=2)
    elif chart_key == "urban_rural_gap":
        pivot = gap.pivot(index="bulan", columns="area_type", values="avg_cost").fillna(0)
        positions = range(len(pivot.index))
        width = 0.38
        ax.bar([pos - width / 2 for pos in positions], pivot.get("Urban", pd.Series(index=pivot.index, data=0)), width=width, label="Urban", color="#0f766e")
        ax.bar([pos + width / 2 for pos in positions], pivot.get("Rural", pd.Series(index=pivot.index, data=0)), width=width, label="Rural", color="#f59e0b")
        ax.set_xticks(list(positions))
        ax.set_xticklabels(pivot.index.tolist(), rotation=45, ha="right")
        ax.set_title("Jurang Kos Bakul Bandar-Luar Bandar")
        ax.set_ylabel("RM")
        ax.legend()
    elif chart_key == "ramadan":
        ax.bar(ramadan["ramadan_flag"], ramadan["avg_cost"], color=["#7c3aed", "#94a3b8"][: len(ramadan)])
        ax.set_title("Purata Kos Bakul Ramadan vs Bukan Ramadan")
        ax.set_ylabel("RM")
    elif chart_key == "basket_vs_cpi":
        data = basket_vs_cpi.dropna(subset=["low_income_cpi_rebased"]).copy()
        ax.plot(data["bulan"], data["basket_index"], marker="o", linewidth=1.5, label="basket_index")
        ax.plot(data["bulan"], data["low_income_cpi_rebased"], marker="o", linewidth=1.5, label="low_income_cpi_rebased")
        ax.set_title("Indeks Bakul vs CPI Low-Income (Rebase=100)")
        ax.set_ylabel("Index")
        ax.legend()
    else:
        plt.close(fig)
        print(f"Warning: no matplotlib fallback registered for {destination.name}")
        return

    ax.grid(True, axis="y", alpha=0.25)
    if chart_key not in {"urban_rural_gap"}:
        for label in ax.get_xticklabels():
            label.set_rotation(45)
            label.set_ha("right")
    fig.tight_layout()
    fig.savefig(destination, format="png", bbox_inches="tight")
    plt.close(fig)
    print(f"Saved matplotlib fallback {destination.name}")


def run_analysis(data_mode: str = "real") -> None:
    config = load_config()
    paths = get_paths(config)
    ensure_directories(paths["processed_dir"], paths["figures_dir"])

    clean = pd.read_parquet(paths["clean_parquet"])
    fallback_income_rm = float(config["analysis"]["household_monthly_income_rm"])
    cpi_low_income = load_cpi_low_income(paths["cpi_low_income_parquet"], month_range(config))
    wages = load_state_wages(paths["wages_median_csv"])

    item_monthly = build_monthly_item_basket(clean, config)
    total_basket = build_total_basket(item_monthly, wages, fallback_income_rm)
    basket_vs_cpi = build_basket_vs_cpi_table(total_basket, cpi_low_income)
    inflation = build_inflation_table(item_monthly)
    volatility = build_volatility_table(total_basket)
    gap = build_gap_table(total_basket)
    ramadan = build_ramadan_table(total_basket, config)
    kpis = build_kpis(total_basket, volatility, basket_vs_cpi, config, data_mode)
    insights = build_insights(item_monthly, total_basket, inflation, basket_vs_cpi, gap, ramadan, kpis)

    item_monthly.to_csv(paths["basket_item_csv"], index=False)
    total_basket.to_csv(paths["basket_cost_csv"], index=False)
    cpi_low_income.to_csv(paths["cpi_low_income_csv"], index=False)
    basket_vs_cpi.to_csv(paths["basket_vs_cpi_csv"], index=False)
    inflation.to_csv(paths["inflation_csv"], index=False)
    volatility.to_csv(paths["volatility_csv"], index=False)
    gap.to_csv(paths["gap_csv"], index=False)
    ramadan.to_csv(paths["ramadan_csv"], index=False)
    write_json(paths["kpi_json"], kpis)
    write_json(paths["insights_json"], insights)

    source_metadata = read_json(paths["source_json"], default={})
    source_metadata["data_mode"] = data_mode
    source_metadata["note"] = (
        "Generated from the full configured PriceCatcher month range."
        if data_mode == "real"
        else "Bundled demo snapshot for a fast first run. Replace by running the full PriceCatcher pipeline."
    )
    source_metadata["cpi_low_income_available"] = not cpi_low_income.empty
    source_metadata["wages_reference_available"] = not wages.empty
    write_json(paths["source_json"], source_metadata)

    save_figures(item_monthly, total_basket, inflation, basket_vs_cpi, gap, ramadan, paths["figures_dir"])
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
