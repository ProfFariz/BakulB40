# Bakul B40 Malaysia

Projek ini menukar data harga runcit PriceCatcher kepada satu produk analitik kecil: pipeline data, dashboard Streamlit, dan laporan PDF untuk menjawab soalan berikut:

**Berapa besar beban kos bakul makanan asas terhadap isi rumah berpendapatan rendah?**

Versi repo semasa ialah **working real-data version** untuk skop analisis 3 negeri fokus: `Perak`, `W.P. Kuala Lumpur`, dan `Sabah`. Ia sudah menyokong:

- PriceCatcher bulanan
- lookup item dan lookup premis
- CPI Low-Income Households sebagai benchmark inflasi
- gaji median bulanan pekerja mengikut negeri sebagai rujukan pendapatan
- dashboard, output processed, dan laporan PDF

Dokumen aliran projek yang lebih visual ada di [docs/project_overview.md](docs/project_overview.md), manakala nota serahan ringkas ada di [docs/submission_notes.md](docs/submission_notes.md).

## Apa Yang Projek Ini Buat

Secara ringkas:

1. Muat turun data mentah rasmi.
2. Bersihkan dan gabungkan transaksi dengan lookup tables.
3. Tapis item bakul asas yang dipilih dalam `config.yaml`.
4. Kira kos bakul bulanan mengikut negeri dan daerah.
5. Kira `burden_pct` menggunakan gaji median bulanan negeri.
6. Bandingkan trend bakul dengan `CPI Low-Income`.
7. Paparkan hasil dalam dashboard dan PDF report.
8. Gunakan nama basket yang ringkas untuk paparan, tetapi padankan kepada `lookup_name` PriceCatcher yang tepat di belakang tabir.

## Struktur Repository

