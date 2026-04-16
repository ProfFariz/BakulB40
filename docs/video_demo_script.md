# 90-Second Demo Script

## Goal

Show the project problem, prove the pipeline is reproducible, and highlight the dashboard insights in about 90 seconds.

## Storyboard

### 0s-15s: Problem framing

- Open `readme.md`
- Say: "This project asks a simple but important question: how much of a B40 household income is spent on fifteen essential basket items across three focus states in Malaysia?"
- Highlight that the project uses KPDN PriceCatcher and not a toy dataset

### 15s-35s: Pipeline overview

- Open `config.yaml`
- Explain the `2022-01` to `2026-03` analysis window, the three focus states, and the 15 basket quantities
- Show `src/pipeline.py` and mention there are two modes:
  - `python src/bootstrap_demo.py` for a fast bundled demo
  - `python src/pipeline.py --download` for the full real-data workflow

### 35s-55s: Processing code

- Open `src/clean_data.py` and `src/calculate_basket.py`
- Say: "DuckDB filters the large raw parquet files, then Pandas calculates basket cost, burden percentage, item inflation, volatility, urban-rural gap, and Ramadan effects."
- Mention that outputs are written to `data/processed/` and figures to `report/figures/`

### 55s-80s: Dashboard walkthrough

- Run `streamlit run dashboard/app.py`
- Point to the KPI cards, district trend line, burden-by-state chart, item contribution chart, and insight panel
- Say: "The dashboard is interactive, so recruiters can switch state and district without touching code."

### 80s-90s: Close

- Show `report/Bakul_B40_2026.pdf`
- End with: "This repository is built as a reproducible portfolio project: one config file, one pipeline, one dashboard, and a shareable report based on real PriceCatcher, CPI, and wage data."
