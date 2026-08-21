# SPEC-203 Exploration: Supplier & Component Data Sources

**Status:** Research findings and proposed plan · **Date:** 2026-08-18 · **Verified against live
vendor terms pages on this date**

> **Not legal advice.** This is a careful read of published terms by a non-lawyer. Several of the
> conclusions below turn on contestable readings, and at least one vendor's terms are unreadable
> from the public web. Before shipping any distributor integration to real users, get an actual
> lawyer to read §3 — it is cheap relative to having an API relationship terminated.

---

## 1. The headline, up front

**The ROADMAP entry for SPEC-203 — "DigiKey / Octopart / Mouser: authentication, rate limits, a
local cache, graceful degradation" — describes something that is, as written, not permitted by
those vendors' terms.** Not "expensive," not "rate-limited." Not permitted.

Three clauses recur across nearly every distributor API, and this product violates all three by
design:

| Clause | Who has it | Why it kills the plan |
| :--- | :--- | :--- |
| **No local caching / no building your own database** | Mouser (flat ban), Farnell/element14 (flat ban), DigiKey §5.1(e), Arrow (48h in terms, "violation" in best practices), Nexar (24h ceiling) | The entire product is a persistent local component library |
| **No aggregating that distributor's data with third-party content "without distinction"** | DigiKey §5.1(b), Mouser §1, Farnell §1, Arrow | A multi-distributor part view is the obvious feature |
| **Principal purpose must be driving *that distributor's* sales** | DigiKey §5.2, Mouser §2, Arrow, Farnell | A neutral CAD tool has a different principal purpose |

DigiKey is the sharpest case. Its three Permitted Purposes are: your public website, an approved
"Downstream Website," or **your internal** application for automating your own purchasing. *A
third-party desktop app distributed to strangers fits none of them.* That isn't a restriction to
work around; it's a statement that this use case was never contemplated.

**The good news is that you don't need them.** The data this product actually depends on — pins,
packages, footprints, datasheet locations — is largely available from sources that are free, need
no key, and permit local storage. Pricing and stock, which is what the distributor APIs are really
for, is the *least* important thing this app does. The plan below inverts the roadmap's assumption
accordingly.

---

## 2. Direct answers to your questions

**Are the supplier developer options free to use?**
Signup is free almost everywhere — DigiKey's license is "royalty-free," Mouser is free in practice,
element14 is free, TME says so in its contract, Nexar has a free evaluation tier. **Price is not the
constraint. Terms are.**

**Can you readily enroll and get a key free?**
Depends sharply on the vendor. Self-serve and near-instant: **Mouser, element14/Farnell, TME,
Nexar**. Self-serve with an undocumented cap on production apps: **DigiKey**. Not self-serve —
human review, company details, "name of your Arrow salesperson," account numbers: **Arrow**. Gated
on a **business license** or on your **prior order volume**: **LCSC** and **JLCPCB**. For a solo
open-source project, the last three are effectively closed.

**Is it possible to use in your open-source app?**
Only under a bring-your-own-key model, and even then only for some vendors. **TME is the single
vendor whose terms explicitly contemplate this**, granting a license "to use the content obtained
via the API **in native desktop applications** (for personal use)" for a user holding their own key
(§8.5). Nexar's terms don't forbid it. DigiKey's and Mouser's terms don't fit a third-party desktop
app at all, regardless of how keys are handled.

**Would each user need to obtain their own developer keys?**
**Yes — and not as a courtesy. It is the only lawful model.** Every vendor prohibits sharing,
sublicensing, transferring, or publishing keys. Nexar §1.2(xii) explicitly forbids posting a key "in
any publicly accessible forum," which an open-source repo plainly is. Bundling a project key is not
an option anywhere.

**So you'd need to add key entry to the settings menu?**
Yes. That lands on **SPEC-106** (config & secrets, OS keychain) and **SPEC-303** (settings UI),
both of which already exist as roadmap entries. This is one more provider section in an existing
surface, not new infrastructure.

**Your concern about maintaining keys if someone takes over the project —**
**BYO-key eliminates it entirely.** The project holds no credentials, so there is nothing to hand
over, rotate, revoke, or be liable for. No shared rate-limit pool that one user's loop exhausts for
everyone. No key in CI. No abuse traced back to you. A fork inherits working code and zero secrets.
The architecture the law forces on you is also the one that solves the governance problem you were
worried about. That is a rare alignment and worth stating explicitly in the spec.

