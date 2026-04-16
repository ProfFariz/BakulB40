from __future__ import annotations

import re
import shutil
from pathlib import Path

import pandas as pd
import pdfplumber
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[1]
SOURCE_PDF = ROOT / "data" / "raw" / "salaries_wages_survey_report_2024.pdf"
WAGES_DIR = ROOT / "data" / "raw" / "wages"
TARGET_PDF = WAGES_DIR / "salaries_wages_survey_report_2024.pdf"
ALL_METRICS_CSV = WAGES_DIR / "salaries_wages_a8_long.csv"
MEDIAN_ONLY_CSV = WAGES_DIR / "salaries_wages_state_median_2010_2024.csv"

YEARS = list(range(2010, 2025))
STATES = [
    "Malaysia",
    "Johor",
    "Kedah",
    "Kelantan",
    "Melaka",
    "Negeri Sembilan",
    "Pahang",
    "Pulau Pinang",
    "Perak",
    "Perlis",
    "Selangor",
    "Terengganu",
    "Sabah",
    "Sarawak",
    "W.P. Kuala Lumpur",
    "W.P. Labuan",
    "W.P. Putrajaya",
]
PAGE_BY_METRIC = {
    "number_of_recipients_000": 71,
    "median_monthly_wage_rm": 73,
    "mean_monthly_wage_rm": 75,
}
UNIT_BY_METRIC = {
    "number_of_recipients_000": "thousand_recipients",
    "median_monthly_wage_rm": "RM",
    "mean_monthly_wage_rm": "RM",
}
SOURCE_RELEASE_DATE = "2025-09-29"
SOURCE_TABLE = "A8"
SOURCE_TITLE = "Salaries and Wages Survey Report 2024"


def normalize_numeric(value: str) -> float:
    return float(value.replace(",", ""))


def extract_layout_text(page_index: int) -> str:
    with pdfplumber.open(SOURCE_PDF) as pdf:
        return pdf.pages[page_index].extract_text(layout=True, x_tolerance=1, y_tolerance=2) or ""


def extract_plain_lines(page_index: int) -> list[str]:
    reader = PdfReader(str(SOURCE_PDF))
    text = reader.pages[page_index].extract_text() or ""
    return [" ".join(line.split()) for line in text.splitlines() if line.strip()]


def parse_page(page_index: int) -> dict[str, list[str]]:
    text = extract_layout_text(page_index)
    rows: dict[str, list[str]] = {}
    pending_value: str | None = None

    for raw_line in text.splitlines():
        line = " ".join(raw_line.split())
        if not line:
            continue
        if re.fullmatch(r"[\d,\.]+", line):
            pending_value = line
            continue

        matched_state = next((state for state in STATES if line.startswith(state)), None)
        if matched_state is None:
            continue

        body = line[len(matched_state) :].strip()
        if body.endswith(matched_state):
            body = body[: -len(matched_state)].strip()

        values = re.findall(r"\d[\d,]*(?:\.\d+)?", body)
        if pending_value:
            values = [pending_value] + values
            pending_value = None
        rows[matched_state] = values

    # Fallback for rows that lose a value at a page break in layout extraction.
    plain_lines = extract_plain_lines(page_index)
    for state in STATES:
        if len(rows.get(state, [])) == len(YEARS):
            continue
        matching_lines = [line for line in plain_lines if state in line]
        if not matching_lines:
            continue
        best_line = max(matching_lines, key=lambda line: len(re.findall(r"\d[\d,]*(?:\.\d+)?", line)))
        values = re.findall(r"\d[\d,]*(?:\.\d+)?", best_line)
        if len(values) == len(YEARS):
            rows[state] = values

    missing = [state for state in STATES if len(rows.get(state, [])) != len(YEARS)]
    if missing:
        raise ValueError(f"Could not fully parse A8 rows for: {', '.join(missing)}")

    return rows


def build_output_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    records: list[dict[str, object]] = []
    for metric, page_index in PAGE_BY_METRIC.items():
        page_rows = parse_page(page_index)
        for state, values in page_rows.items():
            for year, value in zip(YEARS, values):
                records.append(
                    {
                        "metric": metric,
                        "state": state,
                        "year": year,
                        "value": normalize_numeric(value),
                        "unit": UNIT_BY_METRIC[metric],
                        "source_table": SOURCE_TABLE,
                        "source_title": SOURCE_TITLE,
                        "source_release_date": SOURCE_RELEASE_DATE,
                        "source_pdf": TARGET_PDF.name,
                    }
                )

    all_metrics = pd.DataFrame(records).sort_values(["metric", "state", "year"]).reset_index(drop=True)
    median_only = (
        all_metrics[all_metrics["metric"] == "median_monthly_wage_rm"][["state", "year", "value"]]
        .rename(columns={"value": "median_monthly_wage_rm"})
        .reset_index(drop=True)
    )
    return all_metrics, median_only


def main() -> None:
    if not SOURCE_PDF.exists():
        raise FileNotFoundError(f"Missing source PDF: {SOURCE_PDF}")

    WAGES_DIR.mkdir(parents=True, exist_ok=True)
    if SOURCE_PDF.resolve() != TARGET_PDF.resolve():
        shutil.copy2(SOURCE_PDF, TARGET_PDF)

    all_metrics, median_only = build_output_frames()
    all_metrics.to_csv(ALL_METRICS_CSV, index=False)
    median_only.to_csv(MEDIAN_ONLY_CSV, index=False)

    print(f"Saved {ALL_METRICS_CSV.name} with {len(all_metrics):,} rows")
    print(f"Saved {MEDIAN_ONLY_CSV.name} with {len(median_only):,} rows")


if __name__ == "__main__":
    main()
