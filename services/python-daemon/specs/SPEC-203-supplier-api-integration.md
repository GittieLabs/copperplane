---
id: SPEC-203
title: "Supplier API Integration (RETIRED)"
status: Deprecated
type: Module
user_facing: false
created: 2026-08-18
last_updated: 2026-08-18
target_version: n/a
location: "services/python-daemon/specs/SPEC-203-supplier-api-integration.md"
parent_spec: "../../../specs/SPEC-000-architecture-overview.md"
child_specs: []
---

# SPEC-203: Supplier API Integration — RETIRED, NOT BUILT

> **This spec exists as a tombstone.** It was never implemented and will not be. It is kept at the
> path `ROADMAP.md` pointed to so that anyone — human or agent — who follows that link finds the
> reasoning instead of an absence, and does not spend a week rediscovering it.
>
> **If you are considering adding a distributor API to this project, read §2 before writing any
> code.** The blockers are contractual, not technical.

## 1. What this was going to be

`ROADMAP.md` originally specified: *"DigiKey / Octopart / Mouser: authentication, rate limits, a
local cache (part data barely changes; re-querying on every request wastes quota and adds latency),
and graceful degradation to LLM-only extraction when no key is configured or the user is offline."*

The premise was that supplier APIs are how you get authoritative component data.

## 2. Why it was retired

Two independent findings, either of which alone would be sufficient.

### 2.1 The APIs do not contain what this product needs

Verified against live vendor documentation on 2026-08-18. For this product's actual goals — pin
layouts, footprints, and the power/passive/protection requirements for using a part correctly —
the distributor APIs contribute essentially nothing:

*   **Pin assignments:** no vendor returns them. Not one.
*   **Footprints / symbols / 3D models:** no vendor returns them, except Nexar at the
    **Enterprise** tier.
*   **Application and design guidance** (decoupling, supply range, pull-ups, protection): no vendor
    returns it. It lives in datasheet prose and reference designs.
*   What they *do* return: price, stock, lead time, package name, and — for some vendors — a
    datasheet URL. Arrow returns `hasDataSheet` as a **boolean**, not a URL.

This project is not helping a user purchase components. Pricing and availability are the entire
value proposition of these APIs and are out of scope for this product.

### 2.2 The terms forbid what this product does

Three clauses recur across nearly every distributor API. A local-first CAD tool violates all three
structurally, not incidentally.

| Clause | Vendors | Conflict |
| :--- | :--- | :--- |
| No caching / no building your own database | Mouser §4 (flat ban), element14 §4.A–B (flat ban), DigiKey §5.1(e), Arrow, Nexar §1.2(vi) (24h ceiling) | The product is a persistent local component library |
| No aggregating their content with third-party content "without distinction" | DigiKey §5.1(b), Mouser §1, element14 §1, Arrow | A multi-source part view is the obvious feature |
| Principal purpose must be driving *that distributor's* sales | DigiKey §5.2, Mouser §2, Arrow, element14 | A CAD tool's principal purpose is CAD |

**DigiKey is the decisive case.** Its three Permitted Purposes are: your public website, an approved
"Downstream Website," or **your internal** application for automating your own purchasing. A
third-party desktop application distributed to strangers fits none of them. That is not a
restriction to design around; it is a statement that this use case was never contemplated.

Additional access barriers, for completeness: **Arrow** requires a manual form including your Arrow
salesperson's name and account number. **LCSC** requires a business license plus IP whitelisting —
the latter alone is fatal for a distributed desktop app. **JLCPCB** weights approval on the
applicant's prior order volume. **Nexar's** free tier is evaluation-grade (official pages conflict
between "100 matched parts" and "1000 lifetime") and paid pricing is not published anywhere public.

### 2.3 The one vendor that would have worked

**TME** is the sole exception and deserves recording in case circumstances change. Its terms
(2026-07-01) state use is *"free of charge"* (§3.5), contain **no caching prohibition**, **no
competing-product clause**, and — uniquely — §8.5 expressly licenses content *"in native desktop
applications (for personal use)"* for a user holding their own key. Self-serve signup, OAuth2, and
an anonymous mode for neutral market data.

TME was not retained only because §2.1 applies to it equally: it returns datasheets and parametrics,
but no pin, symbol, or footprint data. **If this project ever does need distributor data, TME is the
starting point and everything else is a distant second.**

## 3. What replaced it

| Need | Where it now lives |
| :--- | :--- |
| Pin layouts | SPEC-202 — datasheet extraction pipeline |
| Design/application guidance | **SPEC-205** — Datasheet-Driven Design Guidance |
| Footprints | SPEC-308 — the user's installed KiCad libraries, IPC-rule generation, MIT community libraries |
| Datasheet resolution ("find the datasheet for this MPN") | SPEC-306 — Component Discovery |
| "Open this part at a distributor" | SPEC-307 — a constructed deep link. No API, no key, compliant everywhere |

## 4. Standing rules that survive this retirement

These outlive the spec and apply to any future work in this area:

1.  **Never bundle an API key.** Every vendor prohibits sharing, transferring or publishing keys;
    Nexar §1.2(xii) explicitly bars posting one "in any publicly accessible forum," which an
    open-source repository is. Any future integration is bring-your-own-key, per user, disabled by
    default. This also means the project holds no credentials to hand over if maintainership
    changes.
2.  **Never persist a distributor API response.** If a provider is ever added, its payload is
    session-scoped and never written to the library. Note that under a literal reading of Mouser §4,
    even storing a returned *datasheet URL* is storing "a portion of the Content."
3.  **Single-part, user-initiated lookups only.** DigiKey §5.1(d) and Mouser §4 both bar "providing
    a means to" bulk download. A "look up every part in my BOM" feature is the thing that would flip
    an otherwise-defensible integration into a clear breach.
4.  **Per-source attribution is mandatory**, not cosmetic. DigiKey §3.1.4, Mouser §5, element14 §1,
    Arrow and TME §8.7 all require it, and several require outbound links be preserved unobscured.
    The provenance model in the product plan already satisfies this.
5.  **Do not build on undocumented endpoints.** The unauthenticated JLCPCB cart endpoint returns
    richer data than several authorised APIs, and carries no licence grant of any kind. It can be
    WAF-blocked or removed without notice.
6.  **Web search is not automatically safer than an API.** Auto-fetching manufacturer datasheet PDFs
    runs into anti-automation clauses (TI prohibits "automated programs, data mining, robots,
    scrapers" and licenses downloads for "personal and non-commercial use"). Store the URL, let the
    user's browser fetch, or let the user supply the PDF.

## 5. Caveat

The analysis above is a careful reading of published terms by a non-lawyer, current as of
2026-08-18. Several vendors' terms are old (Mouser's are dated 2013) or unreadable from the public
web. Terms change. **If this decision is ever revisited, re-verify rather than trusting this
document**, and get a lawyer to read the vendor terms before shipping any distributor integration.

## 6. Module Map & Reference Links

*   [Root Architecture: SPEC-000](../../../specs/SPEC-000-architecture-overview.md)
*   [SPEC-202: Component Intelligence Pipeline](SPEC-202-component-intelligence-pipeline.md)
*   [SPEC-205: Datasheet-Driven Design Guidance](SPEC-205-datasheet-design-guidance.md)
*   Full research findings, with per-clause citations and source URLs: `docs/research/SPEC-203-supplier-api-exploration.md`