---

## 3. Vendor findings

### 3.1 Distributor APIs

| Vendor | Signup | Free tier / limits | Caching | Aggregation | BYO-key OSS desktop | Verdict |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TME** | Self-serve; needs a tme.eu customer account **and** a developer account. OAuth2 (v2 API; apps created after 2026-05-14 are v2-only) | "Use of the Electronic Services, including the TME API Service, is **free of charge**" (§3.5). 50 items/call. Numeric query limits referenced but unpublished | **No caching prohibition found** in the 2026-07-01 terms | **No competing-product clause** | **§8.5 expressly permits native desktop apps** for a key-holding user | ✅ **Best fit by a wide margin** |
| **Nexar** (Altium/Octopart) | Self-serve portal, client ID + secret | Free "Evaluation" app. Official pages conflict: compare-plans says **100 matched parts**; support FAQ says **1000 lifetime**. Paid pricing **not published anywhere public** | **24-hour ceiling** (§1.2(vi)); no self-hosting datasheets or images (§1.2(v)) | §1.6 bans mass aggregation for predictive analytics; §1.2(vii)(b) bans competing products | Not forbidden, not blessed | ⚠️ **Demo-grade.** ECAD data is Enterprise-only |
| **Mouser** | Self-serve, instant static key | 50 results/call, 30/min, 1000/day — clearly published | **Flat ban** (§4): may not "cache, record, pre-fetch, or otherwise store any portion" | §1: no aggregation "without distinction" | Keys are per-user and self-service, so BYO is clean — but the app's *behaviour* conflicts | ⚠️ **Live-query only, never persist.** Terms last modified **2013** |
| **element14 / Farnell** | Self-serve, 24-char key | Free; assigned quota **never published** | **Flat ban** (§4.A) plus "nor use it to update or create your own database" (§4.B) | §1 bans aggregation "in any way" | §2: key usable only "with the application you initially applied for" | ❌ **Best data, worst terms.** Easiest onboarding, hardest compliance |
| **DigiKey** | Self-serve, OAuth2 (10-min tokens); undocumented cap on production apps | 120/min, 1000/day on Product Information | §5.1(e) bars using data "to update or create your own database" | §5.1(b) aggregation must be clearly labelled per-source | **Permitted Purposes don't include a third-party desktop app** | ❌ **Needs written permission.** Also §5.2: principal purpose must be driving DigiKey sales |
| **Arrow** | Manual form: company, website, salesperson name, account number, human review | No published quota | Terms say 48h; best-practices page says caching is "a violation" | Bans aggregating into public data services | Keys non-transferable "under any circumstances" | ❌ **Closed, and thin data** — `hasDataSheet` is a boolean, not a URL |
| **LCSC** (official) | **Business license required**, plus **IP whitelisting** | 200/min, 1000/day | No caching clause | Bans aggregation | IP whitelist alone kills a distributed desktop app | ❌ **Unavailable** |
| **JLCPCB** (official) | Approval weighted on "the partner's previous orders" and "business situation" | Unpublished | — | — | — | ❌ **Unavailable** |

### 3.2 The unofficial JLCPCB endpoint — named, and declined

`jlcpcb.com/api/overseas-pcb-order/v1/shoppingCart/smtGood/selectSmtComponentList` responds
unauthenticated and returns package, full parametric attributes, stock, tiered pricing, and
`dataManualUrl` — a direct datasheet link. It is free, keyless, and richer than Arrow's *authorised*
API. Several respected OSS projects use it.

**Recommend against it, on grounds of durability rather than purity.** It carries no license grant
of any kind, is undocumented, and can be WAF-blocked or removed without notice — the research
session hit exactly such a block from a datacenter IP. Building a documented product feature on an
endpoint that can vanish silently is a support burden you'd own forever. Worth revisiting only as an
explicitly-labelled community/experimental provider that ships disabled.

### 3.3 CAD data: symbols, footprints, 3D models

This is a different problem from pricing, with much better answers.

