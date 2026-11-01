"""
Collect GitHub activity for use in project dashboards.

historia saves the issues and pull requests that a GitHub user opened, was assigned, or reviewed, one JSON file
per day, and turns that history into a GitHub Project.

- ``historia.github``, also reachable as ``historia.data.github``, fetches the activity and saves it to disk.
- ``historia.project`` creates a GitHub Project and keeps its items in step with the saved activity.
- ``historia_cli`` is the ``historia`` command-line interface built on both.
"""

from . import data, project
from .data import github
from ._cli import historia_cli

__all__ = [
    "data",
    "github",
    "historia_cli",
    "project",
]
