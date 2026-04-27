"""Inspect Running Object Table entries related to Aspen HYSYS."""

from __future__ import annotations

import pythoncom
import win32com.client


HYSYS_CLSID = "{8F98FC8F-4853-4B46-AF78-FF008E09CF6E}"


def is_hysys_candidate(name: str) -> bool:
    upper_name = name.upper()
    return (
        "HYSYS" in upper_name
        or "ASPEN" in upper_name
        or ".HSC" in upper_name
        or ".TPL" in upper_name
        or HYSYS_CLSID.upper() in upper_name
    )


def try_print_attribute(obj: object, attr_name: str) -> None:
    try:
        value = getattr(obj, attr_name)
        print(f"    {attr_name}: OK ({type(value).__name__})")
    except Exception as exc:
        print(f"    {attr_name}: NG ({exc})")


def inspect_object(moniker: object, name: str, rot: object) -> None:
    print(f"\n[Candidate] {name}")

    try:
        raw_obj = rot.GetObject(moniker)
        print(f"  GetObject: OK ({type(raw_obj).__name__})")
    except Exception as exc:
        print(f"  GetObject: NG ({exc})")
        return

    try:
        dispatch_obj = raw_obj.QueryInterface(pythoncom.IID_IDispatch)
        print(f"  QueryInterface(IDispatch): OK ({type(dispatch_obj).__name__})")
    except Exception as exc:
        print(f"  QueryInterface(IDispatch): NG ({exc})")
        return

    try:
        obj = win32com.client.Dispatch(dispatch_obj)
        print(f"  Dispatch wrapper: OK ({type(obj).__name__})")
    except Exception as exc:
        print(f"  Dispatch wrapper: NG ({exc})")
        return

    for attr_name in (
        "Application",
        "Parent",
        "Name",
        "FullName",
        "Path",
        "Version",
        "Visible",
        "SimulationCases",
    ):
        try_print_attribute(obj, attr_name)


def main() -> int:
    pythoncom.CoInitialize()

    rot = pythoncom.GetRunningObjectTable()
    ctx = pythoncom.CreateBindCtx(0)
    monikers = rot.EnumRunning()

    found = False

    while True:
        batch = monikers.Next(1)
        if not batch:
            break

        moniker = batch[0]

        try:
            name = moniker.GetDisplayName(ctx, None)
        except Exception as exc:
            name = f"<could not read display name: {exc}>"

        print(name)

        if is_hysys_candidate(name):
            found = True
            inspect_object(moniker, name, rot)

    print()
    print("HYSYS/ASPEN found in ROT:", found)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