| Source | License | Key? | Local store | Ship with app? |
| :--- | :--- | :--- | :--- | :--- |
| **The user's installed KiCad libraries** | CC-BY-SA 4.0 **+ design exception** | No | ✅ | Only as a CC-BY-SA collection with attribution — not under Apache-2.0 |
| **Digi-Key KiCad library** (GitHub) | Same CC-BY-SA + exception | No | ✅ | ✅ under CC-BY-SA + attribution |
| **CDFER/JLCPCB-Kicad-Library** | **MIT** | No | ✅ | ✅ — genuinely redistributable symbols, footprints and STEP |
| **kicad-footprint-generator** | GPLv3+ (possible partial LGPL — unverified) | No | ✅ | Generated footprints yes; **do not link the generator** into Apache-2.0 code |
| **SnapMagic / SnapEDA** | CC-BY-SA files, but ToS §5.1(j) bars "automated means," §5.1(f) bars bundling | Negotiated, not self-serve | User's manual downloads only | ❌ |
| **Ultra Librarian** | **No license grant published at all** | No public API | User's manual downloads only | ❌ |
| **Component Search Engine** | Terms robots-disallowed; site is Cloudflare bot-protected | No public API | User's downloads only | ❌ |
| **EasyEDA via converters** | Source data licensing genuinely **unresolved**; EasyEDA has never answered the question on its own forum | Legacy no, Pro yes | Grey | ❌ |

Three things fall out of this table.

**The KiCad license exception is more generous than it first looks, and stops exactly where you'd
expect.** Using library data in a design — and in generated files from that design — is explicitly
waived from CC-BY-SA's share-alike. Redistributing the libraries *as a collection*, including
modified, is not. So: read, search, and copy into the user's own project freely; do not ship a
derived library inside an Apache-2.0 installer without segregating it under CC-BY-SA.

**KiCad already ships its own EasyEDA importer.** It handles `.elibz`, `.esym`, `.epro` and more. If
a user wants an EasyEDA part, handing their own file to KiCad's importer offloads both the parsing
and the legal exposure onto a file they obtained themselves. That is strictly better than calling
undocumented endpoints, and it's free.

**There is no open, permissively-licensed dataset of manufacturer pin assignments or authoritative
package dimensions.** JEDEC outlines and IPC-7351 land patterns are copyrighted paid standards. This
is precisely why SPEC-202's LLM extraction from datasheets exists, and why its provenance and
validation layers matter — that pipeline isn't a shortcut around a database, it's the substitute for
a database that doesn't exist.

---

## 4. Proposed architecture: three tiers

### Tier 0 — Ships on by default, no keys, no accounts

*   The user's own installed KiCad symbol and footprint libraries: indexed and searchable.
*   IPC-rule-based footprint generation (rules, not copied geometry).
*   Datasheet **URL** storage and open-in-browser. Never a fetch, never a mirror.
*   Optionally, MIT-licensed community libraries bundled and clearly attributed.
*   SPEC-202's datasheet→pins extraction on a PDF **the user supplies**.

**This tier alone satisfies most of the product plan's M2 and M3.** It needs no API relationship, has
no rate limit, works offline, and cannot be revoked. It should be built first and be genuinely
complete on its own.

### Tier 1 — Optional, per-user key, off until configured

*   **TME first.** It is the only vendor with an on-point desktop clause, it's free by contract,
    self-serve, OAuth2, and has an anonymous market-data mode for neutral pricing.
*   **Nexar second**, clearly labelled as an evaluation-grade allowance so nobody is surprised when
    100 parts run out.
*   Each provider is a plugin behind one interface. Absent a key, the provider is invisible — not an
    error, not a nag.

### Tier 2 — Link-out only, forever

DigiKey, Mouser, SnapMagic, Ultra Librarian, Component Search Engine: **deep links the user clicks,
opening in their own browser.** No API calls, no automated fetching, no scraping. This is fully
compliant everywhere, costs nothing to build, and is genuinely useful — "open this part on DigiKey"
is a real feature.

### Never

Bundle a key. Ship distributor data. Mirror datasheets. Display multi-source data without per-source
attribution. Use an undocumented endpoint in a shipped default path.

---

## 5. The engineering consequence: split persistable from ephemeral

This is the part that must reach **SPEC-304's schema**, and it is the single most important design
outcome of this research.

The product plan's "files as truth" local library and the distributors' no-caching clauses collide
head-on. The resolution is not to weaken either — it is to recognise that **they apply to different
fields.**

