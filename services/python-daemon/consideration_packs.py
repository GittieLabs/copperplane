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
import power_path as P

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
            # SPEC-343 §2.7's second constraint: a pack whose trigger is simply
            # absent has taught nothing. "This net has no LED missing a
            # resistor" is true, useless and faintly absurd.
            continue
        resistors = _nodes_by_prefix(net, "R")
        if resistors:
            # SPEC-343 §2.7: the reason this pack stays quiet is a computed fact
            # about THIS board, and it was being calculated and thrown away.
            # SPEC-210 §2.3 says reinforcement needs a baseline; the finding
            # that was not raised IS the baseline.
            led = ", ".join(sorted({n["reference"] for n in anodes}))
            res = ", ".join(sorted({n["reference"] for n in resistors}))
            raised.append(C.cleared(
                id="led_series_resistor",
                domain="power",
                trigger={"kind": "net", "ref": net["name"], "parts": led},
                explanation=(
                    f"{led}'s anode reaches {res} on {net['name']} — that resistor is what "
                    f"stops the LED drawing more current than the pin driving it can give."
                ),
            ))
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

# --- Absence-shaped triggers (SPEC-343 §2.6) ---------------------------
#
# What a novice is missing is usually a part, or a number, that is not there.
# So the trigger is an empty set rather than a present thing -- and `SPEC-210`
# §2.2 still applies unchanged: it must name something real.
#
# **The rule that makes an absence sayable: it must be an absence OF something,
# ON something the files name.** "No capacitor on `+5V`" names `+5V`. "`R1` has
# no value" names `R1`. "No ESD protection" names nothing, so it is not said,
# however true it might be.
#
# `CTX-343.1` Phase 5 measured the obvious version of this first and it was
# badly wrong. KiCad writes a symbol's own name into its value property by
# default, so "value equals the symbol name" looks like a perfect
# never-set detector -- and on the maintainer's correct board it matches **all
# eleven symbols**: `power:GND` whose value `GND` is right, four
# `Mechanical:MountingHole` which have no value to set, and
# `MCU_Module:Arduino_UNO_R3` whose value IS its part name.
#
# So the rule is narrowed to the only case where a value is an electrical
# parameter that something downstream computes with. On the same board that
# raises exactly one: `R1`.

#: Symbols whose `value` is a number the app would calculate from. A closed
#: list, not a prefix match: `Device:R_Potentiometer` is a resistor whose value
#: means something different, and guessing from the name is how the eleven
#: false positives above happened.
_VALUE_IS_A_PARAMETER = {
    "Device:R", "Device:R_Small", "Device:R_US",
    "Device:C", "Device:C_Small", "Device:C_Polarized", "Device:C_Polarized_Small",
    "Device:L", "Device:L_Small",
}


def component_without_value(symbols: list) -> list:
    """A passive still carrying KiCad's placeholder value.

    `computed`: the schematic states the symbol and states the value, and the
    two being equal is a fact rather than an inference.

    This is the absence that `SPEC-343` §2.5.2 found blocking a real answer. On
    the maintainer's board `R1` is `Device:R` with value `R`, so there is no
    resistance, so no current can be derived, so `SPEC-210` §2.5's promised
    estimate cannot run. The consideration converts *"we cannot help"* into
    *"set this and it becomes answerable"*, which is the whole argument for
    absence-shaped triggers.
    """
    raised = []
    for symbol in symbols:
        lib_id = symbol.get("lib_id") or ""
        if lib_id not in _VALUE_IS_A_PARAMETER:
            continue
        value = (symbol.get("value") or "").strip()
        leaf = lib_id.split(":")[-1]
        if value and value != leaf:
            continue
        reference = symbol.get("reference")
        if not reference:
            # No reference, nothing named, no consideration. SPEC-210 §2.2.
            continue
        raised.append(C.make(
            id="component_without_value",
            domain="power",
            claim_class=C.COMPUTED,
            trigger={"kind": "reference", "ref": reference, "lib_id": lib_id},
            explanation=(
                f"{reference} still has KiCad's placeholder value ({value or 'empty'}). "
                f"Until it says what it actually is, nothing here can work out what this "
                f"circuit draws — and that is what a trace width and a power budget both "
                f"rest on."
            ),
        ))
    return raised


