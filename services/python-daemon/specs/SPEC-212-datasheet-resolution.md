---
id: SPEC-212
title: "Datasheet Resolution for Parts Nobody Publishes Individually (DECLINED)"
status: Deprecated
type: Feature
created: 2026-09-10
last_updated: 2026-09-10
target_version: n/a
location: "services/python-daemon/specs/SPEC-212-datasheet-resolution.md"
parent_spec: "SPEC-203-supplier-api-integration.md"
child_specs: []
user_facing: true
---

# SPEC-212: Datasheet Resolution for Parts Nobody Publishes Individually

> **Declined 2026-09-10, the day it was written. Kept for the measurement in §1, not the plan.**
>
> This reopened exactly one paragraph of `SPEC-203` — TME, datasheets only — because that spec ends
> with *"If this project ever does need distributor data, TME is the starting point."* The
> circumstance was real. The answer is still no:
>
> > *"i don't want to deal with licenses or having users use their own vendor api keys."*
>
> That rules out the entire approach rather than an implementation detail of it. §2.3 of `SPEC-203`
> is the *only* reason any distributor API is usable here, and it works by requiring the user to
> hold their own key — remove that and there is nothing left to build. `SPEC-203` §2.2's other
> vendors were never available at any price.
>
> **What is kept is §1's measurement**, which stands regardless: guessed datasheet URLs resolve 3 of
> 3 for an IC and 0 of 3 for passives, and no prompt fixes it. That is a real defect with a real
> cause, and it now needs a fix that involves no vendor account at all.
>
> **The fix taken instead** is `SPEC-203` §3's own row for this: *"Open this part at a distributor"
> → `SPEC-307` — a constructed deep link. No API, no key, compliant everywhere."* Applied to
> datasheets: when the guess fails, hand the user a working search rather than a dead link. That
> needs no terms review, no key, and no relationship with anybody.
>
> **What would reopen this:** not a better implementation. Only a source of per-part datasheet URLs
> that needs no user-held credential — which, per `SPEC-203` §2.2, does not currently exist.

## 1. Executive Summary & Goals

*   **High-Level Goal:** Resolve a real datasheet for a manufacturer part number when the model's
    guessed URL cannot work — which is every generic passive, the parts a first PCB is mostly made
    of.

*   **The gap, measured 2026-09-10.** `SPEC-306` resolves a datasheet by having the search agent
    guess the URL, then fetching it before opening so a bad guess fails in the app rather than in
    the browser. Driven through the app's own `library_store.cache_datasheet`:

    | search | datasheets fetched |
    | :--- | :--- |
    | `ATtiny85 microcontroller` | **3 of 3** — a real 3.7 MB PDF each time |
    | `220 ohm resistor LED current limiting` | **0 of 3** |
    | `0.1uF ceramic capacitor switch debounce` | **0 of 3** |

    Guessing works for ICs and fails completely for passives, and **no better prompt fixes it**. A
    220Ω resistor's datasheet is a family document covering hundreds of values; Yageo does not host
    `CFR-25JB-52-220R.pdf`. There is no correct URL to guess, so the model invents one and it 404s.

*   **Why this surfaced now.** `SPEC-328` shipped a surface that turns *"a blinking led controlled
    by a pushbutton"* into part categories and sends the user straight into `SPEC-306`'s search.
    That changed what gets searched — from ICs a user already named, to the resistors and
    capacitors every beginner project needs first. A path that was almost always fine became almost
    always broken, without either spec changing. Reported directly, on the maintainer's own board:
    *"part of this seems to work."*

*   **Business / Technical Value:** A card whose datasheet link always fails teaches the user to
    distrust the whole card, including the parts of it that are correct. `SPEC-306`'s confidence
    signal and `SPEC-328`'s suggestions both depend on the surface being believable.

*   **Non-Goals:**
    *   **Not pricing, stock or availability.** `SPEC-203` §2.1 is unchanged and still correct:
        those are the entire value of distributor APIs and are out of scope for this product.
    *   **Not pins, symbols, footprints or design guidance.** `SPEC-203` §2.1 verified that no
        vendor returns them, TME included. That finding is why 203 was retired and it still stands.
        `SPEC-202`, `SPEC-205` and `SPEC-308` own those and are not affected.
    *   **Not a second distributor.** `SPEC-203` §2.2 documents why every other vendor's terms
        forbid what this product is. Adding a second source is a new spec with a new terms review,
        not a configuration option.
    *   **Not replacing the guess.** The guess works for ICs and costs nothing. This is a fallback
        for when it fails, not a new first choice.

