from __future__ import annotations

import argparse
import csv
import json
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEFAULT_INPUT_PATH = Path("cost_estimation/inputs/equipment_costs.json")
DEFAULT_OUTPUT_DIR = Path("cost_estimation/outputs")


@dataclass(frozen=True)
class CostParameters:
    k1: float
    k2: float
    k3: float
    b1: float
    b2: float
    fp: float
    fm: float
    a_label: str
    a_unit: str


DEFAULT_EQUIPMENT_PARAMETERS: dict[str, CostParameters] = {
    "pump": CostParameters(
        k1=3.3892,
        k2=0.0536,
        k3=0.1538,
        b1=1.89,
        b2=1.35,
        fp=1.0,
        fm=1.0,
        a_label="Power",
        a_unit="kW",
    ),
    "decanter": CostParameters(
        k1=3.5565,
        k2=0.3776,
        k3=0.0905,
        b1=0.96,
        b2=1.21,
        fp=1.0,
        fm=1.0,
        a_label="Volume",
        a_unit="m^3",
    ),
    "psa": CostParameters(
        k1=3.4974,
        k2=0.4485,
        k3=0.1074,
        b1=2.25,
        b2=1.82,
        fp=1.13,
        fm=1.0,
        a_label="Volume",
        a_unit="m^3",
    ),
}


def calculate_bare_module_cost_jpy(
    equipment_type: str,
    a_value: float,
    *,
    parameters: dict[str, CostParameters] | None = None,
    cost_index_ratio: float = 846.3 / 397.0,
    exchange_rate_jpy_per_usd: float = 150.0,
) -> float:
    if a_value <= 0.0:
        raise ValueError("A must be greater than 0 because log10(A) is used.")

    equipment_parameters = parameters or DEFAULT_EQUIPMENT_PARAMETERS
    if equipment_type not in equipment_parameters:
        valid_types = ", ".join(sorted(equipment_parameters))
        raise ValueError(f"Unknown equipment type: {equipment_type}. Valid types: {valid_types}")

    params = equipment_parameters[equipment_type]
    log_a = math.log10(a_value)
    purchased_cost_usd = 10 ** (params.k1 + params.k2 * log_a + params.k3 * log_a**2)
    bare_module_factor = params.b1 + params.b2 * params.fp * params.fm
    return purchased_cost_usd * bare_module_factor * cost_index_ratio * exchange_rate_jpy_per_usd


def run_cost_estimation(input_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    input_path = Path(input_path)
    output_dir = Path(output_dir)

    with input_path.open("r", encoding="utf-8") as handle:
        config = json.load(handle)

    cost_index_ratio = float(config.get("cost_index_ratio", 846.3 / 397.0))
    exchange_rate = float(config.get("exchange_rate_jpy_per_usd", 150.0))
    parameters = _load_parameters(config.get("equipment_parameters", {}))

    case_rows = _calculate_case_rows(config.get("cases", []), parameters, cost_index_ratio, exchange_rate)
    sweep_rows = _calculate_sweep_rows(config.get("sweeps", []), parameters, cost_index_ratio, exchange_rate)

    output_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "input_path": str(input_path),
        "cost_index_ratio": cost_index_ratio,
        "exchange_rate_jpy_per_usd": exchange_rate,
        "cases": case_rows,
        "sweeps": sweep_rows,
    }

    summary_path = output_dir / "bare_module_cost_summary.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    csv_paths = _write_csv_outputs(case_rows, sweep_rows, output_dir)
    plot_paths = _write_plots(case_rows, sweep_rows, parameters, output_dir, dpi=int(config.get("dpi", 150)))

    return {
        "summary_path": summary_path,
        "csv_paths": csv_paths,
        "plot_paths": plot_paths,
        "case_count": len(case_rows),
        "sweep_point_count": len(sweep_rows),
    }


