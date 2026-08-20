"""
Pad-layout geometry generation for the KiCad write path (SPEC-108,
CTX-108.1): turns SPEC-202's validated component schema -- which has
pin count, pitch, and package/courtyard dimensions but no per-pin
(x, y) -- into real pad positions a kipy FootprintInstance's Pad
objects can be built from.

Covers, deliberately: 2-pad passives (0603/0805); dual-row
surface-mount (SOIC-8/14/16, TSSOP-8); dual-row through-hole
(DIP-8/14) -- standard IC pin numbering (pin 1 top-left, down the left
column, then up the right column), derived from each pin's `number`
field alone. Does NOT cover TQFP/QFN (four-side perimeter numbering,
genuinely different geometry) or SOT-23 (irregular 3-pin layout) --
An unsupported package raises UnsupportedPackageError rather than
guessing a layout, the same fail-closed decision component_pipeline.py
makes for an unrecognized package.

Pad dimensions here are conservative, generic defaults per package
family -- not IPC-7351 nominal/least/most land patterns. Good enough
to prove the write path end-to-end and to visually inspect in KiCad
before a write ever reaches a real board; not something to fabricate a
board from without human review. SPEC-204's confirmation gate (not yet
written) is the intended safety net for that gap.

Also builds the real kipy FootprintInstance/Pad/courtyard objects from
that layout -- board-local only, never saved into a footprint library
(kipy's real API has no call to write one).
"""
from kipy.board_types import (
    BoardLayer,
    BoardRectangle,
    DrillShape,
    FootprintInstance,
    Pad,
    PadStackShape,
    PadStackType,
    PadType,
)
from kipy.common_types import LibraryIdentifier
from kipy.geometry import Vector2


class UnsupportedPackageError(Exception):
    """Raised when a package has no pad-layout generator, or its pin
    numbers don't form the simple 1..n sequence every covered family
    assumes -- fails closed rather than guessing a layout."""


TWO_PIN_PACKAGES = frozenset({"0603", "0805"})
DUAL_ROW_PACKAGES = frozenset({"SOIC-8", "SOIC-14", "SOIC-16", "TSSOP-8", "DIP-8", "DIP-14"})
THROUGH_HOLE_PACKAGES = frozenset({"DIP-8", "DIP-14"})

SUPPORTED_PACKAGES = TWO_PIN_PACKAGES | DUAL_ROW_PACKAGES

# Fraction of the package body length a 2-pad passive's pad occupies
# along that axis -- a conservative, generic default, not a per-package
# IPC land pattern.
_TWO_PIN_PAD_LENGTH_RATIO = 0.35

# Dual-row SMD pad size as a fraction of pitch: along the row axis
# (must stay under 1x pitch to avoid adjacent pads touching), and
# across it (toward the package center).
_DUAL_ROW_SMD_PAD_ROW_RATIO = 0.6
_DUAL_ROW_SMD_PAD_SPAN_RATIO = 1.5

# Through-hole (DIP) pads: fixed generic size, independent of pitch --
# DIP pitch is always the same ~2.54mm family (already validated by
# component_pipeline.PACKAGE_REFERENCE's pitch_range_mm), so a fixed
# pad/drill size is a reasonable conservative default.
_THROUGH_HOLE_PAD_SIZE_MM = 1.6
_THROUGH_HOLE_DRILL_MM = 0.8

# Real, standardized lead-to-lead row spacing for the "wide" (0.3in body)
# DIP-8/DIP-14 family this module supports (JEDEC MS-001; the real
# ATtiny85 datasheet's own PDIP-8 mechanical drawing states this
# explicitly as "eA 0.300 BSC" = 7.62mm). A real bug found by live user
# testing: this row spacing was previously computed from
# `package_dimensions["width_mm"]` -- the package BODY width, a
# genuinely different real dimension (JEDEC "E1", typically ~0.25in for
# this same package) -- producing a generated footprint whose pads sat
# 6.35mm apart instead of the real 7.62mm the part's actual leads need,
# silently unusable with a real, physically fabricated part. Row spacing
# for a through-hole DIP is a fixed, standardized package-family
# constant, never derived from body width the way an SMD package's pad
# span legitimately is.
_DIP_ROW_SPACING_MM = 7.62


def _parse_pin_sequence(pin_numbers: list[str], expected_count: int, package: str) -> list[int]:
    """Parses each pin's `number` field as an int and confirms they form
    the simple 1..expected_count sequence every layout generator below
    assumes. Raises UnsupportedPackageError (not a bare ValueError) for
    anything else -- a non-numeric pin name (e.g. a BGA's "A1") is a
    real, different numbering scheme this module doesn't support, not a
    malformed schema."""
    try:
        parsed = sorted(int(n) for n in pin_numbers)
    except ValueError as e:
        raise UnsupportedPackageError(
            f"Package '{package}' has non-numeric pin numbers {pin_numbers!r} -- this "
            f"module only supports simple 1..n numbered packages."
        ) from e

    if parsed != list(range(1, expected_count + 1)):
        raise UnsupportedPackageError(
            f"Package '{package}' pin numbers {pin_numbers!r} are not a contiguous "
            f"1..{expected_count} sequence."
        )
    return parsed


def _two_pin_layout(pin_numbers: list[str], package_dimensions: dict, package: str) -> list[dict]:
    parsed = _parse_pin_sequence(pin_numbers, 2, package)

    length = package_dimensions["length_mm"]
    width = package_dimensions["width_mm"]
    pad_length = length * _TWO_PIN_PAD_LENGTH_RATIO
    span = length - pad_length

    return [
        {
            "number": str(pin),
            "x_mm": x,
            "y_mm": 0.0,
            "width_mm": pad_length,
            "height_mm": width,
            "pad_type": "smd",
            "drill_mm": None,
        }
        for pin, x in zip(parsed, (-span / 2, span / 2))
    ]


