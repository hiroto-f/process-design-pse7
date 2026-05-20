from __future__ import annotations

import argparse
import csv
import json
import os
import tempfile
from copy import deepcopy
from pathlib import Path
from typing import Any

from .preprocess import Preprocessor
from .simulators import FastPsaSimulator
from .structured_io import load_common_inputs, load_json, load_tower_input, save_outputs


DEFAULT_CASES: list[dict[str, Any]] = [
    {
        "name": "base",
        "tower": {
            "purge_fraction": 0.10,
            "desorption_residual_loading_threshold": 0.01,
            "adsorption_breakthrough_threshold": 0.05,
            "adsorption_velocity_m_per_s": 0.15,
        },
    },
    {
        "name": "low_purge_005",
        "tower": {
            "purge_fraction": 0.05,
            "desorption_residual_loading_threshold": 0.01,
            "adsorption_breakthrough_threshold": 0.05,
            "adsorption_velocity_m_per_s": 0.15,
        },
    },
    {
        "name": "low_purge_002",
        "tower": {
            "purge_fraction": 0.02,
            "desorption_residual_loading_threshold": 0.01,
            "adsorption_breakthrough_threshold": 0.05,
            "adsorption_velocity_m_per_s": 0.15,
        },
    },
    {
        "name": "early_desorption_stop",
        "tower": {
            "purge_fraction": 0.05,
            "desorption_residual_loading_threshold": 0.03,
            "adsorption_breakthrough_threshold": 0.05,
            "adsorption_velocity_m_per_s": 0.15,
        },
    },
    {
        "name": "strict_adsorption",
        "tower": {
            "purge_fraction": 0.05,
            "desorption_residual_loading_threshold": 0.03,
            "adsorption_breakthrough_threshold": 0.02,
            "adsorption_velocity_m_per_s": 0.15,
        },
    },
    {
        "name": "slower_adsorption",
        "tower": {
            "purge_fraction": 0.05,
            "desorption_residual_loading_threshold": 0.03,
            "adsorption_breakthrough_threshold": 0.02,
            "adsorption_velocity_m_per_s": 0.10,
        },
    },
]


COMPARISON_COLUMNS = [
    "case",
    "purge_fraction",
    "adsorption_velocity_m_per_s",
    "desorption_velocity_m_per_s",
    "adsorption_breakthrough_threshold",
    "desorption_residual_loading_threshold",
    "adsorption_end_time_s",
    "desorption_end_time_s",
    "cycle_time_s",
    "feed_methane_mole_fraction_h2_ch4",
    "desorption_product_methane_mole_fraction",
    "methane_enrichment_factor",
    "methane_desorption_recovery_percent",
    "hydrogen_contamination_in_desorption_product_kmol",
    "desorption_product_h2_kmol",
    "desorption_product_ch4_kmol",
]


COMPARISON_PLOT_GROUPS = [
    {
        "filename": "comparison_methane_performance.png",
        "title": "Methane performance comparison",
        "metrics": [
            ("feed_methane_mole_fraction_h2_ch4", "Feed CH4 mole fraction [-]"),
            ("desorption_product_methane_mole_fraction", "Product CH4 mole fraction [-]"),
            ("methane_enrichment_factor", "Methane enrichment factor [-]"),
            ("methane_desorption_recovery_percent", "Methane recovery [%]"),
        ],
    },
    {
        "filename": "comparison_cycle_times.png",
        "title": "Cycle time comparison",
        "metrics": [
            ("adsorption_end_time_s", "Adsorption end time [s]"),
            ("desorption_end_time_s", "Desorption end time [s]"),
            ("cycle_time_s", "Cycle time [s]"),
        ],
    },
    {
        "filename": "comparison_product_amounts.png",
        "title": "Desorption product comparison",
        "metrics": [
            ("hydrogen_contamination_in_desorption_product_kmol", "H2 contamination [kmol]"),
            ("desorption_product_h2_kmol", "Product H2 [kmol]"),
            ("desorption_product_ch4_kmol", "Product CH4 [kmol]"),
        ],
    },
    {
        "filename": "comparison_operating_conditions.png",
        "title": "Operating condition comparison",
        "metrics": [
            ("purge_fraction", "Purge fraction [-]"),
            ("adsorption_velocity_m_per_s", "Adsorption velocity [m/s]"),
            ("desorption_velocity_m_per_s", "Desorption velocity [m/s]"),
            ("adsorption_breakthrough_threshold", "Adsorption breakthrough threshold [-]"),
            ("desorption_residual_loading_threshold", "Desorption residual loading threshold [-]"),
        ],
    },
]


