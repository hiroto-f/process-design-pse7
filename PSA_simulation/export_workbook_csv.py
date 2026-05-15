from __future__ import annotations

import argparse
import csv
from pathlib import Path


def export_workbook(workbook_path: Path, output_dir: Path) -> None:
    import win32com.client

    output_dir.mkdir(parents=True, exist_ok=True)
    excel = win32com.client.DispatchEx("Excel.Application")
    excel.Visible = False
    excel.DisplayAlerts = False
    try:
        workbook = excel.Workbooks.Open(str(workbook_path), ReadOnly=True)
        try:
            for worksheet in workbook.Worksheets:
                used = worksheet.UsedRange
                row_count = used.Rows.Count
                col_count = used.Columns.Count
                values = used.Value
                path = output_dir / f"{worksheet.Name}.csv"
                with path.open("w", encoding="utf-8-sig", newline="") as handle:
                    writer = csv.writer(handle)
                    for row in range(1, row_count + 1):
                        output_row = []
                        for col in range(1, col_count + 1):
                            if row_count == 1 and col_count == 1:
                                value = values
                            else:
                                value = values[row - 1][col - 1]
                            output_row.append("" if value is None else value)
                        writer.writerow(output_row)
                print(path)
        finally:
            workbook.Close(False)
    finally:
        excel.Quit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Export all Excel worksheets to CSV.")
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("PSA_simulation/csv_input"))
    args = parser.parse_args()
    export_workbook(args.workbook, args.output_dir)


if __name__ == "__main__":
    main()

