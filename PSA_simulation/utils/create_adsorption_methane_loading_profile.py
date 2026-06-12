from __future__ import annotations

import argparse
import csv
import os
import tempfile
from collections import defaultdict
from pathlib import Path


DEFAULT_CASE_DIR = Path(
    "PSA_simulation/outputs/tower_1_pressure_pair_sweep_purge_002_des_0p1_0p5/"
    "tower_1_ads_4p8bar_des_0p1bar_25c_purge_002"
)
DEFAULT_INPUT_NAME = "adsorption_1_profile.csv"
DEFAULT_OUTPUT_NAME = "adsorption_methane_loading_profile.png"


def create_adsorption_methane_loading_profile(
    case_dir: str | Path = DEFAULT_CASE_DIR,
    *,
    input_name: str = DEFAULT_INPUT_NAME,
    output_name: str = DEFAULT_OUTPUT_NAME,
    dpi: int = 180,
) -> Path:
    case_dir = Path(case_dir)
    series = _read_profile(case_dir / input_name)
    selected_times = _select_endpoint_and_intermediate_times(sorted(series), intermediate_count=2)
    output_path = case_dir / output_name
    _write_plot(series, selected_times, output_path, dpi=dpi)
    return output_path


def _read_profile(input_path: Path) -> dict[float, list[tuple[float, float]]]:
    series: dict[float, list[tuple[float, float]]] = defaultdict(list)
    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required_columns = {"time_s", "position_m", "q_CH4"}
        missing_columns = sorted(required_columns - set(reader.fieldnames or []))
        if missing_columns:
            missing_text = ", ".join(missing_columns)
            raise ValueError(f"{input_path} is missing required columns: {missing_text}")

        for row_number, row in enumerate(reader, start=2):
            try:
                time_s = float(row["time_s"])
                position_m = float(row["position_m"])
                methane_loading = float(row["q_CH4"])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{input_path} contains non-numeric data at row {row_number}") from exc
            series[time_s].append((position_m, methane_loading))

    if not series:
        raise ValueError(f"{input_path} contains no profile rows")
    return series


def _select_endpoint_and_intermediate_times(available_times: list[float], *, intermediate_count: int) -> list[float]:
    first_time = min(available_times)
    final_time = max(available_times)
    target_times = [first_time]
    target_times.extend(
        final_time * index / (intermediate_count + 1)
        for index in range(1, intermediate_count + 1)
    )
    target_times.append(final_time)
    return [min(available_times, key=lambda time_s: abs(time_s - target_time)) for target_time in target_times]


def _write_plot(
    series: dict[float, list[tuple[float, float]]],
    selected_times: list[float],
    output_path: Path,
    *,
    dpi: int,
) -> None:
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

    fig, ax = plt.subplots(figsize=(7.8, 6.0))
    for time_s in selected_times:
        sorted_points = sorted(series[time_s], key=lambda point: point[0])
        positions = [point[0] for point in sorted_points]
        methane_loading_mol_per_kg = [point[1] * 1000.0 for point in sorted_points]
        ax.plot(positions, methane_loading_mol_per_kg, linewidth=2.0, label=f"{time_s:.1f} s")

    ax.set_xlabel("塔内位置 [m]", fontsize=18)
    ax.set_ylabel("メタン吸着量 [mol/kg]", fontsize=18)
    ax.tick_params(axis="both", which="both", direction="in", top=True, right=True, labelsize=16)
    ax.legend(frameon=False, fontsize=15)
    fig.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi)
    plt.close(fig)


def _set_matplotlib_config_dir() -> None:
    if "MPLCONFIGDIR" not in os.environ:
        os.environ["MPLCONFIGDIR"] = tempfile.mkdtemp(prefix="psa-matplotlib-")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create adsorption CH4 loading profile plot.")
    parser.add_argument("--case-dir", type=Path, default=DEFAULT_CASE_DIR)
    parser.add_argument("--input-name", default=DEFAULT_INPUT_NAME)
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_NAME)
    parser.add_argument("--dpi", type=int, default=180)
    args = parser.parse_args()

    output_path = create_adsorption_methane_loading_profile(
        args.case_dir,
        input_name=args.input_name,
        output_name=args.output_name,
        dpi=args.dpi,
    )
    print(f"Output written to: {output_path}")


if __name__ == "__main__":
    main()
