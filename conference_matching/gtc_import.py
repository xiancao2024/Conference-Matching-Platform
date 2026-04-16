from __future__ import annotations

import argparse
from pathlib import Path

from .data import NORMALIZED_GTC_PATH, import_gtc_profile_csv


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Import a one-row-per-attendee (wide) GTC-style profile CSV into the "
            "normalized conference JSON used by the matcher."
        )
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to the wide-row CSV (must include a Name column).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help=f"Output JSON path. Default: {NORMALIZED_GTC_PATH}",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()
    out = import_gtc_profile_csv(input_path=args.input, output_path=args.output)
    print(f"Normalized GTC profile dataset written to {out}")
    print("Point the app at it with: CONFERENCE_DATA_PATH=" + str(out))


if __name__ == "__main__":
    main()
