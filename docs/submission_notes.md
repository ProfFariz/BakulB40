# Submission Notes

Dokumen ini merangkum perkara utama untuk serahan akhir projek.

## Scope

- Tempoh analisis: `2022-01` hingga `2026-03`
- Negeri fokus: `Perak`, `W.P. Kuala Lumpur`, `Sabah`
- Saiz bakul: `15` item asas
- Rujukan pendapatan: gaji median bulanan pekerja mengikut negeri daripada DOSM
- Benchmark inflasi: `CPI Low-Income Households`

## Important Method Notes

- Basket analysis menggunakan **3 negeri fokus**, bukan semua negeri Malaysia.
- `Beras putih` menggunakan **state-specific proxy** kerana tiada satu kod beras 10kg yang konsisten merentas ketiga-tiga negeri fokus.
- `Tepung` dan `kicap` telah diganti kepada proxy yang mempunyai liputan lebih stabil merentas 3 negeri.
- Jika bulan analisis melebihi tahun gaji rasmi terkini, nilai gaji tahun terakhir yang tersedia akan dibawa ke hadapan.

## Recommended Files To Show

- [readme.md](/C:/Users/Acer%20Evo/Desktop/KerjaIntern/BakulB40/readme.md)
- [docs/project_overview.md](/C:/Users/Acer%20Evo/Desktop/KerjaIntern/BakulB40/docs/project_overview.md)
- [report/Bakul_B40_2026.pdf](/C:/Users/Acer%20Evo/Desktop/KerjaIntern/BakulB40/report/Bakul_B40_2026.pdf)
- [data/processed/kpi_summary.json](/C:/Users/Acer%20Evo/Desktop/KerjaIntern/BakulB40/data/processed/kpi_summary.json)
- [data/processed/basket_item_codes.csv](/C:/Users/Acer%20Evo/Desktop/KerjaIntern/BakulB40/data/processed/basket_item_codes.csv)

## Repro Commands

```powershell
py -3.10 src/download_data.py
py -3.10 src/clean_data.py
py -3.10 src/calculate_basket.py
py -3.10 src/generate_report.py
py -3.10 -m streamlit run dashboard/app.py
```

## Current Final Snapshot

- Latest focus district: `Batang Padang`
- Latest month: `2026-03`
- Latest basket cost: `RM197.34`
- Latest burden: `9.63%`