def regulated_rail_into_module_input(nets: list) -> list:
    """A module is being fed the voltage it makes itself -- `SPEC-211` §2.0.

    **This is the pack that speaks about the boards this project actually has.**
    `CTX-211.1` Phase 1 measured that none of the five carries a discrete linear
    regulator, so the regulator every maker's first board really does have is
    the one inside the dev board they plugged into. `SPEC-211` §1's arithmetic
    applies to it exactly; what does not apply is the datasheet, because this
    app does not hold the Arduino's.

    So the claim is built from what the SYMBOL declares and nothing else. A part
    with a `VIN` pin and a separate `+5V` pin is telling us, in the schematic,
    that those are different pins with different jobs. Connecting a rail
    labelled `+5V` to the first one is worth asking about, and asking needs no
    datasheet at all.

    **It asks rather than asserts**, which is `SPEC-211` §2.4's shape and the
    part of §2.4 that survived the netlist landing. The app cannot see inside
    the module. A buck-boost converter would accept 5V on `VIN` quite happily,
    so a flat "this is wrong" would be confidently wrong on a real design --
    §3's named worst case. What the app can see is that the user connected a
    rail to the input pin while the pin that makes that same voltage sits
    unconnected, and that is a question worth putting.

    `computed`: every fact is read from the file. The net name, the pin names,
    the pin roles and which pins are unconnected are all in the netlist.
    """
    raised = []
    for reference, pins in sorted(P.module_power_pins(nets).items()):
        made = [o for o in pins["outputs"] if o["volts"] is not None]
        if not made:
            continue
        highest = max(o["volts"] for o in made)
        for supply in pins["supplies"]:
            rail = supply["net_volts"]
            if rail is None or not P._net_is_real(supply["net"]):
                continue
            if rail > highest:
                # Headroom above everything the module makes. Nothing to say.
                continue
            same = [o for o in made if o["volts"] == rail]
            spare = [o for o in same if not P._net_is_real(o["net"])]
            also = ""
            if spare:
                pin_list = " and ".join(f"pin {o['pin']}" for o in spare)
                also = (
                    f" Its own {rail:g}V pin ({pin_list}) is not connected to "
                    f"anything."
                )
            raised.append(C.make(
                id="regulated_rail_into_module_input",
                domain="power",
                claim_class=C.COMPUTED,
                trigger={
                    "kind": "net",
                    "ref": supply["net"],
                    "reference": reference,
                    "pin": supply["pin"],
                },
                explanation=(
                    f"{reference} pin {supply['pin']} is its {supply['name']} pin, and you "
                    f"have the {supply['net']} rail on it. This part also declares a "
                    f"{highest:g}V output pin of its own, which means {supply['name']} is "
                    f"the input that feeds whatever makes that — so the two are not "
                    f"interchangeable.{also} A supply going into {supply['name']} normally "
                    f"has to sit above the voltage the board produces from it. Is "
                    f"{supply['net']} what you meant here?"
                ),
            ))
    return raised