## 2. System Architecture & Design Choices

*Open questions this spec must settle:*

*   **Whether the terms actually say what `SPEC-203` §2.3 recorded.** Read on 2026-08-18 and not
    re-verified since — see §3, which treats this as the blocking risk rather than a formality.

*   **What happens for a user with no TME key.** Self-serve signup with the user holding their own
    key is what makes the terms work at all, so a key cannot be bundled. That means the default
    experience is unchanged and this only ever helps a user who opted in — which may make the whole
    feature not worth building, and that possibility belongs in §2, not in a footnote.

*   **Whether a family datasheet is an acceptable answer.** The honest result for `CFR-25JB-52-220R`
    is Yageo's whole carbon-film family document. Whether the app presents that as "the datasheet
    for this part" or as something weaker is a product decision with a wrong answer available.

*   **What is cached, and for how long.** `SPEC-203` §2.3 records TME as uniquely having **no
    caching prohibition**, which is the clause that makes a local-first tool possible at all. The
    scope of what this app stores still needs stating rather than assuming.

*   **Whether this belongs behind `SPEC-306`'s existing route** or beside it.

## 3. Known Constraints & Risks

*   **The terms have not been re-read, and this spec must not be built until they are.**
    `SPEC-203` §2.3's reading is dated **2026-08-18**. On 2026-09-10 I confirmed only two things:
    the service is still described as free of charge, and the Terms of Service document on
    `developers.tme.eu` is still dated **2026-07-01** — unchanged, which is consistent with that
    reading still holding. **I could not re-read the clauses themselves:** the PDF at
    `developers.tme.eu/pdfs/en/terms.pdf` returns 404 and `/en/rules` is behind a login.

    So §8.5's native-desktop licence, the absence of a caching prohibition, and the absence of a
    competing-product clause are all **second-hand** here. A human must read them before a key is
    requested. `SPEC-203` §2.2 is a list of what happens when a project assumes distributor terms
    permit the obvious thing.

*   **This is a distributor's data about a manufacturer's document.** TME returns a datasheet URL
    for a part it sells. A part it does not sell has no answer, and the app must say so rather than
    falling back to a guess and presenting it the same way.

*   **`SPEC-203`'s retirement was correct and this does not overturn it.** §2.1's finding — the APIs
    contribute nothing for pins, footprints or guidance — is what retired that spec and is
    untouched. This takes the one thing §2.1 says they *do* return, for the one vendor §2.3 says
    can be used, for the one case where the existing approach cannot work.

*   **A fallback that is slower and rarer than the primary path will be tested less.** The guess
    succeeds for ICs, so this code runs only for passives, only for opted-in users. That is the
    profile of a path that rots quietly.

## 4. Module Map & Reference Links

*   [SPEC-203](SPEC-203-supplier-api-integration.md) — the tombstone this reopens one paragraph of.
    **Read §2.1, §2.2 and §2.3 before writing any code here.**
*   [SPEC-306](../../../apps/tauri-ui/specs/SPEC-306-component-discovery.md) — where datasheet
    resolution lives today, and where the guess is made.
*   [SPEC-328](../../../apps/tauri-ui/specs/SPEC-328-project-intent-and-suggested-parts.md) — the
    surface that changed which searches get run.
*   `services/python-daemon/library_store.py` — `cache_datasheet`, the real fetch, and the
    `certifi` SSL context a bare `urllib` probe does not have.
*   `services/python-daemon/agentflow/agents/component_search.prompt.md` — the prompt that guesses
    the URL, including its own note that manufacturer product pages sit behind bot detection.
*   https://developers.tme.eu — API documentation and self-serve signup.

## 5. User & Interaction

*   **Product Stage:** Components — choosing a part, before anything is placed.

*   **What the user is trying to accomplish:** Reading the datasheet for a part they are
    considering. Today, for anything that is not an IC, they click "view datasheet" and get an
    error every time.

*   **What the user sees and does:** *(To settle: whether this is invisible — the link simply works
    where it used to fail — or whether a resolved-from-TME datasheet is labelled differently from a
    guessed one. §2's family-datasheet question decides it: if the answer is a family document
    rather than that exact part's, saying so is the honest framing and hiding it is the SPEC-203
    §2.2 mistake in miniature.)*