def _dual_row_layout(
    pin_numbers: list[str], package_dimensions: dict, pitch_mm: float, package: str, through_hole: bool
) -> list[dict]:
    n = len(pin_numbers)
    parsed = _parse_pin_sequence(pin_numbers, n, package)
    rows = n // 2

    if through_hole:
        span = _DIP_ROW_SPACING_MM
        pad_size = _THROUGH_HOLE_PAD_SIZE_MM
        pad_row_size = pad_size
        drill_mm = _THROUGH_HOLE_DRILL_MM
        pad_type = "pth"
    else:
        span = package_dimensions["width_mm"]
        pad_size = pitch_mm * _DUAL_ROW_SMD_PAD_SPAN_RATIO
        pad_row_size = pitch_mm * _DUAL_ROW_SMD_PAD_ROW_RATIO
        drill_mm = None
        pad_type = "smd"

    pads = []
    for pin in parsed:
        if pin <= rows:
            row_index = pin - 1
            x = -span / 2
        else:
            row_index = rows - 1 - (pin - rows - 1)
            x = span / 2
        y = (row_index - (rows - 1) / 2) * pitch_mm

        pads.append({
            "number": str(pin),
            "x_mm": x,
            "y_mm": y,
            "width_mm": pad_size,
            "height_mm": pad_row_size,
            "pad_type": pad_type,
            "drill_mm": drill_mm,
        })

    return pads


def generate_pad_layout(package: str, pin_numbers: list[str], package_dimensions: dict) -> list[dict]:
    """Returns one pad descriptor per pin -- `{number, x_mm, y_mm,
    width_mm, height_mm, pad_type, drill_mm}`, `(x_mm, y_mm)` centered
    on the package origin. Raises UnsupportedPackageError for a package
    outside SUPPORTED_PACKAGES, or pin numbers that aren't a simple
    1..n sequence."""
    if package in TWO_PIN_PACKAGES:
        return _two_pin_layout(pin_numbers, package_dimensions, package)

    if package in DUAL_ROW_PACKAGES:
        pitch_mm = package_dimensions["pitch_mm"]
        return _dual_row_layout(
            pin_numbers, package_dimensions, pitch_mm, package, through_hole=package in THROUGH_HOLE_PACKAGES
        )

    raise UnsupportedPackageError(
        f"No pad-layout generator for package '{package}' -- supported: {sorted(SUPPORTED_PACKAGES)}."
    )


# The library name this write path stamps onto every board-local
# footprint's LibraryIdentifier -- metadata only (never saved into
# KiCad's own footprint-library-table), so a human reviewing the board
# can see at a glance which footprints this pipeline generated.
_LIBRARY_NAME = "HardwareAgentStudio"


def build_footprint_instance(schema: dict, pads: list[dict], courtyard: dict) -> FootprintInstance:
    """Builds a real kipy FootprintInstance -- one Pad per `pads`
    descriptor (from generate_pad_layout) plus a courtyard rectangle on
    BL_F_CrtYd sized from `courtyard` -- centered on the origin. The
    caller sets `.position` afterward to place it on the board: kipy's
    own position setter then shifts every child pad/shape by the
    resulting delta, so building at the origin first and moving the
    whole footprint once (rather than building pads at absolute board
    coordinates directly) is the correct order.

    Verified for real against a live KiCad 10.0.3 instance (both the
    SMD and PTH pad paths) before being written here -- see CTX-108.1."""
    fi = FootprintInstance()
    fi.layer = BoardLayer.BL_F_Cu

    fi.reference_field.text.value = "REF**"
    fi.value_field.text.value = schema["part_number"]

    lib_id = LibraryIdentifier()
    lib_id.library = _LIBRARY_NAME
    lib_id.name = schema["part_number"]
    fi.definition.id = lib_id

    for pad_desc in pads:
        pad = Pad()
        pad.number = pad_desc["number"]
        is_pth = pad_desc["pad_type"] == "pth"
        pad.pad_type = PadType.PT_PTH if is_pth else PadType.PT_SMD
        pad.padstack.type = PadStackType.PST_NORMAL

        copper_layer = pad.padstack.copper_layer(BoardLayer.BL_F_Cu)
        copper_layer.shape = PadStackShape.PSS_CIRCLE if is_pth else PadStackShape.PSS_RECTANGLE
        copper_layer.size = Vector2.from_xy_mm(pad_desc["width_mm"], pad_desc["height_mm"])

        if is_pth:
            pad.padstack.layers = [
                BoardLayer.BL_F_Cu, BoardLayer.BL_B_Cu, BoardLayer.BL_F_Mask, BoardLayer.BL_B_Mask,
            ]
            pad.padstack.drill.diameter = Vector2.from_xy_mm(pad_desc["drill_mm"], pad_desc["drill_mm"])
            pad.padstack.drill.shape = DrillShape.DS_CIRCLE
        else:
            pad.padstack.layers = [BoardLayer.BL_F_Cu, BoardLayer.BL_F_Mask, BoardLayer.BL_F_Paste]

        pad.position = Vector2.from_xy_mm(pad_desc["x_mm"], pad_desc["y_mm"])
        fi.definition.add_item(pad)

    rect = BoardRectangle()
    rect.layer = BoardLayer.BL_F_CrtYd
    half_length = courtyard["length_mm"] / 2
    half_width = courtyard["width_mm"] / 2
    rect.top_left = Vector2.from_xy_mm(-half_length, -half_width)
    rect.bottom_right = Vector2.from_xy_mm(half_length, half_width)
    fi.definition.add_item(rect)

    return fi
