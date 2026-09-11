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
