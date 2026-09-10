"""Packs: the domain knowledge, kept out of the machinery -- `SPEC-210` §2.

`SPEC-210`'s goal is that *"adding a second and third subject area is a data
file and a trigger rather than a rebuild"*. This module is the test of that
claim. A pack is three things, per §2.0.1: a **trigger** that names something
real, a **rule** that decides, and where a claim rests on a calculation, the
**arithmetic** shown.

`CTX-210.1` Phase 2 found the trap that shapes every rule here. A first version
of `led_series_resistor` asked *"is there a `D` on this net and no `R`"* and
fired on `GND`, because an LED's cathode sits on ground and no resistor does.
`GND` is real, so §2.2's trigger discipline passed it. The board was correct and
the claim was false.

**So every rule below keys on a fact KiCad states, never on a shape that looks
right.** `pinfunction` says `A_2` and `K_1`; a reference designator prefix says
almost nothing. Where a rule cannot be grounded in a stated fact it is a
`judgement`, and a judgement is never volunteered.
"""

import considerations as C

#: KiCad's own pin-name convention for a diode: anode `A`, cathode `K`. Read
#: from `pinfunction`, which is the symbol's own labelling rather than a guess
#: from the reference designator.
_ANODE = "A"


def _nodes_by_prefix(net: dict, prefix: str) -> list:
    return [n for n in net["nodes"] if (n.get("reference") or "").startswith(prefix)]


def led_series_resistor(nets: list) -> list:
    """Every LED anode net should reach a current-limiting resistor.

    `computed`: it is read from the netlist and is true or false. No source,
    because the netlist IS the source.

    Keyed on the **anode**, per the false positive above. A cathode on a ground
    net is correct and must stay silent.
    """
    raised = []
    for net in nets:
        anodes = [
            n for n in _nodes_by_prefix(net, "D")
            if (n.get("function") or "").startswith(_ANODE)
        ]
        if not anodes:
            continue
        if _nodes_by_prefix(net, "R"):
            continue
        refs = ", ".join(sorted({n["reference"] for n in anodes}))
        raised.append(C.make(
            id="led_without_series_resistor",
            domain="power",
            claim_class=C.COMPUTED,
            trigger={"kind": "net", "ref": net["name"], "parts": refs},
            explanation=(
                f"{refs}'s anode is on {net['name']}, and nothing on that net is a resistor. "
                f"An LED driven straight from a pin draws whatever the supply will give it, "
                f"which is usually more than the LED or the pin is rated for."
            ),
        ))
    return raised


# --- Withdrawn: power_pin_without_decoupling ---------------------------
#
# Written, run against the maintainer's real board, and removed the same hour.
# `CTX-210.1` Phase 5 keeps it as a comment rather than deleting it, because the
# reason it failed is the most useful thing this pack produced.
#
# The rule was "a `power_in` pin with no capacitor on its net". It raised two
# considerations on a correct board:
#
#   * `GND` -- because KiCad marks a ground pin `pintype="power_in"` exactly as
#     it marks a supply pin. `A1.7` is `GND_7`, `power_in`; `A1.8` is `VIN_8`,
#     `power_in`. **The netlist states no difference between a supply rail and
#     the ground reference**, so a rule about decoupling cannot tell which net
#     it is talking about.
#   * `+5V` -- a claim that is at best debatable: this board is an Arduino
#     shield, and the Arduino supplies and decouples that rail. "Add a
#     decoupling capacitor" is a judgement here, not a computed fact.
#
# The available fix is to match `GND` in the pin's name, which is a name
# heuristic dressed as a fact and breaks on the first symbol library that spells
# it differently. `SPEC-210` §2.2's discipline is that a claim rests on
# something the files state; there is nothing here to rest on.
#
# **What would make it buildable:** identifying the ground reference from
# something stated rather than spelled -- the schematic's own `power:GND` symbol
# rather than the netlist's flattened pin types. That is a real piece of work and
# it belongs to whoever writes the second real pack, not to a footnote here.

#: The registry. `SPEC-210`'s claim is that a new subject area is a row here
#: plus a function, not a rebuild.
#:
#: **The mechanism held and the rule did not, and those are different results.**
#: Adding a second pack cost exactly one function and one list entry, which is
#: the claim proven. That second pack was then withdrawn because it could not be
#: grounded in a stated fact -- see above. Cheap to add is not the same as safe
#: to ship, and §3's bar is the second one.
PACKS = {
    "power": [led_series_resistor],
}


def run(nets: list, domains: list = None) -> list:
    """Every pack's considerations for this project.

    Order is by `SPEC-210` §2.6's third option -- *"would this have built
    silently wrong"* -- approximated as computed before cited before judgement,
    since a computed claim is the one the user can go and check.
    """
    out = []
    for domain, packs in PACKS.items():
        if domains and domain not in domains:
            continue
        for pack in packs:
            out.extend(pack(nets))
    order = {C.COMPUTED: 0, C.CITED: 1, C.JUDGEMENT: 2}
    return sorted(out, key=lambda c: order.get(c["claim_class"], 9))
