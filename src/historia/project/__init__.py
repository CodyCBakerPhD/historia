"""
Create a GitHub Project from the saved activity and keep its items up to date.

- ``create_project_page`` creates the project with Start date and End date fields.
- ``add_to_project`` adds each saved issue and pull request and sets its status, dates, and optionally members.
- ``update_project_item_dates`` and ``update_project_item_members`` refresh items already in the project.
- ``transition_status`` moves every item with one status to another.
- ``get_project_closing_workflows`` lists the enabled auto-close workflows that a status change can set off.
- ``get_project_info`` returns a ``ProjectInfo`` with the project's node ID and the IDs of the fields historia
  writes to.
"""

from ._add_to_project import (
    add_to_project,
    get_project_closing_workflows,
    get_project_info,
    transition_status,
    update_project_item_dates,
    update_project_item_members,
)
from ._create_project import create_project_page
from .._models import ProjectInfo

__all__ = [
    "ProjectInfo",
    "add_to_project",
    "create_project_page",
    "get_project_closing_workflows",
    "get_project_info",
    "transition_status",
    "update_project_item_dates",
    "update_project_item_members",
]