def _load_parameters(overrides: dict[str, Any]) -> dict[str, CostParameters]:
    parameters = dict(DEFAULT_EQUIPMENT_PARAMETERS)
    for equipment_type, values in overrides.items():
        base = parameters.get(equipment_type)
        if base is None:
            base = CostParameters(
                k1=0.0,
                k2=0.0,
                k3=0.0,
                b1=0.0,
                b2=0.0,
                fp=1.0,
                fm=1.0,
                a_label="A",
                a_unit="-",
            )
        parameters[equipment_type] = CostParameters(
            k1=float(values.get("K1", values.get("k1", base.k1))),
            k2=float(values.get("K2", values.get("k2", base.k2))),
            k3=float(values.get("K3", values.get("k3", base.k3))),
            b1=float(values.get("B1", values.get("b1", base.b1))),
            b2=float(values.get("B2", values.get("b2", base.b2))),
            fp=float(values.get("FP", values.get("fp", base.fp))),
            fm=float(values.get("FM", values.get("fm", base.fm))),
            a_label=str(values.get("a_label", base.a_label)),
            a_unit=str(values.get("a_unit", base.a_unit)),
        )
    return parameters


def _calculate_case_rows(
    cases: list[dict[str, Any]],
    parameters: dict[str, CostParameters],
    cost_index_ratio: float,
    exchange_rate: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for index, case in enumerate(cases, start=1):
        equipment_type = str(case["type"])
        a_value = float(case["A"])
        cost_jpy = calculate_bare_module_cost_jpy(
            equipment_type,
            a_value,
            parameters=parameters,
            cost_index_ratio=cost_index_ratio,
            exchange_rate_jpy_per_usd=exchange_rate,
        )
        rows.append(
            {
                "case": str(case.get("name", f"case_{index}")),
                "type": equipment_type,
                "A": a_value,
                "A_unit": parameters[equipment_type].a_unit,
                "cost_jpy": cost_jpy,
            }
        )
    return rows


def _calculate_sweep_rows(
    sweeps: list[dict[str, Any]],
    parameters: dict[str, CostParameters],
    cost_index_ratio: float,
    exchange_rate: float,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for sweep_index, sweep in enumerate(sweeps, start=1):
        equipment_types = [str(equipment_type) for equipment_type in sweep["types"]]
        a_values = _make_a_values(sweep)
        sweep_name = str(sweep.get("name", f"sweep_{sweep_index}"))
        for equipment_type in equipment_types:
            for a_value in a_values:
                cost_jpy = calculate_bare_module_cost_jpy(
                    equipment_type,
                    a_value,
                    parameters=parameters,
                    cost_index_ratio=cost_index_ratio,
                    exchange_rate_jpy_per_usd=exchange_rate,
                )
                rows.append(
                    {
                        "sweep": sweep_name,
                        "type": equipment_type,
                        "A": a_value,
                        "A_unit": parameters[equipment_type].a_unit,
                        "cost_jpy": cost_jpy,
                    }
                )
    return rows


def _make_a_values(sweep: dict[str, Any]) -> list[float]:
    if "A_values" in sweep:
        values = [float(value) for value in sweep["A_values"]]
    else:
        a_min = float(sweep["A_min"])
        a_max = float(sweep["A_max"])
        points = int(sweep.get("points", 25))
        if points < 2:
            raise ValueError("Sweep points must be at least 2.")

        scale = str(sweep.get("scale", "linear")).lower()
        if scale == "linear":
            step = (a_max - a_min) / (points - 1)
            values = [a_min + step * index for index in range(points)]
        elif scale == "log":
            if a_min <= 0.0 or a_max <= 0.0:
                raise ValueError("Log scale sweep requires A_min and A_max greater than 0.")
            log_min = math.log10(a_min)
            log_max = math.log10(a_max)
            step = (log_max - log_min) / (points - 1)
            values = [10 ** (log_min + step * index) for index in range(points)]
        else:
            raise ValueError(f"Unknown sweep scale: {scale}")

    if any(value <= 0.0 for value in values):
        raise ValueError("All A values must be greater than 0.")
    return values


def _write_csv_outputs(
    case_rows: list[dict[str, Any]], sweep_rows: list[dict[str, Any]], output_dir: Path
) -> list[Path]:
    output_paths: list[Path] = []
    if case_rows:
        path = output_dir / "bare_module_cost_cases.csv"
        _write_dict_rows(path, case_rows, ["case", "type", "A", "A_unit", "cost_jpy"])
        output_paths.append(path)

    if sweep_rows:
        path = output_dir / "bare_module_cost_sweeps.csv"
        _write_dict_rows(path, sweep_rows, ["sweep", "type", "A", "A_unit", "cost_jpy"])
        output_paths.append(path)

    return output_paths


def _write_dict_rows(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_plots(
    case_rows: list[dict[str, Any]],
    sweep_rows: list[dict[str, Any]],
    parameters: dict[str, CostParameters],
    output_dir: Path,
    *,
    dpi: int,
) -> list[Path]:
    if not case_rows and not sweep_rows:
        return []

    _set_matplotlib_config_dir()
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    try:
        import japanize_matplotlib  # noqa: F401
    except ImportError:
        pass

    output_paths: list[Path] = []

    if case_rows:
        output_paths.append(_plot_case_costs(case_rows, output_dir, dpi=dpi, plt=plt))

    sweep_names = sorted({row["sweep"] for row in sweep_rows})
    for sweep_name in sweep_names:
        rows = [row for row in sweep_rows if row["sweep"] == sweep_name]
        output_paths.append(_plot_sweep_costs(sweep_name, rows, parameters, output_dir, dpi=dpi, plt=plt))

    return output_paths


def _plot_case_costs(case_rows: list[dict[str, Any]], output_dir: Path, *, dpi: int, plt: Any) -> Path:
    labels = [f"{row['case']}\n({row['type']})" for row in case_rows]
    costs = [row["cost_jpy"] for row in case_rows]

    fig, ax = plt.subplots(figsize=(10.0, 5.5))
    ax.bar(labels, costs, color="#4C78A8")
    ax.set_ylabel("Bare module cost [JPY]")
    ax.tick_params(axis="x", labelrotation=25)
    ax.tick_params(axis="both", which="both", direction="in", top=True, right=True)
    ax.grid(axis="y", color="#D0D0D0", linestyle="--", linewidth=0.6, alpha=0.8)
    fig.tight_layout()

    output_path = output_dir / "bare_module_cost_cases.png"
    fig.savefig(output_path, dpi=dpi)
    plt.close(fig)
    return output_path


def _plot_sweep_costs(
    sweep_name: str,
    rows: list[dict[str, Any]],
    parameters: dict[str, CostParameters],
    output_dir: Path,
    *,
    dpi: int,
    plt: Any,
) -> Path:
    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    colors = {
        "pump": "#4C78A8",
        "decanter": "#F58518",
        "psa": "#54A24B",
    }

    for equipment_type in sorted({row["type"] for row in rows}):
        equipment_rows = sorted((row for row in rows if row["type"] == equipment_type), key=lambda row: row["A"])
        ax.plot(
            [row["A"] for row in equipment_rows],
            [row["cost_jpy"] for row in equipment_rows],
            marker="o",
            linewidth=1.8,
            markersize=3.5,
            label=equipment_type,
            color=colors.get(equipment_type),
        )

    units = sorted({parameters[row["type"]].a_unit for row in rows})
    x_unit = units[0] if len(units) == 1 else "equipment-specific units"
    ax.set_xlabel(f"A [{x_unit}]")
    ax.set_ylabel("Bare module cost [JPY]")
    ax.set_title(sweep_name)
    ax.tick_params(axis="both", which="both", direction="in", top=True, right=True)
    ax.grid(axis="both", color="#D0D0D0", linestyle="--", linewidth=0.6, alpha=0.8)
    ax.legend()
    fig.tight_layout()

    output_path = output_dir / f"bare_module_cost_{_safe_filename(sweep_name)}.png"
    fig.savefig(output_path, dpi=dpi)
    plt.close(fig)
    return output_path


def _safe_filename(value: str) -> str:
    safe_chars = [char.lower() if char.isalnum() else "_" for char in value]
    filename = "".join(safe_chars).strip("_")
    return filename or "sweep"


def _set_matplotlib_config_dir() -> None:
    if "MPLCONFIGDIR" not in os.environ:
        os.environ["MPLCONFIGDIR"] = tempfile.mkdtemp(prefix="cost-estimation-matplotlib-")


def main() -> None:
    parser = argparse.ArgumentParser(description="Calculate and plot bare module costs for pump, decanter, and PSA.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT_PATH, help="JSON input file path.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR, help="Directory for CSV, JSON, and plots.")
    args = parser.parse_args()

    result = run_cost_estimation(args.input, args.output_dir)
    print(f"Summary written to: {result['summary_path']}")
    for csv_path in result["csv_paths"]:
        print(f"CSV written to: {csv_path}")
    for plot_path in result["plot_paths"]:
        print(f"Plot written to: {plot_path}")


if __name__ == "__main__":
    main()
