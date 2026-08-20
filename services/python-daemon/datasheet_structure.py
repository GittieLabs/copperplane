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
# real regex matched case-insensitively against a page's extracted
# text. Deliberately permissive (substring/keyword match, not just a
# heading pattern) -- a real datasheet's section boundaries vary too
# much across manufacturers to rely on heading formatting alone; a page
# is a real candidate for a category if it *mentions* that category's
# real subject matter anywhere on it, not only in a heading line.
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


def locate_candidate_sections(pages: list[dict]) -> dict[str, list[int]]:
    """Maps each real category in `CATEGORY_PATTERNS` to the real page
    numbers whose extracted text matches it. A category with no match
    anywhere in the document is present in the result with an empty
    list, not omitted -- callers (and eventually the UI's own
    first-class empty state, SPEC-205 §5) can tell "this category was
    checked and found nothing" from "this category was never checked"."""
    candidates: dict[str, list[int]] = {category: [] for category in CATEGORY_PATTERNS}
    for page in pages:
        text = page["text"]
        for category, pattern in CATEGORY_PATTERNS.items():
            if pattern.search(text):
                candidates[category].append(page["page"])
    return candidates
