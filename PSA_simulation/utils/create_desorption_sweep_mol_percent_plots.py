from __future__ import annotations

import argparse
import csv
import os
import tempfile
from pathlib import Path


DEFAULT_SWEEP_OUTPUT_DIR = Path("PSA_simulation/outputs/tower_1_desorption_pressure_sweep")
DEFAULT_OUTPUT_NAME = "desorption_outlet_ch4_mol_percent.png"


def create_desorption_sweep_mol_percent_plots(
    sweep_output_dir: str | Path = DEFAULT_SWEEP_OUTPUT_DIR,
    *,
    output_name: str = DEFAULT_OUTPUT_NAME,
    dpi: int = 150,
) -> list[Path]:
    output_dir = Path(sweep_output_dir)
    _set_matplotlib_config_dir(output_dir)

    output_paths: list[Path] = []
    for case_dir in sorted(path for path in output_dir.iterdir() if path.is_dir()):
        csv_path = case_dir / "desorption_outlet_ch4_curve.csv"
        if not csv_path.exists():
            continue

        output_path = case_dir / output_name
        _plot_desorption_outlet_ch4_mol_percent(csv_path, output_path, dpi=dpi)
        output_paths.append(output_path)

    return output_paths


def _plot_desorption_outlet_ch4_mol_percent(csv_path: Path, output_path: Path, *, dpi: int) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    time_s: list[float] = []
    ch4_mol_percent: list[float] = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required_columns = {"time_s", "y_CH4_out"}
        fieldnames = set(reader.fieldnames or [])
        missing_columns = sorted(required_columns - fieldnames)
        if missing_columns:
            missing_text = ", ".join(missing_columns)
            raise ValueError(f"{csv_path} is missing required columns: {missing_text}")

        for row_number, row in enumerate(reader, start=2):
            try:
                time_s.append(float(row["time_s"]))
                ch4_mol_percent.append(float(row["y_CH4_out"]) * 100.0)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{csv_path} contains non-numeric data at row {row_number}") from exc

    if not time_s:
        raise ValueError(f"{csv_path} contains no rows")

    fig, ax = plt.subplots(figsize=(8.0, 5.0))
    ax.plot(time_s, ch4_mol_percent, color="#D65F00", linewidth=1.8)
    ax.set_xlabel("Desorption time [s]")
    ax.set_ylabel("Outlet CH4 [mol%]")
    ax.set_ylim(bottom=0.0, top=max(100.0, max(ch4_mol_percent) * 1.05))
    ax.tick_params(axis="both", which="both", direction="in", top=True, right=True)
    ax.grid(axis="both", color="#D0D0D0", linestyle="--", linewidth=0.6, alpha=0.8)
    fig.tight_layout()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=dpi)
    plt.close(fig)


def _set_matplotlib_config_dir(output_dir: Path) -> None:
    if "MPLCONFIGDIR" not in os.environ:
        os.environ["MPLCONFIGDIR"] = tempfile.mkdtemp(prefix="psa-matplotlib-")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create outlet CH4 mol percent plots for tower_1 desorption pressure sweep outputs."
    )
    parser.add_argument("--sweep-output-dir", type=Path, default=DEFAULT_SWEEP_OUTPUT_DIR)
    parser.add_argument("--output-name", default=DEFAULT_OUTPUT_NAME)
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args()

    output_paths = create_desorption_sweep_mol_percent_plots(
        args.sweep_output_dir,
        output_name=args.output_name,
        dpi=args.dpi,
    )
    for output_path in output_paths:
        print(f"Output written to: {output_path}")


if __name__ == "__main__":
    main()
