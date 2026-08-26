#!/usr/bin/env python3
"""Generate the Copperplane identity sheet as a self-contained artifact page."""
import os
import re

SVG = "/home/claude/copperplane/brand/svg"
OUT = "/home/claude/copperplane/copperplane-identity.html"


def s(name, w=None, h=None):
    raw = open(os.path.join(SVG, name)).read()
    if w or h:
        repl = (f'width="{w}" ' if w else "") + (f'height="{h}"' if h else "")
        raw = re.sub(r'width="[\d.]+" height="[\d.]+"', repl.strip(), raw, count=1)
    return raw


PAL = [
    ("Solder mask", "--green-700", "#0B5C34", "Deepest green. Rules, pressed states, print.", "8.09:1 on white"),
    ("Copperplane green", "--green-600", "#10743F", "The primary. Mark, links, buttons, focus.", "5.85:1 on white"),
    ("Signal", "--green-500", "#178F4E", "Accents and fills only, never body text.", "4.14:1 — large text only"),
    ("Bright", "--green-300", "#4FC17E", "The mark and links on dark surfaces.", "8.27:1 on ink"),
    ("Copper", "--copper", "#C0703A", "Annotation and provenance cues. Sparingly.", "3.74:1 — large text only"),
    ("Ink", "--ink", "#0A1410", "Dark ground and body text on paper.", "17.35:1 vs paper"),
    ("Paper", "--paper", "#F4F7F3", "Light ground.", "—"),
]

pal_rows = "".join(
    f'<tr><td><span class="chip" style="background:{hexv}"></span></td>'
    f'<td class="pname">{name}</td><td class="mono">{hexv}</td>'
    f'<td class="mono dim">{tok}</td><td class="use">{use}</td>'
    f'<td class="mono num">{ratio}</td></tr>'
    for name, tok, hexv, use, ratio in PAL)

FILES = [
    ("svg/lockup-horizontal.svg", "Primary lockup. Default for docs, README, site header."),
    ("svg/lockup-horizontal-on-dark.svg", "Same, for dark surfaces."),
    ("svg/lockup-horizontal-mono.svg", "Inherits currentColor. For one-colour print or embeds."),
    ("svg/lockup-stacked.svg", "Stacked lockup, for square or narrow space."),
    ("svg/lockup-stacked-on-dark.svg", "Stacked, dark surfaces."),
    ("svg/mark.svg", "Mark alone, 24px and up."),
    ("svg/mark-on-dark.svg", "Mark alone, dark surfaces."),
    ("svg/mark-small.svg", "Small-size mark. Heavier trace, no drills. Under 24px."),
    ("svg/mark-mono.svg", "Mark in currentColor."),
    ("svg/icon.svg", "App icon. Green plane, ink substrate through the channel."),
    ("svg/icon-inverse.svg", "App icon, inverted."),
    ("svg/icon-small.svg", "App icon tuned for 16-20px."),
    ("svg/favicon.svg", "Favicon, mark on transparent."),
    ("svg/wordmark.svg", "Wordmark alone (plus -on-dark and -green)."),
    ("png/*", "Rasterised at 16 through 1024. Transparent."),
    ("favicon.ico", "Multi-resolution 16/32/64."),
]
file_rows = "".join(f'<tr><td class="mono">{f}</td><td>{d}</td></tr>' for f, d in FILES)

# construction diagram: the mark on its routing grid
grid = "".join(f'<line x1="{i*8}" y1="0" x2="{i*8}" y2="64" />'
               f'<line x1="0" y1="{i*8}" x2="64" y2="{i*8}" />' for i in range(9))

TRACE_D = ("M48.5 24.2 L39.5 15.5 L24.5 15.5 L15.5 24.5 L15.5 39.5 "
           "L24.5 48.5 L39.5 48.5 L48.5 39.8")

CONSTRUCTION = f'''<svg viewBox="-8 -14 94 90" class="constr" role="img"
  aria-label="Construction drawing of the mark on its 8-unit routing grid">
  <g class="grid">{grid}</g>
  <rect x="0" y="0" width="64" height="64" class="frame"/>
  <path d="{TRACE_D}" class="trace"/>
  <circle cx="48.5" cy="24.2" r="2.7" class="drill"/>
  <circle cx="48.5" cy="39.8" r="2.7" class="drill"/>
  <path d="M44 19.5 L58 -1" class="leader"/>
  <text x="58" y="-3" class="ann">45° miter</text>
  <path d="M55 24.2 L66 24.2" class="leader"/>
  <text x="67" y="26" class="ann">drilled</text>
  <text x="0" y="71" class="ann">64 × 64 board, 8u grid</text>
</svg>'''

