from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from common import get_paths, load_config, read_json


def build_styles() -> dict[str, ParagraphStyle]:
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="BodySmall",
            parent=styles["BodyText"],
            fontSize=9,
            leading=12,
            spaceAfter=6,
        )
    )
    styles["Title"].fontSize = 20
    styles["Heading2"].spaceAfter = 8
    return styles


def report_image(path: Path, width_cm: float, height_cm: float) -> Image | Paragraph:
    if not path.exists():
        return Paragraph(f"Figure missing: {path.name}", build_styles()["BodySmall"])
    return Image(str(path), width=width_cm * cm, height=height_cm * cm)


def build_story() -> list:
    config = load_config()
    paths = get_paths(config)
    styles = build_styles()
    kpis = read_json(paths["kpi_json"], default={})
    insights = read_json(paths["insights_json"], default=[])

    story = [
        Paragraph(config["project"]["subtitle"], styles["Title"]),
        Paragraph("Laporan ringkas 3 muka surat untuk portfolio data analyst.", styles["BodySmall"]),
        Spacer(1, 0.4 * cm),
        Paragraph("Soalan utama", styles["Heading2"]),
        Paragraph(
            "Berapa peratus gaji isi rumah B40 habis hanya untuk 15 item asas isi rumah, "
            "dan negeri mana paling tertekan?",
            styles["BodySmall"],
        ),
        Paragraph("KPI utama", styles["Heading2"]),
    ]

    kpi_table = Table(
        [
            ["Metrik", "Nilai"],
            ["Bulan terkini", str(kpis.get("latest_month", "N/A"))],
            ["Kos bakul Tapah", f"RM{kpis.get('latest_focus_cost_rm', 0):.2f}"],
            ["Beban pendapatan", f"{kpis.get('latest_focus_burden_pct', 0):.2f}%"],
            [
                "Pendapatan rujukan negeri",
                f"RM{kpis.get('reference_income_rm', 0):.0f}"
                + (f" ({kpis.get('reference_income_year')})" if kpis.get("reference_income_year") else ""),
            ],
            [
                "Jurang bakul vs CPI",
                (
                    f"{kpis.get('latest_basket_vs_cpi_gap', 0):.2f} mata"
                    if kpis.get("latest_basket_vs_cpi_gap") is not None
                    else "N/A"
                ),
            ],
            ["Perubahan 12 bulan", f"{kpis.get('focus_district_12m_change_pct', 0):.2f}%"],
            ["Negeri paling tertekan", str(kpis.get("highest_pressure_state", "N/A"))],
        ],
        colWidths=[6.5 * cm, 8.5 * cm],
    )
    kpi_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                ("BACKGROUND", (0, 1), (-1, -1), colors.HexColor("#f8fafc")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    )
    story.extend(
        [
            kpi_table,
            Spacer(1, 0.4 * cm),
            Paragraph("Metodologi", styles["Heading2"]),
            Paragraph(
                "1. Muat turun PriceCatcher bagi julat bulan analisis bersama lookup item dan premis. "
                "2. Tapis kepada 15 item bakul dan 3 negeri fokus. "
                "3. Kira harga purata bulanan dan jumlahkan kos bakul keluarga 4 orang. "
                "4. Tukarkan kepada peratus beban terhadap pendapatan rujukan gaji median bulanan mengikut negeri, "
                "dengan tahun rujukan rasmi terkini dibawa ke hadapan jika bulan analisis melebihi tahun data gaji. "
                "5. Bandingkan trajektori indeks bakul dengan CPI Low-Income keseluruhan sebagai benchmark inflasi isi rumah berpendapatan rendah.",
                styles["BodySmall"],
            ),
            Paragraph("Sumber data", styles["Heading2"]),
            Paragraph(
                "PriceCatcher data.gov.my, lookup_item.parquet, lookup_premise.parquet, "
                "CPI Low-Income Households, dan Salaries & Wages Survey DOSM. Akses pada 2026-04-16. "
                "Lesen data: CC BY 4.0.",
                styles["BodySmall"],
            ),
            PageBreak(),
            Paragraph("Visual utama", styles["Heading2"]),
            report_image(paths["figures_dir"] / "01_kos_bakul_bulanan.png", 16.5, 8.7),
            Spacer(1, 0.2 * cm),
            report_image(paths["figures_dir"] / "02_beban_gaji_negeri.png", 16.5, 8.7),
            Spacer(1, 0.2 * cm),
            Paragraph("Insight utama", styles["Heading2"]),
        ]
    )

    for insight in insights[:4]:
        story.append(Paragraph(f"<b>{insight['title']}</b>: {insight['detail']}", styles["BodySmall"]))

    story.extend(
        [
            PageBreak(),
            Paragraph("Analisis tambahan", styles["Heading2"]),
            report_image(paths["figures_dir"] / "03_inflasi_item.png", 16.5, 6.2),
            Spacer(1, 0.2 * cm),
            report_image(paths["figures_dir"] / "06_bakul_vs_cpi_lowincome.png", 16.5, 6.2),
            Spacer(1, 0.2 * cm),
            report_image(paths["figures_dir"] / "04_jurang_bandar_luar_bandar.png", 16.5, 6.2),
            Spacer(1, 0.2 * cm),
            report_image(paths["figures_dir"] / "05_kesan_ramadan.png", 16.5, 6.2),
            Spacer(1, 0.2 * cm),
            Paragraph("Limitasi", styles["Heading2"]),
            Paragraph(
                "Klasifikasi bandar-luar bandar menggunakan heuristik metadata premis, "
                "manakala analisis beban pendapatan menggunakan gaji median bulanan pekerja mengikut negeri "
                "sebagai proksi rujukan, dengan carry-forward pada tahun rasmi terkini yang tersedia jika perlu. "
                "CPI Low-Income digunakan sebagai benchmark konteks, bukan sebagai denominator beban pendapatan. "
                "Output demo dibundel untuk memudahkan semakan awal, dan boleh diganti "
                "sepenuhnya dengan output data sebenar selepas pipeline penuh dijalankan.",
                styles["BodySmall"],
            ),
        ]
    )
    return story


def main() -> None:
    config = load_config()
    paths = get_paths(config)
    doc = SimpleDocTemplate(
        str(paths["report_pdf"]),
        pagesize=A4,
        leftMargin=1.4 * cm,
        rightMargin=1.4 * cm,
        topMargin=1.4 * cm,
        bottomMargin=1.2 * cm,
    )
    doc.build(build_story())
    print(f"Saved {paths['report_pdf'].name}")


if __name__ == "__main__":
    main()
