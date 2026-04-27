"""Create a Peng-Robinson property package in a HYSYS template."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from connect_test.test import get_hysys_application
from hysys_methanation.complete_components import (
    first_collection_item,
    find_template_path,
    normalize_name,
    open_template,
)


PPKG_PENG_ROBINSON = 5891
DEFAULT_PACKAGE_NAME = "Peng-Robinson"
DEFAULT_COMPONENT_LIST_NAME = "Methanation Components"


def log(message: str) -> None:
    print(f"[HYSYS PROPERTY PACKAGE] {message}")


def find_by_name(collection: Any, name: str) -> Any | None:
    target = normalize_name(name)
    for index in range(int(collection.Count)):
        item = collection.Item(index)
        if normalize_name(str(item.Name)) == target:
            return item
    return None


def get_component_list(case: Any, component_list_name: str) -> Any:
    component_lists = case.BasisManager.ComponentLists

    component_list = find_by_name(component_lists, component_list_name)
    if component_list is not None:
        return component_list

    if int(component_lists.Count) < 1:
        raise RuntimeError(
            "No component list exists. Run complete_components.py before "
            "creating the property package."
        )

    component_list = first_collection_item(component_lists, "component list")
    log(f"Using existing component list: {component_list.Name}")
    return component_list


def get_or_create_peng_robinson_package(case: Any, package_name: str) -> tuple[Any, bool]:
    fluid_packages = case.BasisManager.FluidPackages

    fluid_package = find_by_name(fluid_packages, package_name)
    if fluid_package is not None:
        return fluid_package, False

    fluid_packages.Add(package_name, PPKG_PENG_ROBINSON)
    fluid_package = find_by_name(fluid_packages, package_name)
    if fluid_package is None:
        fluid_package = first_collection_item(fluid_packages, "fluid package")

    return fluid_package, True


def assign_component_list(fluid_package: Any, component_list: Any) -> None:
    try:
        fluid_package.ComponentList = component_list
    except Exception as exc:
        raise RuntimeError(
            f"Could not assign component list {component_list.Name} "
            f"to fluid package {fluid_package.Name}: {exc}"
        ) from exc


def create_property_package(
    case: Any,
    package_name: str,
    component_list_name: str,
) -> tuple[Any, bool]:
    basis = case.BasisManager

    basis.StartBasisChange()
    try:
        component_list = get_component_list(case, component_list_name)
        fluid_package, created = get_or_create_peng_robinson_package(case, package_name)
        assign_component_list(fluid_package, component_list)

        try:
            fluid_package.PropertyPackageName = "Peng-Robinson"
        except Exception:
            pass
    finally:
        if basis.CanEndBasisChange:
            basis.EndBasisChange()

    return fluid_package, created


def save_case(case: Any, template_path: Path) -> None:
    log(f"Saving template: {template_path}")
    case.Save()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a Peng-Robinson property package in methanation.tpl."
    )
    parser.add_argument(
        "--template",
        help="Path to methanation.tpl. If omitted, Documents is searched.",
    )
    parser.add_argument(
        "--package-name",
        default=DEFAULT_PACKAGE_NAME,
        help="Fluid package name to create or reuse.",
    )
    parser.add_argument(
        "--component-list",
        default=DEFAULT_COMPONENT_LIST_NAME,
        help="Component list to assign to the property package.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    template_path = find_template_path(args.template)

    app, source, mode = get_hysys_application()
    log(f"Connected: {source} ({mode})")
    app.Visible = True

    case = open_template(app, template_path)
    case.Visible = True
    case.Activate()

    fluid_package, created = create_property_package(
        case,
        args.package_name,
        args.component_list,
    )
    save_case(case, template_path)

    action = "Created" if created else "Reused"
    log(f"{action}: {fluid_package.Name}")
    try:
        log(f"Property package: {fluid_package.PropertyPackageName}")
    except Exception:
        log("Property package: Peng-Robinson")
    log("Done.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[HYSYS PROPERTY PACKAGE] FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
