from __future__ import annotations

import argparse

import bootstrap_demo
import calculate_basket
import clean_data
import download_data
import generate_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Bakul B40 pipeline.")
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download the full PriceCatcher dataset before cleaning and analysis.",
    )
    parser.add_argument(
        "--demo-only",
        action="store_true",
        help="Generate bundled demo outputs only.",
    )
    args = parser.parse_args()

    if args.demo_only:
        bootstrap_demo.main()
        return

    if args.download:
        download_data.main()
        clean_data.main()
        calculate_basket.run_analysis(data_mode="real")
        generate_report.main()
        return

    bootstrap_demo.main()


if __name__ == "__main__":
    main()
