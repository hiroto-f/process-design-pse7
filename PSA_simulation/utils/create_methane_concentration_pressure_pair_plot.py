from __future__ import annotations

import argparse
import csv
import os
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any


DEFAULT_SWEEP_OUTPUT_DIR = Path("PSA_simulation/outputs/tower_1_pressure_pair_sweep_purge_002_des_0p1_0p5")
DEFAULT_INPUT_NAME = "methane_concentration_summary.csv"
DEFAULT_OUTPUT_NAME = "methane_concentration_by_pressure_pair.png"


def create_methane_concentration_pressure_pair_plot(
    sweep_output_dir: str | Path = DEFAULT_SWEEP_OUTPUT_DIR,
    *,
    input_name: str = DEFAULT_INPUT_NAME,
    output_name: str = DEFAULT_OUTPUT_NAME,
    dpi: int = 150,
) -> Path:
    output_dir = Path(sweep_output_dir)
    rows = _read_rows(output_dir / input_name)
    output_path = output_dir / output_name
    _write_plot(rows, output_path, dpi=dpi)
    return output_path


def _read_rows(input_path: Path) -> list[dict[str, float]]:
    rows: list[dict[str, float]] = []
    with input_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required_columns = {
            "adsorption_pressure_bar",
            "desorption_pressure_bar",
            "desorption_product_methane_mol_percent",
        }
        missing_columns = sorted(required_columns - set(reader.fieldnames or []))
        if missing_columns:
            missing_text = ", ".join(missing_columns)
            raise ValueError(f"{input_path} is missing required columns: {missing_text}")

        for row_number, row in enumerate(reader, start=2):
            try:
                rows.append(
                    {
                        "adsorption_pressure_bar": float(row["adsorption_pressure_bar"]),
                        "desorption_pressure_bar": float(row["desorption_pressure_bar"]),
                        "methane_mol_percent": float(row["desorption_product_methane_mol_percent"]),
                    }
                )
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{input_path} contains non-numeric data at row {row_number}") from exc

    if not rows:
        raise ValueError(f"{input_path} contains no rows")
    return rows


def _write_plot(rows: list[dict[str, float]], output_path: Path, *, dpi: int) -> None:
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

    by_adsorption_pressure: dict[float, list[dict[str, float]]] = defaultdict(list)
    for row in rows:
        by_adsorption_pressure[row["adsorption_pressure_bar"]].append(row)

    fig, ax = plt.subplots(figsize=(8.0, 8.0))
    for adsorption_pressure in sorted(by_adsorption_pressure):
        pressure_rows = sorted(
            by_adsorption_pressure[adsorption_pressure],
            key=lambda row: row["desorption_pressure_bar"],
        )
        x = [row["desorption_pressure_bar"] for row in pressure_rows]
        y = [row["methane_mol_percent"] for row in pressure_rows]
        ax.plot(x, y, marker="o", linewidth=2.0, label=f"吸着圧 {_display_pressure(adsorption_pressure)} bar")

    ax.axhline(90.0, color="#C43C39", linestyle="--", linewidth=1.5, label="目標 90 mol%")
    ax.set_xlabel("脱着圧 [bar]", fontsize=18)
    ax.set_ylabel("製品CH$_4$濃度 [mol%]", fontsize=18)
    ax.tick_params(axis="both", which="both", direction="in", top=True, right=True, labelsize=16)
    ax.legend(frameon=True, ncol=2, fontsize=15)
    fig.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi)
    plt.close(fig)


def _display_pressure(pressure: float) -> str:
    if abs(pressure - 4.8) < 1e-9:
        return "5"
    if pressure.is_integer():
        return str(int(pressure))
    return f"{pressure:g}"


def _set_matplotlib_config_dir() -> None:
    if "MPLCONFIGDIR" not in os.environ:
        os.environ["MPLCONFIGDIR"] = tempfile.mkdtemp(prefix="psa-matplotlib-")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create CH4 concentration plot by pressure pair.")
    parser.add_argument("--sweep-output-dir", type=Path, default=DEFAULT_SWEEP_OUTPUT_DIR)
    parser.add_argument("--input-name", default=DEFAULT_INPUT_NAME)
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_NAME)
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args()

    output_path = create_methane_concentration_pressure_pair_plot(
        args.sweep_output_dir,
        input_name=args.input_name,
        output_name=args.output_name,
        dpi=args.dpi,
    )
    print(f"Output written to: {output_path}")


if __name__ == "__main__":
    main()