def regulator_dissipation(project: dict) -> list:
    """What a linear regulator throws away as heat -- `SPEC-211` §2.1 item 1.

    `(Vin - Vout) x Iout`, from three facts that live in three different places:
    `Vout` from the symbol name, `Vin` from the rail the netlist proves reaches
    the part, `Iout` from what the user said the board draws. Every one of them
    is named in the explanation, per `SPEC-211` §2.2 -- *"a finding built on the
    user's guess says so and a finding built on the app's estimate says so"*.

    **It states the watts and refuses to state a temperature, and that is the
    spec being corrected rather than implemented.** `SPEC-211` §1 says the
    sentence to put in front of the user is the ceiling -- *"your 1A regulator
    is a 130mA regulator on this supply"* -- which needs a thermal resistance.

    Measured 2026-09-10: **this app holds no thermal data for any part, and no
    numeric datasheet field of any kind.** `SPEC-205`'s guidance is quotes and
    page numbers; `datasheet_structure.CATEGORY_PATTERNS` has no thermal
    category, and neither datasheet module parses a number at all. So §2.6's
    open question -- *"what happens to a part record that has no thermal data"*
    -- turns out to describe every part there is.

    The choice §2.6 offered was *"silence, or an explicit 'cannot compare',
    never an assumed value"*. Inventing a package-typical figure would be an
    assumed value wearing a citation's clothes, and §3 names a wrong thermal
    claim as the worst output this pack can produce. So: the watts, which are
    real arithmetic over stated numbers, and an explicit sentence about what
    would be needed to turn them into a temperature.
    """
    nets = project.get("nets") or []
    symbols = project.get("symbols") or []
    intent = project.get("intent_fields") or {}

    raised = []
    for regulator in P.regulators(symbols):
        reference = regulator["reference"]
        out_volts = regulator["output_volts"]
        supply = P.supply_volts(reference, nets, intent)
        in_volts = supply["volts"]
        milliamps = P.budget_milliamps(intent)

        missing = _dissipation_gap(out_volts, in_volts, milliamps)
        if missing:
            raised.append(C.make(
                id="regulator_dissipation_unanswerable",
                domain="power",
                claim_class=C.COMPUTED,
                trigger={"kind": "reference", "ref": reference,
                         "lib_id": regulator["lib_id"]},
                explanation=(
                    f"{reference} is a linear regulator, which works by turning the "
                    f"voltage it does not pass on into heat. Whether that matters here "
                    f"is arithmetic, and one number is missing to do it: {missing}."
                ),
            ))
            continue

        if in_volts <= out_volts:
            # A dropout problem rather than a heat one, and a different claim.
            continue

        watts = (in_volts - out_volts) * milliamps / 1000.0
        origin = (
            f"the {supply['ref']} rail on your schematic"
            if supply["source"] == P.FROM_RAIL
            else "the supply voltage you entered"
        )
        raised.append(C.make(
            id="regulator_dissipation",
            domain="power",
            claim_class=C.COMPUTED,
            trigger={"kind": "reference", "ref": reference,
                     "lib_id": regulator["lib_id"]},
            arithmetic={
                "expression": "(Vin - Vout) * Iout",
                "inputs": {
                    "Vin": {"value": in_volts, "unit": "V", "from": supply["source"],
                            "ref": supply["ref"]},
                    "Vout": {"value": out_volts, "unit": "V", "from": "symbol",
                             "ref": regulator["lib_id"]},
                    "Iout": {"value": milliamps, "unit": "mA", "from": "intent",
                             "ref": "current_budget"},
                },
                "result": {"value": round(watts, 3), "unit": "W"},
            },
            explanation=(
                f"{reference} takes {in_volts:g}V in and puts {out_volts:g}V out, and a "
                f"linear regulator gets rid of the difference as heat. At the "
                f"{milliamps:g}mA you said this board draws, that is "
                f"({in_volts:g} - {out_volts:g}) x {milliamps / 1000:g} = "
                f"{watts:.2f}W it has to lose. The {in_volts:g}V came from {origin}, the "
                f"{out_volts:g}V from the part's own name, and the {milliamps:g}mA from "
                f"what you told us. Whether {watts:.2f}W is survivable depends on the "
                f"package and on how much copper the tab is soldered to — this app does "
                f"not hold that figure for {reference}, so it is telling you the watts "
                f"and not a temperature."
            ),
        ))
    return raised


