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


def _parse(text: str) -> list:
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


def _sym(node) -> str:
    """The leading symbol of an s-expression node, or '' if it has none."""
    if node and isinstance(node[0], tuple):
        return node[0][1]
    return ""


def _value(node):
    """A node's first non-symbol payload, unquoted."""
    for item in node[1:]:
        if isinstance(item, tuple):
            return item[1]
    return None


def read_board_footprints(pcb_path: str) -> list:
    """Every footprint physically on the board, in file order.

    Each entry is {reference, footprint, value, layer} -- `footprint` being
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

    top = _parse(text)
    if not top or _sym(top[0]) != "kicad_pcb":
        raise BoardReadError(f"Not a KiCad board file: {pcb_path}")

    found = []
    for node in top[0]:
        if not isinstance(node, list) or _sym(node) != "footprint":
            continue
        entry = {
            "reference": None,
            "footprint": _value(node),
            "value": None,
            "layer": None,
        }
        for child in node:
            if not isinstance(child, list):
                continue
            kind = _sym(child)
            if kind == "layer" and entry["layer"] is None:
                entry["layer"] = _value(child)
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
