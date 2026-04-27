"""Aspen HYSYS connection test.

This script checks whether Python can connect to Aspen HYSYS through COM.
It first tries to attach to an already running HYSYS instance, then tries to
start HYSYS if no running instance is found.
"""

from __future__ import annotations

import sys
from typing import Any


HYSYS_CLSID = "{8F98FC8F-4853-4B46-AF78-FF008E09CF6E}"

PROG_IDS = (
    "HYSYS.Application",
    "HYSYS.Application.Latest",
    "HYSYS.Application.V14.0",
    "HYSYS.Application.NewInstance",
    "HYSYS.Application.NewInstance.Latest",
    "HYSYS.Application.NewInstance.V14.0",
)


APP_ATTRIBUTE_CANDIDATES = (
    (),
    ("Application",),
    ("Parent",),
    ("Application", "Parent"),
    ("Parent", "Application"),
)


def print_step(message: str) -> None:
    print(f"[HYSYS TEST] {message}")


def has_application_shape(obj: Any) -> bool:
    for attr_name in ("Version", "SimulationCases", "Visible"):
        try:
            getattr(obj, attr_name)
            return True
        except Exception:
            pass

    return False


def follow_attributes(obj: Any, attributes: tuple[str, ...]) -> Any:
    current = obj
    for attr_name in attributes:
        current = getattr(current, attr_name)
    return current


def get_hysys_from_rot(pythoncom: Any, win32com_client: Any) -> tuple[Any, str] | None:
    rot = pythoncom.GetRunningObjectTable()
    ctx = pythoncom.CreateBindCtx(0)
    monikers = rot.EnumRunning()

    while True:
        batch = monikers.Next(1)
        if not batch:
            break

        moniker = batch[0]

        try:
            name = moniker.GetDisplayName(ctx, None)
        except Exception:
            name = ""

        upper_name = name.upper()
        is_hysys_candidate = (
            "HYSYS" in upper_name
            or "ASPEN" in upper_name
            or ".HSC" in upper_name
            or ".TPL" in upper_name
            or HYSYS_CLSID.upper() in upper_name
        )
        if not is_hysys_candidate:
            continue

        try:
            raw_obj = rot.GetObject(moniker)
            dispatch_obj = raw_obj.QueryInterface(pythoncom.IID_IDispatch)
            obj = win32com_client.Dispatch(dispatch_obj)
        except Exception:
            continue

        for attributes in APP_ATTRIBUTE_CANDIDATES:
            try:
                app = follow_attributes(obj, attributes)
                if has_application_shape(app):
                    suffix = ".".join(attributes) if attributes else "object"
                    return app, f"ROT moniker: {name} -> {suffix}"
            except Exception:
                continue

    return None


def get_hysys_application() -> tuple[Any, str, str]:
    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise RuntimeError(
            "pywin32 is not installed. Install it with: pip install pywin32"
        ) from exc

    pythoncom.CoInitialize()

    errors: list[str] = []
    for prog_id in PROG_IDS:
        try:
            app = win32com.client.GetActiveObject(prog_id)
            return app, prog_id, "attached to running instance"
        except Exception as exc:
            errors.append(f"{prog_id} GetActiveObject: {exc}")

    rot_result = get_hysys_from_rot(pythoncom, win32com.client)
    if rot_result is not None:
        app, source = rot_result
        return app, source, "attached through Running Object Table"

    errors.append("ROT lookup: HYSYS-like entries were not usable as Application objects")

    for prog_id in PROG_IDS:
        try:
            app = win32com.client.Dispatch(prog_id)
            return app, prog_id, "started new instance"
        except Exception as exc:
            errors.append(f"{prog_id} Dispatch: {exc}")

    details = "\n".join(f"- {error}" for error in errors)
    raise RuntimeError(f"Could not connect to Aspen HYSYS through COM.\n{details}")


def main() -> int:
    print_step("Starting connection test...")

    try:
        app, prog_id, mode = get_hysys_application()
    except Exception as exc:
        print_step("FAILED")
        print(exc)
        return 1

    print_step("CONNECTED")
    print(f"ProgID: {prog_id}")
    print(f"Mode: {mode}")

    try:
        app.Visible = True
        print("Visible: True")
    except Exception as exc:
        print(f"Visible: could not set ({exc})")

    try:
        version = app.Version
        print(f"Version: {version}")
    except Exception as exc:
        print(f"Version: could not read ({exc})")

    try:
        case_count = app.SimulationCases.Count
        print(f"Open simulation cases: {case_count}")
    except Exception as exc:
        print(f"Open simulation cases: could not read ({exc})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
