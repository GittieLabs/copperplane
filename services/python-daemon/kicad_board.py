"""Read a `.kicad_pcb` directly -- SPEC-326 §2.7.

The enclosure is built around the BOARD, so the board is what this app
measures. Getting a complete list of what is physically on it turns out to
be harder than it looks, and both obvious routes are wrong:

*   **`kicad-cli pcb export pos` silently omits footprints.** Position
    files honour KiCad's `exclude_from_pos_files` footprint attribute --
    confirmed directly, by setting that attribute on a fixture and watching
    the component vanish from the CSV while the board itself was unchanged.
    That attribute is routinely set on mounting holes, fiducials, logos and
    test points: precisely the board-only mechanical parts that decide
    whether a board fits in a box. A quiet omission there produces an
    enclosure that is wrong in the one way nobody checks.
*   **`kiutils` cannot read a full board at all.** `Board().from_file()`
    raises `IndexError` on real boards from this machine (already recorded
    in `CTX-314.1`, re-confirmed here against the maintainer's own project).
    It reads `.kicad_mod` footprint files fine, which is why `kicad_bridge`
    still uses it for those.

So this reads the file. Nothing can be excluded from it by an export
setting, because there is no export.
"""
import os
import re


class BoardReadError(Exception):
    """A .kicad_pcb that could not be read as one."""


def _tokenize(text: str):
    """S-expression tokens. Quoted strings are one token, and may contain
    parentheses -- a footprint's Value property routinely does, e.g.
    "Battery_Cell (CR2032)" -- so a naive paren count over the raw text
    mis-nests. Backslash escapes are honoured inside strings."""
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        if c in "()":
            yield c
            i += 1
        elif c.isspace():
            i += 1
        elif c == '"':
            i += 1
            out = []
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n:
                    out.append(text[i + 1])
                    i += 2
                else:
                    out.append(text[i])
                    i += 1
            i += 1
            yield ('str', "".join(out))
        else:
            start = i
            while i < n and not text[i].isspace() and text[i] not in '()"':
                i += 1
            yield ('atom', text[start:i])


def parse(text: str) -> list:
    """A KiCad s-expression file as nested lists.

    Public because `.kicad_pcb`, `.kicad_sch` and `.kicad_mod` are the same
    format and this repo should not grow a second parser for them --
    `structural_checks` reads schematics and footprints with this one. The
    error type still says "board file"; it is the message a user sees when any
    of the three is malformed and renaming it is a separate change.
    """
    stack = [[]]
    for tok in _tokenize(text):
        if tok == "(":
            stack.append([])
        elif tok == ")":
            if len(stack) == 1:
                raise BoardReadError("Unbalanced parentheses in board file")
            node = stack.pop()
            stack[-1].append(node)
        else:
            stack[-1].append(tok)
    if len(stack) != 1:
        raise BoardReadError("Unbalanced parentheses in board file")
    return stack[0]


def sym(node) -> str:
    """The leading symbol of an s-expression node, or '' if it has none."""
    if node and isinstance(node[0], tuple):
        return node[0][1]
    return ""


def value(node):
    """A node's first non-symbol payload, unquoted."""
    for item in node[1:]:
        if isinstance(item, tuple):
            return item[1]
    return None


# SPEC-109 §2's own convention, kept in one place: a footprint is a recognized
# mounting hole when it comes from KiCad's own standard MountingHole library,
# or carries that library's default H<digits> reference-designator convention.
# Lives here rather than in `kicad_bridge` because that module needs `kipy`
# importable and the file-reading path does not.
_MOUNTING_HOLE_REF_PATTERN = re.compile(r"^H\d+$")


def is_mounting_hole(footprint_id: str, reference: str) -> bool:
    """A screw hole, not a part standing on the board.

    `CTX-311.15` found this once already, from a real click-through: the
    height-derivation route reported a board's unannotated MountingHole
    footprints as "missing a 3D model" -- technically true and misleading,
    because a screw hole was never going to have one, and the enclosure
    represents it separately as standoff geometry.

    `CTX-326.4` repeated it. The placeholder preview counted four mounting
    holes among "6 components are missing ... add a height in the Components
    tab", which is advice about four things that cannot have a height. A
    warning whose items are mostly unactionable teaches people to skip it.
    """
    library = (footprint_id or "").split(":")[0].lower()
    return "mountinghole" in library or bool(
        _MOUNTING_HOLE_REF_PATTERN.match(reference or "")
    )