| Persist to the library (indefinitely) | Session-only, TTL, never written to disk |
| :--- | :--- |
| Pins, names, electrical types | Price and price breaks |
| Package name and dimensions | Stock / availability |
| Datasheet **URL** | Lead time |
| Manufacturer, MPN | Distributor-specific part numbers |
| Symbol and footprint references | Anything else returned by a Tier 1 provider |
| Provenance for each of the above | — |

Notice that this split is *also correct on the merits*, independent of any license. Price and stock
are stale within hours; caching them produces wrong answers. Pins don't change. **The lawful design
and the correct design are the same design** — which is the strongest possible sign it's right.

Concretely, the `Part` record persists the left column. Distributor responses populate a transient
view model that is never serialised into `library/parts/*.part.json`. A reviewer should be able to
verify compliance by grepping the write path.

---

## 6. Attribution, and why it's already built

DigiKey §3.1.4, Mouser §5, Farnell §1, Arrow, and TME §8.7 all require conspicuous per-source
attribution, and several require outbound links be preserved unobscured. TME even specifies the
string: *"Data powered by TME.eu Data – no guarantee of data accuracy."*

**The provenance model already required by the product plan satisfies this.** Provenance exists there
for trust reasons — so an engineer can see why a pin value is what it is. It turns out to be the same
mechanism the terms demand. One implementation, two justifications. The spec should say so, because
it means the attribution requirement adds display work but no new architecture.

---

## 7. Phased implementation

| Phase | Scope | Depends on |
| :--- | :--- | :--- |
| **203.0** | Provider interface + settings surface, with **zero providers**. Establishes the plugin shape, the enabled/disabled model, keychain storage via SPEC-106, and the persist/ephemeral split in the schema. | SPEC-106, SPEC-304 |
| **203.1** | **Tier 0**: index the user's local KiCad libraries; datasheet-URL-only handling. No network. | SPEC-304, SPEC-307 |
| **203.2** | **Tier 2**: link-out targets for DigiKey/Mouser/SnapMagic/UL/CSE. Pure URL construction. Cheap, compliant, immediately useful. | 203.0 |
| **203.3** | **Tier 1, TME only.** OAuth2, anonymous market-data mode, the §8.7 attribution string, TTL'd ephemeral pricing. The reference implementation every later provider copies. | 203.0 |
| **203.4** | **Tier 1, Nexar.** Evaluation-cap handling and honest UI when the allowance is exhausted. | 203.3 |
| **Deferred** | DigiKey and Mouser — only if written permission is obtained. Track as a business task, not an engineering one. | — |

Note the ordering: **the two vendors the roadmap named first are the two that come last, or never.**

---

## 8. What this changes elsewhere

*   **ROADMAP §3.2, SPEC-203 entry** — rewrite. "DigiKey/Octopart/Mouser integration" becomes the
    tiered model above. The entry currently promises something not permitted.
*   **SPEC-304** — the schema must encode the persist/ephemeral split, not merely describe it.
*   **SPEC-106 / SPEC-303** — provider keys are a settings section; keychain, never plaintext, never
    a command-line argument where `ps` can see it.
*   **SPEC-202** — its provenance fields must carry the source attribution string, not just a source
    identifier, so the display layer can satisfy the terms without a lookup table.
*   **SPEC-306 (Discovery)** — the "closest matches with links" flow can be built entirely on Tier 0
    plus Tier 2 link-outs. It does **not** need a distributor API, which removes a dependency from
    the M2 critical path.
*   **NOTICE / licensing** — if any CC-BY-SA library content is ever bundled, it needs its own
    segregated directory and license file. Relevant to the Apache-2.0 work now in flight.

---

## 9. Open questions

1.  **Does TME's §8.5 "(for personal use)" qualifier restrict commercial users of the app?** The
    clause permits native desktop use by a key-holder but parenthetically limits it. A professional
    engineer using this at work may fall outside. **Worth asking TME directly** — they are the one
    vendor likely to answer a straightforward question well.
2.  **Nexar's real free allowance** — 100 matched parts or 1000 lifetime? Two current official pages
    disagree. And paid pricing is unpublished; you cannot plan around a number nobody will state.
3.  **Is it worth asking DigiKey for written permission?** Their API team can approve a
    "Downstream Website" and can sublicense "if expressly approved." A short, honest email describing
    the app costs an afternoon and would settle it. Same for Mouser, whose terms date from 2013 and
    may not reflect current practice.
