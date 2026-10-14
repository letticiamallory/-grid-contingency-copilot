"""Programmatic citation check (ADR-003): the quoted text must exist in the cited chunk."""

import unicodedata

# A quote shorter than this would match almost any text and prove nothing.
MIN_QUOTE_CHARS = 15


def normalize(text: str) -> str:
    """Case and whitespace insensitive. Accents are NOT stripped: a quote that differs by an
    accent is a different text and is rejected."""
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def quote_is_in(quote: str, source: str) -> bool:
    needle = normalize(quote)
    return len(needle) >= MIN_QUOTE_CHARS and needle in normalize(source)