def _dissipation_gap(out_volts, in_volts, milliamps):
    """Which single piece stops the sum, phrased for a person.

    One at a time and in this order, because a list of three unknowns reads as
    a form to fill in and the first one is often the only one the user has to
    do anything about.
    """
    if out_volts is None:
        return ("what it is set to produce. This part's name does not say, because an "
                "adjustable regulator's output is set by the resistors around it")
    if in_volts is None:
        return ("the voltage going into it. Neither the schematic's rail names nor "
                "your project settings say yet")
    if milliamps is None:
        return "roughly how much current this board draws, which nothing has said yet"
    return None

def trace_too_narrow_for_current(project: dict) -> list:
    """A supply trace against what IPC-2221 says it carries -- §2.1 item 4.

    `cited`, not `computed`, and the distinction is the point. The arithmetic is
    ours; the relationship it computes is IPC's, and `SPEC-210` §2.1 says a claim
    that relays someone else's fact must say whose. The `source` is the standard
    by name, and `arithmetic` carries the sum so the user can check it in KiCad's
    own Track Width calculator and get the same answer.

    **Only the supply rails and grounds are checked**, because only they can be
    said to carry the whole board's current. A signal trace carries whatever that
    signal draws, which nothing here knows. Conservative in the direction §2.5
    argues for, and stated in the explanation rather than assumed silently.

    Copper weight is assumed to be 1oz when the board does not say, and it did
    not say on any of the five real boards measured. The claim states that.
    """
    tracks = project.get("tracks") or []
    if not tracks:
        return []
    milliamps = P.budget_milliamps(project.get("intent_fields"))
    if milliamps is None:
        # Nothing to compare against. `regulator_dissipation` already asks for
        # this number, and asking twice in one review is nagging.
        return []

    narrowest = {}
    for track in tracks:
        net = track.get("net")
        width = track.get("width_mm")
        if not net or not width:
            continue
        if P.nominal_volts(net) is None and not P.is_ground(net):
            continue
        current = narrowest.get(net)
        if current is None or width < current["width_mm"]:
            narrowest[net] = {"width_mm": width, "layer": track.get("layer")}

    raised = []
    for net, track in sorted(narrowest.items()):
        capacity_ma = P.ipc2221_current_amps(
            track["width_mm"], track["layer"]
        ) * 1000.0
        if capacity_ma >= milliamps:
            continue
        raised.append(C.make(
            id="trace_too_narrow_for_current",
            domain="power",
            claim_class=C.CITED,
            trigger={"kind": "net", "ref": net, "width_mm": track["width_mm"]},
            source={
                "ref": "IPC-2221",
                "title": "IPC-2221, Generic Standard on Printed Board Design",
                "note": (
                    "The same standard KiCad's own Track Width calculator uses, so "
                    "this number can be checked there. IPC-2152 supersedes its "
                    "trace-sizing charts and generally allows narrower traces for "
                    "the same current."
                ),
            },
            arithmetic={
                "expression": "I = k * dT^0.44 * A^0.725",
                "inputs": {
                    "width": {"value": track["width_mm"], "unit": "mm", "from": "board"},
                    "layer": {"value": track["layer"], "from": "board"},
                    "copper": {"value": 1.0, "unit": "oz", "from": "assumed"},
                    "rise": {"value": P.DEFAULT_RISE_C, "unit": "degC", "from": "assumed"},
                },
                "result": {"value": round(capacity_ma), "unit": "mA"},
            },
            explanation=(
                f"The narrowest trace on {net} is {track['width_mm']:g}mm. By IPC-2221 "
                f"that carries about {capacity_ma:.0f}mA for a 10 degC temperature rise, "
                f"and you said this board draws {milliamps:g}mA. {net} is a supply net, so "
                f"it is the one carrying that whole figure. Assumes 1oz copper, because "
                f"this board does not state its copper weight. IPC-2152 replaced these "
                f"charts and usually allows a narrower trace than this — IPC-2221 is used "
                f"here because it is more conservative and because it is what KiCad's own "
                f"Track Width calculator uses, so you can check this number there."
            ),
        ))
    return raised


