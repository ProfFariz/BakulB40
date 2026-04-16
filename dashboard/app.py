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
        [data-testid="stExpander"] details { border-radius:20px; border:1px solid var(--line); background:rgba(255,255,255,.78); }
        [data-testid="stExpander"] summary { font-weight:800; color:var(--navy); }
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


def build_item_table_html(item_snapshot: pd.DataFrame) -> str:
    rows = []
    for row in item_snapshot.itertuples():
        yoy = getattr(row, "yoy_pct")
        if pd.isna(yoy):
            delta_class, delta_text = "delta-neutral", "Tiada YoY"
        elif float(yoy) >= 0:
            delta_class, delta_text = "delta-pos", f"+{float(yoy):.1f}%"
        else:
            delta_class, delta_text = "delta-neg", f"{float(yoy):.1f}%"
        rows.append(
            f"""
            <tr>
              <td><div class="item-cell"><span class="item-pill">{html.escape(item_abbreviation(str(row.item)))}</span><div><div class="item-name">{html.escape(str(row.item))}</div><div class="item-meta">{float(row.qty):.0f} unit basket | {int(row.sampel_harga)} sampel harga</div></div></div></td>
              <td>{format_money(float(row.harga_purata))}</td>
              <td>{format_money(float(row.cost_item))}</td>
              <td><span class="delta {delta_class}">{html.escape(delta_text)}</span></td>
              <td>{float(row.share_pct):.1f}%</td>
            </tr>
            """
        )
    if not rows:
        rows.append('<tr><td colspan="5"><div class="snapshot-note">Tiada item snapshot untuk pilihan ini.</div></td></tr>')
    return f'<table class="custom-table"><thead><tr><th>Item</th><th>Harga Purata</th><th>Kos Basket</th><th>Perubahan YoY</th><th>Share</th></tr></thead><tbody>{"".join(rows)}</tbody></table>'


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
    st.markdown('<div class="label">State</div>', unsafe_allow_html=True)
    selected_state = st.selectbox("State", states, index=states.index(default_state) if default_state in states else 0, label_visibility="collapsed")
with filter_cols[1]:
    districts = sorted(basket_cost.loc[basket_cost["state"] == selected_state, "district"].dropna().unique().tolist())
    default_district = kpis.get("latest_focus_district")
    if default_district not in districts and districts:
        default_district = districts[0]
    st.markdown('<div class="label">District</div>', unsafe_allow_html=True)
    selected_district = st.selectbox("District", districts, index=districts.index(default_district) if default_district in districts else 0, label_visibility="collapsed")
with filter_cols[2]:
    st.markdown('<div class="label">Month snapshot</div>', unsafe_allow_html=True)
    selected_month = st.selectbox("Month snapshot", months, index=len(months) - 1, label_visibility="collapsed")

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
state_cards = []
max_burden = float(selected_snapshot.groupby("state")["burden_pct"].mean().max()) if not selected_snapshot.empty else 1.0
for state in states:
    subset = selected_snapshot[selected_snapshot["state"] == state]
    if subset.empty:
        continue
    hotspot = subset.sort_values("burden_pct", ascending=False).iloc[0]
    avg_burden = float(subset["burden_pct"].mean())
    avg_cost = float(subset["cost_item"].mean())
    progress = 0 if max_burden <= 0 else avg_burden / max_burden * 100
    state_cards.append((state, str(hotspot["district"]), avg_burden, avg_cost, progress))

st.markdown('<div class="panel"><div class="hero-kicker">Perbandingan negeri</div><div class="section-title">Peta beban mengikut negeri terpilih</div><div class="section-note">Cards ini ringkaskan tekanan kos semasa untuk setiap negeri fokus. Chip kecil menunjukkan district dengan burden tertinggi untuk snapshot bulan semasa.</div></div>', unsafe_allow_html=True)
for column, card in zip(st.columns(len(state_cards), gap="medium"), state_cards):
    state, hotspot, avg_burden, avg_cost, progress = card
    with column:
        st.markdown(f'<div class="state-card"><div class="state-top"><div class="state-name"><span class="state-dot" style="background:{STATE_COLORS.get(state, "#17233E")};"></span>{html.escape(state)}</div><div class="state-chip">{html.escape(hotspot)}</div></div><div class="state-value">{avg_burden:.1f}%</div><div class="state-copy">Purata burden pada {html.escape(format_month_label(selected_month))}. Purata basket cost negeri ini sekitar <b>{format_money(avg_cost)}</b>.</div><div class="progress"><div class="progress-fill" style="width:{progress:.1f}%"></div></div></div>', unsafe_allow_html=True)

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

