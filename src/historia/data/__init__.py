"""
Fetch and save activity from each supported data source.

GitHub is the only source so far, in ``historia.data.github``.
"""

from . import github

__all__ = ["github"]