def reversible_power_input(project: dict) -> list:
    """A two-pin power input with nothing stopping it going in backwards.

    `SPEC-211` §2.1 item 5. §2.4 called this *"a question until the connector's
    role is confirmed, then a finding"* — and the netlist confirms the role, so
    it is a finding. On `BB8-Breakout`, `Net-(J4-Pin_1)` carries J4 pin 1 and
    `X1`'s `5V` power-in pin, while J4 pin 2 sits on ground. That is a power
    input, proven, with nobody having been asked anything.

    **Only a footprint this module positively recognises as reversible counts.**
    A bare pin header or a screw terminal goes in either way round; a barrel
    jack, a USB connector and a polarised JST housing do not. The list is
    positive rather than negative on purpose: an unrecognised connector produces
    silence, which is wrong in the direction that costs nothing.
    """
    nets = project.get("nets") or []
    footprints = {
        f.get("reference"): f.get("footprint") or ""
        for f in (project.get("footprints") or []) if f.get("reference")
    }
    if not footprints:
        return []

    raised = []
    for reference, pins in sorted(P.power_input_connectors(nets).items()):
        footprint = footprints.get(reference)
        if not footprint or not P.is_reversible_connector(footprint):
            continue
        raised.append(C.make(
            id="reversible_power_input",
            domain="power",
            claim_class=C.COMPUTED,
            trigger={"kind": "reference", "ref": reference,
                     "footprint": footprint, "net": pins["supply_net"]},
            explanation=(
                f"{reference} is this board's power input — its pin {pins['supply_pin']} "
                f"reaches {pins['fed']}, and pin {pins['ground_pin']} is ground. Its "
                f"footprint is a plain two-pin header, which goes on either way round, "
                f"and nothing on this board stops the supply arriving backwards. One "
                f"reversed connection is usually the end of whatever is downstream. A "
                f"keyed connector, or a diode in the input, is what normally prevents it."
            ),
        ))
    return raised

#: The USB figure's citation, shared by both halves of the pack below so the
#: reinforcement is sourced exactly as rigorously as the warning. `SPEC-210`
#: §2.1's rule is about the claim class, not about whether the news is good.
_USB_SOURCE = {
    "ref": "USB 2.0 Specification",
    "title": "USB 2.0 Specification, bus-powered device power budgeting",
    "note": (
        "A configured high-power bus-powered device may draw five unit loads of "
        "100mA at 5V. Chargers and USB-C sources with power delivery supply more, "
        "and hubs or older ports often do not."
    ),
}


def current_budget_against_source(project: dict) -> list:
    """What the board draws against what its supply guarantees -- §2.1 item 3.

    *"Twelve LEDs off a USB port."*

    **It reports a guarantee, never a prediction.** Exceeding USB's 500mA does
    not mean the board fails -- the charger on the user's desk probably delivers
    two amps. It means the board has stopped being portable between the things
    they might plug it into, which is true where *"this will not work"* would be
    false, and the second sentence is the one a novice would remember.

    `cited` in both directions, including when the news is good. The
    `considerations.cleared` helper builds a `computed` claim, and this figure is
    USB's rather than ours however it is being used, so the satisfied case is
    built through `make` directly with its source attached.
    """
    headroom = P.usb_headroom(project.get("intent_fields"))
    if headroom is None:
        return []

    drawn = headroom["milliamps"]
    guaranteed = headroom["guaranteed"]
    trigger = {"kind": "intent_field", "ref": "input_supply", "source": "usb"}

    if headroom["fits"]:
        return [C.make(
            id="current_budget_against_source",
            domain="power",
            claim_class=C.CITED,
            trigger=trigger,
            source=_USB_SOURCE,
            state=C.SATISFIED,
            explanation=(
                f"You said this board runs from USB and draws about {drawn:g}mA. A USB "
                f"port has to be able to supply {guaranteed:g}mA, so it fits with room "
                f"to spare — this board will run off any USB port you find rather than "
                f"only off the charger you happen to own."
            ),
        )]

    return [C.make(
        id="current_budget_against_source",
        domain="power",
        claim_class=C.CITED,
        trigger=trigger,
        source=_USB_SOURCE,
        arithmetic={
            "expression": "drawn - guaranteed",
            "inputs": {
                "drawn": {"value": drawn, "unit": "mA", "from": "intent",
                          "ref": "current_budget"},
                "guaranteed": {"value": guaranteed, "unit": "mA", "from": "cited",
                               "ref": "USB 2.0 Specification"},
            },
            "result": {"value": round(drawn - guaranteed), "unit": "mA"},
        },
        explanation=(
            f"You said this board runs from USB and draws about {drawn:g}mA. A USB port "
            f"is only required to supply {guaranteed:g}mA, so you are {drawn - guaranteed:g}mA "
            f"over what the standard guarantees. That does not mean it will not run: a "
            f"phone charger usually delivers far more, and a USB-C supply more still. It "
            f"means it will run from some ports and not others — a hub or an older laptop "
            f"port is where it would stop working, and that is a miserable fault to chase "
            f"later. Worth knowing now rather than finding out."
        ),
    )]

