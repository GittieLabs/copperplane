"""Reading a board's power chain -- `SPEC-211`.

Identification only. This module answers *which part is a linear regulator*
and *what does it put out*, and does not do the arithmetic; `SPEC-211` §3 is
emphatic that a wrong thermal claim is the worst output this pack can produce,
so the number that feeds it gets its own module and its own tests.

Every function here returns `None` rather than a default when it cannot answer.
That is `SPEC-211` §3's rule -- *"an unknown must produce silence rather than a
default"* -- expressed as a type rather than as a convention.
"""

import re

#: KiCad's own functional taxonomy, which is the classifier. `SPEC-211` §2.3
#: called identifying a regulator *"probably the largest unknown in this spec"*;
#: it is library membership, the same trick `SPEC-210` used for `Device:LED`.
#:
#: **The split between these two libraries is the point, not an implementation
#: detail.** Dissipation arithmetic applies to a linear regulator, which throws
#: the voltage difference away as heat. It is nonsense for a switching one,
#: which is what this pack *recommends* as the fix. A classifier that lumped
#: them together would confidently tell a user to go and buy the part they
#: already have.
LINEAR = "linear"
SWITCHING = "switching"

_LIBRARIES = {
    "Regulator_Linear": LINEAR,
    "Regulator_Switching": SWITCHING,
}

#: An output voltage encoded in the symbol name, read ONLY in the unambiguous
#: form: a trailing group containing a decimal point.
#:
#: Measured 2026-09-10 against KiCad's `Regulator_Linear` (1,626 symbols), and
#: the conservative rule is not caution for its own sake. 440 symbols end in a
#: numeric group; parsing all of them is wrong on roughly a third, and wrong in
#: the plausible direction rather than the absurd one:
#:
#:   * `LM317_SOT-223`, `LM317_TO-220`, `LM317L_SOT-89` -- package codes. These
#:     produce 223V, 220V, 89V, which at least look insane.
#:   * `APE8865N-12-HF-3` -- 125 symbols of this shape, where the trailing `-3`
#:     is a variant code and the real output is the `-12` in the middle, so the
#:     parse says 3V for a 1.2V part. Nothing about that reads as wrong.
#:   * `TC1262-33`, `AP1117-50` -- the decimal-elided convention, where `-33`
#:     means 3.3V. Indistinguishable from a genuine 33V part without a rule
#:     this module has no grounds to invent.
#:
#: Restricting to an explicit decimal point yields 226 symbols spanning 1.0V to
#: 10.0V, with no package-code collisions at all, and it keeps the case that
#: actually matters: `AMS1117-3.3`, 52 symbols at 3.3V, the regulator on every
#: maker's first board.
_NAME_ENCODED_VOLTS = re.compile(r"-(\d+\.\d+)$")

#: A linear regulator outside this range is not impossible -- an LM317 reaches
#: 37V -- but a name-encoded value outside it is far more likely to be
#: something this module has misread. The belt to `_NAME_ENCODED_VOLTS`'
#: braces, and the measured spread sits entirely inside it.
_PLAUSIBLE_OUTPUT_VOLTS = (0.8, 24.0)


def library_of(lib_id: str) -> str:
    """The library half of a `lib_id`, which is the half that classifies."""
    return (lib_id or "").split(":")[0]


def regulator_kind(lib_id: str):
    """`LINEAR`, `SWITCHING`, or `None` for anything that is not a regulator.

    Checks the **library**, never the whole id and never the value string.
    `CTX-326.3` shipped a defect by matching a whole id where it meant a
    library, and `component_without_value` reads values precisely because a
    value is user-authored and unreliable -- a part named `AMS1117` in a
    `Device:` symbol is not a regulator record, whatever it is called.
    """
    return _LIBRARIES.get(library_of(lib_id))


def output_volts(lib_id: str):
    """The regulator's output voltage if its NAME states it, else `None`.

    `None` is a real answer here and the common one: an adjustable `AMS1117`
    genuinely has no fixed output, and 1,400 of the library's 1,626 symbols do
    not encode one. Returning a default would invent the input to an arithmetic
    claim about someone's board, which is `SPEC-211` §3's named worst case.
    """
    if regulator_kind(lib_id) is None:
        return None
    match = _NAME_ENCODED_VOLTS.search(lib_id.split(":")[-1])
    if not match:
        return None
    volts = float(match.group(1))
    low, high = _PLAUSIBLE_OUTPUT_VOLTS
    return volts if low <= volts <= high else None


def pin_role(pintype: str) -> str:
    """The electrical role from a netlist node's `pintype`.

    **`pintype` is a compound string and an equality test silently undercounts.**
    The real values include `power_out+no_connect`, `power_in+no_connect` and
    `bidirectional+no_connect`; `pintype == "power_out"` drops every unconnected
    power pin and raises nothing while doing it. Measured on five real boards,
    `CTX-211.1` Phase 1.
    """
    return (pintype or "").split("+")[0]


def regulators(symbols: list) -> list:
    """Every linear regulator among a schematic's symbols, with what is known.

    Switching regulators are deliberately absent: this pack has nothing true to
    say about them, and `SPEC-210` §2.2 forbids a consideration that does not
    name something real.

    A board with no regulator yields an empty list, which is the ordinary case
    rather than an error. Measured Phase 1: none of the five boards available to
    this project carries a discrete linear regulator at all.
    """
    found = []
    for symbol in symbols:
        lib_id = symbol.get("lib_id") or ""
        if regulator_kind(lib_id) != LINEAR:
            continue
        reference = symbol.get("reference")
        if not reference:
            # Nothing to name, so nothing can be claimed. `SPEC-210` §2.2.
            continue
        found.append({
            "reference": reference,
            "lib_id": lib_id,
            "output_volts": output_volts(lib_id),
        })
    return found


