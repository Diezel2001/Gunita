"""Thin re-export of the unified Settings from BFAI.

Kept so that all 22 existing ``from gunita.config import settings``
import sites continue to work without changes.
"""

from bfai.config import settings  # noqa: F401