#: The registry. `SPEC-210`'s claim is that a new subject area is a row here
#: plus a function, not a rebuild.
#:
#: **The mechanism held and the rule did not, and those are different results.**
#: Adding a second pack cost exactly one function and one list entry, which is
#: the claim proven. That second pack was then withdrawn because it could not be
#: grounded in a stated fact -- see above. Cheap to add is not the same as safe
#: to ship, and §3's bar is the second one.
PACKS = {
    "power": [
        led_series_resistor,
        component_without_value,
        regulated_rail_into_module_input,
        regulator_dissipation,
        trace_too_narrow_for_current,
        reversible_power_input,
        current_budget_against_source,
    ],
}


#: Which packs read which source. `led_series_resistor` needs the netlist;
#: `component_without_value` needs the schematic's symbols. Declared rather than
#: inferred from a signature, so a caller knows what to gather before running.
#: A pack wanting more than one of them takes the whole bundle.
PROJECT = "project"

PACK_INPUTS = {
    "led_series_resistor": "nets",
    "component_without_value": "symbols",
    "regulated_rail_into_module_input": "nets",
    "regulator_dissipation": PROJECT,
    "trace_too_narrow_for_current": PROJECT,
    "reversible_power_input": PROJECT,
    "current_budget_against_source": PROJECT,
}


def run(nets: list, domains: list = None, symbols: list = None,
        intent_fields: dict = None, tracks: list = None,
        footprints: list = None) -> list:
    """Every pack's considerations for this project.

    Order is by `SPEC-210` §2.6's third option -- *"would this have built
    silently wrong"* -- approximated as computed before cited before judgement,
    since a computed claim is the one the user can go and check.

    A pack declares what it wants in `PACK_INPUTS`. Most want one thing;
    `PROJECT` hands over everything, for a pack whose claim genuinely spans the
    schematic, the netlist and what the user has told us -- `SPEC-211`'s
    dissipation needs an output voltage from the symbol, an input voltage from
    the net, and a current from the user's own answer, and no two of those three
    live in the same place.
    """
    bundle = {
        "nets": nets or [],
        "symbols": symbols or [],
        "intent_fields": intent_fields or {},
        # Board-side inputs. Empty is ordinary rather than exceptional: a
        # project with no PCB yet, or one nobody has routed, is the normal
        # state early on -- two of five real boards have zero segments.
        "tracks": tracks or [],
        "footprints": footprints or [],
    }
    out = []
    for domain, packs in PACKS.items():
        if domains and domain not in domains:
            continue
        for pack in packs:
            wants = PACK_INPUTS.get(pack.__name__)
            if wants == PROJECT:
                source = bundle
            elif wants == "nets":
                source = bundle["nets"]
            else:
                source = bundle["symbols"]
            out.extend(pack(source))
    order = {C.COMPUTED: 0, C.CITED: 1, C.JUDGEMENT: 2}
    return sorted(out, key=lambda c: order.get(c["claim_class"], 9))