#: Ground, identified by NAME and never by pin type.
#:
#: **Pin type cannot do this job, measured 2026-09-10.** A ground pin is typed
#: `power_in` on `Arduino_UNO_R3` and `Adafruit-Feather-ESP32-S3`, and
#: `power_out` on `XIAO_ESP32-S3` -- the same electrical node, opposite
#: declarations, on three boards in the same project. Any rule that reads
#: "power_in means a supply input" silently treats every Arduino's ground as
#: one, and the finding it builds is about the wrong pin.
_GROUND_NAMES = frozenset({
    "GND", "AGND", "DGND", "GNDA", "GNDD", "GNDPWR", "GNDREF", "VSS", "VSSA",
    "EARTH", "COMMON",
})

#: Names that state a ROLE rather than a voltage. `VIN` is the unregulated
#: input, `VBUS` happens to be 5V by USB convention and `VBAT` is whatever the
#: cell is -- none of them is a number this module may assert.
_ROLE_ONLY_NAMES = frozenset({
    "VIN", "VBUS", "VBAT", "VCC", "VDD", "VDDA", "VVCC", "PWR", "POWER", "V+",
})

#: KiCad's pin names carry a `_<pin number>` suffix on a module symbol:
#: `+5V_5`, `3V3_4`, `VIN_8`. Strip it before reading a name.
_PIN_NUMBER_SUFFIX = re.compile(r"_\d+$")

#: `3V3` and `1V8` -- the V-as-decimal-point convention, and the common form.
_V_AS_POINT = re.compile(r"^\+?(\d+)V(\d+)$")
#: `5V`, `3.3V`, `+9V`.
_PLAIN_VOLTS = re.compile(r"^\+?(\d+(?:\.\d+)?)V$")


def pin_name(node: dict) -> str:
    """What a netlist node's pin is CALLED, upper-cased.

    `pinfunction` where the symbol supplies one, and the pin number where it
    does not. **The fallback is not defensive coding.** `XIAO_ESP32-S3` has no
    `pinfunction` on any pin, and its pins are *numbered* `5V`, `3V3` and `GND`
    -- so a rule keyed only on `pinfunction` reads nothing at all from that
    board, silently, and looks like a board with no power pins.
    """
    raw = node.get("function") or node.get("pin") or ""
    return _PIN_NUMBER_SUFFIX.sub("", str(raw).strip()).upper()


def is_ground(name: str) -> bool:
    return name.strip().upper().lstrip("/") in _GROUND_NAMES


def nominal_volts(name: str):
    """The voltage a rail or pin NAME states, or `None` if it states none.

    `None` for `VIN`, `VBUS`, `VCC` and friends. Those are roles, and a USB
    `VBUS` being 5V in practice is not the same kind of fact as a net the user
    labelled `+5V` -- one is this module reciting a convention, the other is
    reading what is written on the schematic.
    """
    text = (name or "").strip().upper().lstrip("/")
    if not text or text in _ROLE_ONLY_NAMES or is_ground(text):
        return None
    match = _V_AS_POINT.match(text)
    if match:
        return float(f"{match.group(1)}.{match.group(2)}")
    match = _PLAIN_VOLTS.match(text)
    if match:
        return float(match.group(1))
    return None


def module_power_pins(nets: list) -> dict:
    """Per reference, the non-ground power pins a schematic declares.

    Returns `{reference: {"supplies": [...], "outputs": [...]}}`, each entry
    `{"pin", "name", "net", "volts", "net_volts"}` -- see the comment below on
    why a pin carries two voltages and which one means what. A part appears only if it has at least
    one of each, which is the shape of a thing that takes power in and makes a
    different rail out of it -- a dev board module, in practice, on every board
    measured.
    """
    found = {}
    for net in nets:
        for node in net.get("nodes", []):
            role = pin_role(node.get("type"))
            if role not in ("power_in", "power_out"):
                continue
            name = pin_name(node)
            if is_ground(name):
                continue
            reference = node.get("reference")
            if not reference:
                continue
            entry = found.setdefault(reference, {"supplies": [], "outputs": []})
            bucket = "supplies" if role == "power_in" else "outputs"
            net_name = net.get("name") or ""
            entry[bucket].append({
                "pin": node.get("pin"),
                "name": name,
                "net": net_name,
                # TWO voltages, and reading the wrong one makes this whole pack
                # silent. `volts` is what the PIN declares -- what the module
                # says it makes on an output. `net_volts` is what the RAIL is
                # labelled -- what the user says they are feeding it.
                #
                # A supply pin is named for its role (`VIN`) and so has no
                # voltage of its own; all its information is in the net. An
                # output pin is the reverse. Caught by running against a real
                # board, where the pack found nothing on the one case it was
                # written for.
                "volts": nominal_volts(name),
                "net_volts": nominal_volts(net_name),
            })
    return {
        ref: entry for ref, entry in found.items()
        if entry["supplies"] and entry["outputs"]
    }


def _net_is_real(net_name: str) -> bool:
    """KiCad names an unconnected pin's net `unconnected-(REF-PIN-PadN)`."""
    return bool(net_name) and not net_name.startswith("unconnected-")
