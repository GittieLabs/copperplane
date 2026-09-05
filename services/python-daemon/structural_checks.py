"""Disagreements between a schematic and the footprints it assigns.

`SPEC-113`. ERC checks a schematic against itself and DRC checks a board
against its own rules. Neither compares a symbol against the footprint chosen
for it, so a two-pin `Device:LED` carrying a four-pin RGB footprint is
completely invisible: `kicad-cli pcb drc --schematic-parity --severity-all` on
the example project reports zero parity issues.

Deterministic on purpose. A symbol's pin count and a footprint's pad count are
facts in files on disk; asking a model to notice them is why the finding only
ever appeared when a user thought to ask for it. What this produces is the
fact and the counts -- what the disagreement *means* is the review's job, with
the component data `CTX-319.7` supplies.
"""
import logging
import os
import re

import kicad_board

logger = logging.getLogger(__name__)


class SchematicReadError(Exception):
    """Raised when a file is not a readable `.kicad_sch`."""


def _children(node, name):
    return [c for c in node if isinstance(c, list) and kicad_board.sym(c) == name]


def _property(node, name):
    """A symbol's `(property "Name" "value")`, or None."""
    for child in _children(node, "property"):
        pair = [item[1] for item in child[1:] if isinstance(item, tuple)]
        if len(pair) >= 2 and pair[0] == name:
            return pair[1]
    return None


def _pin_counts_by_lib_id(root) -> dict:
    """Every symbol definition embedded in the schematic, and its pin count.

    Read from the file's own `lib_symbols`, not from the user's installed
    libraries: what matters is the symbol this schematic actually contains.

    Pins live in a definition's unit sub-symbols (`Device:LED_1_1`), not on the
    definition itself, so both levels are counted. A multi-unit part spreads
    its pins across several units and they sum.
    """
    counts = {}
    for block in _children(root, "lib_symbols"):
        for definition in _children(block, "symbol"):
            name = kicad_board.value(definition)
            if name is None:
                continue
            pins = len(_children(definition, "pin"))
            for unit in _children(definition, "symbol"):
                pins += len(_children(unit, "pin"))
            counts[name] = pins
    return counts


def read_schematic_symbols(sch_path: str) -> list:
    """Every placed symbol, with its pin count and assigned footprint.

    `kicad_cli.export_schematic_bom` is deliberately not the source: it reports
    reference, value and footprint, and no pin count at all. It also omits
    parts excluded from the BOM, which on the example project is every
    mounting hole -- and this check has to see them to conclude they are fine.
    """
    if not os.path.exists(sch_path):
        raise SchematicReadError(f"Schematic file does not exist: {sch_path}")

    with open(sch_path, encoding="utf-8") as handle:
        top = kicad_board.parse(handle.read())

    if not top or kicad_board.sym(top[0]) != "kicad_sch":
        raise SchematicReadError(f"Not a KiCad schematic file: {sch_path}")

    root = top[0]
    pins_by_lib_id = _pin_counts_by_lib_id(root)

    symbols = []
    for node in _children(root, "symbol"):
        lib_id_node = _children(node, "lib_id")
        lib_id = kicad_board.value(lib_id_node[0]) if lib_id_node else None
        symbols.append({
            "reference": _property(node, "Reference"),
            "value": _property(node, "Value"),
            "lib_id": lib_id,
            "footprint": _property(node, "Footprint") or None,
            "pin_count": pins_by_lib_id.get(lib_id),
        })
    return symbols


#: `(pad "3" thru_hole ...)`. The number is quoted and may be empty; the type
#: follows it as a bare atom.
_PAD = re.compile(r'\(pad\s+"([^"]*)"\s+(\S+)')

#: Pads that are not electrical connections. A shield header's mounting holes
#: are drilled, not plated, and carry no pad number -- counting them is what
#: makes a correct 32-pin Arduino footprint look like a 36-pin one.
_UNPLATED = "np_thru_hole"


