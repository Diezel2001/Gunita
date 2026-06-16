"""Keyword extraction module for BFAI.

Provides functions to extract meaningful keywords from natural language
queries using KeyBERT, enabling FTS5 keyword search to work with
full-sentence queries like "tell me about machine learning".

Uses ``sentence-transformers`` under the hood (already a project dependency).
The KeyBERT model is loaded lazily on first use.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy KeyBERT wrapper
# ---------------------------------------------------------------------------

_KEYBERT_MODEL: Any = None  # Singleton KeyBERT instance


def _get_keybert() -> Any:
    """Lazily import and return the KeyBERT model singleton.

    Returns:
        A ``KeyBERT`` instance, or ``None`` if keybert is not installed.

    Raises:
        ImportError: If ``keybert`` is not installed.
    """
    global _KEYBERT_MODEL
    if _KEYBERT_MODEL is not None:
        return _KEYBERT_MODEL

    try:
        from keybert import KeyBERT  # type: ignore[import-untyped]
    except ImportError as exc:
        raise ImportError(
            "keybert is not installed. Install it with: pip install keybert"
        ) from exc

    try:
        _KEYBERT_MODEL = KeyBERT(model="all-MiniLM-L6-v2")
        logger.info("Initialised KeyBERT model: all-MiniLM-L6-v2")
    except Exception as exc:
        logger.warning("Failed to initialise KeyBERT: %s", exc)
        _KEYBERT_MODEL = None

    return _KEYBERT_MODEL


def _is_natural_language_query(query: str) -> bool:
    """Heuristic: detect if a query looks like natural language vs. keywords.

    A query is considered natural language if it:
    - Contains more than 4 words, OR
    - Contains common English stop words (the, a, an, is, are, was, etc.)
      that suggest a sentence rather than keyword search terms.

    Args:
        query: The raw user query string.

    Returns:
        ``True`` if the query appears to be natural language.
    """
    words = query.lower().split()
    if len(words) <= 2:
        return False  # Short keyword queries pass through unchanged

    # Common stop words that indicate a sentence
    STOP_WORDS = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "shall", "can",
        "i", "you", "he", "she", "it", "we", "they", "me", "him",
        "her", "us", "them", "my", "your", "his", "its", "our",
        "their", "this", "that", "these", "those", "what", "which",
        "who", "whom", "when", "where", "why", "how", "all", "each",
        "every", "both", "few", "some", "any", "no", "not", "only",
        "own", "same", "so", "than", "too", "very", "just", "about",
        "above", "after", "again", "against", "because", "before",
        "between", "down", "during", "from", "in", "into", "off",
        "on", "out", "over", "through", "to", "under", "up", "with",
        "and", "but", "or", "nor", "for", "yet", "not", "if", "then",
        "else", "tell", "show", "give", "find", "get", "know", "want",
        "need", "like", "make", "use", "take", "look", "see", "come",
        "go", "think", "say", "mean", "describe", "explain", "list",
        "please", "help",
    }

    # Check if any word in the query is a stop word
    for w in words:
        if w in STOP_WORDS:
            return True

    return len(words) > 4  # Long queries are assumed to be natural language


def _strip_stop_words(query: str) -> str:
    """Simple fallback: strip common English stop words from a query.

    Used when KeyBERT is unavailable or fails. Preserves the remaining
    words joined by spaces for FTS5 matching.

    Args:
        query: The raw user query string.

    Returns:
        Query with stop words removed.
    """
    STOP_WORDS = {
        "a", "an", "the", "is", "are", "was", "were", "be", "been",
        "being", "have", "has", "had", "do", "does", "did", "will",
        "would", "could", "should", "may", "might", "shall", "can",
        "i", "you", "he", "she", "it", "we", "they", "me", "him",
        "her", "us", "them", "my", "your", "his", "its", "our",
        "their", "this", "that", "these", "those", "what", "which",
        "who", "whom", "when", "where", "why", "how", "all", "each",
        "every", "both", "few", "some", "any", "no", "not", "only",
        "own", "same", "so", "than", "too", "very", "just", "about",
        "above", "after", "again", "against", "because", "before",
        "between", "down", "during", "from", "in", "into", "off",
        "on", "out", "over", "through", "to", "under", "up", "with",
        "and", "but", "or", "nor", "for", "yet", "not", "if", "then",
        "else", "tell", "show", "give", "find", "get", "know", "want",
        "need", "like", "make", "use", "take", "look", "see", "come",
        "go", "think", "say", "mean", "describe", "explain", "list",
        "please", "help",
    }

    words = query.split()
    filtered = [w for w in words if w.lower() not in STOP_WORDS]
    return " ".join(filtered) if filtered else query


def extract_keywords(
    query: str,
    top_n: int = 5,
    use_keybert: bool = True,
) -> str:
    """Extract keywords from a natural language query for FTS5 search.

    Uses KeyBERT to extract the most relevant keywords/keyphrases, then
    returns them joined with ``OR`` so FTS5 matches any of them.

    If KeyBERT is unavailable or the query is short (already keyword-like),
    falls back to simple stop-word removal.

    Args:
        query: The raw user query string.
        top_n: Maximum number of keywords to extract (default 5).
        use_keybert: Whether to attempt KeyBERT extraction (default
            ``True``). Set to ``False`` to force stop-word removal only.

    Returns:
        An FTS5-compatible query string (terms joined with ``OR``).
    """
    if not query or not query.strip():
        return query

    # Short queries (2 words or fewer) are already keyword searches
    if len(query.split()) <= 2:
        return query

    # Try KeyBERT extraction
    if use_keybert:
        try:
            kw_model = _get_keybert()
            if kw_model is not None:
                keywords = kw_model.extract_keywords(
                    query,
                    keyphrase_ngram_range=(1, 2),  # Unigrams + bigrams
                    stop_words="english",
                    top_n=top_n,
                )
                # keywords = [("machine learning", 0.85), ("machine", 0.6), ...]
                if keywords:
                    terms = [kw for kw, _ in keywords if kw]
                    if terms:
                        result = " OR ".join(terms)
                        logger.debug(
                            "KeyBERT extracted keywords from %r → %r",
                            query, result,
                        )
                        return result
        except (ImportError, Exception) as exc:
            logger.debug("KeyBERT extraction failed, falling back: %s", exc)

    # Fallback: stop word removal
    result = _strip_stop_words(query)
    logger.debug("Stop-word fallback: %r → %r", query, result)
    return result if result.strip() else query