def _case_path(output_dir: Path, case_name: str) -> Path:
    return output_dir / case_name


def _write_case_input(base_input: dict[str, Any], case: dict[str, Any], case_dir: Path) -> Path:
    case_input = deepcopy(base_input)
    case_input["tower"].update(case["tower"])
    case_dir.mkdir(parents=True, exist_ok=True)
    case_input_path = case_dir / "tower_input.json"
    with case_input_path.open("w", encoding="utf-8") as handle:
        json.dump(case_input, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return case_input_path


def _read_comparison_row(case_name: str, summary_path: Path) -> dict[str, Any]:
    summary = load_json(summary_path)
    setup = summary["setup"]
    performance = summary.get("performance", {})
    desorption_product = performance.get("desorption_product_kmol", {})
    return {
        "case": case_name,
        "purge_fraction": setup.get("purge_fraction"),
        "adsorption_velocity_m_per_s": setup.get("adsorption_velocity_m_per_s"),
        "desorption_velocity_m_per_s": setup.get("desorption_velocity_m_per_s"),
        "adsorption_breakthrough_threshold": setup.get("adsorption_breakthrough_threshold"),
        "desorption_residual_loading_threshold": setup.get("desorption_residual_loading_threshold"),
        "adsorption_end_time_s": performance.get("adsorption_end_time_s"),
        "desorption_end_time_s": performance.get("desorption_end_time_s"),
        "cycle_time_s": performance.get("cycle_time_s"),
        "feed_methane_mole_fraction_h2_ch4": performance.get("feed_methane_mole_fraction_h2_ch4"),
        "desorption_product_methane_mole_fraction": performance.get("desorption_product_methane_mole_fraction"),
        "methane_enrichment_factor": performance.get("methane_enrichment_factor"),
        "methane_desorption_recovery_percent": performance.get("methane_desorption_recovery_percent"),
        "hydrogen_contamination_in_desorption_product_kmol": performance.get(
            "hydrogen_contamination_in_desorption_product_kmol"
        ),
        "desorption_product_h2_kmol": desorption_product.get("H2"),
        "desorption_product_ch4_kmol": desorption_product.get("CH4"),
    }


def _write_comparison_outputs(rows: list[dict[str, Any]], output_dir: Path) -> None:
    comparison_json = output_dir / "comparison_summary.json"
    with comparison_json.open("w", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    comparison_csv = output_dir / "comparison_summary.csv"
    with comparison_csv.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMPARISON_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _write_comparison_plots(rows: list[dict[str, Any]], output_dir: Path, dpi: int = 150) -> list[Path]:
    if not rows:
        return []

    _set_matplotlib_config_dir(output_dir)

    try:
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("matplotlib is required to create comparison plots.") from exc

    try:
        import japanize_matplotlib  # noqa: F401
    except ImportError:
        pass

    case_names = [str(row["case"]) for row in rows]
    x_positions = list(range(len(case_names)))
    output_paths: list[Path] = []

    for group in COMPARISON_PLOT_GROUPS:
        metrics = group["metrics"]
        fig_height = max(4.0, 2.2 * len(metrics) + 1.0)
        fig, axes = plt.subplots(
            nrows=len(metrics),
            ncols=1,
            figsize=(10.0, fig_height),
            sharex=True,
        )
        if len(metrics) == 1:
            axes = [axes]

        for ax, (column, label) in zip(axes, metrics):
            values = [_as_float(row.get(column)) for row in rows]
            ax.bar(x_positions, values, color="#4C78A8")
            ax.axhline(0.0, color="#444444", linewidth=0.8)
            ax.set_ylabel(label)
            ax.grid(axis="y", color="#D0D0D0", linestyle="--", linewidth=0.6, alpha=0.8)
            ax.tick_params(axis="both", which="both", direction="in", top=True, right=True)

        axes[-1].set_xticks(x_positions)
        axes[-1].set_xticklabels(case_names, rotation=30, ha="right")
        fig.suptitle(str(group["title"]), fontsize=13)
        fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.97))

        output_path = output_dir / str(group["filename"])
        fig.savefig(output_path, dpi=dpi)
        plt.close(fig)
        output_paths.append(output_path)

    return output_paths