def count_numbered_plated_pads(footprint_path: str) -> int:
    """Distinct plated, numbered pads on a `.kicad_mod`.

    Distinct, because a footprint may repeat a pad number for two legs of the
    same electrical node. Numbered and plated, because anything else is
    mechanical.

    `footprint_detail._pads` looks like this function and is not: it counts
    every pad including unplated ones and never deduplicates, so it reports 36
    for `Module:Arduino_UNO_R3_WithMountingHoles` where this reports 32.
    """
    with open(footprint_path, encoding="utf-8") as handle:
        text = handle.read()
    return len({
        number
        for number, kind in _PAD.findall(text)
        if number and kind != _UNPLATED
    })


#: The finding's own type, so a reader can tell Copperplane's checks from
#: KiCad's. KiCad's own types are lowercase words like `power_pin_not_driven`;
#: this namespace makes the source unambiguous without relying on wording.
PIN_COUNT_MISMATCH = "copperplane.pin_count_mismatch"
FOOTPRINT_UNRESOLVED = "copperplane.footprint_not_found"


def check_pin_counts(sch_path: str, resolve_footprint=None) -> list:
    """Every symbol whose pin count disagrees with its footprint's pad count.

    Two exclusions carry the whole rule, and both were measured against the
    real example project rather than reasoned about:

    *   **A symbol with no footprint assigned is skipped.** That is the power
        symbols, and nothing else.
    *   **Unplated and unnumbered pads are not counted.** That is the Arduino
        shield's four mechanical holes, and nothing else.

    Mounting holes need no rule of their own, which the spec expected them to.
    `Mechanical:MountingHole` has zero pins and `MountingHole_2.2mm_M2` has
    zero numbered plated pads, so they agree and stay silent.

    A footprint that cannot be resolved reports that it could not be compared.
    Silence there would read as a clean part.

    Returns findings shaped like `kicad_cli`'s own, so
    `chat_agents._finding_for_agent` carries them without a second code path.
    """
    if resolve_footprint is None:  # imported lazily: kicad_bridge is optional
        import kicad_bridge

        resolve_footprint = kicad_bridge.resolve_footprint_model

    findings = []
    for symbol in read_schematic_symbols(sch_path):
        footprint_id = symbol.get("footprint")
        reference = symbol.get("reference")
        pins = symbol.get("pin_count")
        if not footprint_id or pins is None:
            continue

        try:
            path = (resolve_footprint(footprint_id) or {}).get("footprint_path")
        except Exception as exc:  # noqa: BLE001 -- reportable, never fatal
            logger.warning("footprint resolution failed for %s: %s", footprint_id, exc)
            path = None

        if not path or not os.path.exists(path):
            findings.append({
                "severity": "warning",
                "type": FOOTPRINT_UNRESOLVED,
                "description": (
                    f"{reference}'s footprint {footprint_id} is not installed, so its pad "
                    f"count could not be compared against the symbol's {pins} pins."
                ),
                "items": [{"description": f"Symbol {reference} [{symbol.get('lib_id')}]"}],
            })
            continue

        try:
            pads = count_numbered_plated_pads(path)
        except OSError as exc:
            logger.warning("footprint unreadable at %s: %s", path, exc)
            continue

        if pads == pins:
            continue

        findings.append({
            "severity": "warning",
            "type": PIN_COUNT_MISMATCH,
            "description": (
                f"{reference}'s symbol and footprint disagree about how many pins this part "
                f"has. The symbol {symbol.get('lib_id')} has {pins}; the footprint "
                f"{footprint_id} has {pads} numbered pads. Neither ERC nor DRC reports this."
            ),
            "items": [{
                "description": (
                    f"Symbol {reference} [{symbol.get('lib_id')}, {pins} pins] "
                    f"against footprint {footprint_id} [{pads} pads]"
                ),
            }],
        })
    return findings