# clear space = one trace width outside the mark's visible bounds
VIS_LO, VIS_HI = 11.25, 52.75
KO_LO, KO_SIZE = VIS_LO - 8.5, (VIS_HI - VIS_LO) + 17.0

CLEARSPACE = f'''<svg viewBox="-12 -18 88 94" class="constr" role="img"
  aria-label="Clear space equals one trace width on all four sides of the mark">
  <rect x="{KO_LO}" y="{KO_LO}" width="{KO_SIZE}" height="{KO_SIZE}" class="keepout"/>
  <path d="{TRACE_D}" class="trace"/>
  <circle cx="48.5" cy="24.2" r="2.7" class="drill"/>
  <circle cx="48.5" cy="39.8" r="2.7" class="drill"/>
  <path d="M{KO_LO} 32 L{VIS_LO} 32" class="dim"/>
  <path d="M{KO_LO} 29.5 L{KO_LO} 34.5 M{VIS_LO} 29.5 L{VIS_LO} 34.5" class="dim"/>
  <path d="M32 {KO_LO} L32 {VIS_LO}" class="dim"/>
  <path d="M29.5 {KO_LO} L34.5 {KO_LO} M29.5 {VIS_LO} L34.5 {VIS_LO}" class="dim"/>
  <text x="32" y="-8" class="ann mid">one trace width, all four sides</text>
  <text x="{KO_LO - 1.5}" y="26" class="ann end">1×</text>
</svg>'''