4.  **Does the user's local KiCad library index count as "your own database"** if it never touches
    distributor data? Almost certainly fine — it derives from CC-BY-SA content on the user's disk —
    but keep the two indexes physically separate so the answer stays obviously yes.
5.  **macOS stock library path.** Do not hardcode. Resolve `KICAD_STOCK_DATA_HOME` /
    `KICAD10_SYMBOL_DIR` / `KICAD10_FOOTPRINT_DIR` from `~/Library/Preferences/kicad/10.0/`. Note
    KiCad is now **10.0**, so the variables are `KICAD10_*`.

## 10. Explicitly not verified

*   Nexar Standard/Pro pricing — not published publicly anywhere.
*   element14's and TME's actual numeric query quotas — both terms reference limits that are never
    stated.
*   DigiKey's registration form fields, hobbyist approval rate, and production-app cap — the relevant
    pages are robots-disallowed.
*   DigiKey's refresh-token lifetime — two official pages contradict each other (never expires vs 90
    days).
*   Whether Mouser's 2013 terms have been superseded by an unpublished newer version.
*   SnapMagic's API terms (behind an access-request form) and Component Search Engine's end-user
    terms (robots-disallowed; old SamacSys terms now redirect away).
*   Whether `kicad-footprint-generator` is now dual GPL/LGPL — a `LICENSE.LGPL` appears in the repo
    listing but was not readable.
*   **No vendor's terms explicitly address the open-source-distribution-with-no-bundled-key pattern
    except TME.** Everything else is inference from key-sharing prohibitions.

---

## Sources

**Distributor terms:** [DigiKey API User Agreement](https://developer.digikey.com/api-user-agreement) ·
[DigiKey Shared Concepts (rate limits)](https://developer.digikey.com/tutorials-and-resources/shared-concepts) ·
[Mouser API Terms](https://www.mouser.com/en/apiterms/) ·
[Mouser API Guide (PDF)](https://www.mouser.com/pdfDocs/api-guide.pdf) ·
[Altium/Nexar API License Terms](https://nexar.com/api/legal) ·
[Nexar Compare Plans](https://nexar.com/compare-plans) ·
[Nexar FAQ](https://support.nexar.com/support/solutions/articles/101000497890-frequently-asked-questions) ·
[Arrow API Terms of Use](https://developers.arrow.com/api/index.php/site/page?view=terms) ·
[element14 Partner API Terms](https://partner.element14.com/terms) ·
[TME Terms and Conditions 2026-07-01 (PDF)](https://developers.tme.eu/pdfs/en/terms_2026-07-01.pdf) ·
[TME setup instructions (PDF)](https://developers.tme.eu/pdfs/en/instruction.pdf) ·
[LCSC API Instruction & Terms](https://www.lcsc.com/docs/index.html) ·
[JLCPCB API application](https://jlcpcb.com/help/article/jlcpcb-online-api-available-now)

**CAD data:** [KiCad Libraries License](https://www.kicad.org/libraries/license/) ·
[kicad-symbols LICENSE.md](https://github.com/KiCad/kicad-symbols/blob/master/LICENSE.md) ·
[KiCad Libraries Download](https://www.kicad.org/libraries/download/) ·
[KiCad 10.0 docs — paths & env vars](https://docs.kicad.org/10.0/en/kicad/kicad.html) ·
[KiCad dev-docs — EasyEDA import](https://dev-docs.kicad.org/en/import-formats/easyeda/index.html) ·
[SnapMagic Terms of Service](https://www.snapeda.com/about/terms/) ·
[Ultra Librarian Legal](https://www.ultralibrarian.com/legal) ·
[CDFER/JLCPCB-Kicad-Library (MIT)](https://github.com/CDFER/JLCPCB-Kicad-Library) ·
[Digi-Key KiCad library](https://github.com/Digi-Key/digikey-kicad-library/blob/master/LICENSE.md) ·
[kicad-footprint-generator](https://gitlab.com/kicad/libraries/kicad-footprint-generator) ·
[yaqwsx/jlcparts (MIT)](https://github.com/yaqwsx/jlcparts) ·
[TousstNicolas/JLC2KiCad_lib (MIT)](https://github.com/TousstNicolas/JLC2KiCad_lib)

**Datasheets:** [TI Terms of Use](https://www.ti.com/legal/terms-conditions/terms-of-use.html) ·
[TI Copyrights](https://www.ti.com/legal/terms-conditions/copyright.html)
