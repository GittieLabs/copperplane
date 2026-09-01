"""Shared Copperplane mark geometry. 64x64 viewBox, everything on a 45-degree routing grid."""

# The routed C: an octagonal ring with the right side opened.
# Every corner is a 45-degree miter, the way a real autorouter breaks a corner.
CHANNEL = "M49 24 L40 15 L24 15 L15 24 L15 40 L24 49 L40 49 L49 40"
CHANNEL_W = 7.0

# Via pads sit at both open ends of the trace.
VIA_A = (49.0, 24.0)
VIA_B = (49.0, 40.0)
VIA_OUTER_R = 7.6
VIA_HOLE_R = 3.0

TILE_RX = 14.0

PALETTE = {
    "green700": "#0B5C34",   # deep solder mask
    "green600": "#10743F",   # primary
    "green500": "#178F4E",
    "green300": "#4FC17E",   # dark-surface / bright accent
    "copper":   "#C0703A",   # material accent, used sparingly
    "ink":      "#0A1410",   # near-black with a green cast
    "paper":    "#F4F7F3",
}


def mask_defs(mask_id):
    """A mask that keeps the plane and cuts the channel + via holes out of it."""
    return f"""<mask id="{mask_id}" maskUnits="userSpaceOnUse" x="0" y="0" width="64" height="64">
      <rect x="0" y="0" width="64" height="64" fill="#fff"/>
      <path d="{CHANNEL}" fill="none" stroke="#000" stroke-width="{CHANNEL_W}"
            stroke-linecap="round" stroke-linejoin="round"/>
      <circle cx="{VIA_A[0]}" cy="{VIA_A[1]}" r="{VIA_OUTER_R}" fill="#000"/>
      <circle cx="{VIA_B[0]}" cy="{VIA_B[1]}" r="{VIA_OUTER_R}" fill="#000"/>
      <circle cx="{VIA_A[0]}" cy="{VIA_A[1]}" r="{VIA_HOLE_R}" fill="#fff"/>
      <circle cx="{VIA_B[0]}" cy="{VIA_B[1]}" r="{VIA_HOLE_R}" fill="#fff"/>
    </mask>"""


def trace_group(color):
    """Positive form: the copper trace itself, landing on a via pad at each end."""
    return f"""<g fill="{color}">
      <path d="{CHANNEL}" fill="none" stroke="{color}" stroke-width="{CHANNEL_W}"
            stroke-linecap="round" stroke-linejoin="round"/>
      <path fill-rule="evenodd" d="M{VIA_A[0]} {VIA_A[1] - VIA_OUTER_R}
        a{VIA_OUTER_R} {VIA_OUTER_R} 0 1 0 0 {VIA_OUTER_R * 2}
        a{VIA_OUTER_R} {VIA_OUTER_R} 0 1 0 0 -{VIA_OUTER_R * 2}
        M{VIA_A[0]} {VIA_A[1] - VIA_HOLE_R}
        a{VIA_HOLE_R} {VIA_HOLE_R} 0 1 1 0 {VIA_HOLE_R * 2}
        a{VIA_HOLE_R} {VIA_HOLE_R} 0 1 1 0 -{VIA_HOLE_R * 2}Z"/>
      <path fill-rule="evenodd" d="M{VIA_B[0]} {VIA_B[1] - VIA_OUTER_R}
        a{VIA_OUTER_R} {VIA_OUTER_R} 0 1 0 0 {VIA_OUTER_R * 2}
        a{VIA_OUTER_R} {VIA_OUTER_R} 0 1 0 0 -{VIA_OUTER_R * 2}
        M{VIA_B[0]} {VIA_B[1] - VIA_HOLE_R}
        a{VIA_HOLE_R} {VIA_HOLE_R} 0 1 1 0 {VIA_HOLE_R * 2}
        a{VIA_HOLE_R} {VIA_HOLE_R} 0 1 1 0 -{VIA_HOLE_R * 2}Z"/>
    </g>"""
