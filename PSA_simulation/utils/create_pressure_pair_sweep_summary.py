from __future__ import annotations

import argparse
import csv
import json
import math
import os
import tempfile
from pathlib import Path
from typing import Any


DEFAULT_SWEEP_OUTPUT_DIR = Path("PSA_simulation/outputs/tower_1_pressure_pair_sweep_purge_002_des_0p1_0p5")
DEFAULT_MIN_PRODUCT_CH4_MOLE_FRACTION = 0.90
DEFAULT_MIN_TOWER_COUNT = 3

SUMMARY_COLUMNS = [
    "case",
    "adsorption_pressure_bar",
    "desorption_pressure_bar",
    "pressure_ratio",
    "purge_fraction",
    "product_ch4_mole_percent",
    "methane_recovery_percent",
    "product_total_kmol_per_cycle",
    "product_ch4_kmol_per_cycle",
    "product_h2_kmol_per_cycle",
    "product_total_kmol_per_h",
    "product_ch4_kmol_per_h",
    "product_h2_kmol_per_h",
    "adsorption_end_time_s",
    "desorption_end_time_s",
    "cycle_time_s",
    "minimum_tower_count",
    "meets_product_ch4_spec",
]


def create_pressure_pair_sweep_summary(
    sweep_output_dir: str | Path = DEFAULT_SWEEP_OUTPUT_DIR,
    *,
    min_product_ch4_mole_fraction: float = DEFAULT_MIN_PRODUCT_CH4_MOLE_FRACTION,
    min_tower_count: int = DEFAULT_MIN_TOWER_COUNT,
    dpi: int = 150,
) -> list[Path]:
    output_dir = Path(sweep_output_dir)
    rows = read_pressure_pair_sweep_rows(
        output_dir,
        min_product_ch4_mole_fraction=min_product_ch4_mole_fraction,
        min_tower_count=min_tower_count,
    )
    if not rows:
        raise ValueError(f"{output_dir} contains no case directories with summary.json")

    output_paths = _write_summary_outputs(rows, output_dir)
    output_paths.extend(_write_plots(rows, output_dir, dpi=dpi))
    return output_paths


