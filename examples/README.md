# Example projects

Real KiCad projects the documentation walks through. Small on purpose: three
files each, no build artifacts, no local settings.

## Copperplane_Blink_LEDs

An Arduino UNO shield — an RGB LED, a resistor, a tactile switch and four M2
mounting holes. It is the subject of
[Your first board check](https://gittielabs.github.io/copperplane/tutorials/blink-leds/).

**It is not a clean board, and that is the point.** Measured with `kicad-cli`
against the files in this directory:

| Check | `kicad-cli` reports | Copperplane shows |
| :--- | :--- | :--- |
| ERC | 2 errors, both `power_pin_not_driven` | the same 2 |
| DRC violations | 4 errors, all `annular_width` — every pad of D1, 0.085 mm against a 0.100 mm minimum | **1 finding**: same problem, same cause, same fix |
| DRC unconnected | 1 error — GND, between a track and pad 7 of A1 | 1 finding |
| Schematic parity | clean | — |
| — | — | plus 1 **suggestion**: courtyard checking is off, which the enclosure tool depends on |

So `kicad-cli` counts five DRC violations and a reader of the tutorial sees
three findings. Both numbers are correct; they are counting different things.

And one defect **neither check reports**: D1 pairs a two-pin `Device:LED` symbol
with a four-pin `LED_THT:LED_D5.0mm-4_RGB` footprint, so two pads carry no net
and a single resistor stands in for three colour channels. ERC passes. DRC does
not call it an error. It is a part that was never going to work, described
perfectly consistently — which is the tutorial's closing point.

If you change these files, the numbers above stop being true and the tutorial
starts lying. Re-measure before committing:

```bash
kicad-cli sch erc --format json --severity-all -o /tmp/erc.json Copperplane_Blink_LEDs/Copperplane_Blink_LEDs.kicad_sch
kicad-cli pcb drc --format json --severity-all -o /tmp/drc.json Copperplane_Blink_LEDs/Copperplane_Blink_LEDs.kicad_pcb
```

`Copperplane_Blink_LEDs.zip` is the same three files, for a one-click download
from the tutorial. Rebuild it after any change:

```bash
cd examples && zip -r Copperplane_Blink_LEDs.zip Copperplane_Blink_LEDs -x "*.DS_Store"
```
