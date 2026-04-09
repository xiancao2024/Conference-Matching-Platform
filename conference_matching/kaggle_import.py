from __future__ import annotations

import argparse
from pathlib import Path

from .data import KAGGLE_DATASET_ID, import_kaggle_dataset


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Normalize the Kaggle Event Attendance Dataset into the conference matching schema."
    )
    parser.add_argument(
        "--input",
        type=Path,
        help="Path to a downloaded Kaggle zip, csv, or extracted directory. If omitted, kagglehub will be used.",
    )
    parser.add_argument(
        "--dataset-id",
        default=KAGGLE_DATASET_ID,
        help=f"Kaggle dataset id to download with kagglehub. Defaults to {KAGGLE_DATASET_ID}.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    output_path = import_kaggle_dataset(input_path=args.input, dataset_id=args.dataset_id)
    print(f"Normalized dataset written to {output_path}")


if __name__ == "__main__":
    main()