HTML = f'''<title>Copperplane Identity</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600;700&display=swap">
<style>
:root {{
  --green-700:#0B5C34; --green-600:#10743F; --green-500:#178F4E; --green-300:#4FC17E;
  --copper:#C0703A; --ink:#0A1410; --paper:#F4F7F3;
  --bg:#F4F7F3; --surface:#FFFFFF; --line:#DCE5DF; --line-soft:#E9EFEA;
  --text:#0A1410; --text-dim:#5C6E64; --text-faint:#8A9A90;
  --accent:var(--green-600); --rule:#C8D5CC;
  --sans:"IBM Plex Sans",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg:#080F0B; --surface:#101A14; --line:#1E2C24; --line-soft:#18241D;
    --text:#E6EEE8; --text-dim:#93A69A; --text-faint:#69796F;
    --accent:var(--green-300); --rule:#26372C;
  }}
}}
:root[data-theme="dark"] {{
  --bg:#080F0B; --surface:#101A14; --line:#1E2C24; --line-soft:#18241D;
  --text:#E6EEE8; --text-dim:#93A69A; --text-faint:#69796F;
  --accent:var(--green-300); --rule:#26372C;
}}
* {{ box-sizing:border-box; }}
body {{
  background:var(--bg); color:var(--text); font-family:var(--sans);
  font-size:16px; line-height:1.6; margin:0; padding:0 24px 96px;
  -webkit-font-smoothing:antialiased;
}}
.wrap {{ max-width:1000px; margin:0 auto; }}

/* --- masthead, set like the title block of a fab drawing --- */
.masthead {{ padding:64px 0 34px; border-bottom:2px solid var(--text); }}
.masthead .logo {{ display:block; margin-bottom:30px; }}
.masthead h1 {{
  font-size:clamp(30px,4.4vw,44px); line-height:1.1; letter-spacing:-.022em;
  font-weight:600; margin:0 0 12px; text-wrap:balance; max-width:20ch;
}}
.masthead p {{ margin:0; color:var(--text-dim); max-width:62ch; font-size:17px; }}
.titleblock {{
  display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr));
  gap:0; border:1px solid var(--line); border-radius:3px; margin-top:32px;
  background:var(--surface); overflow:hidden;
}}
.titleblock div {{ padding:12px 16px; border-right:1px solid var(--line); }}
.titleblock div:last-child {{ border-right:0; }}
.titleblock dt {{
  font:500 10px/1.4 var(--mono); letter-spacing:.13em; text-transform:uppercase;
  color:var(--text-faint); margin:0 0 4px;
}}
.titleblock dd {{ margin:0; font:400 13px/1.4 var(--mono); color:var(--text); }}

/* --- sheets --- */
section {{ padding-top:64px; }}
.sheet-no {{
  display:flex; align-items:baseline; gap:14px; margin-bottom:6px;
  font:500 11px/1 var(--mono); letter-spacing:.14em; text-transform:uppercase;
  color:var(--accent);
}}
.sheet-no::after {{ content:""; flex:1; height:1px; background:var(--rule); }}
h2 {{ font-size:25px; letter-spacing:-.018em; font-weight:600; margin:0 0 10px; }}
.lede {{ color:var(--text-dim); max-width:64ch; margin:0 0 26px; }}
h3 {{ font-size:15px; font-weight:600; margin:30px 0 10px; letter-spacing:-.005em; }}
p {{ max-width:64ch; }}

/* --- specimen boards --- */
.boards {{ display:grid; gap:10px; }}
.two {{ grid-template-columns:1fr 1fr; }}
@media (max-width:720px) {{ .two {{ grid-template-columns:1fr; }} }}
.board {{
  background:#fff; border:1px solid var(--line); border-radius:3px;
  padding:34px 28px; display:flex; align-items:center; justify-content:center;
  gap:26px; flex-wrap:wrap; position:relative; min-height:120px;
}}
.board.dark {{ background:#0A1410; border-color:#1E2C24; }}
.board .tag {{
  position:absolute; top:9px; left:12px; font:500 9.5px/1 var(--mono);
  letter-spacing:.12em; text-transform:uppercase; color:#9AAAA0;
}}
.board.dark .tag {{ color:#5E6F65; }}
.board.baseline {{ align-items:flex-end; }}

/* --- construction drawings --- */
.constr {{ width:100%; max-width:300px; height:auto; overflow:visible; }}
.constr .grid line {{ stroke:var(--rule); stroke-width:.25; }}
.constr .frame {{ fill:none; stroke:var(--text-faint); stroke-width:.4; stroke-dasharray:2 1.5; }}
.constr .trace {{ fill:none; stroke:var(--accent); stroke-width:8.5; stroke-linecap:round; stroke-linejoin:round; }}
.constr .drill {{ fill:var(--surface); stroke:none; }}
.constr .leader {{ stroke:var(--copper); stroke-width:.55; fill:none; }}
.constr .ann.end {{ text-anchor:end; }}
.constr .keepout {{ fill:none; stroke:var(--copper); stroke-width:.7; stroke-dasharray:3 2.5; }}
.constr .dim {{ stroke:var(--copper); stroke-width:.7; }}
.constr .ann {{ font:500 5px var(--mono); fill:var(--copper); letter-spacing:.04em; }}
.constr .ann.mid {{ text-anchor:middle; }}
.diagram {{
  display:grid; grid-template-columns:300px 1fr; gap:34px; align-items:center;
  background:var(--surface); border:1px solid var(--line); border-radius:3px; padding:28px;
}}
@media (max-width:720px) {{ .diagram {{ grid-template-columns:1fr; }} }}
.diagram p {{ margin:0 0 14px; }}
.diagram p:last-child {{ margin-bottom:0; }}

/* --- tables --- */
.tablewrap {{ overflow-x:auto; border:1px solid var(--line); border-radius:3px; background:var(--surface); }}
table {{ border-collapse:collapse; width:100%; font-size:14px; }}
th {{
  text-align:left; font:500 10px/1 var(--mono); letter-spacing:.13em; text-transform:uppercase;
  color:var(--text-faint); padding:13px 14px; border-bottom:1px solid var(--line); white-space:nowrap;
}}
td {{ padding:12px 14px; border-bottom:1px solid var(--line-soft); vertical-align:middle; }}
tr:last-child td {{ border-bottom:0; }}
.mono {{ font-family:var(--mono); font-size:12.5px; }}
.num {{ font-variant-numeric:tabular-nums; white-space:nowrap; color:var(--text-dim); }}
.dim {{ color:var(--text-faint); }}
.pname {{ font-weight:500; white-space:nowrap; }}
.use {{ color:var(--text-dim); font-size:13.5px; min-width:22ch; }}
.chip {{ display:block; width:34px; height:34px; border-radius:2px; border:1px solid rgba(10,20,16,.14); }}

/* --- rules list --- */
.rules {{ display:grid; grid-template-columns:1fr 1fr; gap:10px; }}
@media (max-width:720px) {{ .rules {{ grid-template-columns:1fr; }} }}
.rules > div {{ background:var(--surface); border:1px solid var(--line); border-radius:3px; padding:20px 22px; }}
.rules h4 {{
  font:500 10px/1 var(--mono); letter-spacing:.13em; text-transform:uppercase;
  margin:0 0 14px; color:var(--text-faint);
}}
.rules .do h4 {{ color:var(--green-500); }}
.rules .dont h4 {{ color:var(--copper); }}
.rules ul {{ margin:0; padding:0; list-style:none; display:grid; gap:9px; }}
.rules li {{ padding-left:18px; position:relative; font-size:14.5px; color:var(--text-dim); }}
.rules li::before {{
  content:""; position:absolute; left:0; top:.62em; width:8px; height:1.5px; background:var(--rule);
}}
.rules .do li::before {{ background:var(--green-500); }}
.rules .dont li::before {{ background:var(--copper); }}

.note {{
  border-left:2px solid var(--accent); padding:2px 0 2px 18px; margin:26px 0 0;
  color:var(--text-dim); font-size:14.5px; max-width:66ch;
}}
.note strong {{ color:var(--text); font-weight:600; }}
footer {{
  margin-top:72px; padding-top:22px; border-top:1px solid var(--line);
  font:400 12.5px/1.7 var(--mono); color:var(--text-faint);
}}
a {{ color:var(--accent); }}
:focus-visible {{ outline:2px solid var(--accent); outline-offset:3px; }}
</style>

<div class="wrap">

<header class="masthead">
  <span class="logo">{s('lockup-horizontal.svg', 300)}</span>
  <h1>A routed trace, a plane, and two drilled terminals.</h1>
  <p>Copperplane is a local-first workspace for hardware engineers, bridging PCB layout and
  mechanical CAD. The identity is drawn the way the product's users draw: on a grid, at 45 degrees,
  with holes where the copper needs to change layers.</p>
  <dl class="titleblock">
    <div><dt>Mark</dt><dd>Routed C, drilled</dd></div>
    <div><dt>Type</dt><dd>IBM Plex Sans 600</dd></div>
    <div><dt>Primary</dt><dd>#10743F</dd></div>
    <div><dt>Grid</dt><dd>64 × 64, 8u</dd></div>
    <div><dt>Rev</dt><dd>A</dd></div>
  </dl>
</header>

<section>
  <div class="sheet-no">Sheet 01 · Mark</div>
  <h2>The construction</h2>
  <p class="lede">The mark is a single copper trace routed into a C, on the same 8-unit grid and the
  same 45-degree corner rule a real autorouter follows. It is not a letterform with circuit
  decoration on it.</p>
  <div class="diagram">
    {CONSTRUCTION}
    <div>
      <p><strong>Every corner is a 45-degree miter.</strong> Right-angle corners are avoided in real
      layout because acid traps at the inside of the bend during etching. The mark inherits the
      constraint rather than imitating the look.</p>
      <p><strong>Both terminals are drilled.</strong> The holes are plated through-holes, drawn as
      voids in the trace rather than added rings. They stay legible down to about 24px and then
      disappear, which is why there is a separate small-size mark below.</p>
      <p><strong>The trace is 8.5 units on a 64-unit board.</strong> That ratio holds at every size,
      so the mark scales without redrawing.</p>
    </div>
  </div>
  <div class="boards two" style="margin-top:10px">
    <div class="board baseline"><span class="tag">On paper</span>
      {s('mark.svg', 92, 92)}{s('mark.svg', 44, 44)}{s('mark-small.svg', 24, 24)}</div>
    <div class="board dark baseline"><span class="tag">On ink</span>
      {s('mark-on-dark.svg', 92, 92)}{s('mark-on-dark.svg', 44, 44)}{s('mark-small-on-dark.svg', 24, 24)}</div>
  </div>
</section>

<section>
  <div class="sheet-no">Sheet 02 · Lockups</div>
  <h2>Mark and wordmark</h2>
  <p class="lede">The horizontal lockup is the default. Use the stacked one only where the
  horizontal would have to shrink below about 140px wide.</p>
  <div class="boards">
    <div class="board"><span class="tag">Primary · horizontal</span>{s('lockup-horizontal.svg', 380)}</div>
    <div class="board dark"><span class="tag">Primary · on ink</span>{s('lockup-horizontal-on-dark.svg', 380)}</div>
  </div>
  <div class="boards two" style="margin-top:10px">
    <div class="board"><span class="tag">Stacked</span>{s('lockup-stacked.svg', 190)}</div>
    <div class="board dark"><span class="tag">Stacked · on ink</span>{s('lockup-stacked-on-dark.svg', 190)}</div>
  </div>
  <h3>Clear space and minimum size</h3>
  <div class="diagram">
    {CLEARSPACE}
    <div>
      <p><strong>Keep one trace width clear on every side.</strong> The trace width is the stroke of
      the C, which makes the clear space scale with the mark automatically. Nothing crosses that
      boundary, including the edge of a container.</p>
      <p><strong>Minimums.</strong> Full mark down to 24px. Below that, switch to
      <span class="mono">mark-small.svg</span>, which drops the drilled terminals and thickens the
      trace. The horizontal lockup stops at 140px wide; the wordmark alone stops at 90px.</p>
    </div>
  </div>
</section>

<section>
  <div class="sheet-no">Sheet 03 · Application</div>
  <h2>Icon and product surfaces</h2>
  <p class="lede">The app icon inverts the mark: the tile is the copper plane, and the routed
  channel exposes the substrate underneath. It is the same drawing, read as a board instead of a
  trace.</p>
  <div class="boards two">
    <div class="board baseline"><span class="tag">App icon · 128 / 64 / 32 / 16</span>
      {s('icon.svg', 128, 128)}{s('icon.svg', 64, 64)}{s('icon.svg', 32, 32)}{s('icon-small.svg', 16, 16)}</div>
    <div class="board"><span class="tag">Inverse · dock, dark chrome</span>
      {s('icon-inverse.svg', 128, 128)}{s('icon-inverse.svg', 64, 64)}</div>
  </div>
  <p class="note"><strong>The 16px icon is a different drawing.</strong> Below about 20px the trace
  and the counter both fall under two pixels and the C fills in. The small-size files widen the
  mouth, thicken the trace to 11 units, and drop the drills. Use them; do not scale the full mark
  down and hope.</p>
</section>

<section>
  <div class="sheet-no">Sheet 04 · Colour</div>
  <h2>Solder mask green</h2>
  <p class="lede">The primary is the green of PCB solder mask, not a generic brand green. Contrast
  ratios below are measured against white for the light values and against ink for the bright one.</p>
  <div class="tablewrap">
    <table>
      <thead><tr><th></th><th>Name</th><th>Hex</th><th>Token</th><th>Use</th><th>Contrast</th></tr></thead>
      <tbody>{pal_rows}</tbody>
    </table>
  </div>
  <p class="note"><strong>Two values are accent-only.</strong> Signal and Copper both land under
  4.5:1 on white, so they are fine for fills, rules, and large display type, and wrong for body
  text. Copper earns its place as the annotation colour because it is the other material on the
  board, not because it is a second brand colour.</p>
</section>

<section>
  <div class="sheet-no">Sheet 05 · Type</div>
  <h2>IBM Plex Sans</h2>
  <p class="lede">The wordmark is Plex Sans SemiBold, all caps, tracked +55/1000, converted to
  outlines. Plex was drawn for an engineering company and carries the right amount of
  machined-not-cute; it also ships a mono that matches, which the product's own interface needs for
  part numbers and file paths.</p>
  <div class="boards">
    <div class="board" style="justify-content:flex-start;padding:30px">{s('wordmark.svg', 420)}</div>
  </div>
  <div class="tablewrap" style="margin-top:10px">
    <table>
      <thead><tr><th>Role</th><th>Face</th><th>Setting</th></tr></thead>
      <tbody>
        <tr><td class="pname">Wordmark</td><td>IBM Plex Sans SemiBold</td><td class="mono">caps, +55 tracking, outlined</td></tr>
        <tr><td class="pname">Headings</td><td>IBM Plex Sans SemiBold</td><td class="mono">-0.02em, balance</td></tr>
        <tr><td class="pname">Body</td><td>IBM Plex Sans Regular</td><td class="mono">16px / 1.6, 64ch max</td></tr>
        <tr><td class="pname">Data, paths, labels</td><td>IBM Plex Mono</td><td class="mono">+0.13em when uppercase</td></tr>
      </tbody>
    </table>
  </div>
  <p class="note"><strong>Licensing.</strong> IBM Plex is published under the SIL Open Font License
  1.1, which permits commercial use and outlining into a logo. The wordmark files are outlines, so
  nothing has to ship the font to render them.</p>
</section>

<section>
  <div class="sheet-no">Sheet 06 · Rules</div>
  <h2>Handling</h2>
  <div class="rules">
    <div class="do">
      <h4>Do</h4>
      <ul>
        <li>Use the on-dark files on dark grounds. The bright green is a different value, not the same green lightened by the browser.</li>
        <li>Let the mono lockup inherit <span class="mono">currentColor</span> for one-colour print, laser engraving, and embedded SVG.</li>
        <li>Keep the mark's mouth pointing right. It reads as a C in one orientation only.</li>
        <li>Put the mark on a solid ground. Over photography, use the tile.</li>
      </ul>
    </div>
    <div class="dont">
      <h4>Don't</h4>
      <ul>
        <li>Redraw the C in another weight or add a second trace. The geometry is the identity.</li>
        <li>Set the wordmark in live text. It is tracked and outlined for a reason.</li>
        <li>Recolour the mark outside the palette, including a gradient.</li>
        <li>Scale the full mark below 24px, or stretch either lockup non-uniformly.</li>
        <li>Add a drop shadow or an outer glow to the tile.</li>
      </ul>
    </div>
  </div>
</section>

<section>
  <div class="sheet-no">Sheet 07 · Files</div>
  <h2>What ships</h2>
  <p class="lede">Everything is generated from one script, so the geometry cannot drift between
  formats. Re-run it to change a colour or a size rather than editing a file by hand.</p>
  <div class="tablewrap">
    <table>
      <thead><tr><th>File</th><th>Purpose</th></tr></thead>
      <tbody>{file_rows}</tbody>
    </table>
  </div>
</section>

<section>
  <div class="sheet-no">Sheet 08 · Name</div>
  <h2>Why Copperplane</h2>
  <p class="lede">A copper plane is the solid layer of copper on a board that carries ground or
  power. It is a real term from the user's own vocabulary, and it is available in the places that
  matter.</p>
  <div class="tablewrap">
    <table>
      <thead><tr><th>Check</th><th>Result</th><th>Date</th></tr></thead>
      <tbody>
        <tr><td class="pname">USPTO, word mark</td><td>No filings for COPPERPLANE or COPPER PLANE</td><td class="mono num">2026-08-25</td></tr>
        <tr><td class="pname">GitHub org</td><td class="mono">github.com/copperplane</td><td class="mono num">unclaimed</td></tr>
        <tr><td class="pname">Product search</td><td>No software product using the name</td><td class="mono num">2026-08-25</td></tr>
        <tr><td class="pname">copperplane.com</td><td>Registered 2025-08-23, GoDaddy, parked</td><td class="mono num">take .dev / .app</td></tr>
      </tbody>
    </table>
  </div>
  <p class="note"><strong>The name it replaces.</strong> Hardware Agent Studio was legally clear but
  commercially invisible: Oracle, Google, Automation Anywhere, Workato, Algolia, Cognigy, and
  Siemens all ship something called Agent Studio, and Orange Logic has a pending USPTO application
  on the bare mark in class 42 for AI SaaS. The only distinctive word in the old name was the one
  that plainly described the category. None of this is a clearance opinion; get a real search from
  an attorney before the name carries revenue.</p>
</section>

<footer>
  COPPERPLANE IDENTITY · REV A · DRAWN 2026-08-25 · GITTIELABS<br>
  Mark and wordmark generated from tools/build.py · IBM Plex under SIL OFL 1.1
</footer>

</div>
'''

open(OUT, "w").write(HTML)
print(f"wrote {OUT} ({len(HTML)} bytes)")
