from __future__ import annotations

import html
import json
import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"

MONTH_NAMES = {1: "Jan", 2: "Feb", 3: "Mac", 4: "Apr", 5: "Mei", 6: "Jun", 7: "Jul", 8: "Ogo", 9: "Sep", 10: "Okt", 11: "Nov", 12: "Dis"}
STATE_COLORS = {"Perak": "#17233E", "Sabah": "#22B8C9", "W.P. Kuala Lumpur": "#5D6BFF"}
ITEM_COLORS = ["#17233E", "#22B8C9", "#5D6BFF", "#F97316", "#14B8A6", "#EC4899", "#EAB308", "#0EA5E9", "#7C3AED", "#64748B"]


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


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;700&display=swap');
        :root { --bg:#f7f9fc; --card:rgba(255,255,255,.88); --line:#e5ebf4; --ink:#11203b; --muted:#66748d; --teal:#22b8c9; --navy:#17233e; --shadow:0 22px 55px rgba(23,35,62,.08); }
        html, body, [class*="css"] { font-family:"Manrope", sans-serif; }
        .stApp { background: radial-gradient(circle at top right, rgba(34,184,201,.12), transparent 24rem), radial-gradient(circle at top left, rgba(93,107,255,.10), transparent 22rem), linear-gradient(180deg, #fbfcfe 0%, #f4f7fb 100%); color:var(--ink); }
        [data-testid="stHeader"] { background:rgba(247,249,252,.72); border-bottom:1px solid rgba(229,235,244,.72); backdrop-filter:blur(10px); }
        [data-testid="block-container"] { max-width:1280px; padding-top:1.8rem; padding-bottom:3rem; }
        .topbar { display:flex; justify-content:space-between; gap:1rem; align-items:center; padding:.85rem 1.2rem; border-radius:999px; background:linear-gradient(90deg, #13233f 0%, #1b4a66 62%, #1eb6bb 100%); color:#f8fbff; box-shadow:var(--shadow); margin-bottom:1.2rem; font-size:.92rem; }
        .chip-row { display:flex; flex-wrap:wrap; gap:.55rem; }
        .chip { display:inline-flex; align-items:center; gap:.45rem; padding:.5rem .9rem; border-radius:999px; background:rgba(255,255,255,.88); border:1px solid rgba(255,255,255,.75); color:var(--navy); font-size:.84rem; font-weight:700; }
        .chip::before { content:""; width:.5rem; height:.5rem; border-radius:999px; background:var(--teal); }
        .hero-kicker, .label { font-size:.8rem; text-transform:uppercase; letter-spacing:.16em; color:#7f8da8; font-weight:800; margin-bottom:.35rem; }
        .hero-title { font-family:"Space Grotesk","Manrope",sans-serif; font-size:clamp(2.5rem,5vw,4.25rem); line-height:.95; letter-spacing:-.06em; color:var(--navy); margin:0 0 1rem; }
        .hero-title .accent { color:var(--teal); }
        .hero-copy { font-size:1.08rem; line-height:1.7; color:#44546a; max-width:46rem; margin:0 0 .4rem; }
        .hero-note { color:var(--muted); font-size:.97rem; line-height:1.6; }
        .panel, .metric-card, .state-card, .insight-card, .method-card { background:var(--card); border:1px solid var(--line); border-radius:24px; box-shadow:var(--shadow); }
        .panel { padding:1.15rem 1.2rem; margin-bottom:1rem; }
        .metric-card { padding:1.15rem 1.2rem; min-height:8rem; margin-bottom:.9rem; }
        .metric-eyebrow { font-size:.76rem; text-transform:uppercase; letter-spacing:.15em; color:#7f8da8; font-weight:800; margin-bottom:.55rem; }
        .metric-value, .state-value, .insight-value { font-family:"Space Grotesk","Manrope",sans-serif; font-size:2.15rem; line-height:1; color:var(--navy); font-weight:700; margin-bottom:.45rem; }
        .metric-copy, .state-copy, .section-note, .insight-detail, .method-copy, .snapshot-note { color:var(--muted); font-size:.95rem; line-height:1.55; }
        .section-title { font-family:"Space Grotesk","Manrope",sans-serif; font-size:1.85rem; line-height:1.06; color:var(--navy); margin:0 0 .35rem; }
        .state-card { padding:1.1rem 1.15rem; min-height:11rem; }
        .state-top { display:flex; justify-content:space-between; align-items:center; gap:.75rem; margin-bottom:.9rem; }
        .state-name { display:flex; align-items:center; gap:.7rem; color:var(--navy); font-size:1.12rem; font-weight:800; }
        .state-dot { width:1rem; height:1rem; border-radius:999px; background:var(--navy); }
        .state-chip { padding:.35rem .65rem; border-radius:999px; background:#def8f4; color:#168a90; font-size:.78rem; font-weight:700; }
        .progress { width:100%; height:.45rem; border-radius:999px; background:#edf2f8; overflow:hidden; margin-top:.9rem; }
        .progress-fill { height:100%; border-radius:999px; background:linear-gradient(90deg, #22b8c9 0%, #5d6bff 100%); }
        .mini-note { padding:.7rem .85rem; border-radius:16px; background:rgba(255,255,255,.75); border:1px solid var(--line); color:var(--muted); font-size:.88rem; font-weight:700; min-height:4.1rem; }
        .insight-card, .method-card { padding:1.1rem 1.15rem; min-height:12rem; }
        .insight-title, .method-title { color:var(--navy); font-size:1.1rem; font-weight:800; line-height:1.32; margin-bottom:.7rem; }
        .method-step { color:#8c9bb3; letter-spacing:.16em; text-transform:uppercase; font-size:.76rem; font-weight:800; margin-bottom:.65rem; }
        .method-code { margin-top:.8rem; background:#f5f8fc; border:1px solid var(--line); border-radius:14px; padding:.75rem .85rem; color:#4e5d75; font-size:.84rem; line-height:1.45; }
        .section-break { height:1.35rem; margin:.15rem 0 .5rem; position:relative; }
        .section-break::after { content:""; position:absolute; left:0; right:0; top:50%; height:1px; background:linear-gradient(90deg, rgba(23,35,62,0), rgba(23,35,62,.14), rgba(34,184,201,.14), rgba(23,35,62,0)); }
        .rank-card { padding:.9rem 1rem; border-radius:18px; background:rgba(255,255,255,.8); border:1px solid var(--line); margin-top:.75rem; }
        .rank-top { display:flex; justify-content:space-between; align-items:center; gap:.75rem; margin-bottom:.45rem; }
        .rank-name { color:var(--navy); font-size:1rem; font-weight:800; }
        .rank-badge { padding:.28rem .6rem; border-radius:999px; background:#eef7ff; color:#2d5b87; font-size:.74rem; font-weight:800; }
        .rank-metric { font-family:"Space Grotesk","Manrope",sans-serif; font-size:1.9rem; line-height:1; color:var(--navy); margin-bottom:.35rem; }
        .rank-copy { color:var(--muted); font-size:.88rem; line-height:1.5; }
        .custom-table { width:100%; border-collapse:collapse; margin-top:.2rem; }
        .custom-table thead th { text-align:left; color:#7f8da8; font-size:.78rem; letter-spacing:.08em; text-transform:uppercase; font-weight:800; padding:0 0 .8rem; border-bottom:1px solid var(--line); }
        .custom-table tbody td { padding:.9rem 0; border-bottom:1px solid rgba(229,235,244,.72); color:var(--navy); font-size:.95rem; vertical-align:middle; }
        .item-cell { display:flex; align-items:center; gap:.8rem; }
        .item-pill { width:2rem; height:2rem; border-radius:12px; background:var(--navy); color:#fff; display:inline-flex; align-items:center; justify-content:center; font-size:.76rem; font-weight:800; flex-shrink:0; }
        .item-name { font-weight:700; color:var(--navy); margin-bottom:.12rem; }
        .item-meta { color:var(--muted); font-size:.82rem; }
        .delta { display:inline-flex; align-items:center; justify-content:center; padding:.3rem .65rem; border-radius:999px; font-size:.8rem; font-weight:800; }
        .delta-pos { background:#ecfdf5; color:#0f9d63; } .delta-neg { background:#fff1f3; color:#e11d48; } .delta-neutral { background:#f1f5f9; color:#64748b; }
        div[data-baseweb="select"] > div { border-radius:16px !important; border:1px solid var(--line) !important; min-height:3rem !important; background:rgba(255,255,255,.9) !important; box-shadow:none !important; }
        div[data-testid="stPopover"] > div > button { width:100%; min-height:3.25rem; border-radius:18px; border:1px solid var(--line); background:rgba(255,255,255,.9); color:var(--navy); font-weight:700; font-size:1rem; justify-content:space-between; padding:.35rem 1rem; box-shadow:none; }
        div[data-testid="stPopover"] > div > button:hover { border-color:#cfd9e8; background:#ffffff; color:var(--navy); }
        div[data-testid="stPopover"] > div > button:focus { box-shadow:0 0 0 1px rgba(34,184,201,.28); border-color:rgba(34,184,201,.55); }
        div[data-testid="stPopover"] div[role="dialog"] { border-radius:18px; border:1px solid var(--line); background:rgba(255,255,255,.98); box-shadow:var(--shadow); }
        div[data-testid="stPopover"] div[role="dialog"] [role="radiogroup"] { gap:.3rem; }
        [data-testid="stExpander"] details { border-radius:20px; border:1px solid var(--line); background:rgba(255,255,255,.78); }
        [data-testid="stExpander"] summary { font-weight:800; color:var(--navy); }
        div[data-testid="stDataFrame"] { border:1px solid var(--line); border-radius:18px; overflow:hidden; background:rgba(255,255,255,.78); }
        </style>
        """,
        unsafe_allow_html=True,
    )


def format_month_label(month_value: str) -> str:
    period = pd.Period(month_value, freq="M")
    return f"{MONTH_NAMES[period.month]} {period.year}"


def format_money(value: float) -> str:
    return f"RM{value:,.2f}"


def item_abbreviation(name: str) -> str:
    letters = [part[0] for part in re.findall(r"[A-Za-z]+", name)]
    return ("".join(letters[:2]) or "IT").upper()


def extract_highlight(detail: str) -> str:
    for pattern in (r"RM\d+(?:\.\d+)?", r"-?\d+(?:\.\d+)?%", r"-?\d+(?:\.\d+)?\s*mata", r"\d+\s*minggu", r"\d+\.\d+"):
        match = re.search(pattern, detail)
        if match:
            return match.group(0)
    return "Insight"


def style_figure(fig, yaxis_title: str = "", legend_title: str = "", height: int = 420):
    fig.update_layout(
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Manrope, sans-serif", "color": "#24324a"},
        margin={"l": 8, "r": 8, "t": 56, "b": 8},
        legend={"orientation": "h", "yanchor": "bottom", "y": 1.02, "xanchor": "left", "x": 0, "title": {"text": legend_title}},
        height=height,
        title={"font": {"family": "Space Grotesk, Manrope, sans-serif", "size": 23, "color": "#17233e"}},
    )
    fig.update_xaxes(showgrid=False, tickfont={"color": "#69788f"})
    fig.update_yaxes(showgrid=True, gridcolor="#e8eef6", zeroline=False, tickfont={"color": "#69788f"}, title=yaxis_title)
    return fig


def weighted_average(series: pd.Series, weights: pd.Series) -> float:
    valid = series.notna() & weights.notna()
    if not valid.any():
        return float("nan")
    weight_values = weights[valid].astype(float)
    if float(weight_values.sum()) <= 0:
        return float(series[valid].astype(float).mean())
    return float((series[valid].astype(float) * weight_values).sum() / weight_values.sum())


def aggregate_district_costs(frame: pd.DataFrame, keys: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=keys + ["cost_item", "burden_pct", "household_income_rm", "item_count", "total_observation", "income_reference_year"])

    rows: list[dict[str, object]] = []
    for group_key, group in frame.groupby(keys, dropna=False):
        if not isinstance(group_key, tuple):
            group_key = (group_key,)
        key_payload = dict(zip(keys, group_key))
        weights = group["total_observation"].fillna(1).clip(lower=1)
        rows.append(
            {
                **key_payload,
                "cost_item": weighted_average(group["cost_item"], weights),
                "burden_pct": weighted_average(group["burden_pct"], weights),
                "household_income_rm": weighted_average(group["household_income_rm"], weights),
                "item_count": int(group["item_count"].max()) if "item_count" in group else 0,
                "total_observation": int(group["total_observation"].sum()) if "total_observation" in group else 0,
                "income_reference_year": int(group["income_reference_year"].dropna().max()) if "income_reference_year" in group and group["income_reference_year"].notna().any() else None,
            }
        )
    return pd.DataFrame(rows).sort_values(keys).reset_index(drop=True)


def aggregate_district_items(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=["bulan", "item", "harga_purata", "harga_median", "sampel_harga", "qty", "cost_item"])

    rows: list[dict[str, object]] = []
    for (bulan, item), group in frame.groupby(["bulan", "item"], dropna=False):
        weights = group["sampel_harga"].fillna(1).clip(lower=1)
        qty_value = float(group["qty"].dropna().iloc[0]) if group["qty"].notna().any() else 0.0
        avg_price = weighted_average(group["harga_purata"], weights)
        median_price = weighted_average(group["harga_median"], weights)
        rows.append(
            {
                "bulan": bulan,
                "item": item,
                "harga_purata": avg_price,
                "harga_median": median_price,
                "sampel_harga": int(group["sampel_harga"].sum()),
                "qty": qty_value,
                "cost_item": avg_price * qty_value if pd.notna(avg_price) else float("nan"),
            }
        )
    return pd.DataFrame(rows).sort_values(["bulan", "item"]).reset_index(drop=True)


def build_item_snapshot(district_items: pd.DataFrame, selected_month: str, latest_cost: float) -> pd.DataFrame:
    current = district_items[district_items["bulan"] == selected_month].copy()
    prior_month = str(pd.Period(selected_month, freq="M") - 12)
    prior = district_items[district_items["bulan"] == prior_month][["item", "harga_purata"]].rename(columns={"harga_purata": "harga_lalu"})
    current = current.merge(prior, on="item", how="left")
    current["yoy_pct"] = (current["harga_purata"] - current["harga_lalu"]) / current["harga_lalu"] * 100
    current["share_pct"] = current["cost_item"] / latest_cost * 100 if latest_cost > 0 else 0.0
    return current.sort_values("cost_item", ascending=False).reset_index(drop=True)


def format_delta(value: float) -> str:
    if pd.isna(value):
        return "Tiada YoY"
    sign = "+" if float(value) > 0 else ""
    return f"{sign}{float(value):.1f}%"


def build_item_display_table(item_snapshot: pd.DataFrame) -> pd.DataFrame:
    if item_snapshot.empty:
        return pd.DataFrame(columns=["Item", "Harga Purata", "Kos Basket", "Perubahan YoY", "Share", "Qty Basket", "Sampel Harga"])

    display = item_snapshot.copy()
    display["Harga Purata"] = display["harga_purata"].apply(lambda value: format_money(float(value)) if pd.notna(value) else "-")
    display["Kos Basket"] = display["cost_item"].apply(lambda value: format_money(float(value)) if pd.notna(value) else "-")
    display["Perubahan YoY"] = display["yoy_pct"].apply(format_delta)
    display["Share"] = display["share_pct"].apply(lambda value: f"{float(value):.1f}%" if pd.notna(value) else "-")
    display["Qty Basket"] = display["qty"].apply(lambda value: f"{float(value):g}" if pd.notna(value) else "-")
    display["Sampel Harga"] = display["sampel_harga"].fillna(0).astype(int)
    display = display.rename(columns={"item": "Item"})
    return display[["Item", "Harga Purata", "Kos Basket", "Perubahan YoY", "Share", "Qty Basket", "Sampel Harga"]]


def render_section_break() -> None:
    st.markdown('<div class="section-break"></div>', unsafe_allow_html=True)


def render_picker(label: str, options: list[str], state_key: str, format_func=lambda value: value) -> str:
    if not options:
        return ""

    radio_key = f"{state_key}_radio"
    current_value = st.session_state.get(state_key)
    if current_value not in options:
        st.session_state[state_key] = options[0]
    if radio_key in st.session_state and st.session_state[radio_key] not in options:
        del st.session_state[radio_key]

    current_value = st.session_state[state_key]
    st.markdown(f'<div class="label">{html.escape(label)}</div>', unsafe_allow_html=True)
    with st.popover(f"{format_func(current_value)}  v", use_container_width=True):
        choice = st.radio(
            label,
            options,
            index=options.index(current_value),
            format_func=format_func,
            key=radio_key,
            label_visibility="collapsed",
        )
        st.session_state[state_key] = choice
    return st.session_state[state_key]


st.set_page_config(page_title="Bakul B40", page_icon=":bar_chart:", layout="wide", initial_sidebar_state="collapsed")
inject_styles()

basket_cost = require_data(PROCESSED / "basket_cost.csv")
item_monthly = require_data(PROCESSED / "basket_item_monthly.csv")
inflation = require_data(PROCESSED / "inflation_by_item.csv")
basket_vs_cpi = optional_data(PROCESSED / "basket_vs_cpi.csv")
gap = require_data(PROCESSED / "urban_rural_gap.csv")
ramadan = require_data(PROCESSED / "ramadan_effect.csv")
kpis = load_json(PROCESSED / "kpi_summary.json", {})
insights = load_json(PROCESSED / "insights.json", [])

states = sorted(basket_cost["state"].dropna().unique().tolist())
months = sorted(basket_cost["bulan"].dropna().unique().tolist())
configured_item_count = int(item_monthly["item"].nunique())
default_state = kpis.get("latest_focus_state") or kpis.get("highest_pressure_state")
if default_state not in states and states:
    default_state = states[0]

st.markdown(
    f"""
    <div class="topbar">
      <div>Portfolio demo yang dibina untuk memaparkan dashboard data awam dengan rasa yang lebih editorial, lebih kemas, dan lebih mudah difahami.</div>
      <div class="chip-row">
        <span class="chip">Data sebenar PriceCatcher</span>
        <span class="chip">15 item basket</span>
        <span class="chip">Snapshot {html.escape(format_month_label(months[-1]))}</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

hero_left, hero_right = st.columns([1.75, 1.0], gap="large")
with hero_left:
    st.markdown(
        f"""
        <div class="hero-kicker">Dashboard portfolio data awam</div>
        <div class="hero-title">Bakul B40: Analisis Beban Harga<br/>Makanan Asas <span class="accent">{months[0][:4]}-{months[-1][:4]}</span></div>
        <p class="hero-copy">Data sebenar KPDN PriceCatcher digabungkan dengan <b>CPI Low-Income</b> dan <b>state median wage</b> supaya kos basket isi rumah berpendapatan rendah boleh dibaca dengan lebih cepat dan lebih jelas.</p>
        <p class="hero-note">Skop semasa fokus pada <b>Perak</b>, <b>W.P. Kuala Lumpur</b>, dan <b>Sabah</b>. Untuk beras putih, dashboard menggunakan <b>state-specific proxy</b> supaya liputan data lebih stabil.</p>
        <div class="chip-row">
          <span class="chip">2022-01 hingga 2026-03</span>
          <span class="chip">3 negeri fokus</span>
          <span class="chip">Wage-referenced burden</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
with hero_right:
    for eyebrow, value, copy in [
        (f"Kos basket {kpis.get('latest_focus_district', 'district')} {format_month_label(kpis.get('latest_month', months[-1]))}".upper(), format_money(float(kpis.get("latest_focus_cost_rm", 0.0))), "Berdasarkan basket semasa dan output processed terkini."),
        ("Beban pendapatan".upper(), f"{float(kpis.get('latest_focus_burden_pct', 0.0)):.2f}%", f"Bahagian basket terhadap income reference RM{float(kpis.get('reference_income_rm', 0.0)):,.0f}."),
        (f"Pendapatan rujukan ({kpis.get('reference_income_year', 'N/A')})".upper(), f"RM{float(kpis.get('reference_income_rm', 0.0)):,.0f}", "State median wage digunakan untuk kira burden_pct."),
    ]:
        st.markdown(f'<div class="metric-card"><div class="metric-eyebrow">{html.escape(eyebrow)}</div><div class="metric-value">{html.escape(value)}</div><div class="metric-copy">{html.escape(copy)}</div></div>', unsafe_allow_html=True)

filter_cols = st.columns([1.0, 1.15, 1.0, 1.15], gap="small")
with filter_cols[0]:
    if "selected_state" not in st.session_state and default_state in states:
        st.session_state["selected_state"] = default_state
    selected_state = render_picker("State", states, "selected_state")
with filter_cols[1]:
    districts = sorted(basket_cost.loc[basket_cost["state"] == selected_state, "district"].dropna().unique().tolist())
    default_district = kpis.get("latest_focus_district")
    if "selected_district" not in st.session_state and default_district in districts:
        st.session_state["selected_district"] = default_district
    selected_district = render_picker("District", districts, "selected_district")
with filter_cols[2]:
    if "selected_month" not in st.session_state and months:
        st.session_state["selected_month"] = months[-1]
    selected_month = render_picker("Month snapshot", months, "selected_month", format_month_label)

state_df = basket_cost[basket_cost["state"] == selected_state].copy()
state_district_df = aggregate_district_costs(state_df, ["bulan", "district"])
district_df = state_df[state_df["district"] == selected_district].copy()
district_monthly_df = aggregate_district_costs(district_df, ["bulan"])
latest_district = district_monthly_df[district_monthly_df["bulan"] == selected_month]
latest_cost = float(latest_district["cost_item"].iloc[0]) if not latest_district.empty else 0.0
latest_burden = float(latest_district["burden_pct"].iloc[0]) if not latest_district.empty else 0.0
income_rm = float(latest_district["household_income_rm"].iloc[0]) if not latest_district.empty else float(kpis.get("reference_income_rm", 0.0))
snapshot_item_count = int(latest_district["item_count"].iloc[0]) if not latest_district.empty else 0
snapshot_obs = int(latest_district["total_observation"].iloc[0]) if not latest_district.empty else 0
with filter_cols[3]:
    st.markdown('<div class="label">Snapshot note</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="mini-note"><b>{snapshot_item_count}/{configured_item_count} item</b> muncul untuk snapshot ini.<br/>Jumlah observation: <b>{snapshot_obs:,}</b></div>', unsafe_allow_html=True)

district_series = district_monthly_df.sort_values("bulan")
change_pct = 0.0
if len(district_series) > 1 and float(district_series["cost_item"].iloc[0]) > 0:
    change_pct = (float(district_series["cost_item"].iloc[-1]) - float(district_series["cost_item"].iloc[0])) / float(district_series["cost_item"].iloc[0]) * 100

selected_snapshot = basket_cost[basket_cost["bulan"] == selected_month].copy()
selected_snapshot_district = aggregate_district_costs(selected_snapshot, ["state", "district"])
state_burden_summary = (
    selected_snapshot_district.groupby("state", as_index=False)
    .agg(
        avg_burden=("burden_pct", "mean"),
        avg_cost=("cost_item", "mean"),
        avg_income=("household_income_rm", "mean"),
        income_reference_year=("income_reference_year", "max"),
    )
    .sort_values("avg_burden", ascending=False)
)

state_cards = []
max_burden = float(state_burden_summary["avg_burden"].max()) if not state_burden_summary.empty else 1.0
hotspot_map: dict[str, dict[str, object]] = {}
for state_name, group in selected_snapshot_district.groupby("state", dropna=False):
    hotspot = group.sort_values("burden_pct", ascending=False).iloc[0]
    hotspot_map[str(state_name)] = {
        "district": str(hotspot["district"]),
        "burden_pct": float(hotspot["burden_pct"]),
    }

for state in states:
    subset = state_burden_summary[state_burden_summary["state"] == state]
    if subset.empty:
        continue
    summary = subset.iloc[0]
    hotspot = hotspot_map.get(state, {"district": state, "burden_pct": float(summary["avg_burden"])})
    avg_burden = float(summary["avg_burden"])
    avg_cost = float(summary["avg_cost"])
    progress = 0 if max_burden <= 0 else avg_burden / max_burden * 100
    state_cards.append((state, str(hotspot["district"]), avg_burden, avg_cost, progress))

st.markdown('<div class="panel"><div class="hero-kicker">Perbandingan negeri</div><div class="section-title">Peta beban mengikut negeri terpilih</div><div class="section-note">Cards ini ringkaskan tekanan kos semasa untuk setiap negeri fokus. Chip kecil menunjukkan district dengan burden tertinggi untuk snapshot bulan semasa.</div></div>', unsafe_allow_html=True)
for column, card in zip(st.columns(len(state_cards), gap="medium"), state_cards):
    state, hotspot, avg_burden, avg_cost, progress = card
    with column:
        st.markdown(f'<div class="state-card"><div class="state-top"><div class="state-name"><span class="state-dot" style="background:{STATE_COLORS.get(state, "#17233E")};"></span>{html.escape(state)}</div><div class="state-chip">{html.escape(hotspot)}</div></div><div class="state-value">{avg_burden:.1f}%</div><div class="state-copy">Purata burden pada {html.escape(format_month_label(selected_month))}. Purata basket cost negeri ini sekitar <b>{format_money(avg_cost)}</b>.</div><div class="progress"><div class="progress-fill" style="width:{progress:.1f}%"></div></div></div>', unsafe_allow_html=True)
render_section_break()

st.markdown('<div class="panel"><div class="hero-kicker">Trend utama</div><div class="section-title">Kos basket bulanan mengikut negeri pilihan</div><div class="section-note">Saya tukar chart ini kepada <b>selected district vs state context</b>. Ribbon lembut menunjukkan julat tengah district dalam negeri itu, garis putus-putus menunjukkan purata negeri, dan garis tebal menunjukkan district yang sedang dipilih.</div></div>', unsafe_allow_html=True)
state_trend = (
    state_district_df.groupby("bulan", as_index=False)
    .agg(
        state_avg=("cost_item", "mean"),
        lower_band=("cost_item", lambda s: s.quantile(0.25)),
        upper_band=("cost_item", lambda s: s.quantile(0.75)),
        state_min=("cost_item", "min"),
        state_max=("cost_item", "max"),
    )
    .sort_values("bulan")
)
district_trend = district_monthly_df.sort_values("bulan")

trend_chart = go.Figure()
trend_chart.add_trace(
    go.Scatter(
        x=state_trend["bulan"],
        y=state_trend["upper_band"],
        mode="lines",
        line={"width": 0},
        name="Julat tengah district",
        hoverinfo="skip",
        showlegend=False,
    )
)
trend_chart.add_trace(
    go.Scatter(
        x=state_trend["bulan"],
        y=state_trend["lower_band"],
        mode="lines",
        fill="tonexty",
        fillcolor="rgba(34, 184, 201, 0.16)",
        line={"width": 0},
        name="Julat tengah district",
        hovertemplate="Julat tengah: RM %{y:.2f}<extra></extra>",
    )
)
trend_chart.add_trace(
    go.Scatter(
        x=state_trend["bulan"],
        y=state_trend["state_avg"],
        mode="lines+markers",
        name=f"Purata {selected_state}",
        line={"color": "#7A889F", "width": 2.4, "dash": "dash"},
        marker={"size": 5},
        hovertemplate="Purata negeri: RM %{y:.2f}<extra></extra>",
    )
)
trend_chart.add_trace(
    go.Scatter(
        x=district_trend["bulan"],
        y=district_trend["cost_item"],
        mode="lines+markers",
        name=selected_district,
        line={"color": "#17233E", "width": 4},
        marker={"size": 7, "color": "#22B8C9", "line": {"color": "#17233E", "width": 1.5}},
        hovertemplate=f"{selected_district}: RM %{{y:.2f}}<extra></extra>",
    )
)
trend_chart = style_figure(trend_chart, yaxis_title="RM", legend_title="", height=470)
trend_chart.update_layout(margin={"l": 8, "r": 8, "t": 24, "b": 8})
st.plotly_chart(trend_chart, use_container_width=True, config={"displayModeBar": False})

for column, note in zip(
    st.columns(3, gap="medium"),
    [
        f"<b>{html.escape(selected_district)}</b> mencatat {format_money(latest_cost)} pada {html.escape(format_month_label(selected_month))}, bersamaan <b>{latest_burden:.2f}%</b> daripada income reference <b>RM{income_rm:,.0f}</b>.",
        f"Perubahan siri semasa ialah <b>{change_pct:+.2f}%</b> sejak awal tempoh analisis untuk district ini.",
        f"Snapshot semasa menggunakan <b>{snapshot_item_count}</b> item tersedia dengan <b>{snapshot_obs:,}</b> observation harga.",
    ],
):
    with column:
        st.markdown(f'<div class="mini-note">{note}</div>', unsafe_allow_html=True)
render_section_break()

district_items = item_monthly[(item_monthly["state"] == selected_state) & (item_monthly["district"] == selected_district)].copy()
district_items = aggregate_district_items(district_items)
item_snapshot = build_item_snapshot(district_items, selected_month, latest_cost)
left, right = st.columns([1.22, 1.0], gap="medium")
with left:
    st.markdown(
        f'<div class="panel"><div class="hero-kicker">Komposisi basket</div><div class="section-title">Item terkini untuk {html.escape(selected_district)}</div><div class="section-note">{len(item_snapshot)}/{configured_item_count} item tersedia untuk snapshot {html.escape(format_month_label(selected_month))}. Saya tukar section ini kepada <b>composition chart + audit table</b> supaya item driver lebih cepat dibaca dan detail YoY masih boleh disemak tanpa HTML custom yang rapuh.</div></div>',
        unsafe_allow_html=True,
    )
    if item_snapshot.empty:
        st.info("Tiada item snapshot untuk pilihan ini.")
    else:
        composition_data = item_snapshot.copy().reset_index(drop=True)
        composition_data["rank"] = composition_data.index
        composition_data["yoy_label"] = composition_data["yoy_pct"].apply(format_delta)
        composition_data["label"] = composition_data["cost_item"].apply(lambda value: format_money(float(value)))
        composition_data["bar_color"] = composition_data["rank"].map(
            lambda rank: "#17233E" if rank == 0 else "#2F5B84" if rank == 1 else "#22B8C9" if rank == 2 else "#D7F3F6"
        )
        composition_chart_data = composition_data.sort_values("cost_item", ascending=True)

        composition_chart = go.Figure(
            go.Bar(
                x=composition_chart_data["cost_item"],
                y=composition_chart_data["item"],
                orientation="h",
                marker={
                    "color": composition_chart_data["bar_color"],
                    "line": {"color": "rgba(23,35,62,0.12)", "width": 1},
                },
                text=composition_chart_data["label"],
                textposition="outside",
                cliponaxis=False,
                customdata=composition_chart_data[["share_pct", "harga_purata", "yoy_label", "qty", "sampel_harga"]],
                hovertemplate="<b>%{y}</b><br>Kos Basket: RM %{x:.2f}<br>Share: %{customdata[0]:.1f}%<br>Harga Purata: RM %{customdata[1]:.2f}<br>Perubahan YoY: %{customdata[2]}<br>Qty Basket: %{customdata[3]:g}<br>Sampel Harga: %{customdata[4]}<extra></extra>",
            )
        )
        composition_chart = style_figure(composition_chart, yaxis_title="", height=max(360, 28 * len(composition_chart_data) + 120))
        composition_chart.update_layout(showlegend=False, margin={"l": 8, "r": 28, "t": 24, "b": 8})
        composition_chart.update_xaxes(title="Kos Basket (RM)", automargin=True)
        composition_chart.update_yaxes(categoryorder="array", categoryarray=composition_chart_data["item"].tolist(), automargin=True)
        st.plotly_chart(composition_chart, use_container_width=True, config={"displayModeBar": False})

        item_display = build_item_display_table(item_snapshot)
        st.dataframe(
            item_display,
            use_container_width=True,
            hide_index=True,
            height=min(520, 42 + len(item_display) * 36),
        )
with right:
    st.markdown(
        f'<div class="panel"><div class="hero-kicker">Beban gaji</div><div class="section-title">Ranking negeri untuk snapshot semasa</div><div class="section-note">Saya ubah layout ini daripada <b>vertical bar chart biasa</b> kepada <b>ranked horizontal view</b> dengan summary cards supaya audience boleh terus nampak negeri mana paling tertekan, berapa purata basket cost, dan district hotspot untuk bulan semasa.</div></div>',
        unsafe_allow_html=True,
    )
    burden_chart = go.Figure(
        go.Bar(
            x=state_burden_summary["avg_burden"],
            y=state_burden_summary["state"],
            orientation="h",
            marker={
                "color": [STATE_COLORS.get(state, "#17233E") for state in state_burden_summary["state"]],
                "line": {"color": "rgba(23,35,62,0.14)", "width": 1},
            },
            text=state_burden_summary["avg_burden"].map(lambda value: f"{float(value):.2f}%"),
            textposition="outside",
            cliponaxis=False,
            customdata=state_burden_summary[["avg_cost", "avg_income", "income_reference_year"]],
            hovertemplate="<b>%{y}</b><br>Purata burden: %{x:.2f}%<br>Purata basket cost: RM %{customdata[0]:.2f}<br>Income reference: RM %{customdata[1]:.0f} (%{customdata[2]})<extra></extra>",
        )
    )
    burden_chart = style_figure(burden_chart, yaxis_title="", height=360)
    burden_chart.update_layout(showlegend=False, margin={"l": 8, "r": 32, "t": 24, "b": 8})
    burden_chart.update_xaxes(title="Purata Beban Pendapatan (%)", automargin=True)
    burden_chart.update_yaxes(categoryorder="array", categoryarray=state_burden_summary["state"].tolist()[::-1], automargin=True)
    st.plotly_chart(burden_chart, use_container_width=True, config={"displayModeBar": False})
    for row in state_burden_summary.itertuples():
        hotspot = hotspot_map.get(str(row.state), {"district": "-", "burden_pct": float(row.avg_burden)})
        st.markdown(
            f'<div class="rank-card"><div class="rank-top"><div class="rank-name">{html.escape(str(row.state))}</div><div class="rank-badge">Hotspot: {html.escape(str(hotspot["district"]))}</div></div><div class="rank-metric">{float(row.avg_burden):.2f}%</div><div class="rank-copy">Purata basket cost sekitar <b>{format_money(float(row.avg_cost))}</b> dengan income reference <b>RM{float(row.avg_income):,.0f}</b> ({int(row.income_reference_year) if pd.notna(row.income_reference_year) else "N/A"}). District paling berat untuk snapshot ini mencatat <b>{float(hotspot["burden_pct"]):.2f}%</b>.</div></div>',
            unsafe_allow_html=True,
        )
render_section_break()

left, right = st.columns(2, gap="medium")
with left:
    st.markdown(
        '<div class="panel"><div class="hero-kicker">Pergerakan harga</div><div class="section-title">Peta haba harga item asas</div><div class="section-note">Daripada memaksa audience baca 15 garis serentak, saya tukar chart ini kepada <b>heatmap</b> supaya item mana yang semakin panas atau semakin murah boleh ditangkap lebih cepat sepanjang tempoh analisis.</div></div>',
        unsafe_allow_html=True,
    )
    latest_item_index = inflation.sort_values("bulan").groupby("item", as_index=False).tail(1)[["item", "price_index"]].rename(columns={"price_index": "latest_index"})
    heatmap_frame = inflation.merge(latest_item_index, on="item", how="left")
    item_order = heatmap_frame.sort_values(["latest_index", "item"], ascending=[False, True])["item"].drop_duplicates().tolist()
    heatmap_matrix = (
        heatmap_frame.assign(item=pd.Categorical(heatmap_frame["item"], categories=item_order, ordered=True))
        .pivot(index="item", columns="bulan", values="price_index")
        .reindex(item_order)
    )
    inflation_chart = go.Figure(
        go.Heatmap(
            z=heatmap_matrix.values,
            x=heatmap_matrix.columns.tolist(),
            y=heatmap_matrix.index.tolist(),
            colorscale=[[0.0, "#e7f7fb"], [0.45, "#8ad9e4"], [0.7, "#5d6bff"], [1.0, "#17233E"]],
            colorbar={"title": "Index"},
            hovertemplate="<b>%{y}</b><br>Bulan: %{x}<br>Price index: %{z:.1f}<extra></extra>",
        )
    )
    inflation_chart = style_figure(inflation_chart, yaxis_title="", legend_title="", height=460)
    inflation_chart.update_layout(margin={"l": 8, "r": 8, "t": 24, "b": 8})
    inflation_chart.update_xaxes(title="")
    inflation_chart.update_yaxes(title="")
    st.plotly_chart(inflation_chart, use_container_width=True, config={"displayModeBar": False})
with right:
    st.markdown(
        '<div class="panel"><div class="hero-kicker">Benchmark</div><div class="section-title">Indeks basket vs CPI Low-Income</div><div class="section-note">Section ini dikekalkan sebagai dua siri utama sahaja supaya beza arah pergerakan basket berbanding CPI benchmark masih mudah dibaca.</div></div>',
        unsafe_allow_html=True,
    )
    if basket_vs_cpi.empty or basket_vs_cpi["low_income_cpi_rebased"].isna().all():
        st.warning("CPI Low-Income comparison is not available yet for this snapshot.")
    else:
        comparison_chart = px.line(basket_vs_cpi.melt(id_vars="bulan", value_vars=["basket_index", "low_income_cpi_rebased"], var_name="series", value_name="index_value").sort_values("bulan"), x="bulan", y="index_value", color="series", markers=True, title="", color_discrete_map={"basket_index": "#17233E", "low_income_cpi_rebased": "#22B8C9"})
        comparison_chart = style_figure(comparison_chart, yaxis_title="Index (Rebase=100)", legend_title="Series", height=420)
        comparison_chart.for_each_trace(lambda trace: trace.update(name="Basket Index" if trace.name == "basket_index" else "CPI Low-Income"))
        comparison_chart.update_layout(margin={"l": 8, "r": 8, "t": 24, "b": 8})
        st.plotly_chart(comparison_chart, use_container_width=True, config={"displayModeBar": False})
render_section_break()

left, right = st.columns(2, gap="medium")
with left:
    st.markdown(
        '<div class="panel"><div class="hero-kicker">Spatial context</div><div class="section-title">Jurang kos basket bandar-luar bandar</div><div class="section-note">Grouped bars dikekalkan di sini kerana cuma dua kategori utama dan pattern perbezaannya masih jelas tanpa menambah noise.</div></div>',
        unsafe_allow_html=True,
    )
    gap_chart = px.bar(gap.sort_values("bulan"), x="bulan", y="avg_cost", color="area_type", barmode="group", title="", color_discrete_map={"Urban": "#17233E", "Rural": "#22B8C9", "Unknown": "#CBD5E1"})
    gap_chart = style_figure(gap_chart, yaxis_title="RM", legend_title="Area type", height=400)
    gap_chart.update_layout(margin={"l": 8, "r": 8, "t": 24, "b": 8})
    st.plotly_chart(gap_chart, use_container_width=True, config={"displayModeBar": False})
with right:
    st.markdown(
        '<div class="panel"><div class="hero-kicker">Seasonal lens</div><div class="section-title">Purata kos basket Ramadan vs bukan Ramadan</div><div class="section-note">Layout ini sengaja dibiarkan ringkas supaya seasonal difference boleh terus dibandingkan tanpa banyak gangguan visual.</div></div>',
        unsafe_allow_html=True,
    )
    ramadan_chart = px.bar(ramadan, x="ramadan_flag", y="avg_cost", color="ramadan_flag", title="", color_discrete_map={"Ramadan": "#22B8C9", "Non-Ramadan": "#17233E"})
    ramadan_chart = style_figure(ramadan_chart, yaxis_title="RM", height=400)
    ramadan_chart.update_layout(showlegend=False)
    ramadan_chart.update_layout(margin={"l": 8, "r": 8, "t": 24, "b": 8})
    st.plotly_chart(ramadan_chart, use_container_width=True, config={"displayModeBar": False})
render_section_break()

st.markdown('<div class="panel"><div class="hero-kicker">Insight utama</div><div class="section-title">Ringkasan cepat untuk pembentangan</div><div class="section-note">Cards ini cuba bawa rasa reference video tadi: cepat dibaca, ada hierarchy yang jelas, dan tak terus lempar pengguna ke lautan chart.</div></div>', unsafe_allow_html=True)
featured = insights[:3]
for column, insight in zip(st.columns(max(len(featured), 1), gap="medium"), featured):
    with column:
        st.markdown(f'<div class="insight-card"><div class="insight-title">{html.escape(str(insight.get("title", "Insight")))}</div><div class="insight-value">{html.escape(extract_highlight(str(insight.get("detail", ""))))}</div><div class="insight-detail">{html.escape(str(insight.get("detail", "")))}</div></div>', unsafe_allow_html=True)
if len(insights) > 3:
    with st.expander("Lihat insight tambahan"):
        for insight in insights[3:]:
            st.markdown(f"- **{insight['title']}**: {insight['detail']}")
render_section_break()

st.markdown('<div class="panel"><div class="hero-kicker">Metodologi ringkas</div><div class="section-title">Bagaimana dashboard ini dibina</div><div class="section-note">Reference yang you bagi ada satu blok metodologi yang memang membantu. Saya ikut idea itu, tapi disesuaikan dengan pipeline sebenar project ini.</div></div>', unsafe_allow_html=True)
method_cards = [
    ("Langkah 1", "Ambil raw data rasmi", "Muat turun PriceCatcher bulanan, lookup item, lookup premise, CPI Low-Income, dan sumber wages rasmi untuk julat analisis penuh.", "pricecatcher_YYYY-MM.parquet + cpi_2d_lowincome.parquet"),
    ("Langkah 2", "Gabung dengan lookup dan tapis skop", "Padankan kod item dan premise, kemudian tapis kepada 3 negeri fokus dan 15 item basket yang relevan.", "Perak + W.P. Kuala Lumpur + Sabah"),
    ("Langkah 3", "Bina basket dan burden metrics", "Kira harga purata bulanan setiap item, jumlahkan cost_item menjadi basket cost, kemudian bandingkan dengan state median wage.", "burden_pct = kos_bakul / household_income_rm * 100"),
    ("Langkah 4", "Terbitkan dashboard dan report", "Simpan outputs ke data/processed, visualkan dalam Streamlit, dan jana PDF supaya hasil analisis boleh dibentang atau diserahkan.", "dashboard/app.py + report/Bakul_B40_2026.pdf"),
]
for column, card in zip(st.columns(4, gap="medium"), method_cards):
    step, title, copy, code = card
    with column:
        st.markdown(f'<div class="method-card"><div class="method-step">{html.escape(step)}</div><div class="method-title">{html.escape(title)}</div><div class="method-copy">{html.escape(copy)}</div><div class="method-code">{html.escape(code)}</div></div>', unsafe_allow_html=True)

with st.expander("Lihat data snapshot dan audit rows"):
    st.markdown(f'<div class="snapshot-note">Table ini memudahkan semakan manual untuk <b>{html.escape(selected_district)}</b>, supaya nombor dalam KPI cards boleh diaudit balik ke processed outputs.</div>', unsafe_allow_html=True)
    st.dataframe(district_df.sort_values("bulan", ascending=False), use_container_width=True, hide_index=True)
