from __future__ import annotations

import argparse
import csv
import math
import os
import tempfile
from collections import defaultdict
from pathlib import Path


DEFAULT_CASE_DIR = Path(
    "PSA_simulation/outputs/tower_1_pressure_pair_sweep_purge_002_des_0p1_0p5/"
    "tower_1_ads_4p8bar_des_0p1bar_25c_purge_002"
)
DEFAULT_INPUT_NAME = "desorption_profile.csv"
DEFAULT_OUTPUT_NAME = "desorption_methane_loading_profile.png"


def create_desorption_methane_loading_profile(
    case_dir: str | Path = DEFAULT_CASE_DIR,
    *,
    input_name: str = DEFAULT_INPUT_NAME,
    output_name: str = DEFAULT_OUTPUT_NAME,
    dpi: int = 180,
    zero_final_profile: bool = False,
    zero_profile_display_offset_mol_per_kg: float = 0.0,
) -> Path:
    case_dir = Path(case_dir)
    series = _read_profile(case_dir / input_name)
    selected_times = _select_endpoint_and_intermediate_times(sorted(series), intermediate_count=2)
    if zero_final_profile:
        _set_profile_to_zero(series, max(series), display_offset_mol_per_kg=zero_profile_display_offset_mol_per_kg)
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


def _set_profile_to_zero(
    series: dict[float, list[tuple[float, float]]],
    time_s: float,
    *,
    display_offset_mol_per_kg: float,
) -> None:
    display_offset_kmol_per_kg = display_offset_mol_per_kg / 1000.0
    series[time_s] = [(position_m, display_offset_kmol_per_kg) for position_m, _loading in series[time_s]]


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
    from matplotlib.ticker import FuncFormatter

    plt.rcParams["font.family"] = "sans-serif"
    plt.rcParams["font.sans-serif"] = [
        "Hiragino Sans",
        "Yu Gothic",
        "Noto Sans CJK JP",
        "DejaVu Sans",
    ]
    plt.rcParams["axes.unicode_minus"] = False

    fig, ax = plt.subplots(figsize=(7.8, 6.0))
    all_positions = []
    all_loading_mol_per_kg = []
    for time_s in selected_times:
        sorted_points = sorted(series[time_s], key=lambda point: point[0])
        positions = [point[0] for point in sorted_points]
        methane_loading_mol_per_kg = [point[1] * 1000.0 for point in sorted_points]
        all_positions.extend(positions)
        all_loading_mol_per_kg.extend(methane_loading_mol_per_kg)
        linewidth = 3.2 if max(methane_loading_mol_per_kg) <= 0.03 else 2.0
        ax.plot(
            positions,
            methane_loading_mol_per_kg,
            linewidth=linewidth,
            label=f"{time_s:.1f} s",
            zorder=4,
        )

    y_max = max(all_loading_mol_per_kg)
    for spine in ax.spines.values():
        spine.set_zorder(1)
    ax.set_xlim(0.0, max(all_positions))
    ax.set_ylim(0.0, _round_axis_limit(y_max * 1.05))
    ax.xaxis.set_major_formatter(FuncFormatter(_format_x_tick_without_origin))
    ax.set_xlabel("塔内位置 [m]", fontsize=18)
    ax.set_ylabel("メタン吸着量 [mol/kg]", fontsize=18)
    ax.tick_params(axis="both", which="both", direction="in", top=True, right=True, labelsize=16, zorder=2)
    ax.legend(frameon=False, fontsize=15)
    fig.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi)
    plt.close(fig)


def _round_axis_limit(value: float) -> float:
    if value <= 0.0:
        return 1.0
    magnitude = 10 ** math.floor(math.log10(value))
    return math.ceil(value / magnitude * 10.0) / 10.0 * magnitude


def _format_x_tick_without_origin(value: float, _position: int) -> str:
    if math.isclose(value, 0.0, abs_tol=1e-12):
        return ""
    return f"{value:.1f}"


def _set_matplotlib_config_dir() -> None:
    if "MPLCONFIGDIR" not in os.environ:
        os.environ["MPLCONFIGDIR"] = tempfile.mkdtemp(prefix="psa-matplotlib-")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create desorption CH4 loading profile plot.")
    parser.add_argument("--case-dir", type=Path, default=DEFAULT_CASE_DIR)
    parser.add_argument("--input-name", default=DEFAULT_INPUT_NAME)
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_NAME)
    parser.add_argument("--dpi", type=int, default=180)
    parser.add_argument(
        "--zero-final-profile",
        action="store_true",
        help="Set the final desorption loading profile to zero for presentation plots.",
    )
    parser.add_argument(
        "--zero-profile-display-offset-mol-per-kg",
        type=float,
        default=0.0,
        help="Draw the zeroed final profile this far above the x-axis, in mol/kg.",
    )
    args = parser.parse_args()

    output_path = create_desorption_methane_loading_profile(
        args.case_dir,
        input_name=args.input_name,
        output_name=args.output_name,
        dpi=args.dpi,
        zero_final_profile=args.zero_final_profile,
        zero_profile_display_offset_mol_per_kg=args.zero_profile_display_offset_mol_per_kg,
    )
    print(f"Output written to: {output_path}")


if __name__ == "__main__":
    main()
