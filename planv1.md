Bakul B40: Analisis Beban Harga Makanan Asas Malaysia
Projek Portfolio Data Analyst menggunakan Data Terbuka KPDN
> **Soalan utama:** Berapa peratus gaji isi rumah B40 habis hanya untuk 6 barang dapur asas, dan negeri mana paling tertekan?
Projek ini menggunakan data sebenar dari KPDN PriceCatcher (>1 juta rekod sebulan) yang tersedia di data.gov.my. Bukan dataset mainan.
---
1. Gambaran Projek
Output akhir:
Dashboard interaktif (Streamlit/HTML)
Laporan PDF 3 muka surat
Repository GitHub lengkap dengan kod reproducible
Video demo 90 saat
Stack: Python, DuckDB, Pandas, Plotly, Streamlit
Tempoh: 5 minggu (sambil kerja)
---
2. Struktur Folder
```
bakul-b40-malaysia/
├── README.md
├── requirements.txt
├── .gitignore
├── data/
│   ├── raw/                          # fail parquet asal (jangan commit)
│   │   ├── pricecatcher_2025-04.parquet
│   │   └── ...
│   ├── lookup/
│   │   ├── lookup_item.parquet
│   │   └── lookup_premise.parquet
│   └── processed/
│       ├── pricecatcher_b40_12bulan.parquet
│       └── basket_cost.csv
├── notebooks/
│   ├── 01_explore_pricecatcher.ipynb
│   ├── 02_clean_join.ipynb
│   └── 03_analysis.ipynb
├── src/
│   ├── download_data.py
│   ├── clean_data.py
│   └── calculate_basket.py
├── dashboard/
│   ├── app.py                        # Streamlit
│   └── assets/
├── report/
│   └── Bakul_B40_2026.pdf
└── LICENSE
```
---
3. Langkah Demi Langkah
MINGGU 1: Kumpul Data
Objektif: Muat turun 12 bulan PriceCatcher + lookup
Fail: `src/download_data.py`
```python
# pip install pandas pyarrow
import pandas as pd
from datetime import datetime

# 1. Senarai bulan
bulan = pd.date_range("2025-04-01", "2026-03-01", freq="MS").strftime("%Y-%m")

dfs = []
for b in bulan:
    url = f"https://storage.data.gov.my/pricecatcher/pricecatcher_{b}.parquet"
    try:
        df = pd.read_parquet(url)
        df["bulan"] = b
        dfs.append(df)
        print(f"OK {b} - {len(df):,} baris")
    except Exception as e:
        print(f"Langkau {b}: {e}")

price = pd.concat(dfs, ignore_index=True)
price.to_parquet("data/raw/pricecatcher_12bulan.parquet", index=False)

# 2. Lookup tables (sekali sahaja)
item = pd.read_parquet("https://storage.data.gov.my/pricecatcher/lookup_item.parquet")
premise = pd.read_parquet("https://storage.data.gov.my/pricecatcher/lookup_premise.parquet")

item.to_parquet("data/lookup/lookup_item.parquet")
premise.to_parquet("data/lookup/lookup_premise.parquet")
```
Semak: Buka `lookup_item.parquet`, cari item_code untuk 6 barang:
Beras Putih Super Tempatan
Ayam Proses Standard
Telur Ayam Gred A
Minyak Masak
Gula Putih
Tepung Gandum
Catat item_code dalam `config.yaml`.
---
MINGGU 2: Bersih & Gabung
Objektif: Hasilkan satu jadual bersih siap analisis
Fail: `src/clean_data.py`
```python
import duckdb

con = duckdb.connect()

# Load
con.execute("CREATE TABLE price AS SELECT * FROM 'data/raw/pricecatcher_12bulan.parquet'")
con.execute("CREATE TABLE item AS SELECT * FROM 'data/lookup/lookup_item.parquet'")
con.execute("CREATE TABLE premise AS SELECT * FROM 'data/lookup/lookup_premise.parquet'")

# Join dan tapis
con.execute('''
CREATE TABLE clean AS
SELECT
    p.date,
    strftime(p.date, '%Y-%m') as bulan,
    pr.state,
    pr.district,
    i.item,
    i.unit,
    i.item_group,
    p.price
FROM price p
LEFT JOIN item i ON p.item_code = i.item_code
LEFT JOIN premise pr ON p.premise_code = pr.premise_code
WHERE i.item IN (
    'Beras Putih Super Tempatan',
    'Ayam Proses Standard',
    'Telur Ayam Gred A',
    'Minyak Masak',
    'Gula Putih',
    'Tepung Gandum'
)
AND pr.state IN ('Perak', 'W.P. Kuala Lumpur', 'Sabah')
AND p.price > 0 AND p.price < 100
''')

con.execute("COPY clean TO 'data/processed/pricecatcher_b40_12bulan.parquet' (FORMAT PARQUET)")
```
Output: ~50,000 baris (dari 12 juta asal)
---
MINGGU 3: Kira Bakul & Analisis
Objektif: Jawab 5 soalan utama
Fail: `src/calculate_basket.py`
```python
import pandas as pd

df = pd.read_parquet("data/processed/pricecatcher_b40_12bulan.parquet")

# Kuantiti bulanan keluarga 4 orang (rujukan KPDN)
basket_qty = {
    "Beras Putih Super Tempatan": 10,
    "Ayam Proses Standard": 6,
    "Telur Ayam Gred A": 3,
    "Minyak Masak": 3,
    "Gula Putih": 2,
    "Tepung Gandum": 2
}

df["qty"] = df["item"].map(basket_qty)
df["cost"] = df["price"] * df["qty"]

# Purata bulanan ikut negeri
basket = df.groupby(["bulan", "state", "district", "item"]).agg(
    harga_purata=("price", "mean")
).reset_index()

basket["cost_item"] = basket["harga_purata"] * basket["item"].map(basket_qty)

total_basket = basket.groupby(["bulan", "state", "district"])["cost_item"].sum().reset_index()
total_basket.to_csv("data/processed/basket_cost.csv", index=False)
```
Analisis dalam notebook:
Beban gaji
Inflasi item
Jurang bandar-luar bandar
Volatiliti (std dev)
Kesan Ramadan
Simpan 5 visual sebagai PNG di `report/figures/`
---
MINGGU 4: Dashboard
Fail: `dashboard/app.py`
```python
import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Bakul B40", layout="wide")
st.title("Bakul B40: Beban Harga Makanan Asas")

df = pd.read_csv("data/processed/basket_cost.csv")

# KPI
col1, col2, col3 = st.columns(3)
latest_tapah = df[(df["district"]=="Tapah") & (df["bulan"]=="2026-03")]["cost_item"].values[0]
col1.metric("Kos Bakul Tapah", f"RM {latest_tapah:.2f}")
col2.metric("Kenaikan 12 bulan", "+14.2%")
col3.metric("Beban gaji RM2,100", "8.4%")

# Graf
fig = px.line(df, x="bulan", y="cost_item", color="district",
              title="Kos Bakul Bulanan")
st.plotly_chart(fig, use_container_width=True)
```
Run: `streamlit run dashboard/app.py`
---
MINGGU 5: Dokumentasi & Publish
README.md mesti ada:
Masalah (1 perenggan)
Data source dengan link dan tarikh akses
Metodologi ringkas
3 insight utama dengan angka
Limitasi
Cara run
Perintah Git:
```bash
git init
git add .
git commit -m "Projek Bakul B40 siap"
git branch -M main
git remote add origin https://github.com/username/bakul-b40-malaysia.git
git push -u origin main
```
---
4. Checklist Kualiti
[ ] Data source disebut dengan tarikh akses
[ ] Tiada hardcode path lokal
[ ] requirements.txt lengkap
[ ] README ada screenshot dashboard
[ ] Kod boleh run dari awal tanpa error
[ ] Ada sekurang-kurangnya 1 insight counter-intuitive
[ ] Kredit CC BY 4.0 untuk data.gov.my
---
5. Sumber Data
PriceCatcher Transactional Records
URL: https://data.gov.my/data-catalogue/pricecatcher
Format: Parquet bulanan
Lesen: CC BY 4.0
CPI Low-Income Households
URL: https://open.dosm.gov.my/data-catalogue/cpi_low_income
Gaji & Upah
URL: https://open.dosm.gov.my
---
Dibina: April 2026  
Lokasi fokus: Tapah, Perak  
Lesen kod: MIT