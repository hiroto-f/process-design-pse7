from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any


DEFAULT_SWEEP_OUTPUT_DIR = Path("PSA_simulation/outputs/tower_1_desorption_pressure_sweep")
DEFAULT_CH4_MIN_MOLE_FRACTION = 0.90


def update_product_cuts_from_outlet_csv(
    sweep_output_dir: str | Path = DEFAULT_SWEEP_OUTPUT_DIR,
    *,
    ch4_min_mole_fraction: float = DEFAULT_CH4_MIN_MOLE_FRACTION,
) -> list[Path]:
    output_dir = Path(sweep_output_dir)
    updated_paths: list[Path] = []

    for case_dir in sorted(path for path in output_dir.iterdir() if path.is_dir() and path.name != "logs"):
        summary_path = case_dir / "summary.json"
        outlet_csv_path = case_dir / "desorption_outlet_ch4_curve.csv"
        if not summary_path.exists() or not outlet_csv_path.exists():
            continue

        summary = _load_json(summary_path)
        product_cut = _calculate_product_cut(summary, outlet_csv_path, ch4_min_mole_fraction)
        summary["performance"]["product_cut"] = product_cut
        _write_json(summary_path, summary)
        updated_paths.append(summary_path)

    return updated_paths


def _calculate_product_cut(
    summary: dict[str, Any],
    outlet_csv_path: Path,
    ch4_min_mole_fraction: float,
) -> dict[str, Any]:
    tower_diameter_m = float(summary["setup"]["tower_diameter_m"])
    tower_area_m2 = math.pi * tower_diameter_m**2 / 4.0
    methane_feed_kmol = float(summary["performance"]["adsorption_feed_kmol"]["CH4"])

    rows = _read_outlet_rows(outlet_csv_path)
    cut_h2_kmol = 0.0
    cut_ch4_kmol = 0.0
    start_time_s: float | None = None
    end_time_s: float | None = None
    duration_s = 0.0

    previous_time_s = 0.0
    for row in rows:
        time_s = row["time_s"]
        interval_s = max(0.0, time_s - previous_time_s)
        previous_time_s = time_s

        if row["y_CH4_out"] < ch4_min_mole_fraction:
            continue

        interval_start_s = time_s - interval_s
        if start_time_s is None:
            start_time_s = interval_start_s
        end_time_s = time_s
        duration_s += interval_s
        cut_h2_kmol += row["C_H2_out_kmol_per_m3"] * row["u_out_m_per_s"] * tower_area_m2 * interval_s
        cut_ch4_kmol += row["C_CH4_out_kmol_per_m3"] * row["u_out_m_per_s"] * tower_area_m2 * interval_s

    cut_product_kmol = cut_h2_kmol + cut_ch4_kmol
    methane_mole_fraction = cut_ch4_kmol / cut_product_kmol if cut_product_kmol else None

    return {
        "ch4_min_mole_fraction": ch4_min_mole_fraction,
        "start_time_s": start_time_s,
        "end_time_s": end_time_s,
        "duration_s": duration_s,
        "product_kmol": {
            "H2": cut_h2_kmol,
            "CH4": cut_ch4_kmol,
        },
        "methane_mole_fraction": methane_mole_fraction,
        "methane_recovery_percent": cut_ch4_kmol / methane_feed_kmol * 100.0 if methane_feed_kmol else None,
    }


def _read_outlet_rows(path: Path) -> list[dict[str, float]]:
    required_columns = {
        "time_s",
        "C_H2_out_kmol_per_m3",
        "C_CH4_out_kmol_per_m3",
        "y_CH4_out",
        "u_out_m_per_s",
    }
    rows: list[dict[str, float]] = []

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing_columns = sorted(required_columns - fieldnames)
        if missing_columns:
            missing_text = ", ".join(missing_columns)
            raise ValueError(f"{path} is missing required columns: {missing_text}")

        for row_number, row in enumerate(reader, start=2):
            try:
                rows.append({column: float(row[column]) for column in required_columns})
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{path} contains non-numeric data at row {row_number}") from exc

    if not rows:
        raise ValueError(f"{path} contains no outlet history rows")

    return rows


def _load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _write_json(path: Path, data: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Update product_cut in summary.json from outlet CH4 CSV files.")
    parser.add_argument("--sweep-output-dir", type=Path, default=DEFAULT_SWEEP_OUTPUT_DIR)
    parser.add_argument("--ch4-min-mole-fraction", type=float, default=DEFAULT_CH4_MIN_MOLE_FRACTION)
    args = parser.parse_args()

    updated_paths = update_product_cuts_from_outlet_csv(
        args.sweep_output_dir,
        ch4_min_mole_fraction=args.ch4_min_mole_fraction,
    )
    for updated_path in updated_paths:
        print(f"Updated: {updated_path}")


if __name__ == "__main__":
    main()
