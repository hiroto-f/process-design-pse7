from __future__ import annotations

import argparse
import csv
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .run_simulation import run_one_tower
from .structured_io import load_common_inputs, load_json, load_tower_input


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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run PSA tower_1 comparison cases for CH4 enrichment.")
    parser.add_argument("--input-dir", type=Path, default=Path("PSA_simulation/inputs/common"))
    parser.add_argument("--tower-input", type=Path, default=Path("PSA_simulation/inputs/towers/tower_1.json"))
    parser.add_argument("--output-dir", type=Path, default=Path("PSA_simulation/outputs/comparison"))
    parser.add_argument("--setup-only", action="store_true", help="Only run setup calculations for each case.")
    parser.add_argument("--max-steps", type=int, default=None, help="Debug safety limit per simulation step.")
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
        run_one_tower(inputs, case_dir, case_name, args.setup_only, args.max_steps)
        rows.append(_read_comparison_row(case_name, case_dir / "summary.json"))

    _write_comparison_outputs(rows, args.output_dir)
    print(f"Comparison written to: {args.output_dir / 'comparison_summary.csv'}")
    print(f"Comparison written to: {args.output_dir / 'comparison_summary.json'}")


if __name__ == "__main__":
    main()
