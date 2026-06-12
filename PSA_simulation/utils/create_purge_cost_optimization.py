from __future__ import annotations

import argparse
import csv
import math
import os
import tempfile
from pathlib import Path
from typing import Any


DEFAULT_SWEEP_OUTPUT_DIR = Path("PSA_simulation/outputs/tower_1_purge_sweep_40c")
DEFAULT_INPUT_NAME = "psa_cost_by_purge_minimum_3_towers.csv"
DEFAULT_OUTPUT_CSV_NAME = "psa_purge_cost_optimization_annual.csv"
DEFAULT_OUTPUT_PLOT_NAME = "psa_purge_cost_optimization_annual.png"
DEFAULT_SERVICE_YEARS = 7.0

OUTPUT_COLUMNS = [
    "case",
    "purge_fraction",
    "purge_percent",
    "report_tower_count",
    "report_total_tower_volume_m3",
    "report_psa_construction_cost_jpy",
    "report_activated_carbon_mass_t",
    "report_activated_carbon_cost_jpy_per_year",
    "service_years",
    "annualized_psa_construction_cost_jpy_per_year",
    "total_annual_cost_jpy_per_year",
    "total_7_year_cost_jpy",
    "is_minimum_annual_cost",
]


def create_purge_cost_optimization(
    sweep_output_dir: str | Path = DEFAULT_SWEEP_OUTPUT_DIR,
    *,
    input_name: str = DEFAULT_INPUT_NAME,
    output_csv_name: str = DEFAULT_OUTPUT_CSV_NAME,
    output_plot_name: str = DEFAULT_OUTPUT_PLOT_NAME,
    service_years: float = DEFAULT_SERVICE_YEARS,
    dpi: int = 150,
) -> list[Path]:
    if service_years <= 0.0:
        raise ValueError("service_years must be greater than 0")

    output_dir = Path(sweep_output_dir)
    input_path = output_dir / input_name
    rows = _read_cost_rows(input_path, service_years=service_years)
    if not rows:
        raise ValueError(f"{input_path} contains no rows")

    minimum_cost = min(row["total_annual_cost_jpy_per_year"] for row in rows)
    for row in rows:
        row["is_minimum_annual_cost"] = math.isclose(row["total_annual_cost_jpy_per_year"], minimum_cost)

    csv_path = output_dir / output_csv_name
    _write_csv(rows, csv_path)

    plot_path = output_dir / output_plot_name
    _write_plot(rows, plot_path, dpi=dpi)

    return [csv_path, plot_path]


def _read_cost_rows(input_path: Path, *, service_years: float) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required_columns = {
            "case",
            "purge_fraction",
            "purge_percent",
            "report_tower_count",
            "report_total_tower_volume_m3",
            "report_psa_construction_cost_jpy",
            "report_activated_carbon_mass_t",
            "report_activated_carbon_cost_jpy",
        }
        missing_columns = sorted(required_columns - set(reader.fieldnames or []))
        if missing_columns:
            missing_text = ", ".join(missing_columns)
            raise ValueError(f"{input_path} is missing required columns: {missing_text}")

        for row_number, source in enumerate(reader, start=2):
            construction_cost = _as_float(source["report_psa_construction_cost_jpy"], input_path, row_number)
            carbon_cost_per_year = _as_float(source["report_activated_carbon_cost_jpy"], input_path, row_number)
            annualized_construction_cost = construction_cost / service_years
            total_annual_cost = annualized_construction_cost + carbon_cost_per_year
            rows.append(
                {
                    "case": source["case"],
                    "purge_fraction": _as_float(source["purge_fraction"], input_path, row_number),
                    "purge_percent": _as_float(source["purge_percent"], input_path, row_number),
                    "report_tower_count": int(_as_float(source["report_tower_count"], input_path, row_number)),
                    "report_total_tower_volume_m3": _as_float(
                        source["report_total_tower_volume_m3"], input_path, row_number
                    ),
                    "report_psa_construction_cost_jpy": construction_cost,
                    "report_activated_carbon_mass_t": _as_float(
                        source["report_activated_carbon_mass_t"], input_path, row_number
                    ),
                    "report_activated_carbon_cost_jpy_per_year": carbon_cost_per_year,
                    "service_years": service_years,
                    "annualized_psa_construction_cost_jpy_per_year": annualized_construction_cost,
                    "total_annual_cost_jpy_per_year": total_annual_cost,
                    "total_7_year_cost_jpy": construction_cost + carbon_cost_per_year * service_years,
                    "is_minimum_annual_cost": False,
                }
            )

    return sorted(rows, key=lambda row: row["purge_fraction"])


def _write_csv(rows: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _write_plot(rows: list[dict[str, Any]], output_path: Path, *, dpi: int) -> None:
    _set_matplotlib_config_dir()

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = [
        "Hiragino Sans",
        "Yu Gothic",
        "Noto Sans CJK JP",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False

    purge_percent = [row["purge_percent"] for row in rows]
    annual_cost_million_jpy = [row["total_annual_cost_jpy_per_year"] / 1_000_000.0 for row in rows]
    minimum_row = min(rows, key=lambda row: row["total_annual_cost_jpy_per_year"])
    minimum_x = minimum_row["purge_percent"]
    minimum_y = minimum_row["total_annual_cost_jpy_per_year"] / 1_000_000.0

    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    ax.plot(purge_percent, annual_cost_million_jpy, marker="o", linewidth=1.8, color="#2F6F9F")
    ax.scatter([minimum_x], [minimum_y], s=90, color="#D65F00", zorder=3, label="最適点")
    ax.annotate(
        f"最適点: {minimum_x:.1f}%\n{minimum_y:.3f} 百万円/年",
        xy=(minimum_x, minimum_y),
        xytext=(8, 12),
        textcoords="offset points",
        fontsize=14,
        color="#333333",
    )
    ax.set_xlabel("パージ率 [%]", fontsize=18)
    ax.set_ylabel("評価関数 [百万円/年]", fontsize=18)
    ax.ticklabel_format(axis="y", style="plain", useOffset=False)
    ax.tick_params(axis="both", which="both", direction="in", top=True, right=True, labelsize=16)
    ax.legend(frameon=False, fontsize=15)
    fig.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi)
    plt.close(fig)


def _set_matplotlib_config_dir() -> None:
    if "MPLCONFIGDIR" not in os.environ:
        os.environ["MPLCONFIGDIR"] = tempfile.mkdtemp(prefix="psa-matplotlib-")


def _as_float(value: Any, path: Path, row_number: int) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{path} contains non-numeric data at row {row_number}: {value!r}") from exc


def main() -> None:
    parser = argparse.ArgumentParser(description="Create annual PSA purge-rate cost optimization plot and CSV.")
    parser.add_argument("--sweep-output-dir", type=Path, default=DEFAULT_SWEEP_OUTPUT_DIR)
    parser.add_argument("--input-name", default=DEFAULT_INPUT_NAME)
    parser.add_argument("--output-csv-name", default=DEFAULT_OUTPUT_CSV_NAME)
    parser.add_argument("--output-plot-name", default=DEFAULT_OUTPUT_PLOT_NAME)
    parser.add_argument("--service-years", type=float, default=DEFAULT_SERVICE_YEARS)
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args()

    output_paths = create_purge_cost_optimization(
        args.sweep_output_dir,
        input_name=args.input_name,
        output_csv_name=args.output_csv_name,
        output_plot_name=args.output_plot_name,
        service_years=args.service_years,
        dpi=args.dpi,
    )
    for output_path in output_paths:
        print(f"Output written to: {output_path}")


if __name__ == "__main__":
    main()