district_items = item_monthly[(item_monthly["state"] == selected_state) & (item_monthly["district"] == selected_district)].copy()
district_items = aggregate_district_items(district_items)
item_snapshot = build_item_snapshot(district_items, selected_month, latest_cost)
left, right = st.columns([1.22, 1.0], gap="medium")
with left:
    st.markdown(f'<div class="panel"><div class="hero-kicker">Komposisi basket</div><div class="section-title">Item terkini untuk {html.escape(selected_district)}</div><div class="section-note">{len(item_snapshot)}/{configured_item_count} item tersedia untuk snapshot {html.escape(format_month_label(selected_month))}. Kolum Perubahan YoY membandingkan harga purata item dengan bulan sama tahun sebelumnya apabila data tersedia.</div>{build_item_table_html(item_snapshot)}</div>', unsafe_allow_html=True)
with right:
    state_snapshot = selected_snapshot.groupby("state", as_index=False)["burden_pct"].mean().sort_values("burden_pct", ascending=False)
    burden_chart = px.bar(state_snapshot, x="state", y="burden_pct", color="state", title=f"Beban gaji mengikut negeri ({format_month_label(selected_month)})", color_discrete_map=STATE_COLORS)
    burden_chart = style_figure(burden_chart, yaxis_title="%", height=420)
    burden_chart.update_layout(showlegend=False)
    st.plotly_chart(burden_chart, use_container_width=True, config={"displayModeBar": False})

left, right = st.columns(2, gap="medium")
with left:
    inflation_chart = px.line(inflation.sort_values("bulan"), x="bulan", y="price_index", color="item", markers=True, title="Indeks harga item asas", color_discrete_sequence=ITEM_COLORS)
    inflation_chart = style_figure(inflation_chart, yaxis_title="Index", legend_title="Item", height=420)
    inflation_chart.update_traces(line={"width": 2.6}, marker={"size": 5.5})
    st.plotly_chart(inflation_chart, use_container_width=True, config={"displayModeBar": False})
with right:
    if basket_vs_cpi.empty or basket_vs_cpi["low_income_cpi_rebased"].isna().all():
        st.warning("CPI Low-Income comparison is not available yet for this snapshot.")
    else:
        comparison_chart = px.line(basket_vs_cpi.melt(id_vars="bulan", value_vars=["basket_index", "low_income_cpi_rebased"], var_name="series", value_name="index_value").sort_values("bulan"), x="bulan", y="index_value", color="series", markers=True, title="Indeks basket vs CPI Low-Income", color_discrete_map={"basket_index": "#17233E", "low_income_cpi_rebased": "#22B8C9"})
        comparison_chart = style_figure(comparison_chart, yaxis_title="Index (Rebase=100)", legend_title="Series", height=420)
        comparison_chart.for_each_trace(lambda trace: trace.update(name="Basket Index" if trace.name == "basket_index" else "CPI Low-Income"))
        st.plotly_chart(comparison_chart, use_container_width=True, config={"displayModeBar": False})

left, right = st.columns(2, gap="medium")
with left:
    gap_chart = px.bar(gap.sort_values("bulan"), x="bulan", y="avg_cost", color="area_type", barmode="group", title="Jurang kos basket bandar-luar bandar", color_discrete_map={"Urban": "#17233E", "Rural": "#22B8C9", "Unknown": "#CBD5E1"})
    gap_chart = style_figure(gap_chart, yaxis_title="RM", legend_title="Area type", height=400)
    st.plotly_chart(gap_chart, use_container_width=True, config={"displayModeBar": False})
with right:
    ramadan_chart = px.bar(ramadan, x="ramadan_flag", y="avg_cost", color="ramadan_flag", title="Purata kos basket Ramadan vs bukan Ramadan", color_discrete_map={"Ramadan": "#22B8C9", "Non-Ramadan": "#17233E"})
    ramadan_chart = style_figure(ramadan_chart, yaxis_title="RM", height=400)
    ramadan_chart.update_layout(showlegend=False)
    st.plotly_chart(ramadan_chart, use_container_width=True, config={"displayModeBar": False})

st.markdown('<div class="panel"><div class="hero-kicker">Insight utama</div><div class="section-title">Ringkasan cepat untuk pembentangan</div><div class="section-note">Cards ini cuba bawa rasa reference video tadi: cepat dibaca, ada hierarchy yang jelas, dan tak terus lempar pengguna ke lautan chart.</div></div>', unsafe_allow_html=True)
featured = insights[:3]
for column, insight in zip(st.columns(max(len(featured), 1), gap="medium"), featured):
    with column:
        st.markdown(f'<div class="insight-card"><div class="insight-title">{html.escape(str(insight.get("title", "Insight")))}</div><div class="insight-value">{html.escape(extract_highlight(str(insight.get("detail", ""))))}</div><div class="insight-detail">{html.escape(str(insight.get("detail", "")))}</div></div>', unsafe_allow_html=True)
if len(insights) > 3:
    with st.expander("Lihat insight tambahan"):
        for insight in insights[3:]:
            st.markdown(f"- **{insight['title']}**: {insight['detail']}")

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
