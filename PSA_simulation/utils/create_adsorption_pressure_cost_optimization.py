from __future__ import annotations

import csv
import json
import math
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from cost_estimation.calculate_bare_module_costs import (
    calculate_activated_carbon_cost_jpy,
    calculate_bare_module_cost_jpy,
)

DEFAULT_OUTPUT_DIR = Path("PSA_simulation/outputs/adsorption_pressure_cost_optimization")
DEFAULT_SWEEP_OUTPUT_DIR = Path(
    "PSA_simulation/outputs/tower_1_pressure_pair_sweep_purge_002_des_0p1_0p5"
)
DEFAULT_SERVICE_YEARS = 7.0
DEFAULT_MINIMUM_TOWER_COUNT = 3

SOURCE_ROWS = [
    {"adsorption_pressure_bar": 5, "simulation_adsorption_pressure_bar": 4.8, "desorption_pressure_bar": 0.122, "compressor_vacuum_cost_jpy": 92_347, "electricity_cost_jpy_per_year": 253_587},
    {"adsorption_pressure_bar": 6, "simulation_adsorption_pressure_bar": 6.0, "desorption_pressure_bar": 0.138, "compressor_vacuum_cost_jpy": 892_902, "electricity_cost_jpy_per_year": 4_034_667},
    {"adsorption_pressure_bar": 8, "simulation_adsorption_pressure_bar": 8.0, "desorption_pressure_bar": 0.156, "compressor_vacuum_cost_jpy": 961_595, "electricity_cost_jpy_per_year": 4_416_333},
    {"adsorption_pressure_bar": 10, "simulation_adsorption_pressure_bar": 10.0, "desorption_pressure_bar": 0.165, "compressor_vacuum_cost_jpy": 1_035_788, "electricity_cost_jpy_per_year": 4_835_333},
    {"adsorption_pressure_bar": 12, "simulation_adsorption_pressure_bar": 12.0, "desorption_pressure_bar": 0.167, "compressor_vacuum_cost_jpy": 1_112_177, "electricity_cost_jpy_per_year": 5_273_667},
    {"adsorption_pressure_bar": 15, "simulation_adsorption_pressure_bar": 15.0, "desorption_pressure_bar": 0.157, "compressor_vacuum_cost_jpy": 1_237_093, "electricity_cost_jpy_per_year": 6_004_667},
]

OUTPUT_COLUMNS = [
    "adsorption_pressure_bar",
    "simulation_adsorption_pressure_bar",
    "desorption_pressure_bar",
    "tower_height_m",
    "tower_diameter_m",
    "single_tower_volume_m3",
    "adsorption_time_s",
    "interpolated_desorption_time_s",
    "interpolated_cycle_time_s",
    "tower_count",
    "total_tower_volume_m3",
    "psa_bare_module_cost_jpy",
    "activated_carbon_mass_t",
    "activated_carbon_cost_jpy",
    "compressor_vacuum_cost_jpy",
    "total_equipment_cost_jpy",
    "depreciation_period_years",
    "annualized_equipment_cost_jpy_per_year",
    "electricity_cost_jpy_per_year",
    "objective_cost_jpy_per_year",
    "annualized_equipment_cost_million_jpy_per_year",
    "electricity_cost_million_jpy_per_year",
    "objective_cost_million_jpy_per_year",
    "is_optimum",
]


def create_cost_optimization(
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    *,
    sweep_output_dir: str | Path = DEFAULT_SWEEP_OUTPUT_DIR,
    service_years: float = DEFAULT_SERVICE_YEARS,
    minimum_tower_count: int = DEFAULT_MINIMUM_TOWER_COUNT,
    dpi: int = 180,
) -> list[Path]:
    if service_years <= 0:
        raise ValueError("service_years must be greater than 0")
    if minimum_tower_count < 1:
        raise ValueError("minimum_tower_count must be at least 1")

    rows = _calculate_rows(
        Path(sweep_output_dir),
        service_years=service_years,
        minimum_tower_count=minimum_tower_count,
    )
    output_dir = Path(output_dir)
    csv_path = output_dir / "adsorption_pressure_cost_optimization.csv"
    plot_path = output_dir / "adsorption_pressure_cost_optimization.png"
    _write_csv(rows, csv_path)
    _write_plot(rows, plot_path, dpi=dpi)
    return [csv_path, plot_path]


