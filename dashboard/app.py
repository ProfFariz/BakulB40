from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def require_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        st.error("Processed data is missing. Run `python src/bootstrap_demo.py` or the full pipeline first.")
        st.stop()
    return pd.read_csv(path)


def optional_data(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


st.set_page_config(page_title="Bakul B40", page_icon=":bar_chart:", layout="wide")
st.title("Bakul B40: Beban Harga Makanan Asas")
st.caption("Portfolio dashboard built with PriceCatcher-compatible processing outputs.")

basket_cost = require_data(PROCESSED / "basket_cost.csv")
item_monthly = require_data(PROCESSED / "basket_item_monthly.csv")
inflation = require_data(PROCESSED / "inflation_by_item.csv")
basket_vs_cpi = optional_data(PROCESSED / "basket_vs_cpi.csv")
gap = require_data(PROCESSED / "urban_rural_gap.csv")
ramadan = require_data(PROCESSED / "ramadan_effect.csv")
kpis = load_json(PROCESSED / "kpi_summary.json", {})
insights = load_json(PROCESSED / "insights.json", [])
source_metadata = load_json(PROCESSED / "source_metadata.json", {})

if source_metadata.get("data_mode") == "demo":
    st.info("This repository ships with a demo snapshot for a fast first run. Run the full pipeline to replace it with real KPDN data.")

states = sorted(basket_cost["state"].dropna().unique().tolist())
default_state = kpis.get("highest_pressure_state")
if default_state not in states and states:
    default_state = states[0]

with st.sidebar:
    st.header("Filters")
    selected_state = st.selectbox("State", states, index=states.index(default_state) if default_state in states else 0)
    districts = sorted(basket_cost.loc[basket_cost["state"] == selected_state, "district"].dropna().unique().tolist())
    default_district = kpis.get("latest_focus_district")
    if default_district not in districts and districts:
        default_district = districts[0]
    selected_district = st.selectbox(
        "District",
        districts,
        index=districts.index(default_district) if default_district in districts else 0,
    )
    selected_month = st.selectbox("Latest month snapshot", sorted(basket_cost["bulan"].unique().tolist()), index=len(basket_cost["bulan"].unique()) - 1)

state_df = basket_cost[basket_cost["state"] == selected_state].copy()
district_df = state_df[state_df["district"] == selected_district].copy()
latest_district = district_df[district_df["bulan"] == selected_month]
income_rm = (
    float(latest_district["household_income_rm"].iloc[0])
    if not latest_district.empty and "household_income_rm" in latest_district
    else float(kpis.get("reference_income_rm", 2100))
)
income_year = (
    int(latest_district["income_reference_year"].iloc[0])
    if not latest_district.empty and "income_reference_year" in latest_district and pd.notna(latest_district["income_reference_year"].iloc[0])
    else kpis.get("reference_income_year")
)
latest_cost = float(latest_district["cost_item"].iloc[0]) if not latest_district.empty else 0.0
latest_burden = float(latest_district["burden_pct"].iloc[0]) if not latest_district.empty else 0.0

district_series = district_df.sort_values("bulan")
change_pct = 0.0
if len(district_series) > 1 and float(district_series["cost_item"].iloc[0]) > 0:
    first_cost = float(district_series["cost_item"].iloc[0])
    last_cost = float(district_series["cost_item"].iloc[-1])
    change_pct = (last_cost - first_cost) / first_cost * 100

col1, col2, col3, col4 = st.columns(4)
col1.metric(f"Kos Bakul {selected_district}", f"RM {latest_cost:,.2f}")
col2.metric("Beban Pendapatan", f"{latest_burden:.2f}%")
col3.metric("Perubahan 12 Bulan", f"{change_pct:.2f}%")
income_label = "Pendapatan Rujukan Negeri"
if income_year:
    income_label = f"Pendapatan Rujukan Negeri ({income_year})"
col4.metric(income_label, f"RM {income_rm:,.0f}")

line_chart = px.line(
    state_df.sort_values("bulan"),
    x="bulan",
    y="cost_item",
    color="district",
    markers=True,
    title=f"Kos Bakul Bulanan di {selected_state}",
)
line_chart.update_layout(template="plotly_white", yaxis_title="RM")
st.plotly_chart(line_chart, use_container_width=True)

left, right = st.columns(2)

with left:
    state_snapshot = (
        basket_cost[basket_cost["bulan"] == selected_month]
        .groupby("state", as_index=False)["burden_pct"]
        .mean()
        .sort_values("burden_pct", ascending=False)
    )
    burden_chart = px.bar(
        state_snapshot,
        x="state",
        y="burden_pct",
        color="state",
        title=f"Beban Gaji Mengikut Negeri ({selected_month})",
    )
    burden_chart.update_layout(template="plotly_white", showlegend=False, yaxis_title="%")
    st.plotly_chart(burden_chart, use_container_width=True)

with right:
    district_items = item_monthly[
        (item_monthly["state"] == selected_state) & (item_monthly["district"] == selected_district)
    ].copy()
    latest_items = district_items[district_items["bulan"] == selected_month].sort_values("cost_item", ascending=False)
    item_chart = px.bar(
        latest_items,
        x="item",
        y="cost_item",
        color="item",
        title=f"Sumbangan Item Kepada Kos Bakul ({selected_district}, {selected_month})",
    )
    item_chart.update_layout(template="plotly_white", showlegend=False, xaxis_title="")
    st.plotly_chart(item_chart, use_container_width=True)

left, right = st.columns(2)

with left:
    inflation_chart = px.line(
        inflation.sort_values("bulan"),
        x="bulan",
        y="price_index",
        color="item",
        markers=True,
        title="Indeks Harga Item Asas",
    )
    inflation_chart.update_layout(template="plotly_white", yaxis_title="Index")
    st.plotly_chart(inflation_chart, use_container_width=True)

with right:
    if basket_vs_cpi.empty or basket_vs_cpi["low_income_cpi_rebased"].isna().all():
        st.warning("CPI Low-Income comparison is not available yet for this snapshot.")
    else:
        comparison_chart = px.line(
            basket_vs_cpi.melt(
                id_vars="bulan",
                value_vars=["basket_index", "low_income_cpi_rebased"],
                var_name="series",
                value_name="index_value",
            ).sort_values("bulan"),
            x="bulan",
            y="index_value",
            color="series",
            markers=True,
            title="Indeks Bakul vs CPI Low-Income",
        )
        comparison_chart.update_layout(template="plotly_white", yaxis_title="Index (Rebase=100)")
        st.plotly_chart(comparison_chart, use_container_width=True)

left, right = st.columns(2)

with left:
    if gap.empty:
        st.warning("Urban-rural gap data is not available yet for this snapshot.")
    else:
        gap_chart = px.bar(
            gap.sort_values("bulan"),
            x="bulan",
            y="avg_cost",
            color="area_type",
            barmode="group",
            title="Jurang Kos Bakul Bandar-Luar Bandar",
        )
        gap_chart.update_layout(template="plotly_white", yaxis_title="RM")
        st.plotly_chart(gap_chart, use_container_width=True)

with right:
    ramadan_chart = px.bar(
        ramadan,
        x="ramadan_flag",
        y="avg_cost",
        color="ramadan_flag",
        title="Purata Kos Bakul Ramadan vs Bukan Ramadan",
    )
    ramadan_chart.update_layout(template="plotly_white", showlegend=False, yaxis_title="RM")
    st.plotly_chart(ramadan_chart, use_container_width=True)

st.subheader("Insight Ringkas")
for insight in insights:
    st.markdown(f"- **{insight['title']}**: {insight['detail']}")

st.subheader("Data Snapshot")
st.dataframe(
    district_df.sort_values("bulan", ascending=False),
    use_container_width=True,
    hide_index=True,
)
