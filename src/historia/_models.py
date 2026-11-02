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


class ItemInfo(typing.NamedTuple):
    """
    The node ID, type, state, and dates of a GitHub issue or pull request.

    Attributes
    ----------
    node_id : str
        The global node ID of the issue or pull request.
    item_type : str
        Either ``"PullRequest"`` or ``"Issue"``.
    item_state : str
        The state in lowercase, such as ``"open"``, ``"closed"``, or ``"merged"``.
    created_at : str
        The ISO 8601 creation timestamp.
    closed_at : str or None
        The ISO 8601 close timestamp, or None if the item is still open.

    """

    node_id: str
    item_type: str
    item_state: str
    created_at: str
    closed_at: str | None
