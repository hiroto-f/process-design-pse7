"""Complete the component list in a methanation HYSYS template.

The script opens methanation.tpl through Aspen HYSYS COM Automation, adds the
components needed for methanation calculations, and saves the edited template.
By default it saves a copy next to the original template.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from connect_test.test import get_hysys_application


CC_INORGANIC = 100
CC_INORGANIC_GAS = 110
CC_ALKANE = 210


@dataclass(frozen=True)
class ComponentSpec:
    canonical_name: str
    component_class: int
    aliases: tuple[str, ...] = ()

    @property
    def names_to_try(self) -> tuple[str, ...]:
        return (self.canonical_name, *self.aliases)


DEFAULT_COMPONENTS = (
    ComponentSpec("Hydrogen", CC_INORGANIC_GAS, ("H2",)),
    ComponentSpec("Carbon Dioxide", CC_INORGANIC_GAS, ("CO2", "CarbonDioxide")),
    ComponentSpec("Methane", CC_ALKANE, ("CH4",)),
    ComponentSpec("Water", CC_INORGANIC, ("H2O",)),
    ComponentSpec("Carbon Monoxide", CC_INORGANIC_GAS, ("CO", "CarbonMonoxide")),
)


def log(message: str) -> None:
    print(f"[HYSYS COMPONENTS] {message}")


def normalize_name(name: str) -> str:
    return "".join(ch for ch in name.casefold() if ch.isalnum())


def as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        return list(value)
    return [value]


def collection_names(collection: Any) -> list[str]:
    try:
        names = as_list(collection.Names)
        return [str(name) for name in names]
    except Exception:
        pass

    names: list[str] = []
    try:
        count = int(collection.Count)
    except Exception:
        return names

    for index in range(count):
        try:
            item = collection.Item(index)
            names.append(str(item.Name))
        except Exception:
            continue

    return names


def first_collection_item(collection: Any, label: str) -> Any:
    count = int(collection.Count)
    if count < 1:
        raise RuntimeError(f"No {label} exists in the template.")

    for index in (0, 1):
        try:
            return collection.Item(index)
        except Exception:
            continue

    raise RuntimeError(f"Could not read the first {label}.")


def find_template_path(explicit_path: str | None) -> Path:
    if explicit_path:
        path = Path(explicit_path).expanduser()
        if not path.exists():
            raise FileNotFoundError(path)
        return path.resolve()

    documents = Path.home() / "Documents"
    matches = sorted(documents.rglob("methanation.tpl"))
    if not matches:
        raise FileNotFoundError(
            "methanation.tpl was not found under your Documents folder. "
            "Pass it explicitly with --template."
        )
    if len(matches) > 1:
        log("Multiple methanation.tpl files found; using the first one:")
        for match in matches:
            log(f"  {match}")

    return matches[0].resolve()


def output_path_for(template_path: Path, output: str | None, in_place: bool) -> Path:
    if in_place:
        return template_path
    if output:
        return Path(output).expanduser().resolve()
    return template_path.with_name(f"{template_path.stem}_components{template_path.suffix}")


def get_or_create_component_list(case: Any, component_list_name: str) -> Any:
    basis = case.BasisManager
    component_lists = basis.ComponentLists

    for index in range(int(component_lists.Count)):
        component_list = component_lists.Item(index)
        if normalize_name(str(component_list.Name)) == normalize_name(component_list_name):
            return component_list

    if int(component_lists.Count) > 0:
        component_list = first_collection_item(component_lists, "component list")
        log(f"Using existing component list: {component_list.Name}")
        return component_list

    try:
        component_lists.Add(component_list_name, 0)
    except Exception as exc:
        raise RuntimeError(
            "The template has no component list, and HYSYS did not allow one "
            f"to be created automatically: {exc}"
        ) from exc

    return first_collection_item(component_lists, "component list")


def component_exists(existing_names: Iterable[str], spec: ComponentSpec) -> bool:
    normalized_existing = {normalize_name(name) for name in existing_names}
    return any(normalize_name(name) in normalized_existing for name in spec.names_to_try)


def add_component(components: Any, spec: ComponentSpec) -> str:
    last_error: Exception | None = None

    for name in spec.names_to_try:
        try:
            components.Add(name, spec.component_class)
            return name
        except Exception as exc:
            last_error = exc

    raise RuntimeError(
        f"Could not add component {spec.canonical_name}. Last error: {last_error}"
    )


def complete_component_list(case: Any, component_list_name: str) -> tuple[list[str], list[str]]:
    basis = case.BasisManager
    component_list = get_or_create_component_list(case, component_list_name)
    components = component_list.Components

    added: list[str] = []
    skipped: list[str] = []

    basis.StartBasisChange()
    try:
        for spec in DEFAULT_COMPONENTS:
            existing_names = collection_names(components)
            if component_exists(existing_names, spec):
                skipped.append(spec.canonical_name)
                continue

            added_name = add_component(components, spec)
            added.append(added_name)
    finally:
        if basis.CanEndBasisChange:
            basis.EndBasisChange()

    return added, skipped


def open_template(app: Any, template_path: Path) -> Any:
    for index in range(int(app.SimulationCases.Count)):
        try:
            case = app.SimulationCases.Item(index)
            if Path(str(case.FullName)).resolve() == template_path:
                log(f"Using already open template: {case.FullName}")
                return case
        except Exception:
            continue

    log(f"Opening template: {template_path}")
    return app.SimulationCases.Open(str(template_path))


def save_case(case: Any, output_path: Path, in_place: bool) -> None:
    if in_place:
        log(f"Saving in place: {output_path}")
        case.Save()
        return

    log(f"Saving edited copy: {output_path}")
    try:
        case.SaveAs2(str(output_path), True)
    except Exception:
        case.SaveAs(str(output_path))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Add methanation components to methanation.tpl through HYSYS."
    )
    parser.add_argument(
        "--template",
        help="Path to methanation.tpl. If omitted, Documents is searched.",
    )
    parser.add_argument(
        "--output",
        help="Save path for the edited template. Default: methanation_components.tpl.",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite the original template instead of saving a copy.",
    )
    parser.add_argument(
        "--component-list",
        default="Methanation Components",
        help="Preferred component list name when a new list can be created.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    template_path = find_template_path(args.template)
    output_path = output_path_for(template_path, args.output, args.in_place)

    app, source, mode = get_hysys_application()
    log(f"Connected: {source} ({mode})")
    app.Visible = True

    case = open_template(app, template_path)
    case.Visible = True
    case.Activate()

    added, skipped = complete_component_list(case, args.component_list)
    save_case(case, output_path, args.in_place)

    if added:
        log("Added: " + ", ".join(added))
    if skipped:
        log("Already present: " + ", ".join(skipped))
    log("Done.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[HYSYS COMPONENTS] FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
