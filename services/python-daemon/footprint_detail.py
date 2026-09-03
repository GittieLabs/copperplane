"""What a footprint actually is, read from its own `.kicad_mod` -- SPEC-334.

A user looking at `Battery_Panasonic_CR2032-HFN_Horizontal_CircularHoles` or
choosing between `P2.54mm_Vertical` and `P2.00mm_Horizontal` is not helped by
the name. KiCad's own files answer it:

    PinHeader_1x04_P2.54mm_Vertical
      descr: "Through hole straight pin header, 1x04, 2.54mm pitch, single row"

That is better than any parser would produce, and it cannot hallucinate.
Measured before being relied on: across a random 400 of KiCad 10's own
footprints, **400 have a non-empty `descr` and 395 have `tags`** -- so this is
the primary source, not a nice-to-have. A user's personal or community library
may carry neither, which is why the naming decoder below exists as a fallback
rather than as the main event.
"""
import os
import re

_DESCR = re.compile(r'\(descr\s+"((?:[^"\\]|\\.)*)"')
_TAGS = re.compile(r'\(tags\s+"((?:[^"\\]|\\.)*)"')
_PAD = re.compile(r'\(pad\s+"([^"]*)"\s+(\S+)\s+(\S+)')
_URL = re.compile(r"https?://\S+")

def _grid_note(rows: str, cols: str) -> str:
    """`1x04` means one row of four, and reads as nonsense pluralised naively
    ("1 rows of 04")."""
    r, c = int(rows), int(cols)
    if r == 1:
        return f"{rows}x{cols} means a single row of {c} pads."
    return f"{rows}x{cols} means {r} rows of {c} pads each, {r * c} in total."


# The conventions KiCad's own names use, which `descr` often states in prose
# but not always. Deliberately small: this is what the maintainer actually hit,
# not a general dictionary of PCB terminology.
_NAME_CONVENTIONS: list[tuple[re.Pattern, object]] = [
    (re.compile(r"_P(\d+\.?\d*)mm"),
     "P{0}mm is the pitch -- the centre-to-centre distance between adjacent pads, {0}mm here. "
     "Two footprints differing only in pitch are for physically different parts and are not "
     "interchangeable."),
    (re.compile(r"_Vertical(?=_|$)"),
     "Vertical means the part stands up off the board, so its height adds to what the enclosure "
     "needs."),
    (re.compile(r"_Horizontal(?=_|$)"),
     "Horizontal means the part lies flat along the board, taking more area but less height."),
    (re.compile(r"_CircularHoles(?=_|$)"),
     "CircularHoles means round drill holes, as opposed to the oval or slotted holes some parts "
     "need for their tabs."),
    (re.compile(r"_HandSolder(?=_|$)"),
     "HandSolder pads are deliberately longer than the datasheet's, to make soldering by hand "
     "easier. Electrically the same part."),
    (re.compile(r"_ThermalVias(?=_|$)"),
     "ThermalVias adds a via array under the part's thermal pad, to move heat into the board's "
     "copper."),
    (re.compile(r"_(\d+)x(\d+)"), _grid_note),
    (re.compile(r"^([A-Z]+)-(\d+)"),
     "{0}-{1} is a standard package: {1} pins in the {0} outline."),
]


def _decode_name(name: str) -> list[str]:
    """Plain-language notes for the conventions in a footprint's own name.

    A fallback for libraries whose `descr` is empty, and a supplement where the
    name says something the description does not. Silent about anything it does
    not recognise -- inventing a reading of a name is the failure mode
    `SPEC-326` §1 exists to prevent.
    """
    notes = []
    for pattern, template in _NAME_CONVENTIONS:
        match = pattern.search(name)
        if match:
            notes.append(
                template(*match.groups()) if callable(template)
                else template.format(*match.groups())
            )
    return notes


def _pads(text: str) -> dict:
    """Pad count and mounting style, counted from the file.

    `through_hole` versus `smd` is the difference between a part with legs
    through the board and one soldered flat on top -- the single most
    consequential thing a footprint choice decides, and not always in the name.
    """
    kinds = [m.group(2) for m in _PAD.finditer(text)]
    smd = sum(1 for k in kinds if k == "smd")
    thru = sum(1 for k in kinds if k in ("thru_hole", "np_thru_hole"))
    if thru and smd:
        mounting = "mixed (both through-hole and surface-mount pads)"
    elif thru:
        mounting = "through-hole -- the part's legs go through the board"
    elif smd:
        mounting = "surface-mount -- the part solders flat onto the board, no holes"
    else:
        mounting = None
    return {"pad_count": len(kinds), "mounting": mounting}


def _split_off_url(raw: str) -> tuple:
    """Lift a datasheet URL out of a description without wrecking the sentence.

    KiCad's own Resistor_SMD library writes:

        ... (Body size source: IPC-SM-782 page 72, https://...pdf)

    so `\\S+` swallows the closing paren, and removing what is left strands an
    opened "(" with no ")" -- the description then ends mid-clause at
    "page 72", which is how this was caught: by reading the frozen daemon's
    actual output, not the regex.
    """
    match = _URL.search(raw)
    if not match:
        return raw, None

    url = match.group(0)
    # A URL at the end of a sentence collects the sentence's punctuation. A
    # closing paren only belongs to the URL if the URL opened one itself.
    while url and url[-1] in ".,;:":
        url = url[:-1]
    while url.endswith(")") and url.count(")") > url.count("("):
        url = url[:-1]

    rest = (raw[: match.start()] + raw[match.start() + len(url):]).strip()
    # Whatever bracket the URL was sitting inside is now empty of content.
    if rest.count("(") > rest.count(")"):
        opened = rest.rfind("(")
        if opened != -1:
            rest = rest[:opened].strip()
    rest = re.sub(r"\s+", " ", rest).strip()
    # The separator that introduced the URL is now trailing its clause.
    rest = re.sub(r"[,;:\s]+\)", ")", rest)
    # The URL's own trailing punctuation stayed behind when it was trimmed off.
    rest = re.sub(r"\s+([.,;:])", r"\1", rest)
    rest = re.sub(r"\(\s*\)", "", rest).strip()
    rest = re.sub(r"\s+", " ", rest).rstrip(" ,;:")
    return rest, url


def describe_footprint(footprint_id: str, footprint_path: str) -> dict:
    """Everything this app can say about a footprint from its own file.

    No LLM and no network: every field here is read off disk, so it is instant
    and can be trusted literally. `datasheet_url` is whatever URL the library
    author put in `descr` -- surfaced rather than followed, since this app does
    not verify it.
    """
    result = {
        "footprint_id": footprint_id,
        "library": footprint_id.partition(":")[0] or None,
        "name": footprint_id.partition(":")[2] or footprint_id,
        "description": None,
        "tags": [],
        "datasheet_url": None,
        "pad_count": None,
        "mounting": None,
        "name_notes": [],
    }
    result["name_notes"] = _decode_name(result["name"])

    if not footprint_path or not os.path.isfile(footprint_path):
        return result

    try:
        with open(footprint_path, encoding="utf-8", errors="replace") as handle:
            text = handle.read()
    except OSError:
        return result

    descr = _DESCR.search(text)
    if descr:
        raw, url = _split_off_url(descr.group(1).replace('\\"', '"').strip())
        result["datasheet_url"] = url
        result["description"] = raw or None

    tags = _TAGS.search(text)
    if tags:
        result["tags"] = [t for t in tags.group(1).replace('\\"', '"').split() if t]

    result.update(_pads(text))
    return result