def _calculate_rows(
    sweep_output_dir: Path,
    *,
    service_years: float,
    minimum_tower_count: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source in SOURCE_ROWS:
        low_summary = _read_summary(sweep_output_dir, source["simulation_adsorption_pressure_bar"], 0.1)
        high_summary = _read_summary(sweep_output_dir, source["simulation_adsorption_pressure_bar"], 0.2)
        setup = low_summary["setup"]
        low_performance = low_summary["performance"]
        high_performance = high_summary["performance"]

        tower_height = float(setup["tower_height_m"])
        tower_diameter = float(setup["tower_diameter_m"])
        single_tower_volume = math.pi * tower_diameter**2 * tower_height / 4.0
        adsorption_time = float(low_performance["adsorption_end_time_s"])
        desorption_time = _linear_interpolate(
            source["desorption_pressure_bar"],
            0.1,
            float(low_performance["desorption_end_time_s"]),
            0.2,
            float(high_performance["desorption_end_time_s"]),
        )
        cycle_time = adsorption_time + desorption_time
        tower_count = max(minimum_tower_count, math.ceil(cycle_time / adsorption_time))
        total_tower_volume = single_tower_volume * tower_count

        psa_cost = calculate_bare_module_cost_jpy("psa", total_tower_volume)
        carbon = calculate_activated_carbon_cost_jpy("psa", total_tower_volume)
        carbon_cost = float(carbon["activated_carbon_cost_jpy"] or 0.0)
        total_equipment_cost = psa_cost + carbon_cost + source["compressor_vacuum_cost_jpy"]
        equipment_cost = total_equipment_cost / service_years
        electricity_cost = source["electricity_cost_jpy_per_year"]
        objective_cost = equipment_cost + electricity_cost
        rows.append(
            {
                **source,
                "tower_height_m": tower_height,
                "tower_diameter_m": tower_diameter,
                "single_tower_volume_m3": single_tower_volume,
                "adsorption_time_s": adsorption_time,
                "interpolated_desorption_time_s": desorption_time,
                "interpolated_cycle_time_s": cycle_time,
                "tower_count": tower_count,
                "total_tower_volume_m3": total_tower_volume,
                "psa_bare_module_cost_jpy": psa_cost,
                "activated_carbon_mass_t": carbon["activated_carbon_mass_t"],
                "activated_carbon_cost_jpy": carbon_cost,
                "total_equipment_cost_jpy": total_equipment_cost,
                "depreciation_period_years": service_years,
                "annualized_equipment_cost_jpy_per_year": equipment_cost,
                "electricity_cost_jpy_per_year": electricity_cost,
                "objective_cost_jpy_per_year": objective_cost,
                "annualized_equipment_cost_million_jpy_per_year": equipment_cost / 1_000_000,
                "electricity_cost_million_jpy_per_year": electricity_cost / 1_000_000,
                "objective_cost_million_jpy_per_year": objective_cost / 1_000_000,
                "is_optimum": False,
            }
        )

    optimum = min(rows, key=lambda row: row["objective_cost_jpy_per_year"])
    optimum["is_optimum"] = True
    return rows


def _read_summary(
    sweep_output_dir: Path,
    adsorption_pressure_bar: float,
    desorption_pressure_bar: float,
) -> dict[str, Any]:
    adsorption_token = str(adsorption_pressure_bar).replace(".", "p")
    desorption_token = str(desorption_pressure_bar).replace(".", "p")
    case_dir = (
        sweep_output_dir
        / f"tower_1_ads_{adsorption_token}bar_des_{desorption_token}bar_25c_purge_002"
    )
    summary_path = case_dir / "summary.json"
    with summary_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _linear_interpolate(x: float, x0: float, y0: float, x1: float, y1: float) -> float:
    return y0 + (x - x0) * (y1 - y0) / (x1 - x0)


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

    pressure = [row["adsorption_pressure_bar"] for row in rows]
    equipment = [row["annualized_equipment_cost_million_jpy_per_year"] for row in rows]
    electricity = [row["electricity_cost_million_jpy_per_year"] for row in rows]
    objective = [row["objective_cost_million_jpy_per_year"] for row in rows]
    optimum = next(row for row in rows if row["is_optimum"])

    fig, ax = plt.subplots(figsize=(7.8, 6.0))
    ax.plot(pressure, objective, marker="o", linewidth=2.2, color="#C43C39", label="評価関数")
    ax.plot(pressure, equipment, marker="s", linewidth=1.8, color="#2F6F9F", label="装置総コスト")
    ax.plot(pressure, electricity, marker="^", linewidth=1.8, color="#3A8F5D", label="電力コスト")
    ax.scatter(
        [optimum["adsorption_pressure_bar"]],
        [optimum["objective_cost_million_jpy_per_year"]],
        s=100,
        facecolors="none",
        edgecolors="#111111",
        linewidths=1.5,
        zorder=4,
        label="最適点",
    )
    ax.annotate(
        f"最小: {optimum['adsorption_pressure_bar']} bar\n"
        f"{optimum['objective_cost_million_jpy_per_year']:.3f} 百万円/年",
        xy=(
            optimum["adsorption_pressure_bar"],
            optimum["objective_cost_million_jpy_per_year"],
        ),
        xytext=(14, 18),
        textcoords="offset points",
        fontsize=14,
    )
    ax.set_xlabel("吸着圧 [bar]", fontsize=18)
    ax.set_ylabel("年間コスト [百万円/年]", fontsize=18)
    ax.set_xticks(pressure)
    ax.set_ylim(bottom=0)
    ax.tick_params(axis="both", direction="in", top=True, right=True, labelsize=16)
    ax.legend(frameon=False, fontsize=15)
    fig.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi)
    plt.close(fig)


def _set_matplotlib_config_dir() -> None:
    if "MPLCONFIGDIR" not in os.environ:
        os.environ["MPLCONFIGDIR"] = tempfile.mkdtemp(prefix="psa-matplotlib-")


if __name__ == "__main__":
    for path in create_cost_optimization():
        print(f"Output written to: {path}")