def read_pressure_pair_sweep_rows(
    sweep_output_dir: Path,
    *,
    min_product_ch4_mole_fraction: float,
    min_tower_count: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case_dir in sorted(path for path in sweep_output_dir.iterdir() if path.is_dir()):
        summary_path = case_dir / "summary.json"
        if not summary_path.exists():
            continue
        with summary_path.open("r", encoding="utf-8") as handle:
            summary = json.load(handle)
        rows.append(
            _read_row(
                case_dir.name,
                summary,
                min_product_ch4_mole_fraction=min_product_ch4_mole_fraction,
                min_tower_count=min_tower_count,
            )
        )

    return sorted(rows, key=lambda row: (row["adsorption_pressure_bar"], row["desorption_pressure_bar"]))


def _read_row(
    case_name: str,
    summary: dict[str, Any],
    *,
    min_product_ch4_mole_fraction: float,
    min_tower_count: int,
) -> dict[str, Any]:
    setup = summary["setup"]
    performance = summary["performance"]
    cycle_time_s = _as_float(performance.get("cycle_time_s"))
    adsorption_time_s = _as_float(performance.get("adsorption_end_time_s"))
    desorption_time_s = _as_float(performance.get("desorption_end_time_s"))
    cycle_to_hour = 3600.0 / cycle_time_s if cycle_time_s else float("nan")

    product = performance.get("desorption_product_kmol") or {}
    product_ch4_kmol = _as_float(product.get("CH4"))
    product_h2_kmol = _as_float(product.get("H2"))
    product_total_kmol = product_ch4_kmol + product_h2_kmol
    product_ch4_mole_fraction = _as_float(performance.get("desorption_product_methane_mole_fraction"))

    required_tower_count = (
        max(min_tower_count, math.ceil(cycle_time_s / adsorption_time_s))
        if cycle_time_s and adsorption_time_s
        else min_tower_count
    )
    meets_spec = product_total_kmol > 0.0 and product_ch4_mole_fraction >= min_product_ch4_mole_fraction

    adsorption_pressure_bar = _as_float(setup.get("adsorption_pressure_kpa")) / 100.0
    desorption_pressure_bar = _as_float(setup.get("desorption_pressure_kpa")) / 100.0
    return {
        "case": case_name,
        "adsorption_pressure_bar": adsorption_pressure_bar,
        "desorption_pressure_bar": desorption_pressure_bar,
        "pressure_ratio": adsorption_pressure_bar / desorption_pressure_bar,
        "purge_fraction": setup.get("purge_fraction"),
        "product_ch4_mole_percent": product_ch4_mole_fraction * 100.0,
        "methane_recovery_percent": _as_float(performance.get("methane_desorption_recovery_percent")),
        "product_total_kmol_per_cycle": product_total_kmol,
        "product_ch4_kmol_per_cycle": product_ch4_kmol,
        "product_h2_kmol_per_cycle": product_h2_kmol,
        "product_total_kmol_per_h": product_total_kmol * cycle_to_hour,
        "product_ch4_kmol_per_h": product_ch4_kmol * cycle_to_hour,
        "product_h2_kmol_per_h": product_h2_kmol * cycle_to_hour,
        "adsorption_end_time_s": adsorption_time_s,
        "desorption_end_time_s": desorption_time_s,
        "cycle_time_s": cycle_time_s,
        "minimum_tower_count": required_tower_count,
        "meets_product_ch4_spec": meets_spec,
    }


def _write_summary_outputs(rows: list[dict[str, Any]], output_dir: Path) -> list[Path]:
    csv_path = output_dir / "pressure_pair_sweep_summary.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    json_path = output_dir / "pressure_pair_sweep_summary.json"
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    return [csv_path, json_path]


def _write_plots(rows: list[dict[str, Any]], output_dir: Path, *, dpi: int) -> list[Path]:
    _set_matplotlib_config_dir()

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    output_paths: list[Path] = []
    plot_specs = [
        ("product_ch4_mole_percent", "Product CH4 [mol%]", "pressure_pair_product_ch4.png"),
        ("methane_recovery_percent", "CH4 recovery [%]", "pressure_pair_methane_recovery.png"),
        ("product_total_kmol_per_h", "Product outlet flow [kmol/h]", "pressure_pair_product_flow.png"),
        ("minimum_tower_count", "Minimum tower count [-]", "pressure_pair_minimum_tower_count.png"),
    ]

    for column, label, filename in plot_specs:
        fig, ax = plt.subplots(figsize=(8.0, 5.5))
        x = [_as_float(row["desorption_pressure_bar"]) for row in rows]
        y = [_as_float(row["adsorption_pressure_bar"]) for row in rows]
        z = [_as_float(row[column]) for row in rows]
        scatter = ax.scatter(x, y, c=z, s=85, cmap="viridis", edgecolors="#333333", linewidths=0.35)
        cbar = fig.colorbar(scatter, ax=ax)
        cbar.set_label(label)
        ax.set_xlabel("Desorption pressure [bar]")
        ax.set_ylabel("Adsorption pressure [bar]")
        ax.set_title(label)
        ax.grid(axis="both", color="#D0D0D0", linestyle="--", linewidth=0.6, alpha=0.8)
        ax.tick_params(axis="both", which="both", direction="in", top=True, right=True)
        fig.tight_layout()
        output_path = output_dir / filename
        fig.savefig(output_path, dpi=dpi)
        plt.close(fig)
        output_paths.append(output_path)

    return output_paths


def _set_matplotlib_config_dir() -> None:
    if "MPLCONFIGDIR" not in os.environ:
        os.environ["MPLCONFIGDIR"] = tempfile.mkdtemp(prefix="psa-matplotlib-")


def _as_float(value: Any) -> float:
    if value in (None, ""):
        return float("nan")
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create adsorption/desorption pressure pair sweep summary plots.")
    parser.add_argument("--sweep-output-dir", type=Path, default=DEFAULT_SWEEP_OUTPUT_DIR)
    parser.add_argument("--min-product-ch4-mole-fraction", type=float, default=DEFAULT_MIN_PRODUCT_CH4_MOLE_FRACTION)
    parser.add_argument("--min-tower-count", type=int, default=DEFAULT_MIN_TOWER_COUNT)
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args()

    output_paths = create_pressure_pair_sweep_summary(
        args.sweep_output_dir,
        min_product_ch4_mole_fraction=args.min_product_ch4_mole_fraction,
        min_tower_count=args.min_tower_count,
        dpi=args.dpi,
    )
    for output_path in output_paths:
        print(f"Output written to: {output_path}")


if __name__ == "__main__":
    main()
