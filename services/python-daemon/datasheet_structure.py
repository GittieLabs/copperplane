"""
Datasheet structure pass (SPEC-205 §2.2): locates candidate page ranges
in a real datasheet PDF before any extraction happens -- "the pipeline
locates before it extracts." Deliberately deterministic, no LLM call,
no network: a page range this module can't find is a real, honest
"couldn't locate the relevant sections" outcome (SPEC-205 §3's own
named risk -- "the fallback must be a clean... message rather than a
full-document sweep"), not something an LLM guesses around.

This module's own output (candidate page numbers per category) is
consumed by a later CTX-205.x's real Class A/B extraction over just
those pages -- kept separate from that extraction work so this
structure pass (the PDF-library choice, the heading/keyword matching
itself) is independently real and testable before any LLM cost is
spent on top of it.
"""
import re

import pdfplumber

# SPEC-205 §2.2's own listed structure-pass targets, each mapped to a
# real regex. Matched first against real detected *heading* text
# (_find_headings below) -- a real, deliberate change from this
# module's original "match anywhere on the page" design (CTX-205.1),
# found broken by real testing against a real 234-page ATtiny85
# datasheet: "reset" alone matched 84 of 234 real pages (register
# descriptions, interrupt vector tables -- anywhere the word appears in
# running prose, not the real Reset section), "clock"/"oscillator"
# matched 141. The same regexes now only need to be specific enough to
# match a real, short heading string ("Reset Sources", "Clock Systems
# and their Distribution"), which they already were.
CATEGORY_PATTERNS = {
    "absolute_maximum_ratings": re.compile(r"absolute maximum", re.IGNORECASE),
    "recommended_operating_conditions": re.compile(r"recommended operating", re.IGNORECASE),
    "power": re.compile(r"\bpower supply\b|\bsupply voltage\b|\bvcc\b", re.IGNORECASE),
    "decoupling": re.compile(r"decoupl", re.IGNORECASE),
    "reset": re.compile(r"\breset\b", re.IGNORECASE),
    "clock_oscillator": re.compile(r"\bclock\b|\boscillator\b|\bcrystal\b", re.IGNORECASE),
    "layout": re.compile(r"\blayout\b|\btrace length\b|\bpcb layout\b", re.IGNORECASE),
    "typical_application": re.compile(r"typical application", re.IGNORECASE),
}

# A real, numbered section-heading line -- "8.2 Reset Sources" (no
# trailing period, real ATtiny85 datasheet style) or "7. Absolute
# Maximum Ratings" (trailing period after the number, this module's
# own synthetic test fixture's style, and a real style other real
# datasheets use too). Anchored to the *whole line* (nothing after the
# title but whitespace) specifically to exclude a Table of Contents'
# own real dotted-leader-plus-page-number lines ("4.8 Reset and
# Interrupt Handling ....... 12"), which otherwise look identical up to
# that point -- confirmed against the real ATtiny85 ToC pages, not
# assumed.
_HEADING_PATTERN = re.compile(r"^[ \t]*\d+(?:\.\d+)*\.?[ \t]+([A-Za-z][A-Za-z0-9 /,&\-]{2,80})[ \t]*$", re.MULTILINE)

# A real, deliberate safety cap -- how many pages a single detected
# section (or, in the no-heading-found fallback, a single category's
# keyword-matched pages) can contribute as candidates. Without this, a
# real, long real section (or a real fallback keyword match with no
# real heading anywhere) could hand dozens of full pages of real text
# to a single downstream LLM call (`CTX-205.2`) -- real cost and
# latency, not just a theoretical concern; this is what actually broke
# against the real ATtiny85 document before this fix.
_MAX_SECTION_PAGES = 4


class DatasheetStructureError(Exception):
    """A real PDF this module cannot open or read at all -- fails closed
    rather than silently returning an empty page list, so a corrupt or
    unreadable cached datasheet (`library_store.cache_datasheet`'s own
    output) is a visible error, not indistinguishable from "no
    candidates found in a real, readable document"."""


def extract_pages(pdf_path: str) -> list[dict]:
    """Real, page-by-page text extraction -- `[{"page": 1, "text":
    "..."}, ...]`, 1-indexed to match how a citation is shown to a user
    (`§7.2 · p31`, SPEC-205 §5), not 0-indexed like `pdfplumber`'s own
    internal list. A page with no extractable text (a scanned image,
    not real text) gets an empty string, not a skipped entry -- every
    real page in the document is accounted for, since a later citation
    must be able to reference any page number that really exists."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            return [{"page": i, "text": page.extract_text() or ""} for i, page in enumerate(pdf.pages, start=1)]
    except Exception as exc:
        raise DatasheetStructureError(f"Could not read {pdf_path}: {exc}") from exc


# A real, genuine false positive found by testing against the real
# ATtiny85 datasheet: prose wrapped across lines can itself start with
# a number ("...an external\n10 kOhm pull-up resistor to VCC should be
# added...") -- indistinguishable from a real heading number by
# position alone. Every real heading found in that document and this
# module's own fixture is a handful of words; a component-value
# sentence caught by the same pattern runs much longer. A real, simple
# word-count cap, not a more elaborate Title-Case heuristic that would
# also need tuning against real, varied datasheet formatting.
_MAX_HEADING_WORDS = 8


def _find_headings(pages: list[dict]) -> list[dict]:
    """Every real numbered section-heading line found anywhere in the
    document, `[{"page": N, "title": "..."}]`, in real page order --
    used both to find a category's own real heading(s) and, via the
    *next* real heading anywhere (any category), to bound how far a
    found section actually extends."""
    headings = []
    for page in pages:
        for line in page["text"].splitlines():
            match = _HEADING_PATTERN.match(line)
            if not match:
                continue
            title = match.group(1).strip()
            if len(title.split()) > _MAX_HEADING_WORDS:
                continue
            headings.append({"page": page["page"], "title": title})
    return headings


def locate_candidate_sections(pages: list[dict]) -> dict[str, list[int]]:
    """Maps each real category in `CATEGORY_PATTERNS` to real candidate
    page numbers. Primary signal: a real detected heading (`_find_headings`)
    whose own title matches the category -- the section then runs from
    that heading's page up to (but not including) the next real heading
    anywhere in the document, capped at `_MAX_SECTION_PAGES`. A category
    with zero real heading matches anywhere falls back to the original
    whole-page keyword search (still capped) -- a real, honest fallback
    for a datasheet whose headings don't follow a numbered-section
    convention this module can detect, not the primary path.

    A category with no real candidates at all is present in the result
    with an empty list, not omitted -- callers (and eventually the UI's
    own first-class empty state, SPEC-205 §5) can tell "checked, found
    nothing" from "never checked"."""
    headings = _find_headings(pages)
    heading_pages = sorted({h["page"] for h in headings})
    last_page = pages[-1]["page"] if pages else 0
    candidates: dict[str, list[int]] = {}

    for category, pattern in CATEGORY_PATTERNS.items():
        matches = [h for h in headings if pattern.search(h["title"])]
        if matches:
            section_pages: set[int] = set()
            for match in matches:
                start = match["page"]
                later = [p for p in heading_pages if p > start]
                end = min(later) - 1 if later else last_page
                end = min(end, start + _MAX_SECTION_PAGES - 1)
                section_pages.update(range(start, end + 1))
            candidates[category] = sorted(section_pages)
        else:
            fallback_pages = [page["page"] for page in pages if pattern.search(page["text"])]
            candidates[category] = fallback_pages[:_MAX_SECTION_PAGES]

    return candidates
