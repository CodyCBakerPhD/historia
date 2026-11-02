"""Data models shared across the package."""

import typing


class ProjectInfo(typing.NamedTuple):
    """
    The node ID of a GitHub Project and the IDs of the fields historia writes to.

    Attributes
    ----------
    project_id : str
        The global node ID of the project.
    status_field_id : str
        The ID of the Status field.
    status_options : dict[str, str]
        The ID of each Status option, keyed by option name.
    start_date_field_id : str or None
        The ID of the "Start date" date field, or None if the project has none.
    end_date_field_id : str or None
        The ID of the "End date" date field, or None if the project has none.
    members_field_id : str or None
        The ID of the "Members" field, or None if the project has none.

    """

    project_id: str
    status_field_id: str
    status_options: dict[str, str]
    start_date_field_id: str | None
    end_date_field_id: str | None
    members_field_id: str | None