def _set_matplotlib_config_dir(output_dir: Path) -> None:
    if "MPLCONFIGDIR" not in os.environ:
        os.environ["MPLCONFIGDIR"] = tempfile.mkdtemp(prefix="psa-matplotlib-")


def _as_float(value: Any) -> float:
    if value in (None, ""):
        return float("nan")
    try:
        return float(value)
    except (TypeError, ValueError):
        return float("nan")


def _run_fast_case(
    inputs,
    output_dir: Path,
    case_name: str,
    setup_only: bool,
    max_steps: int | None,
    grid_size: int,
    adsorption_dt: float,
    desorption_dt: float,
    cycles: int,
    save_profiles: bool,
) -> None:
    setup_state = Preprocessor(inputs).run()
    simulation_state = None
    if not setup_only:
        simulation_state = FastPsaSimulator(
            inputs,
            setup_state,
            max_steps=max_steps,
            grid_size=grid_size,
            adsorption_dt=adsorption_dt,
            desorption_dt=desorption_dt,
            cycles=cycles,
            save_profiles=save_profiles,
        ).run()
    save_outputs(inputs, output_dir, case_name, setup_state, simulation_state)
    print(f"Output written to: {output_dir}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run PSA tower_1 comparison cases for CH4 enrichment.")
    parser.add_argument("--input-dir", type=Path, default=Path("PSA_simulation/inputs/common"))
    parser.add_argument("--tower-input", type=Path, default=Path("PSA_simulation/inputs/towers/tower_1.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("PSA_simulation/outputs/comparison"))
    parser.add_argument("--setup-only", action="store_true", help="Only run setup calculations for each case.")
    parser.add_argument("--max-steps", type=int, default=None, help="Debug safety limit per simulation step.")
    parser.add_argument("--grid-size", type=int, default=50)
    parser.add_argument("--adsorption-dt", type=float, default=0.00002)
    parser.add_argument("--desorption-dt", type=float, default=0.000005)
    parser.add_argument("--cycles", type=int, default=1)
    parser.add_argument("--save-profiles", action="store_true")
    parser.add_argument("--skip-plots", action="store_true", help="Do not create comparison PNG plots.")
    parser.add_argument("--plot-dpi", type=int, default=150, help="DPI for comparison PNG plots.")
    args = parser.parse_args()

    adsorbent, components = load_common_inputs(args.input_dir)
    base_input = load_json(args.tower_input)
    args.output_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for case in DEFAULT_CASES:
        case_name = case["name"]
        case_dir = _case_path(args.output_dir, case_name)
        print(f"Running comparison case: {case_name}")
        case_input_path = _write_case_input(base_input, case, case_dir)
        inputs = load_tower_input(case_input_path, adsorbent, components)
        _run_fast_case(
            inputs,
            case_dir,
            case_name,
            args.setup_only,
            args.max_steps,
            args.grid_size,
            args.adsorption_dt,
            args.desorption_dt,
            args.cycles,
            args.save_profiles,
        )
        rows.append(_read_comparison_row(case_name, case_dir / "summary.json"))

    _write_comparison_outputs(rows, args.output_dir)
    print(f"Comparison written to: {args.output_dir / 'comparison_summary.csv'}")
    print(f"Comparison written to: {args.output_dir / 'comparison_summary.json'}")
    if not args.skip_plots:
        for output_path in _write_comparison_plots(rows, args.output_dir, dpi=args.plot_dpi):
            print(f"Comparison plot written to: {output_path}")


if __name__ == "__main__":
    main()
