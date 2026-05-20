from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path
from typing import Iterable


ProfileSeries = dict[float, list[tuple[float, float]]]


def plot_adsorption_hydrogen_concentration(
    csv_path: str | Path,
    output_path: str | Path | None = None,
    *,
    times_s: Iterable[float] | None = None,
    max_profiles: int = 6,
    figsize: tuple[float, float] = (8.0, 5.0),
    dpi: int = 150,
    show: bool = False,
):
    """Plot H2 concentration profiles during adsorption from a profile CSV."""

    return _plot_profile_column(
        csv_path=csv_path,
        y_column="C_H2",
        output_path=output_path,
        times_s=times_s,
        max_profiles=max_profiles,
        figsize=figsize,
        dpi=dpi,
        show=show,
        y_label="水素濃度 [kmol/m3]",
    )


def plot_adsorption_methane_concentration(
    csv_path: str | Path,
    output_path: str | Path | None = None,
    *,
    times_s: Iterable[float] | None = None,
    max_profiles: int = 6,
    figsize: tuple[float, float] = (8.0, 5.0),
    dpi: int = 150,
    show: bool = False,
):
    """Plot CH4 concentration profiles during adsorption from a profile CSV."""

    return _plot_profile_column(
        csv_path=csv_path,
        y_column="C_CH4",
        output_path=output_path,
        times_s=times_s,
        max_profiles=max_profiles,
        figsize=figsize,
        dpi=dpi,
        show=show,
        y_label="メタン濃度 [kmol/m3]",
    )


def plot_desorption_methane_loading(
    csv_path: str | Path,
    output_path: str | Path | None = None,
    *,
    times_s: Iterable[float] | None = None,
    max_profiles: int = 6,
    figsize: tuple[float, float] = (8.0, 5.0),
    dpi: int = 150,
    show: bool = False,
):
    """Plot adsorbed CH4 loading profiles during desorption from a profile CSV."""

    return _plot_profile_column(
        csv_path=csv_path,
        y_column="q_CH4",
        output_path=output_path,
        times_s=times_s,
        max_profiles=max_profiles,
        figsize=figsize,
        dpi=dpi,
        show=show,
        y_label="メタン吸着量 [mol/g]",
    )


def plot_desorption_outlet_methane_concentration(
    csv_path: str | Path,
    output_path: str | Path | None = None,
    *,
    figsize: tuple[float, float] = (8.0, 5.0),
    dpi: int = 150,
    show: bool = False,
):
    """Plot outlet CH4 concentration during desorption from an outlet history CSV."""

    import matplotlib.pyplot as plt

    try:
        import japanize_matplotlib  # noqa: F401
    except ImportError:
        pass

    time_values, methane_values = _read_time_series(csv_path, "C_CH4_out_kmol_per_m3")
    _time_values, methane_mol_fractions = _read_time_series(csv_path, "y_CH4_out")
    methane_mol_percents = [value * 100.0 for value in methane_mol_fractions]

    fig, ax = plt.subplots(figsize=figsize)
    ax.plot(time_values, methane_values, color="#4C78A8", linewidth=1.8)
    ax.set_xlabel("Desorption time [s]")
    ax.set_ylabel("Outlet CH4 concentration [kmol/m3]")
    ax.tick_params(axis="both", which="both", direction="in", top=True, right=True)
    ax.grid(axis="both", color="#D0D0D0", linestyle="--", linewidth=0.6, alpha=0.8)
    ax_mol_percent = ax.twinx()
    ax_mol_percent.plot(time_values, methane_mol_percents, color="#F58518", linewidth=1.5)
    ax_mol_percent.set_ylabel("Outlet CH4 [mol%]")
    ax_mol_percent.tick_params(axis="y", which="both", direction="in", labelcolor="#F58518")
    fig.tight_layout()

    if output_path is not None:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(destination, dpi=dpi)

    if show:
        plt.show()

    return fig, ax


def _plot_profile_column(
    *,
    csv_path: str | Path,
    y_column: str,
    output_path: str | Path | None,
    times_s: Iterable[float] | None,
    max_profiles: int,
    figsize: tuple[float, float],
    dpi: int,
    show: bool,
    y_label: str,
):
    import matplotlib.pyplot as plt

    try:
        import japanize_matplotlib  # noqa: F401
    except ImportError:
        pass

    series = _read_profile_series(csv_path, y_column)
    selected_times = _select_times(sorted(series), times_s, max_profiles)

    fig, ax = plt.subplots(figsize=figsize)
    for time_s in selected_times:
        points = sorted(series[time_s], key=lambda point: point[0])
        positions = [point[0] for point in points]
        values = [point[1] for point in points]
        ax.plot(positions, values, marker="o", markersize=2.5, linewidth=1.5, label=f"{round(time_s):.0f} s")

    ax.set_xlabel("位置 [m]")
    ax.set_ylabel(y_label)
    ax.tick_params(axis="both", which="both", direction="in", top=True, right=True)
    ax.legend(title="時刻")
    fig.tight_layout()

    if output_path is not None:
        destination = Path(output_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(destination, dpi=dpi)

    if show:
        plt.show()

    return fig, ax


def _read_time_series(csv_path: str | Path, y_column: str) -> tuple[list[float], list[float]]:
    path = Path(csv_path)
    required_columns = {"time_s", y_column}
    time_values: list[float] = []
    y_values: list[float] = []

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing_columns = sorted(required_columns - fieldnames)
        if missing_columns:
            missing_text = ", ".join(missing_columns)
            raise ValueError(f"{path} is missing required columns: {missing_text}")

        for row_number, row in enumerate(reader, start=2):
            try:
                time_values.append(float(row["time_s"]))
                y_values.append(float(row[y_column]))
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{path} contains non-numeric data at row {row_number}") from exc

    if not time_values:
        raise ValueError(f"{path} contains no outlet history rows")

    return time_values, y_values


def _read_profile_series(csv_path: str | Path, y_column: str) -> ProfileSeries:
    path = Path(csv_path)
    required_columns = {"time_s", "position_m", y_column}
    series: ProfileSeries = defaultdict(list)

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = set(reader.fieldnames or [])
        missing_columns = sorted(required_columns - fieldnames)
        if missing_columns:
            missing_text = ", ".join(missing_columns)
            raise ValueError(f"{path} is missing required columns: {missing_text}")

        for row_number, row in enumerate(reader, start=2):
            try:
                time_s = float(row["time_s"])
                position_m = float(row["position_m"])
                value = float(row[y_column])
            except (TypeError, ValueError) as exc:
                raise ValueError(f"{path} contains non-numeric data at row {row_number}") from exc
            series[time_s].append((position_m, value))

    if not series:
        raise ValueError(f"{path} contains no profile rows")

    return series


def _select_times(
    available_times: list[float],
    times_s: Iterable[float] | None,
    max_profiles: int,
) -> list[float]:
    if times_s is not None:
        selected: list[float] = []
        for requested_time in times_s:
            nearest_time = min(available_times, key=lambda time_s: abs(time_s - requested_time))
            if nearest_time not in selected:
                selected.append(nearest_time)
        if not selected:
            raise ValueError("times_s must contain at least one value")
        return selected

    if max_profiles <= 0 or len(available_times) <= max_profiles:
        return available_times

    if max_profiles == 1:
        return [available_times[-1]]

    selected_indexes = {
        round(index * (len(available_times) - 1) / (max_profiles - 1))
        for index in range(max_profiles)
    }
    return [available_times[index] for index in sorted(selected_indexes)]
