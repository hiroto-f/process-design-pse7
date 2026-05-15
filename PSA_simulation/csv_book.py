from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable


_MISSING = object()


def to_float(value, default=_MISSING) -> float:
    if value is None:
        if default is not _MISSING:
            return default
        raise ValueError("empty value")
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace("\ufeff", "")
    if text == "":
        if default is not _MISSING:
            return default
        raise ValueError("empty value")
    return float(text)


def csv_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.15g}"
    return str(value)


class Sheet:
    def __init__(self, name: str, rows: list[list[str]] | None = None):
        self.name = name
        self.rows = rows or []

    @classmethod
    def load(cls, path: Path) -> "Sheet":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return cls(path.stem, [row for row in csv.reader(handle)])

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerows([[csv_text(value) for value in row] for row in self.rows])

    def clear(self) -> None:
        self.rows = []

    def copy(self) -> "Sheet":
        return Sheet(self.name, [row[:] for row in self.rows])

    def _ensure_size(self, row: int, col: int) -> None:
        while len(self.rows) < row:
            self.rows.append([])
        for existing in self.rows:
            while len(existing) < col:
                existing.append("")

    def cell(self, row: int, col: int, default=""):
        r = row - 1
        c = col - 1
        if r < 0 or c < 0:
            raise IndexError("CSV cells are 1-based")
        if r >= len(self.rows) or c >= len(self.rows[r]):
            return default
        value = self.rows[r][c]
        return default if value == "" else value

    def number(self, row: int, col: int, default=_MISSING) -> float:
        return to_float(self.cell(row, col, None), default)

    def set_cell(self, row: int, col: int, value) -> None:
        self._ensure_size(row, col)
        self.rows[row - 1][col - 1] = value

    def range_values(self, row1: int, col1: int, row2: int, col2: int) -> list[list[str]]:
        return [
            [self.cell(row, col, "") for col in range(col1, col2 + 1)]
            for row in range(row1, row2 + 1)
        ]

    def set_range(self, row1: int, col1: int, values: Iterable[Iterable]) -> None:
        for r_offset, row_values in enumerate(values):
            for c_offset, value in enumerate(row_values):
                self.set_cell(row1 + r_offset, col1 + c_offset, value)


class CsvBook:
    def __init__(self, sheets: dict[str, Sheet] | None = None):
        self.sheets = sheets or {}

    @classmethod
    def load(cls, directory: Path | str) -> "CsvBook":
        base = Path(directory)
        sheets = {}
        for path in base.glob("*.csv"):
            sheets[path.stem] = Sheet.load(path)
        return cls(sheets)

    def sheet(self, name: str) -> Sheet:
        if name not in self.sheets:
            self.sheets[name] = Sheet(name)
        return self.sheets[name]

    def copy(self) -> "CsvBook":
        return CsvBook({name: sheet.copy() for name, sheet in self.sheets.items()})

    def replace_sheet(self, sheet: Sheet) -> None:
        self.sheets[sheet.name] = sheet

    def save(self, directory: Path | str) -> None:
        base = Path(directory)
        base.mkdir(parents=True, exist_ok=True)
        for name, sheet in self.sheets.items():
            sheet.save(base / f"{name}.csv")
