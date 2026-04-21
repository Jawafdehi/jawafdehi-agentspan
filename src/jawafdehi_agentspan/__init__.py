"""Jawaf Span package."""

from jawafdehi_agentspan.win_compat import apply_patches as _apply_win_patches

_apply_win_patches()

__all__ = ["__version__"]

__version__ = "0.1.0"
