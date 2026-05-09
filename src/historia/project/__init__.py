import importlib

from .._add_to_project import add_to_project, move_done_to_history, update_project_item_dates
from .._create_project import create_project_page

__all__ = ["add_to_project", "create_project_page", "move_done_to_history", "update_project_item_dates"]


def __getattr__(name: str):
    if name == "update":
        return importlib.import_module(".update", __name__)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
