"""Create the methanation reaction set in a HYSYS template.

The reactions are based on the global reaction scheme discussed by
Xu and Froment for steam reforming, water-gas shift, and methanation.
For the methanation template, the relevant reverse directions are
registered as heterogeneous catalytic reactions.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Any

import pythoncom
from win32com.client import VARIANT

from connect_test.test import get_hysys_application
from hysys_methanation.complete_components import (
    CC_ALKANE,
    CC_INORGANIC,
    CC_INORGANIC_GAS,
    collection_names,
    find_template_path,
    normalize_name,
    open_template,
)
from hysys_methanation.create_property_package import (
    DEFAULT_COMPONENT_LIST_NAME,
    find_by_name,
    object_name,
)


REACTION_SET_TYPE_CANDIDATES = (0, "ReactionSet")
REACTION_PHASE_VAPOUR = 0
NO_TYPE_ARGUMENT = object()
GAS_CONSTANT_KJ_PER_KGMOLE_K = 8.314462618

DEFAULT_REACTION_SET_NAME = "Methanation Reactions"
DEFAULT_FLUID_PACKAGE_NAME = "Peng-Robinson"
HETEROGENEOUS_TYPE_KEYWORDS = (
    "heterogeneous",
    "catalytic",
    "langmuir",
    "hinshelwood",
    "lhkinetic",
)
HETEROGENEOUS_EXPECTED_PROPERTIES = (
    "Reactants",
    "ReactantStoichCoefValue",
    "BalanceStoichiometry",
    "ForwardFrequencyFactor",
    "DenominatorParametersValue",
)

COMPONENT_CLASSES = {
    "Hydrogen": CC_INORGANIC_GAS,
    "Carbon Dioxide": CC_INORGANIC_GAS,
    "Methane": CC_ALKANE,
    "Water": CC_INORGANIC,
    "Carbon Monoxide": CC_INORGANIC_GAS,
}

COMPONENT_ALIASES = {
    "Hydrogen": ("Hydrogen", "H2"),
    "Carbon Dioxide": ("Carbon Dioxide", "CO2", "CarbonDioxide"),
    "Methane": ("Methane", "CH4"),
    "Water": ("Water", "H2O"),
    "Carbon Monoxide": ("Carbon Monoxide", "CO", "CarbonMonoxide"),
}


@dataclass(frozen=True)
class ArrheniusSpec:
    frequency_factor: float
    activation_energy_kj_per_kgmole: float
    temperature_exponent: float = 0.0


@dataclass(frozen=True)
class EquilibriumConstantSpec:
    preexponential: float
    exponent_temperature_k: float


@dataclass(frozen=True)
class DenominatorTerm:
    frequency_factor: float
    activation_energy_kj_per_kgmole: float
    component_orders: tuple[tuple[str, float], ...]


@dataclass(frozen=True)
class KineticSpec:
    forward: ArrheniusSpec
    reverse: ArrheniusSpec
    forward_orders: tuple[tuple[str, float], ...]
    reverse_orders: tuple[tuple[str, float], ...]
    denominator_terms: tuple[DenominatorTerm, ...]
    denominator_exponent: float = 2.0


@dataclass(frozen=True)
class ReactionSpec:
    name: str
    stoichiometry: tuple[tuple[str, float], ...]
    base_component: str
    kinetics: KineticSpec
    note: str


def reverse_arrhenius_from_equilibrium(
    rate: ArrheniusSpec,
    equilibrium: EquilibriumConstantSpec,
) -> ArrheniusSpec:
    return ArrheniusSpec(
        frequency_factor=rate.frequency_factor / equilibrium.preexponential,
        activation_energy_kj_per_kgmole=(
            rate.activation_energy_kj_per_kgmole
            - GAS_CONSTANT_KJ_PER_KGMOLE_K * equilibrium.exponent_temperature_k
        ),
        temperature_exponent=rate.temperature_exponent,
    )


XU_K1_STEAM_REFORMING = ArrheniusSpec(4.225e15, 240100.0)
XU_K2_WATER_GAS_SHIFT = ArrheniusSpec(1.955e6, 67130.0)
XU_K3_OVERALL_REFORMING = ArrheniusSpec(1.020e15, 243900.0)

# K_i = A_eq * exp(-C_i / T), T in K, for the Xu-Froment forward directions.
XU_EQ1_STEAM_REFORMING = EquilibriumConstantSpec(1.198e17, 26830.0)
XU_EQ2_WATER_GAS_SHIFT = EquilibriumConstantSpec(1.767e-2, -4400.0)
XU_EQ3_OVERALL_REFORMING = EquilibriumConstantSpec(2.117e15, 22430.0)


XU_FROMENT_DENOMINATOR_TERMS = (
    DenominatorTerm(
        frequency_factor=8.23e-5,
        activation_energy_kj_per_kgmole=-70650.0,
        component_orders=(("Carbon Monoxide", 1.0),),
    ),
    DenominatorTerm(
        frequency_factor=6.12e-9,
        activation_energy_kj_per_kgmole=-82900.0,
        component_orders=(("Hydrogen", 1.0),),
    ),
    DenominatorTerm(
        frequency_factor=6.65e-4,
        activation_energy_kj_per_kgmole=-38280.0,
        component_orders=(("Methane", 1.0),),
    ),
    DenominatorTerm(
        frequency_factor=1.77e5,
        activation_energy_kj_per_kgmole=88680.0,
        component_orders=(("Water", 1.0), ("Hydrogen", -1.0)),
    ),
)


REACTION_SPECS = (
    ReactionSpec(
        name="CO2 Methanation",
        stoichiometry=(
            ("Carbon Dioxide", -1.0),
            ("Hydrogen", -4.0),
            ("Methane", 1.0),
            ("Water", 2.0),
        ),
        base_component="Carbon Dioxide",
        kinetics=KineticSpec(
            forward=reverse_arrhenius_from_equilibrium(
                XU_K3_OVERALL_REFORMING,
                XU_EQ3_OVERALL_REFORMING,
            ),
            reverse=XU_K3_OVERALL_REFORMING,
            forward_orders=(("Carbon Dioxide", 1.0), ("Hydrogen", 0.5)),
            reverse_orders=(
                ("Methane", 1.0),
                ("Water", 2.0),
                ("Hydrogen", -3.5),
            ),
            denominator_terms=XU_FROMENT_DENOMINATOR_TERMS,
        ),
        note="Reverse of Xu-Froment global reaction III.",
    ),
    ReactionSpec(
        name="Reverse Water-Gas Shift",
        stoichiometry=(
            ("Carbon Dioxide", -1.0),
            ("Hydrogen", -1.0),
            ("Carbon Monoxide", 1.0),
            ("Water", 1.0),
        ),
        base_component="Carbon Dioxide",
        kinetics=KineticSpec(
            forward=reverse_arrhenius_from_equilibrium(
                XU_K2_WATER_GAS_SHIFT,
                XU_EQ2_WATER_GAS_SHIFT,
            ),
            reverse=XU_K2_WATER_GAS_SHIFT,
            forward_orders=(("Carbon Dioxide", 1.0),),
            reverse_orders=(
                ("Carbon Monoxide", 1.0),
                ("Water", 1.0),
                ("Hydrogen", -1.0),
            ),
            denominator_terms=XU_FROMENT_DENOMINATOR_TERMS,
        ),
        note="Reverse of Xu-Froment water-gas shift reaction II.",
    ),
    ReactionSpec(
        name="CO Methanation",
        stoichiometry=(
            ("Carbon Monoxide", -1.0),
            ("Hydrogen", -3.0),
            ("Methane", 1.0),
            ("Water", 1.0),
        ),
        base_component="Carbon Monoxide",
        kinetics=KineticSpec(
            forward=reverse_arrhenius_from_equilibrium(
                XU_K1_STEAM_REFORMING,
                XU_EQ1_STEAM_REFORMING,
            ),
            reverse=XU_K1_STEAM_REFORMING,
            forward_orders=(("Carbon Monoxide", 1.0), ("Hydrogen", 0.5)),
            reverse_orders=(
                ("Methane", 1.0),
                ("Water", 1.0),
                ("Hydrogen", -2.5),
            ),
            denominator_terms=XU_FROMENT_DENOMINATOR_TERMS,
        ),
        note="Reverse of Xu-Froment steam reforming reaction I.",
    ),
)


def log(message: str) -> None:
    print(f"[HYSYS REACTIONS] {message}")


def existing_item(collection: Any, name: str) -> Any | None:
    try:
        return find_by_name(collection, name)
    except Exception:
        return None


def add_collection_item(
    collection: Any,
    name: str,
    type_candidates: tuple[Any, ...],
    label: str,
    validator: Any | None = None,
) -> tuple[Any, bool]:
    item = existing_item(collection, name)
    if item is not None:
        if validator is not None and not validator(item):
            raise RuntimeError(
                f"Existing {label} {name!r} does not have the expected HYSYS "
                "object type. Delete or rename it in HYSYS, then rerun this script."
            )
        return item, False

    errors: list[str] = []
    for item_type in type_candidates:
        try:
            if item_type is NO_TYPE_ARGUMENT:
                collection.Add(name)
            else:
                collection.Add(name, item_type)

            item = existing_item(collection, name)
            if item is not None and (validator is None or validator(item)):
                return item, True

            errors.append(f"{item_type!r}: created object had an unexpected type")
        except Exception as exc:
            errors.append(f"{item_type!r}: {exc}")

    detail = "; ".join(errors)
    raise RuntimeError(f"Could not create {label} {name!r}. Tried: {detail}")


def is_reaction_set(item: Any) -> bool:
    try:
        item.ActiveReactions
        item.AssociateFluidPackage
        return True
    except Exception:
        return False


def read_attr_status(item: Any, attr: str) -> tuple[bool, str]:
    try:
        value = getattr(item, attr)
    except Exception as exc:
        return False, str(exc)

    try:
        return True, type(value).__name__
    except Exception:
        return True, "OK"


def read_text_attr(item: Any, attr: str) -> str:
    ok, detail = read_attr_status(item, attr)
    if not ok:
        return f"<NG: {detail}>"
    try:
        value = getattr(item, attr)
        return str(value)
    except Exception as exc:
        return f"<NG: {exc}>"


def reaction_type_tokens(item: Any) -> str:
    values = [
        object_name(item),
        read_text_attr(item, "TypeName"),
        read_text_attr(item, "VisibleTypeName"),
        read_text_attr(item, "TaggedName"),
    ]
    return normalize_name(" ".join(values))


def reaction_diagnostics(item: Any) -> str:
    lines = [
        f"  object_name: {object_name(item)}",
        f"  python_class: {type(item).__name__}",
        f"  TypeName: {read_text_attr(item, 'TypeName')}",
        f"  VisibleTypeName: {read_text_attr(item, 'VisibleTypeName')}",
        f"  TaggedName: {read_text_attr(item, 'TaggedName')}",
        "  expected heterogeneous catalytic/LH properties:",
    ]

    for attr in HETEROGENEOUS_EXPECTED_PROPERTIES:
        ok, detail = read_attr_status(item, attr)
        status = "OK" if ok else "NG"
        lines.append(f"    {attr}: {status} ({detail})")

    return "\n".join(lines)


def is_heterogeneous_catalytic_reaction(item: Any) -> bool:
    tokens = reaction_type_tokens(item)
    if any(keyword in tokens for keyword in HETEROGENEOUS_TYPE_KEYWORDS):
        return True

    required = (
        "Reactants",
        "ReactantStoichCoefValue",
        "BalanceStoichiometry",
        "ForwardFrequencyFactor",
    )
    return all(read_attr_status(item, attr)[0] for attr in required)


def resolve_component_name(components: Any, logical_name: str) -> str:
    existing_names = collection_names(components)
    normalized_to_name = {normalize_name(name): name for name in existing_names}

    for candidate in COMPONENT_ALIASES[logical_name]:
        existing = normalized_to_name.get(normalize_name(candidate))
        if existing is not None:
            return existing

    raise RuntimeError(
        f"Component {logical_name!r} is not available. "
        "Run complete_components.py before creating reactions."
    )


def resolve_component_object(components: Any, logical_name: str) -> Any:
    component_name = resolve_component_name(components, logical_name)

    for index in range(int(components.Count)):
        component = components.Item(index)
        if normalize_name(object_name(component)) == normalize_name(component_name):
            return component

    try:
        return components.Item(component_name)
    except Exception as exc:
        raise RuntimeError(f"Could not read component {component_name!r}: {exc}") from exc


def add_reactant(reactants: Any, component_name: str, logical_name: str) -> Any:
    type_candidates = (
        COMPONENT_CLASSES[logical_name],
        0,
        "Reactant",
    )
    errors: list[str] = []

    for reactant_type in type_candidates:
        try:
            reactants.Add(component_name, reactant_type)
            break
        except Exception as exc:
            errors.append(f"{reactant_type!r}: {exc}")
    else:
        detail = "; ".join(errors)
        raise RuntimeError(f"Could not add reactant {component_name!r}. Tried: {detail}")

    for index in range(int(reactants.Count)):
        reactant = reactants.Item(index)
        try:
            if normalize_name(object_name(reactant.Component)) == normalize_name(
                component_name
            ):
                return reactant
        except Exception:
            continue

    return reactants.Item(int(reactants.Count) - 1)


def set_stoichiometric_coefficient(reactant: Any, coefficient: float) -> None:
    errors: list[str] = []
    for attr in ("StoichiometricCoefficientValue", "StoichiometricCoefficient"):
        try:
            setattr(reactant, attr, coefficient)
            return
        except Exception as exc:
            errors.append(f"{attr}: {exc}")

    raise RuntimeError(
        "Could not set stoichiometric coefficient on reactant "
        f"{object_name(reactant)!r}. Tried: {'; '.join(errors)}"
    )


def kinetic_component_names(spec: ReactionSpec) -> tuple[str, ...]:
    names: list[str] = []

    def append_unique(component_name: str) -> None:
        if normalize_name(component_name) not in {
            normalize_name(existing) for existing in names
        }:
            names.append(component_name)

    for component_name, _ in spec.stoichiometry:
        append_unique(component_name)
    for component_name, _ in spec.kinetics.forward_orders:
        append_unique(component_name)
    for component_name, _ in spec.kinetics.reverse_orders:
        append_unique(component_name)
    for term in spec.kinetics.denominator_terms:
        for component_name, _ in term.component_orders:
            append_unique(component_name)

    return tuple(names)


def set_scalar_value(reaction: Any, attr: str, value: float, label: str) -> None:
    try:
        setattr(reaction, attr, value)
    except Exception as exc:
        raise RuntimeError(f"Could not set {label} ({attr}) to {value}: {exc}") from exc


def set_optional_scalar_value(
    reaction: Any,
    attrs: tuple[str, ...],
    value: float,
    label: str,
) -> bool:
    errors: list[str] = []
    for attr in attrs:
        try:
            setattr(reaction, attr, value)
            return True
        except Exception as exc:
            errors.append(f"{attr}: {exc}")

    log(f"{label} could not be set. Tried: {'; '.join(errors)}")
    return False


def component_order_vector(
    component_order: tuple[str, ...],
    orders: tuple[tuple[str, float], ...],
) -> tuple[float, ...]:
    order_by_component = {
        normalize_name(component_name): exponent for component_name, exponent in orders
    }
    return tuple(
        order_by_component.get(normalize_name(component_name), 0.0)
        for component_name in component_order
    )


def denominator_parameter_rows(
    component_order: tuple[str, ...],
    terms: tuple[DenominatorTerm, ...],
) -> tuple[tuple[float, ...], ...]:
    rows: list[tuple[float, ...]] = []
    for term in terms:
        rows.append(
            (
                term.frequency_factor,
                term.activation_energy_kj_per_kgmole,
                *component_order_vector(component_order, term.component_orders),
            )
        )
    return tuple(rows)


def transpose(rows: tuple[tuple[float, ...], ...]) -> tuple[tuple[float, ...], ...]:
    if not rows:
        return ()
    return tuple(tuple(row[index] for row in rows) for index in range(len(rows[0])))


def flatten(rows: tuple[tuple[float, ...], ...]) -> tuple[float, ...]:
    return tuple(value for row in rows for value in row)


def as_lists(value: Any) -> Any:
    if isinstance(value, tuple):
        return [as_lists(item) for item in value]
    return value


def as_double_safearray(value: Any) -> Any:
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, value)


def as_variant_safearray(value: Any) -> Any:
    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_VARIANT, value)


def value_candidates(
    values: tuple[float, ...] | tuple[tuple[float, ...], ...],
) -> list[Any]:
    candidates: list[Any] = [values, as_lists(values)]

    if values and isinstance(values[0], tuple):
        rows = values  # type: ignore[assignment]
        base_candidates = [
            rows,
            transpose(rows),
            flatten(rows),
            flatten(transpose(rows)),
        ]
        candidates = []
        for candidate in base_candidates:
            candidates.append(candidate)
            candidates.append(as_lists(candidate))
            candidates.append(as_double_safearray(as_lists(candidate)))
            candidates.append(as_variant_safearray(as_lists(candidate)))
    else:
        candidates.append(as_double_safearray(as_lists(values)))
        candidates.append(as_variant_safearray(as_lists(values)))

    unique: list[Any] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = repr(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def set_flex_values(
    reaction: Any,
    value_attr: str,
    values: tuple[float, ...] | tuple[tuple[float, ...], ...],
    label: str,
    flex_attr: str | None = None,
) -> None:
    candidates = value_candidates(values)

    errors: list[str] = []
    for candidate in candidates:
        try:
            setattr(reaction, value_attr, candidate)
            return
        except Exception as exc:
            errors.append(f"{value_attr}={candidate!r}: {exc}")

    if flex_attr is not None:
        try:
            flex_variable = getattr(reaction, flex_attr)
            for candidate in candidates:
                try:
                    flex_variable.SetValues(candidate)
                    return
                except Exception as exc:
                    errors.append(f"{flex_attr}.SetValues({candidate!r}): {exc}")
                try:
                    flex_variable.SetValues(candidate, "")
                    return
                except Exception as exc:
                    errors.append(f"{flex_attr}.SetValues({candidate!r}, ''): {exc}")
                try:
                    flex_variable.Calculate(candidate)
                    return
                except Exception as exc:
                    errors.append(f"{flex_attr}.Calculate({candidate!r}): {exc}")
                try:
                    flex_variable.Calculate(candidate, "")
                    return
                except Exception as exc:
                    errors.append(f"{flex_attr}.Calculate({candidate!r}, ''): {exc}")
                try:
                    flex_variable.Values = candidate
                    return
                except Exception as exc:
                    errors.append(f"{flex_attr}.Values={candidate!r}: {exc}")
        except Exception as exc:
            errors.append(f"{flex_attr}: {exc}")

    raise RuntimeError(f"Could not set {label}. Tried: {'; '.join(errors)}")


def set_optional_flex_values(
    reaction: Any,
    value_attr: str,
    values: tuple[float, ...] | tuple[tuple[float, ...], ...],
    label: str,
    flex_attr: str | None = None,
) -> bool:
    try:
        set_flex_values(reaction, value_attr, values, label, flex_attr)
        return True
    except RuntimeError as exc:
        log(f"{label} could not be set automatically: {exc}")
        return False


def set_denominator_parameters(
    reaction: Any,
    rows: tuple[tuple[float, ...], ...],
    label: str,
) -> bool:
    errors: list[str] = []

    for row_count in range(1, len(rows) + 1):
        partial_rows = rows[:row_count]
        try:
            set_flex_values(
                reaction,
                "DenominatorParametersValue",
                partial_rows,
                f"{label} first {row_count} row(s)",
                "DenominatorParameters",
            )
        except RuntimeError as exc:
            errors.append(f"{row_count} row table: {exc}")
            if row_count == 1:
                try:
                    set_flex_values(
                        reaction,
                        "DenominatorParametersValue",
                        partial_rows[0],
                        f"{label} first row",
                        "DenominatorParameters",
                    )
                except RuntimeError as row_exc:
                    errors.append(f"single first row: {row_exc}")
                    break
            else:
                break

    try:
        set_flex_values(
            reaction,
            "DenominatorParametersValue",
            rows,
            label,
            "DenominatorParameters",
        )
        return True
    except RuntimeError as exc:
        errors.append(f"full table: {exc}")

    log(f"{label} could not be fully set automatically: {'; '.join(errors)}")
    return False


def configure_kinetics(reaction: Any, spec: ReactionSpec) -> None:
    kinetic = spec.kinetics
    component_order = kinetic_component_names(spec)

    set_scalar_value(
        reaction,
        "ForwardFrequencyFactor",
        kinetic.forward.frequency_factor,
        f"{spec.name} forward frequency factor",
    )
    set_scalar_value(
        reaction,
        "ForwardActivationEnergy",
        kinetic.forward.activation_energy_kj_per_kgmole,
        f"{spec.name} forward activation energy",
    )
    set_scalar_value(
        reaction,
        "ForwardTemperatureExponent",
        kinetic.forward.temperature_exponent,
        f"{spec.name} forward temperature exponent",
    )
    set_scalar_value(
        reaction,
        "ReverseFrequencyFactor",
        kinetic.reverse.frequency_factor,
        f"{spec.name} reverse frequency factor",
    )
    set_scalar_value(
        reaction,
        "ReverseActivationEnergy",
        kinetic.reverse.activation_energy_kj_per_kgmole,
        f"{spec.name} reverse activation energy",
    )
    set_scalar_value(
        reaction,
        "ReverseTemperatureExponent",
        kinetic.reverse.temperature_exponent,
        f"{spec.name} reverse temperature exponent",
    )

    set_flex_values(
        reaction,
        "ComponentForwardOrderValue",
        component_order_vector(component_order, kinetic.forward_orders),
        f"{spec.name} forward component orders",
        "ComponentForwardOrder",
    )
    set_flex_values(
        reaction,
        "ComponentReverseOrderValue",
        component_order_vector(component_order, kinetic.reverse_orders),
        f"{spec.name} reverse component orders",
        "ComponentReverseOrder",
    )
    denominator_set = set_denominator_parameters(
        reaction,
        denominator_parameter_rows(component_order, kinetic.denominator_terms),
        f"{spec.name} denominator parameters",
    )
    if denominator_set:
        set_optional_scalar_value(
            reaction,
            (
                "DenominatorExponentValue",
                "DenominatorExponent",
                "DenominatorPowerValue",
                "DenominatorPower",
            ),
            kinetic.denominator_exponent,
            f"{spec.name} denominator exponent",
        )


def configure_stoichiometry(reaction: Any, spec: ReactionSpec, components: Any) -> None:
    if not is_heterogeneous_catalytic_reaction(reaction):
        raise RuntimeError(
            f"{spec.name!r} is not a heterogeneous catalytic reaction. "
            "Delete the incomplete reaction object in HYSYS, then rerun this script.\n"
            + reaction_diagnostics(reaction)
        )

    reactants = reaction.Reactants

    try:
        reactants.RemoveAll()
    except Exception:
        pass

    stoichiometry = {
        normalize_name(logical_name): coefficient
        for logical_name, coefficient in spec.stoichiometry
    }

    for logical_name in kinetic_component_names(spec):
        coefficient = stoichiometry.get(normalize_name(logical_name), 0.0)
        component_name = resolve_component_name(components, logical_name)
        reactant = add_reactant(reactants, component_name, logical_name)
        set_stoichiometric_coefficient(reactant, coefficient)

    try:
        reaction.ReactantStoichCoefValue = tuple(
            stoichiometry.get(normalize_name(logical_name), 0.0)
            for logical_name in kinetic_component_names(spec)
        )
    except Exception:
        pass

    try:
        reaction.BaseComponent = resolve_component_object(components, spec.base_component)
    except Exception as exc:
        log(f"Base component could not be set for {spec.name}: {exc}")

    try:
        reaction.ReactionPhase = REACTION_PHASE_VAPOUR
    except Exception:
        pass

    try:
        reaction.BalanceStoichiometry()
    except Exception:
        pass

    configure_kinetics(reaction, spec)


def get_or_create_reaction_set(rpm: Any, reaction_set_name: str) -> tuple[Any, bool]:
    return add_collection_item(
        rpm.ReactionSets,
        reaction_set_name,
        REACTION_SET_TYPE_CANDIDATES,
        "reaction set",
        is_reaction_set,
    )


def get_existing_heterogeneous_reaction(
    rpm: Any,
    reaction_set: Any,
    spec: ReactionSpec,
) -> Any:
    for collection in (reaction_set.ActiveReactions, rpm.Reactions):
        existing = existing_item(collection, spec.name)
        if existing is not None:
            if is_heterogeneous_catalytic_reaction(existing):
                return existing
            raise RuntimeError(
                f"Existing reaction {spec.name!r} is not a heterogeneous "
                "catalytic reaction. Delete it or recreate it as a "
                "heterogeneous catalytic reaction in HYSYS.\n"
                "Actual values read from HYSYS:\n"
                + reaction_diagnostics(existing)
            )

    required_names = ", ".join(reaction.name for reaction in REACTION_SPECS)
    raise RuntimeError(
        f"Reaction {spec.name!r} was not found. In HYSYS GUI, create empty "
        "heterogeneous catalytic reactions with these exact names, then "
        "rerun this script: "
        f"{required_names}"
    )


def active_reaction_names(reaction_set: Any) -> set[str]:
    try:
        return {
            normalize_name(name)
            for name in collection_names(reaction_set.ActiveReactions)
        }
    except Exception:
        return set()


def ensure_reaction_active(reaction_set: Any, reaction: Any) -> None:
    reaction_name = object_name(reaction)
    if normalize_name(reaction_name) in active_reaction_names(reaction_set):
        return

    errors: list[str] = []
    for item_type in (
        NO_TYPE_ARGUMENT,
        589,
        "HeterogeneousCatalyticReaction",
        "LHKineticReaction",
        "Langmuir-Hinshelwood Reaction",
    ):
        try:
            if item_type is NO_TYPE_ARGUMENT:
                reaction_set.ActiveReactions.Add(reaction_name)
            else:
                reaction_set.ActiveReactions.Add(reaction_name, item_type)
            if normalize_name(reaction_name) in active_reaction_names(reaction_set):
                return
        except Exception as exc:
            errors.append(f"{item_type!r}: {exc}")

    raise RuntimeError(
        f"Could not add reaction {reaction_name!r} to reaction set "
        f"{object_name(reaction_set)!r}. Tried: {'; '.join(errors)}"
    )


def choose_fluid_package(case: Any, fluid_package_name: str) -> Any:
    fluid_packages = case.BasisManager.FluidPackages

    fluid_package = find_by_name(fluid_packages, fluid_package_name)
    if fluid_package is not None:
        return fluid_package

    if int(fluid_packages.Count) == 1:
        fluid_package = fluid_packages.Item(0)
        log(f"Using the only existing fluid package: {object_name(fluid_package)}")
        return fluid_package

    raise RuntimeError(
        f"Fluid package {fluid_package_name!r} was not found. "
        "Run create_property_package.py and select Peng-Robinson in the HYSYS GUI "
        "before creating reactions."
    )


def component_count(components: Any) -> int:
    try:
        return int(components.Count)
    except Exception:
        return 0


def choose_component_source(case: Any, fluid_package: Any, rpm: Any) -> Any:
    candidates: list[tuple[str, Any]] = []

    try:
        candidates.append(
            (
                f"{object_name(fluid_package)}.ComponentList.Components",
                fluid_package.ComponentList.Components,
            )
        )
    except Exception:
        pass

    try:
        candidates.append(
            (f"{object_name(fluid_package)}.Components", fluid_package.Components)
        )
    except Exception:
        pass

    try:
        component_list = find_by_name(
            case.BasisManager.ComponentLists,
            DEFAULT_COMPONENT_LIST_NAME,
        )
        if component_list is not None:
            candidates.append(
                (f"{object_name(component_list)}.Components", component_list.Components)
            )
    except Exception:
        pass

    try:
        candidates.append(("ReactionPackageManager.Components", rpm.Components))
    except Exception:
        pass

    for label, components in candidates:
        if component_count(components) > 0:
            log(f"Using components from {label}")
            return components

    raise RuntimeError(
        "No non-empty component source was found. Run complete_components.py, "
        "then create_property_package.py, before creating reactions."
    )


def validate_required_components(components: Any) -> None:
    missing: list[str] = []
    for logical_name in COMPONENT_ALIASES:
        try:
            resolve_component_name(components, logical_name)
        except Exception:
            missing.append(logical_name)

    if missing:
        raise RuntimeError(
            "Required components are missing from the selected component source: "
            + ", ".join(missing)
            + ". Run complete_components.py, then create_property_package.py, "
            "before creating reactions."
        )


def create_reaction_package(
    case: Any,
    reaction_set_name: str,
    fluid_package_name: str,
) -> tuple[Any, list[str], list[str]]:
    basis = case.BasisManager
    rpm = basis.ReactionPackageManager

    created: list[str] = []
    reused: list[str] = []

    basis.StartBasisChange()
    try:
        fluid_package = choose_fluid_package(case, fluid_package_name)

        reaction_set, reaction_set_created = get_or_create_reaction_set(
            rpm,
            reaction_set_name,
        )
        if reaction_set_created:
            created.append(object_name(reaction_set))
        else:
            reused.append(object_name(reaction_set))

        try:
            reaction_set.AssociateFluidPackage(fluid_package)
        except Exception as exc:
            log(f"Fluid package association skipped: {exc}")

        components = choose_component_source(case, fluid_package, rpm)
        validate_required_components(components)

        for spec in REACTION_SPECS:
            reaction = get_existing_heterogeneous_reaction(rpm, reaction_set, spec)
            configure_stoichiometry(reaction, spec, components)
            ensure_reaction_active(reaction_set, reaction)
            log(f"{spec.name}: {spec.note}")
            reused.append(object_name(reaction))
    finally:
        if basis.CanEndBasisChange:
            basis.EndBasisChange()

    return reaction_set, created, reused


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create the methanation reaction set in methanation.tpl."
    )
    parser.add_argument(
        "--template",
        help="Path to methanation.tpl. If omitted, Documents is searched.",
    )
    parser.add_argument(
        "--reaction-set",
        default=DEFAULT_REACTION_SET_NAME,
        help="Reaction set name to create or reuse.",
    )
    parser.add_argument(
        "--fluid-package",
        default=DEFAULT_FLUID_PACKAGE_NAME,
        help="Fluid package to associate with the reaction set.",
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

    reaction_set, created, reused = create_reaction_package(
        case,
        args.reaction_set,
        args.fluid_package,
    )

    log(f"Saving template: {template_path}")
    case.Save()

    if created:
        log("Created: " + ", ".join(created))
    if reused:
        log("Reused: " + ", ".join(reused))
    log(f"Reaction set ready: {object_name(reaction_set)}")
    log("Done.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[HYSYS REACTIONS] FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
