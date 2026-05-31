from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
from pathlib import Path
from typing import Any


DEFAULT_SWEEP_OUTPUT_DIR = Path("PSA_simulation/outputs/tower_1_temperature_sweep_4p8bar_purge_001")

SUMMARY_COLUMNS = [
    "case",
    "temperature_c",
    "product_ch4_mole_percent",
    "methane_recovery_percent",
    "methane_enrichment_factor",
    "product_ch4_kmol",
    "product_h2_kmol",
    "product_h2_mole_percent",
    "ch4_productivity_kmol_per_h",
    "adsorption_end_time_s",
    "desorption_end_time_s",
    "cycle_time_s",
]

PLOT_GROUPS = [
    {
        "filename": "temperature_sweep_methane_performance.png",
        "title": "Methane performance vs inlet temperature",
        "metrics": [
            ("product_ch4_mole_percent", "Product CH4 [mol%]"),
            ("methane_recovery_percent", "CH4 recovery [%]"),
            ("methane_enrichment_factor", "CH4 enrichment factor [-]"),
            ("ch4_productivity_kmol_per_h", "CH4 productivity [kmol/h-cycle]"),
        ],
    },
    {
        "filename": "temperature_sweep_product_amounts.png",
        "title": "Product amount vs inlet temperature",
        "metrics": [
            ("product_ch4_kmol", "Product CH4 [kmol/cycle]"),
            ("product_h2_kmol", "Product H2 [kmol/cycle]"),
            ("product_h2_mole_percent", "Product H2 [mol%]"),
        ],
    },
    {
        "filename": "temperature_sweep_cycle_times.png",
        "title": "Cycle time vs inlet temperature",
        "metrics": [
            ("adsorption_end_time_s", "Adsorption time [s]"),
            ("desorption_end_time_s", "Desorption time [s]"),
            ("cycle_time_s", "Cycle time [s]"),
        ],
    },
]


def create_temperature_sweep_plots(
    sweep_output_dir: str | Path = DEFAULT_SWEEP_OUTPUT_DIR,
    *,
    dpi: int = 150,
) -> list[Path]:
    output_dir = Path(sweep_output_dir)
    rows = read_temperature_sweep_rows(output_dir)
    if not rows:
        raise ValueError(f"{output_dir} contains no case directories with summary.json")

    _write_summary_outputs(rows, output_dir)
    return _write_plots(rows, output_dir, dpi=dpi)


def read_temperature_sweep_rows(sweep_output_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for case_dir in sorted(path for path in sweep_output_dir.iterdir() if path.is_dir()):
        summary_path = case_dir / "summary.json"
        if not summary_path.exists():
            continue

        with summary_path.open("r", encoding="utf-8") as handle:
            summary = json.load(handle)
        rows.append(_read_row(case_dir.name, summary))

    return sorted(rows, key=lambda row: _as_float(row["temperature_c"]))


def _read_row(case_name: str, summary: dict[str, Any]) -> dict[str, Any]:
    setup = summary["setup"]
    performance = summary["performance"]
    product = performance["desorption_product_kmol"]
    product_total = _as_float(product.get("H2")) + _as_float(product.get("CH4"))
    cycle_time_s = _as_float(performance.get("cycle_time_s"))
    product_ch4_kmol = _as_float(product.get("CH4"))

    return {
        "case": case_name,
        "temperature_c": _as_float(setup.get("tower_temperature_k")) - 273.15,
        "product_ch4_mole_percent": _as_float(performance.get("desorption_product_methane_mole_fraction")) * 100.0,
        "methane_recovery_percent": _as_float(performance.get("methane_desorption_recovery_percent")),
        "methane_enrichment_factor": _as_float(performance.get("methane_enrichment_factor")),
        "product_ch4_kmol": product_ch4_kmol,
        "product_h2_kmol": _as_float(product.get("H2")),
        "product_h2_mole_percent": 100.0 * _as_float(product.get("H2")) / product_total,
        "ch4_productivity_kmol_per_h": product_ch4_kmol / cycle_time_s * 3600.0,
        "adsorption_end_time_s": _as_float(performance.get("adsorption_end_time_s")),
        "desorption_end_time_s": _as_float(performance.get("desorption_end_time_s")),
        "cycle_time_s": cycle_time_s,
    }


def _write_summary_outputs(rows: list[dict[str, Any]], output_dir: Path) -> None:
    csv_path = output_dir / "temperature_sweep_summary.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    json_path = output_dir / "temperature_sweep_summary.json"
    with json_path.open("w", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def _write_plots(rows: list[dict[str, Any]], output_dir: Path, *, dpi: int) -> list[Path]:
    _set_matplotlib_config_dir()

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    try:
        import japanize_matplotlib  # noqa: F401
    except ImportError:
        pass

    temperatures = [_as_float(row["temperature_c"]) for row in rows]
    output_paths: list[Path] = []

    for group in PLOT_GROUPS:
        metrics = group["metrics"]
        fig_height = max(4.0, 2.1 * len(metrics) + 1.0)
        fig, axes = plt.subplots(
            nrows=len(metrics),
            ncols=1,
            figsize=(8.5, fig_height),
            sharex=True,
        )
        if len(metrics) == 1:
            axes = [axes]

        for ax, (column, label) in zip(axes, metrics):
            values = [_as_float(row.get(column)) for row in rows]
            ax.plot(temperatures, values, marker="o", linewidth=1.8, color="#2F6F9F")
            ax.set_ylabel(label)
            ax.ticklabel_format(axis="y", style="plain", useOffset=False)
            ax.grid(axis="both", color="#D0D0D0", linestyle="--", linewidth=0.6, alpha=0.8)
            ax.tick_params(axis="both", which="both", direction="in", top=True, right=True)

        axes[-1].set_xlabel("Inlet temperature [degC]")
        fig.suptitle(str(group["title"]), fontsize=13)
        fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.97))

        output_path = output_dir / str(group["filename"])
        fig.savefig(output_path, dpi=dpi)
        plt.close(fig)
        output_paths.append(output_path)

    return output_paths


def _set_matplotlib_config_dir() -> None:
    if "MPLCONFIGDIR" not in os.environ:
        os.environ["MPLCONFIGDIR"] = tempfile.mkdtemp(prefix="psa-matplotlib-")


def _as_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create temperature sweep summary plots from PSA tower outputs.")
    parser.add_argument("--sweep-output-dir", type=Path, default=DEFAULT_SWEEP_OUTPUT_DIR)
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args()

    output_paths = create_temperature_sweep_plots(args.sweep_output_dir, dpi=args.dpi)
    for output_path in output_paths:
        print(f"Output written to: {output_path}")


if __name__ == "__main__":
    main()