```text
.
|-- config.yaml
|-- dashboard/
|-- data/
|   |-- raw/
|   |   |-- cpi/
|   |   |-- wages/
|   |   `-- pricecatcher_*.parquet
|   |-- lookup/
|   `-- processed/
|-- docs/
|-- notebooks/
|-- report/
`-- src/
```

## Sumber Data

- PriceCatcher catalogue: [data.gov.my](https://data.gov.my/data-catalogue/pricecatcher)
- PriceCatcher monthly parquet: `https://storage.data.gov.my/pricecatcher/pricecatcher_{month}.parquet`
- PriceCatcher item lookup: `https://storage.data.gov.my/pricecatcher/lookup_item.parquet`
- PriceCatcher premise lookup: `https://storage.data.gov.my/pricecatcher/lookup_premise.parquet`
- CPI Low-Income catalogue: [OpenDOSM](https://open.dosm.gov.my/data-catalogue/cpi_lowincome)
- CPI Low-Income parquet: `https://storage.dosm.gov.my/cpi/cpi_2d_lowincome.parquet`
- Salaries and Wages Survey report page: [DOSM](https://v2.dosm.gov.my/portal-main/release-content/salaries-and-wages-survey-report-2024)

Access date currently documented in the project config: `2026-04-16`.

## Folder Placement Untuk Raw Files

Simpan fail mentah di lokasi ini:

- Monthly PriceCatcher parquet: `data/raw/pricecatcher_YYYY-MM.parquet`
- CPI Low-Income parquet: `data/raw/cpi/cpi_2d_lowincome.parquet`
- Wages extracted CSV: `data/raw/wages/salaries_wages_state_median_2010_2024.csv`
- Wages source PDF: `data/raw/wages/salaries_wages_survey_report_2024.pdf`
- Item lookup: `data/lookup/lookup_item.parquet`
- Premise lookup: `data/lookup/lookup_premise.parquet`

`data/processed/` hanya untuk output yang dijana oleh skrip.

## Workflow Skrip

- `src/download_data.py`
  Download PriceCatcher bulanan, lookup tables, dan CPI Low-Income parquet.
- `src/clean_data.py`
  Join transaksi dengan lookup item/premis, tapis negeri fokus dan item bakul, dan simpan dataset bersih.
- `src/calculate_basket.py`
  Kira kos item, kos bakul, `burden_pct`, inflasi item, jurang bandar-luar bandar, kesan Ramadan, dan perbandingan dengan CPI.
- `src/generate_report.py`
  Jana PDF report berdasarkan output dalam `data/processed/`.
- `src/bootstrap_demo.py`
  Jana snapshot demo supaya dashboard boleh terus dibuka walaupun data sebenar belum dimuat turun.
- `dashboard/app.py`
  Dashboard Streamlit untuk eksplorasi hasil analisis.

## Data Dictionary

### Raw Inputs

| File | Keterangan | Kolum utama |
|---|---|---|
| `data/raw/pricecatcher_YYYY-MM.parquet` | Rekod harga transaksi bulanan PriceCatcher | `date`, `premise_code`, `item_code`, `price` |
| `data/lookup/lookup_item.parquet` | Lookup item untuk padankan `item_code` | `item_code`, `item`, `unit`, `item_group` |
| `data/lookup/lookup_premise.parquet` | Lookup premis untuk padankan `premise_code` | `premise_code`, `premise`, `address`, `state`, `district` |
| `data/raw/cpi/cpi_2d_lowincome.parquet` | CPI Low-Income Households dari DOSM | `date`, `division`, `index` |
| `data/raw/wages/salaries_wages_state_median_2010_2024.csv` | Jadual bersih gaji median bulanan pekerja ikut negeri, diekstrak daripada jadual A8 | `state`, `year`, `median_monthly_wage_rm` |

### Processed Outputs

| File | Keterangan | Kolum utama |
|---|---|---|
| `data/processed/pricecatcher_b40_selected_range.parquet` | Dataset bersih selepas filtering dan join lookup | `bulan`, `state`, `district`, `area_type`, `item`, `price` |
| `data/processed/basket_item_monthly.csv` | Harga purata dan kos bulanan per item | `bulan`, `state`, `district`, `item`, `harga_purata`, `qty`, `cost_item` |
| `data/processed/basket_cost.csv` | Kos bakul total dan beban pendapatan | `bulan`, `state`, `district`, `cost_item`, `household_income_rm`, `burden_pct`, `income_reference_year` |
| `data/processed/cpi_low_income.csv` | Siri CPI Low-Income yang ditapis ke bulan analisis | `date`, `bulan`, `division`, `cpi_index`, `cpi_mom_change_pct`, `cpi_yoy_change_pct` |
| `data/processed/basket_vs_cpi.csv` | Perbandingan indeks bakul dengan CPI Low-Income | `bulan`, `national_avg_basket_cost_rm`, `basket_index`, `low_income_cpi_rebased`, `basket_vs_cpi_gap` |
| `data/processed/inflation_by_item.csv` | Indeks harga item dan perubahan bulanan | `bulan`, `item`, `harga_purata`, `monthly_change_pct`, `price_index` |
| `data/processed/urban_rural_gap.csv` | Purata kos bakul bandar vs luar bandar | `bulan`, `area_type`, `avg_cost` |
| `data/processed/ramadan_effect.csv` | Purata kos bakul Ramadan vs bukan Ramadan | `ramadan_flag`, `avg_cost` |
| `data/processed/volatility.csv` | Ringkasan volatiliti kos bakul ikut daerah | `state`, `district`, `avg_cost`, `std_dev`, `min_cost`, `max_cost` |
| `data/processed/kpi_summary.json` | KPI ringkas untuk dashboard dan report | `latest_month`, `latest_focus_cost_rm`, `latest_focus_burden_pct`, `reference_income_rm` |
| `data/processed/insights.json` | Insight ringkas dalam bentuk teks | `title`, `detail` |
| `data/processed/source_metadata.json` | Metadata tentang mode data dan input tersedia | `data_mode`, `cpi_low_income_available`, `wages_reference_available` |

## Nota Metodologi

- `burden_pct` dikira sebagai `kos_bakul / household_income_rm * 100`.
- `household_income_rm` datang daripada **gaji median bulanan pekerja mengikut negeri**.
- Jika bulan analisis melebihi tahun gaji rasmi terkini, projek ini akan carry forward tahun rasmi terakhir yang tersedia.
- `CPI Low-Income` digunakan sebagai **benchmark konteks inflasi**, bukan sebagai denominator untuk `burden_pct`.
- Skop analisis basket dalam repo ini ialah **3 negeri fokus sahaja**: `Perak`, `W.P. Kuala Lumpur`, dan `Sabah`.
- `Beras putih` kini menggunakan **state-specific proxy** dalam `config.yaml` kerana satu kod beras 10kg tunggal tidak memberi liputan yang stabil untuk Perak, W.P. Kuala Lumpur, dan Sabah secara serentak.
- Beberapa item generik seperti `beras putih`, `kicap`, `mee segera`, dan `sabun` dipetakan kepada satu item PriceCatcher yang mewakili kategori tersebut. Pemetaan tepat ini disimpan dalam `config.yaml`.
- Klasifikasi `Urban/Rural` masih menggunakan heuristik berdasarkan metadata premis.

## Cara Run

Setup:

```powershell
py -3.10 -m pip install -r requirements.txt
```

Fast first run dengan demo data:

```powershell
py -3.10 src/bootstrap_demo.py
py -3.10 -m streamlit run dashboard/app.py
```

Menjalankan pipeline penuh selepas itu akan menggantikan output demo dalam `data/processed/` dengan output data sebenar.

Pipeline data sebenar:

```powershell
py -3.10 src/download_data.py
py -3.10 src/clean_data.py
py -3.10 src/calculate_basket.py
py -3.10 src/generate_report.py
```

Atau satu arahan:

```powershell
py -3.10 src/pipeline.py --download
```

## Wages Note

Setakat `2026-04-16`, rujukan gaji rasmi yang digunakan dalam repo ini datang daripada **Salaries and Wages Survey Report 2024**. Untuk bulan analisis pada `2025` dan `2026`, nilai `2024` dibawa ke hadapan sehingga keluaran rasmi yang lebih baharu tersedia.

## Limitasi Semasa

- Sesetengah item adalah **proxy item** kerana PriceCatcher menyimpan item pada tahap produk/jenama, bukan label generik sepenuhnya.
- Export PNG menggunakan Plotly + Kaleido boleh gagal dalam sesetengah sandbox environment, tetapi repo ini kini akan fallback kepada `matplotlib` untuk figure report apabila perlu.
- Siri gaji median negeri datang daripada keluaran rasmi tahunan. Untuk bulan analisis yang melebihi tahun rasmi terkini, nilai tahun terakhir yang tersedia akan dibawa ke hadapan.

## Final Submission Files

Untuk serahan, fail paling penting ialah:

- `readme.md`
- `docs/project_overview.md`
- `docs/submission_notes.md`
- `report/Bakul_B40_2026.pdf`
- `data/processed/` outputs yang terhasil daripada pipeline sebenar

## Lesen

- Data sumber tertakluk kepada syarat lesen asal data.gov.my dan DOSM.
- Kod projek menggunakan lesen `MIT`.