def read_board_footprints(pcb_path: str) -> list:
    """Every footprint physically on the board, in file order.

    Each entry is {reference, footprint, value, layer, pos_x_mm,
    pos_y_mm, rotation_deg} -- `footprint` being
    the full `Library:Name` id, the same shape `list_schematic_components`
    reports, so the two are directly comparable.

    Raises rather than returning [] when a real board yields no footprints:
    an empty list reads to a user as "your board is empty", which is a
    silent wrong answer of exactly the kind SPEC-326 exists to avoid.
    `.kicad_pcb`'s format is a contract that can change between KiCad
    majors, and failing loudly is the only honest response to that.
    """
    if not os.path.exists(pcb_path):
        raise BoardReadError(f"Board file does not exist: {pcb_path}")

    with open(pcb_path, encoding="utf-8") as f:
        text = f.read()

    top = parse(text)
    if not top or sym(top[0]) != "kicad_pcb":
        raise BoardReadError(f"Not a KiCad board file: {pcb_path}")

    found = []
    for node in top[0]:
        if not isinstance(node, list) or sym(node) != "footprint":
            continue
        entry = {
            "reference": None,
            "footprint": value(node),
            "value": None,
            "layer": None,
            # SPEC-326 §2.4 needs somewhere to put a placeholder solid, and
            # a volume in the wrong place renders perfectly.
            #
            # `pos_` prefixed rather than plain `x_mm`, because a resolved
            # component record also carries `courtyard["x_mm"]` -- which is a
            # SIZE, not a position. Two keys spelled the same in one record,
            # meaning different things, joined together to place geometry, is
            # the shape of the exact bug this context exists to avoid.
            # `rotation_deg`
            # defaults to 0 rather than None: KiCad omits the third value
            # entirely for an unrotated footprint, so absent means zero here
            # and there is no "unknown rotation" state to represent.
            "pos_x_mm": None,
            "pos_y_mm": None,
            "rotation_deg": 0.0,
        }
        for child in node:
            if not isinstance(child, list):
                continue
            kind = sym(child)
            if kind == "layer" and entry["layer"] is None:
                entry["layer"] = value(child)
            elif kind == "at" and entry["pos_x_mm"] is None:
                # Only the footprint's OWN `at`. Pads, texts and graphics
                # each carry one too, relative to the footprint -- and they
                # are nested deeper, so iterating this node's direct
                # children is what keeps them out. Guarded on `is None` as
                # well, so the first one wins if that ever stops being true.
                coords = [i[1] for i in child[1:] if isinstance(i, tuple)]
                try:
                    entry["pos_x_mm"] = float(coords[0])
                    entry["pos_y_mm"] = float(coords[1])
                    if len(coords) > 2:
                        entry["rotation_deg"] = float(coords[2])
                except (IndexError, ValueError):
                    # A malformed `at` leaves the position unknown rather
                    # than defaulting to the origin, which would put a
                    # placeholder in a corner of the board and look
                    # deliberate.
                    entry["pos_x_mm"], entry["pos_y_mm"] = None, None
            elif kind in ("property", "fp_text"):
                # Two spellings, both live. Modern boards carry
                # `(property "Reference" "BT1" ...)`; boards written before
                # KiCad 7 carry `(fp_text reference "SW1" ...)` instead --
                # confirmed against a real 2021 board (version 20211014) on
                # this machine, every one of whose 31 footprints reads as
                # reference `None` if only the modern spelling is handled.
                # That is a silent wrong answer, not a crash, so it would
                # have shipped.
                names = [i[1] for i in child[1:] if isinstance(i, tuple)]
                if len(names) >= 2 and names[0] in ("Reference", "reference"):
                    entry["reference"] = names[1]
                elif len(names) >= 2 and names[0] in ("Value", "value"):
                    entry["value"] = names[1]
        found.append(entry)

    if not found and "(footprint" in text:
        raise BoardReadError(
            f"Read {pcb_path} but recognised no footprints in it, although the "
            "file contains some. The board format has probably changed."
        )
    return found
