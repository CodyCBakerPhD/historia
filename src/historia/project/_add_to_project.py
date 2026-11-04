"""Add saved GitHub activity to a GitHub Project and keep its fields up to date."""

import collections.abc
import datetime
import json
import pathlib
import re
import typing
import warnings

import beartype
import requests
import tqdm

from .._github import get_github_headers, is_server_error_or_not_json, post_graphql_with_retries
from .._models import ItemInfo, ProjectInfo

_TRANSIENT_ERROR_MESSAGE_PREFIX = "Something went wrong while executing your query"
_TEXT_FIELD_VALUE_SELECTION = """{
    ... on ProjectV2ItemFieldTextValue {
        text
        field { ... on ProjectV2Field { id } }
    }
}"""
_STATUS_FIELD_VALUE_SELECTION = """{
    ... on ProjectV2ItemFieldSingleSelectValue {
        optionId
        field { ... on ProjectV2SingleSelectField { id } }
    }
}"""
_ASSIGNEE_SELECTION = "{ login }"
_REVIEW_REQUEST_SELECTION = "{ requestedReviewer { ... on User { login } } }"
_REVIEW_SELECTION = "{ author { ... on User { login } } }"
_GITHUB_API_URL = "https://api.github.com"


def _parse_project_url(project_url: str, /) -> tuple[str, str, int]:
    """
    Parse owner type, owner login, and project number from a GitHub Project URL.

    Handles three URL formats:

    - ``https://github.com/users/{login}/projects/{number}``
    - ``https://github.com/orgs/{login}/projects/{number}``
    - ``https://github.com/{login}/projects/{number}``  (treated as a user project)

    Returns
    -------
    tuple[str, str, int]
        A tuple of (owner_type, owner_login, project_number).

    """
    parts = project_url.rstrip("/").split("/")
    if parts[3] in ("users", "orgs"):
        # Long format: https://github.com/users/{login}/projects/{number}
        owner_type = parts[3]
        owner_login = parts[4]
        project_number = int(parts[6])
    else:
        # Short user format: https://github.com/{login}/projects/{number}
        owner_type = "users"
        owner_login = parts[3]
        project_number = int(parts[5])
    return owner_type, owner_login, project_number


@beartype.beartype
def add_to_project(
    *,
    directory: pathlib.Path,
    project_url: str,
    status: str | None = None,
    end_date_placeholder_days: int = 180,
    assign_members: bool = False,
) -> None:
    """
    Add all unique URLs from the derivatives directory to a GitHub Project (v2).

    Items that are already present in the project are automatically skipped.

    An item that has moved since it was recorded, such as an issue transferred to another repository or anything in
    a renamed or transferred repository, is followed through the redirect GitHub leaves behind to its current URL.
    It is added under that URL, or skipped if the project already has it. The history files under ``directory`` are
    then rewritten to record the item at that URL, so later runs find it directly. URLs that lead to no issue or pull
    request even after following redirects are left as they are, skipped, and listed in a warning.

    For each new item:

    - If ``status`` is provided, all items are assigned that status value.
    - Otherwise, the status is derived from the item type and state:
      - If the Issue or PR is closed, it is given the 'Done' status.
      - If the item is an open PR, it is given the 'In Progress' status.
      - If the item is an open Issue, it is given the 'Todo' status.
    - The start date is set to the item's creation date.
    - The end date is set to the item's closed date (if closed), or to
      ``end_date_placeholder_days`` days after the creation date otherwise.

    Parameters
    ----------
    directory : pathlib.Path
        The directory containing the derivatives JSON files.
        Should be a specific username subdirectory,
        e.g., ``/path/to/version-1/username-codycbakerphd``.
        If a parent directory with multiple ``version-*`` subdirectories is provided,
        only the latest version is used and a warning is emitted.
    project_url : str
        The URL of the GitHub Project v2 to add items to,
        e.g., ``https://github.com/users/username/projects/1``
        or ``https://github.com/orgs/orgname/projects/1``.
    status : str or None, optional
        A custom status value to apply uniformly to all items added to the project.
        If ``None`` (the default), the status is derived from each item's type and state.
    end_date_placeholder_days : int, optional
        Number of days after the item's creation date to use as the placeholder end date
        when the item has not yet been closed. Default is 180 (approximately 6 months).
    assign_members : bool, optional
        When ``True``, update the project's custom ``Members`` text field using usernames
        inferred from ``username-*`` directory names in the data tree.

    Raises
    ------
    ValueError
        If the ``GITHUB_TOKEN`` environment variable is not set, or if ``assign_members`` is ``True``
        and the project has no ``Members`` field.

    """
    headers = get_github_headers()

    data_directory = _resolve_latest_version_data_directory(directory)

    url_to_members = _collect_url_member_usernames(data_directory) if assign_members else {}
    all_urls = list(url_to_members) if assign_members else _collect_unique_urls(data_directory)

    if not all_urls:
        warnings.warn(message=f"No URLs found in directory `{data_directory}`.", stacklevel=2)
        return

    project = _get_project_info(
        project_url=project_url,
        headers=headers,
    )

    owner_type, owner_login, project_number = _parse_project_url(project_url)

    validated_members_field_id: str | None = None
    if assign_members:
        if project.members_field_id is None:
            message = f"No 'Members' field found in project `{project_url}`."
            raise ValueError(message)
        validated_members_field_id = project.members_field_id
        existing_items = _list_project_items_with_member_values(
            owner_type=owner_type,
            owner_login=owner_login,
            project_number=project_number,
            members_field_id=validated_members_field_id,
            headers=headers,
        )
    else:
        existing_items = {
            url: {"item_id": "", "members": None}
            for url in _list_project_item_content_urls(
                owner_type=owner_type,
                owner_login=owner_login,
                project_number=project_number,
                headers=headers,
            )
        }

    if assign_members:
        for url in all_urls:
            if url in existing_items:
                _merge_existing_item_members(
                    project_id=project.project_id,
                    existing_item_info=existing_items[url],
                    usernames=url_to_members.get(url, set()),
                    members_field_id=typing.cast("str", validated_members_field_id),
                    headers=headers,
                )

    urls_to_add = [url for url in all_urls if url not in existing_items]
    moved_urls: dict[str, str] = {}
    unresolved_urls: list[str] = []
    for url in tqdm.tqdm(iterable=urls_to_add, desc="Adding items to project", unit="items", dynamic_ncols=True):

        # Determine the item type, state, and dates from the URL, following the item if it has moved since
        item_info = _get_item_info(url=url, headers=headers)
        current_url = url if item_info is not None else _resolve_current_url(url=url, headers=headers)
        if current_url is None:
            unresolved_urls.append(url)
            continue
        if current_url != url:
            moved_urls[url] = current_url

        # A moved item may already be on the project under its current URL, possibly added earlier in this loop
        if current_url in existing_items:
            if assign_members:
                _merge_existing_item_members(
                    project_id=project.project_id,
                    existing_item_info=existing_items[current_url],
                    usernames=url_to_members.get(url, set()),
                    members_field_id=typing.cast("str", validated_members_field_id),
                    headers=headers,
                )
            continue

        if item_info is None:
            item_info = _get_item_info(url=current_url, headers=headers)
            if item_info is None:
                unresolved_urls.append(url)
                continue

        item_id = _add_item_to_project(project_id=project.project_id, content_id=item_info.node_id, headers=headers)
        if item_id is None:
            continue

        member_usernames = url_to_members.get(url, set())
        _set_initial_project_item_fields(
            url=current_url,
            item_id=item_id,
            item=item_info,
            project=project,
            status=status,
            end_date_placeholder_days=end_date_placeholder_days,
            members_field_id=validated_members_field_id,
            member_usernames=member_usernames,
            headers=headers,
        )
        existing_items[current_url] = {
            "item_id": item_id,
            "members": _merge_member_values(current_value=None, usernames=member_usernames),
        }

    if moved_urls:
        _rewrite_moved_urls(directory=data_directory, moved_urls=moved_urls)

    if unresolved_urls:
        url_list = "\n".join(sorted(unresolved_urls))
        message = (
            f"Skipped {len(unresolved_urls)} recorded URL(s) that lead to no issue or pull request, even after "
            f"following redirects. The items may have been deleted, or the token may lack access to them.\n{url_list}"
        )
        warnings.warn(message=message, stacklevel=2)


def _iter_history_lists(directory: pathlib.Path, /) -> collections.abc.Iterator[tuple[pathlib.Path, list]]:
    """Yield the path and contents of each JSON file under ``directory`` that holds a list."""
    for info_file_path in directory.rglob(pattern="*.json"):
        with info_file_path.open(mode="r") as file_stream:
            info = json.load(file_stream)
        if isinstance(info, list):
            yield info_file_path, info


def _collect_unique_urls(directory: pathlib.Path, /) -> list[str]:
    """Collect all unique URLs from GraphQL JSON files under the given directory."""
    all_urls: set[str] = set()
    for _, info in _iter_history_lists(directory):
        for value in info:
            if isinstance(value, str):
                all_urls.add(value)
    return list(all_urls)


def _rewrite_moved_urls(*, directory: pathlib.Path, moved_urls: dict[str, str]) -> None:
    """Rewrite the history files under ``directory`` so each URL in ``moved_urls`` is recorded where it moved to."""
    for info_file_path, info in _iter_history_lists(directory):
        if not any(isinstance(value, str) and value in moved_urls for value in info):
            continue

        # A file listing an item under both its old and its current URL keeps a single entry for it
        rewritten_info: list = []
        for value in info:
            rewritten_value = moved_urls.get(value, value) if isinstance(value, str) else value
            if rewritten_value not in rewritten_info:
                rewritten_info.append(rewritten_value)
        with info_file_path.open(mode="w") as file_stream:
            json.dump(obj=rewritten_info, fp=file_stream, indent=1)


def _resolve_latest_version_data_directory(directory: pathlib.Path, /) -> pathlib.Path:
    """
    Return the directory to scan for project population data files.

    Parameters
    ----------
    directory : pathlib.Path
        User-supplied base directory for project population.

    Returns
    -------
    pathlib.Path
        ``directory`` by default. If ``directory`` contains more than one numeric
        ``version-*`` subdirectory, this returns only the highest version directory.

    Warns
    -----
    UserWarning
        Emitted when multiple numeric ``version-*`` directories are detected and
        only the highest version directory is selected.

    """
    if not directory.is_dir():
        return directory

    version_directories: list[tuple[int, pathlib.Path]] = []
    for child in directory.iterdir():
        if not child.is_dir() or not child.name.startswith("version-"):
            continue
        version_number = child.name.removeprefix("version-")
        if version_number.isdigit():
            version_directories.append((int(version_number), child))

    if len(version_directories) <= 1:
        return directory

    latest_version_entry = max(version_directories, key=lambda entry: entry[0])
    latest_version_directory = latest_version_entry[1]
    warnings.warn(
        message="Incompatible database versions detected! Using only the latest - please run database migration.",
        stacklevel=2,
    )
    return latest_version_directory


def _collect_url_member_usernames(directory: pathlib.Path, /) -> dict[str, set[str]]:
    """Map each URL under ``directory`` to the set of usernames inferred from its path."""
    url_to_members: dict[str, set[str]] = {}
    for info_file_path, info in _iter_history_lists(directory):
        username = _infer_username_from_data_path(directory=directory, info_file_path=info_file_path)
        for value in info:
            if not isinstance(value, str):
                continue
            url_to_members.setdefault(value, set()).add(username)

    return url_to_members


def _infer_username_from_data_path(*, directory: pathlib.Path, info_file_path: pathlib.Path) -> str:
    """
    Infer a username from the first ``username-*`` path segment for a data file.

    If no non-empty ``username-*`` segment exists in the file path relative to ``directory``,
    this falls back to ``directory.name``.

    Returns
    -------
    str
        The inferred username.

    """
    relative_parts = info_file_path.relative_to(directory).parts
    for part in relative_parts:
        if part.startswith("username-"):
            username = part.removeprefix("username-")
            if username:
                return username
    if directory.name.startswith("username-"):
        username = directory.name.removeprefix("username-")
        if username:
            return username
    return directory.name


def _merge_member_values(*, current_value: str | None, usernames: set[str]) -> str | None:
    """
    Merge existing member text with username values into a deduplicated list.

    Parameters
    ----------
    current_value : str or None
        Existing comma-separated value currently stored in the project's Members field.
    usernames : set[str]
        Usernames inferred from the local history directory structure.

    Returns
    -------
    str or None
        Sorted comma-separated member names, or ``None`` if no non-empty values are present.

    """
    values = {value.strip() for value in (current_value or "").split(",") if value.strip()}
    values.update({username.strip() for username in usernames if username.strip()})
    if not values:
        return None
    return ",".join(sorted(values))


def _normalize_member_value(current_value: str | None, /) -> str | None:
    """Return a normalized comma-separated member string for a current field value."""
    return _merge_member_values(current_value=current_value, usernames=set())


def _merge_existing_item_members(
    *,
    project_id: str,
    existing_item_info: dict[str, str | None],
    usernames: set[str],
    members_field_id: str,
    headers: dict[str, str],
) -> None:
    """Merge usernames into the Members field of an item already in the project, skipping writes that change nothing."""
    current_members = existing_item_info["members"]
    updated_members = _merge_member_values(current_value=current_members, usernames=usernames)
    if updated_members is None or updated_members == _normalize_member_value(current_members):
        return

    _set_item_text(
        project_id=project_id,
        item_id=typing.cast("str", existing_item_info["item_id"]),
        field_id=members_field_id,
        text=updated_members,
        headers=headers,
    )
    existing_item_info["members"] = updated_members


def _set_initial_project_item_fields(  # noqa: PLR0913
    *,
    url: str,
    item_id: str,
    item: ItemInfo,
    project: ProjectInfo,
    status: str | None,
    end_date_placeholder_days: int,
    members_field_id: str | None,
    member_usernames: set[str],
    headers: dict[str, str],
) -> None:
    """Set status/date/member fields for a newly added project item."""
    status_options = project.status_options
    status_name = _resolve_status_name(
        url=url,
        item_type=item.item_type,
        item_state=item.item_state,
        status=status,
    )
    if status_name is None:
        return

    option_id = status_options.get(status_name)
    if option_id is None:
        message = (
            f"Status option `{status_name}` not found in project. Available options: {list(status_options.keys())}."
        )
        warnings.warn(message=message, stacklevel=3)
        return

    _set_item_status(
        project_id=project.project_id,
        item_id=item_id,
        field_id=project.status_field_id,
        option_id=option_id,
        headers=headers,
    )
    _set_item_dates_for_content(
        item_id=item_id,
        item=item,
        project=project,
        end_date_placeholder_days=end_date_placeholder_days,
        headers=headers,
    )

    if members_field_id is not None:
        initial_members = _merge_member_values(
            current_value=None,
            usernames=member_usernames,
        )
        if initial_members is not None:
            _set_item_text(
                project_id=project.project_id,
                item_id=item_id,
                field_id=members_field_id,
                text=initial_members,
                headers=headers,
            )


def _resolve_status_name(*, url: str, item_type: str, item_state: str, status: str | None) -> str | None:
    """Resolve status name from explicit override or item type/state mapping."""
    if status is not None:
        return status

    status_name = {
        ("PullRequest", "closed"): "Done",
        ("PullRequest", "merged"): "Done",
        ("Issue", "closed"): "Done",
        ("PullRequest", "open"): "In Progress",
        ("Issue", "open"): "Todo",
    }.get((item_type, item_state))
    if status_name is None:
        message = f"Unrecognised item type/state combination `({item_type}, {item_state})` for `{url}`; skipping."
        warnings.warn(message=message, stacklevel=3)
    return status_name


def _derive_end_date(*, created_at: str, closed_at: str | None, end_date_placeholder_days: int) -> str:
    """Return the close date of a closed item, or its creation date plus the placeholder days for an open one."""
    if closed_at is not None:
        return closed_at[:10]
    creation_date = datetime.date.fromisoformat(created_at[:10])
    return (creation_date + datetime.timedelta(days=end_date_placeholder_days)).isoformat()


def _set_item_dates_for_content(
    *,
    item_id: str,
    item: ItemInfo,
    project: ProjectInfo,
    end_date_placeholder_days: int,
    headers: dict[str, str],
) -> None:
    """Set start and end date fields for a project item when date fields exist."""
    if project.start_date_field_id is not None:
        start_date = item.created_at[:10]  # Extract YYYY-MM-DD from ISO datetime
        _set_item_date(
            project_id=project.project_id,
            item_id=item_id,
            field_id=project.start_date_field_id,
            date=start_date,
            headers=headers,
        )

    if project.end_date_field_id is None:
        return

    end_date = _derive_end_date(
        created_at=item.created_at,
        closed_at=item.closed_at,
        end_date_placeholder_days=end_date_placeholder_days,
    )
    _set_item_date(
        project_id=project.project_id,
        item_id=item_id,
        field_id=project.end_date_field_id,
        date=end_date,
        headers=headers,
    )


def _post_graphql(*, query: str, variables: dict, headers: dict[str, str]) -> requests.Response:
    """
    Post a GraphQL query, retrying with exponential backoff on transient GitHub failures.

    GitHub occasionally fails a single request for a moment: its edge answers with a 5xx page, the connection drops,
    or the API answers 200 with an empty body or with only a generic "Something went wrong while executing your
    query" error. A repeat of the same request usually succeeds, and every query and mutation posted here is safe to
    repeat. The last response is returned regardless of its status so the caller can report it, and the last
    connection error is re-raised.

    Returns
    -------
    requests.Response
        The last response received, whatever its status.

    """
    return post_graphql_with_retries(
        query=query,
        variables=variables,
        headers=headers,
        is_transient=_is_transient_failure,
    )


def _is_transient_failure(response: requests.Response, /) -> bool:
    """Return ``True`` for a server error, or a 200 that is not JSON or whose only errors are GitHub's generic one."""
    if is_server_error_or_not_json(response):
        return True
    if response.status_code != 200:
        return False
    try:
        errors = response.json().get("errors")
    except AttributeError:
        return False
    if not isinstance(errors, list) or len(errors) == 0:
        return False
    return all(
        isinstance(error, dict)
        and isinstance(error.get("message"), str)
        and error["message"].startswith(_TRANSIENT_ERROR_MESSAGE_PREFIX)
        for error in errors
    )


def _check_graphql_response(*, response: requests.Response, context: str) -> dict:
    """
    Validate a GraphQL API response and raise or warn on errors.

    Parameters
    ----------
    response : requests.Response
        The HTTP response from the GitHub GraphQL API.
    context : str
        A descriptive label used in error/warning messages (e.g., the URL or mutation name).

    Returns
    -------
    dict
        The parsed JSON result from the response.

    Raises
    ------
    RuntimeError
        If the response is not valid JSON, has a non-200 status, or carries GraphQL errors.
        A 403 is also emitted as a warning before raising.

    """
    status = response.status_code
    try:
        result = response.json()
    except requests.exceptions.JSONDecodeError as exception:
        response_body = response.text.strip() or "<empty response body>"
        message = f"{context}\nStatus code {status}: GitHub GraphQL API response was not valid JSON: {response_body}"
        raise RuntimeError(message) from exception
    message = f"{context}\nStatus code {status}: {result}"
    if status == 403:
        warnings.warn(message=message, stacklevel=3)
        raise RuntimeError(message)
    if status != 200:
        raise RuntimeError(message)
    try:
        errors = result.get("errors")
    except AttributeError as exception:
        unexpected_payload_message = (
            f"{context}\nStatus code {status}: GitHub GraphQL API returned unexpected JSON payload: {result}"
        )
        raise RuntimeError(unexpected_payload_message) from exception
    if errors is not None:
        raise RuntimeError(message)
    return result


def _is_missing_project_item_error(*, response: requests.Response, item_id: str) -> bool:
    """Return ``True`` when a GraphQL response indicates the project item no longer exists."""
    if response.status_code != 200:
        return False

    result = response.json()
    errors = result.get("errors")
    if not isinstance(errors, list):
        return False

    for error in errors:
        if not isinstance(error, dict):
            continue
        if error.get("type") != "NOT_FOUND":
            continue
        message = error.get("message")
        if isinstance(message, str) and f"'{item_id}'" in message:
            return True
    return False


def _owner_root_field(owner_type: str, /) -> str:
    """Return the GraphQL root field for a project owner type: ``user`` for ``'users'``, else ``organization``."""
    return "user" if owner_type == "users" else "organization"


def _all_connection_nodes(  # noqa: PLR0913
    *,
    connection_data: dict,
    node_id: str | None,
    node_type: str,
    connection: str,
    selection: str,
    headers: dict[str, str],
    context: str,
) -> list[dict]:
    """
    Return every node of a nested connection, fetching the pages after the first one already in hand.

    A connection nested inside a list of nodes cannot take its own cursor in the same query, so each remaining page
    is read through ``node(id:)`` on the node that owns the connection.

    Parameters
    ----------
    connection_data : dict
        The connection as returned with its parent, holding ``nodes`` and ``pageInfo``.
    node_id : str or None
        The global node ID of the parent. It is only read when there are more pages.
    node_type : str
        The GraphQL type or interface of the parent that declares the connection, such as ``ProjectV2Item``.
    connection : str
        The name of the connection field, such as ``fieldValues``.
    selection : str
        The selection set for each node of the connection, including its braces.
    headers : dict[str, str]
        HTTP headers including the Authorization token.
    context : str
        A descriptive label used in error and warning messages.

    Returns
    -------
    list[dict]
        The nodes of every page, in order.

    Raises
    ------
    RuntimeError
        If more pages exist but the parent's node ID is unknown.

    """
    nodes = list(connection_data.get("nodes") or [])
    page_info = connection_data.get("pageInfo") or {}
    after_cursor = page_info.get("endCursor") if page_info.get("hasNextPage") else None
    if after_cursor is None:
        return nodes
    if node_id is None:
        message = f"{context}\nThe `{connection}` connection has more pages, but its parent has no node ID."
        raise RuntimeError(message)

    remaining_nodes = _read_node_connection(
        node_id=node_id,
        node_type=node_type,
        connection=connection,
        selection=selection,
        after_cursor=after_cursor,
        headers=headers,
        context=context,
    )
    return [*nodes, *remaining_nodes]


def _read_node_connection(  # noqa: PLR0913
    *,
    node_id: str,
    node_type: str,
    connection: str,
    selection: str,
    after_cursor: str | None,
    headers: dict[str, str],
    context: str,
) -> list[dict]:
    """Read a connection of the node with the given ID through ``node(id:)``, from a cursor through its last page."""
    query = """
query GetConnectionNodes($id: ID!, $after: String) {
    node(id: $id) {
        ... on {node_type} {
            {connection}(first: 100, after: $after) {
                nodes {selection}
                pageInfo { hasNextPage endCursor }
            }
        }
    }
}
""".replace("{node_type}", node_type).replace("{connection}", connection).replace("{selection}", selection)
    nodes: list[dict] = []
    while True:
        response = _post_graphql(query=query, variables={"id": node_id, "after": after_cursor}, headers=headers)
        result = _check_graphql_response(response=response, context=context)
        page = result["data"]["node"][connection]
        nodes.extend(page["nodes"])
        if not page["pageInfo"]["hasNextPage"]:
            return nodes
        after_cursor = page["pageInfo"]["endCursor"]


def _get_project_info(
    *,
    project_url: str,
    headers: dict[str, str],
) -> ProjectInfo:
    """
    Retrieve the project node ID and the IDs of its Status (with options), Start date, End date, and Members fields.

    Parameters
    ----------
    project_url : str
        The URL of the GitHub Project v2.
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    Returns
    -------
    ProjectInfo
        The project node ID and the IDs of its fields. A field the project lacks has None as its ID.

    Raises
    ------
    ValueError
        If the project has no ``Status`` field.

    """
    owner_type, owner_login, project_number = _parse_project_url(project_url)

    root_field = _owner_root_field(owner_type)
    query = """
query GetProject($login: String!, $number: Int!, $after: String) {
    {owner_root}(login: $login) {
        projectV2(number: $number) {
            id
            fields(first: 100, after: $after) {
                nodes {
                    ... on ProjectV2SingleSelectField {
                        id
                        name
                        options {
                            id
                            name
                        }
                    }
                    ... on ProjectV2Field {
                        id
                        name
                        dataType
                    }
                }
                pageInfo { hasNextPage endCursor }
            }
        }
    }
}
""".replace("{owner_root}", root_field)

    field_nodes: list[dict] = []
    after_cursor = None
    while True:
        variables = {"login": owner_login, "number": project_number, "after": after_cursor}
        response = _post_graphql(query=query, variables=variables, headers=headers)
        result = _check_graphql_response(
            response=response,
            context=f"Failed to retrieve project info for `{project_url}`.",
        )
        project_data = result["data"][root_field]["projectV2"]
        field_nodes.extend(project_data["fields"]["nodes"])
        page_info = project_data["fields"].get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        after_cursor = page_info["endCursor"]

    project_id = project_data["id"]

    status_field_id = None
    status_options: dict[str, str] = {}
    start_date_field_id = None
    end_date_field_id = None
    members_field_id = None

    for field in field_nodes:
        if not field:
            continue
        field_name = field.get("name", "")
        if field_name == "Status":
            status_field_id = field["id"]
            for option in field.get("options", []):
                status_options[option["name"]] = option["id"]
        elif field.get("dataType") == "DATE" and field_name == "Start date":
            start_date_field_id = field["id"]
        elif field.get("dataType") == "DATE" and field_name == "End date":
            end_date_field_id = field["id"]
        elif field_name == "Members":
            members_field_id = field["id"]

    if status_field_id is None:
        message = f"No 'Status' field found in project `{project_url}`."
        raise ValueError(message)

    return ProjectInfo(
        project_id=project_id,
        status_field_id=status_field_id,
        status_options=status_options,
        start_date_field_id=start_date_field_id,
        end_date_field_id=end_date_field_id,
        members_field_id=members_field_id,
    )


def _get_item_info(*, url: str, headers: dict[str, str]) -> ItemInfo | None:
    """
    Fetch the node ID, type (PullRequest or Issue), state, creation date, and closed date for the given URL.

    Parameters
    ----------
    url : str
        The GitHub URL of the PR or Issue.
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    Returns
    -------
    ItemInfo or None
        The item's node ID, type, state, and dates, or None if the URL does not resolve to a PR or Issue.

    """
    query = """
query GetItem($url: URI!) {
    resource(url: $url) {
        ... on PullRequest {
            id
            state
            createdAt
            closedAt
        }
        ... on Issue {
            id
            state
            createdAt
            closedAt
        }
    }
}
"""
    variables = {"url": url}
    response = _post_graphql(query=query, variables=variables, headers=headers)
    result = _check_graphql_response(response=response, context=f"Failed to retrieve item info for URL `{url}`.")

    resource = result["data"]["resource"]
    if resource is None:
        return None
    return ItemInfo(
        node_id=resource["id"],
        item_type="PullRequest" if "/pull/" in url else "Issue",
        item_state=resource["state"].lower(),
        created_at=resource["createdAt"],
        closed_at=resource.get("closedAt"),
    )


def _resolve_current_url(*, url: str, headers: dict[str, str]) -> str | None:
    """
    Return the URL at which an issue or pull request lives now, following it if it has moved since it was recorded.

    Renaming or transferring a repository, or transferring an issue to another repository, leaves the old URL
    redirecting to the new one. GraphQL ``resource(url:)`` does not follow that redirect, so it finds nothing at the
    old URL. The REST API answers it with the redirect instead, which ``requests`` follows to the item.

    Parameters
    ----------
    url : str
        The GitHub URL of the PR or Issue as it was recorded.
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    Returns
    -------
    str or None
        The current URL of the item, or None if the item cannot be found.

    """
    match = re.fullmatch(
        pattern=r"([^/]+)/([^/]+)/(?:issues|pull)/(\d+)",
        string=url.removeprefix("https://github.com/"),
    )
    if match is None:
        return None
    owner, repository, number = match.groups()

    # The issues endpoint also serves pull requests, and reports them under their `/pull/` URL
    response = requests.get(
        url=f"{_GITHUB_API_URL}/repos/{owner}/{repository}/issues/{number}",
        headers=headers,
        timeout=30,
    )
    if response.status_code != 200:
        return None

    return response.json()["html_url"]


def _add_item_to_project(*, project_id: str, content_id: str, headers: dict[str, str]) -> str | None:
    """
    Add an item to a GitHub Project v2 by its content node ID.

    Parameters
    ----------
    project_id : str
        The global node ID of the GitHub Project v2.
    content_id : str
        The global node ID of the PR or Issue to add.
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    Returns
    -------
    str or None
        The project item ID if successful, or None if rate-limited.

    Raises
    ------
    RuntimeError
        If the mutation fails with any status other than 403.

    """
    mutation = """
mutation AddItem($projectId: ID!, $contentId: ID!) {
    addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
        item {
            id
        }
    }
}
"""
    variables = {"projectId": project_id, "contentId": content_id}
    response = _post_graphql(query=mutation, variables=variables, headers=headers)
    try:
        result = _check_graphql_response(
            response=response,
            context=f"Failed to add item `{content_id}` to project `{project_id}`.",
        )
    except RuntimeError:
        if response.status_code == 403:
            return None
        raise

    return result["data"]["addProjectV2ItemById"]["item"]["id"]


def _set_item_status(
    *,
    project_id: str,
    item_id: str,
    field_id: str,
    option_id: str,
    headers: dict[str, str],
) -> None:
    """
    Set the Status field of a project item.

    Parameters
    ----------
    project_id : str
        The global node ID of the GitHub Project v2.
    item_id : str
        The project item ID.
    field_id : str
        The global node ID of the Status field.
    option_id : str
        The option ID for the desired status value.
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    Raises
    ------
    RuntimeError
        If the mutation fails with any status other than 403.

    """
    mutation = """
mutation SetStatus($projectId: ID!, $itemId: ID!, $fieldId: ID!, $optionId: String!) {
    updateProjectV2ItemFieldValue(
        input: {
            projectId: $projectId
            itemId: $itemId
            fieldId: $fieldId
            value: { singleSelectOptionId: $optionId }
        }
    ) {
        projectV2Item {
            id
        }
    }
}
"""
    variables = {
        "projectId": project_id,
        "itemId": item_id,
        "fieldId": field_id,
        "optionId": option_id,
    }
    response = _post_graphql(query=mutation, variables=variables, headers=headers)
    try:
        _check_graphql_response(
            response=response,
            context=f"Failed to set status for item `{item_id}` in project `{project_id}`.",
        )
    except RuntimeError:
        if response.status_code != 403:
            raise


def _set_item_date(
    *,
    project_id: str,
    item_id: str,
    field_id: str,
    date: str,
    headers: dict[str, str],
) -> None:
    """
    Set a date field of a project item.

    Parameters
    ----------
    project_id : str
        The global node ID of the GitHub Project v2.
    item_id : str
        The project item ID.
    field_id : str
        The global node ID of the date field.
    date : str
        The date value in ISO format (``YYYY-MM-DD``).
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    Raises
    ------
    RuntimeError
        If the mutation fails with any status other than 403, unless the item is missing from the project.

    """
    mutation = """
mutation SetDate($projectId: ID!, $itemId: ID!, $fieldId: ID!, $date: Date!) {
    updateProjectV2ItemFieldValue(
        input: {
            projectId: $projectId
            itemId: $itemId
            fieldId: $fieldId
            value: { date: $date }
        }
    ) {
        projectV2Item {
            id
        }
    }
}
"""
    variables = {
        "projectId": project_id,
        "itemId": item_id,
        "fieldId": field_id,
        "date": date,
    }
    response = _post_graphql(query=mutation, variables=variables, headers=headers)
    try:
        _check_graphql_response(
            response=response,
            context=f"Failed to set date for item `{item_id}` in project `{project_id}`.",
        )
    except RuntimeError:
        if response.status_code == 403:
            return
        if _is_missing_project_item_error(response=response, item_id=item_id):
            warnings.warn(
                message=f"Skipping date update for missing project item `{item_id}` in project `{project_id}`.",
                stacklevel=2,
            )
            return
        raise


def _set_item_text(
    *,
    project_id: str,
    item_id: str,
    field_id: str,
    text: str,
    headers: dict[str, str],
) -> None:
    """Set a text field value on a project item."""
    mutation = """
mutation SetText($projectId: ID!, $itemId: ID!, $fieldId: ID!, $text: String!) {
    updateProjectV2ItemFieldValue(
        input: {
            projectId: $projectId
            itemId: $itemId
            fieldId: $fieldId
            value: { text: $text }
        }
    ) {
        projectV2Item {
            id
        }
    }
}
"""
    variables = {
        "projectId": project_id,
        "itemId": item_id,
        "fieldId": field_id,
        "text": text,
    }
    response = _post_graphql(query=mutation, variables=variables, headers=headers)
    try:
        _check_graphql_response(
            response=response,
            context=f"Failed to set text for item `{item_id}` in project `{project_id}`.",
        )
    except RuntimeError:
        if response.status_code != 403:
            raise


def _is_item_recent(*, item: dict, cutoff_date: datetime.date) -> bool:
    """Return whether the item was created or closed on or after the cutoff date."""
    created_at: str = item["createdAt"]
    closed_at: str | None = item.get("closedAt")

    if datetime.date.fromisoformat(created_at[:10]) >= cutoff_date:
        return True

    return closed_at is not None and datetime.date.fromisoformat(closed_at[:10]) >= cutoff_date


@beartype.beartype
def update_project_item_dates(
    *,
    project_url: str,
    end_date_placeholder_days: int = 180,
    past_number_of_days: int | None = None,
) -> None:
    """
    Update the start and end date fields on items already added to a GitHub Project (v2).

    For each item considered:

    - The start date field ("Start date") is set to the item's creation date.
    - The end date field ("End date") is set to the item's closed date (if closed),
      or to ``end_date_placeholder_days`` days after the creation date otherwise.

    If the project does not have a "Start date" or "End date" field, those updates are skipped.

    Parameters
    ----------
    project_url : str
        The URL of the GitHub Project v2,
        e.g., ``https://github.com/users/username/projects/1``
        or ``https://github.com/orgs/orgname/projects/1``.
    end_date_placeholder_days : int, optional
        Number of days after the item's creation date to use as the placeholder end date
        when the item has not yet been closed. Default is 180 (approximately 6 months).
    past_number_of_days : int, optional
        Consider only items created or closed within this many most recent days.
        Both dates an item derives come from its creation and close timestamps, so an item
        untouched over that window would be written back the value it already holds.
        Every item is considered when this is not specified, which is what a first run or a
        backfill of a project whose items predate this field needs.

    Raises
    ------
    ValueError
        If the ``GITHUB_TOKEN`` environment variable is not set.

    """
    headers = get_github_headers()

    project = _get_project_info(
        project_url=project_url,
        headers=headers,
    )

    if project.start_date_field_id is None and project.end_date_field_id is None:
        warnings.warn(
            message=(
                f"Project `{project_url}` has no 'Start date' or 'End date' fields. No date updates were performed."
            ),
            stacklevel=2,
        )
        return

    owner_type, owner_login, project_number = _parse_project_url(project_url)

    all_items = _list_project_items_with_dates(
        owner_type=owner_type,
        owner_login=owner_login,
        project_number=project_number,
        headers=headers,
    )

    items_to_update = all_items
    if past_number_of_days is not None:
        cutoff_date = datetime.datetime.now(tz=datetime.timezone.utc).date() - datetime.timedelta(
            days=past_number_of_days,
        )
        items_to_update = [item for item in all_items if _is_item_recent(item=item, cutoff_date=cutoff_date)]

    for item in tqdm.tqdm(iterable=items_to_update, desc="Updating item dates", unit="items", dynamic_ncols=True):
        item_id = item["id"]
        created_at: str = item["createdAt"]
        closed_at: str | None = item.get("closedAt")

        if project.start_date_field_id is not None:
            start_date = created_at[:10]
            _set_item_date(
                project_id=project.project_id,
                item_id=item_id,
                field_id=project.start_date_field_id,
                date=start_date,
                headers=headers,
            )

        if project.end_date_field_id is not None:
            end_date = _derive_end_date(
                created_at=created_at,
                closed_at=closed_at,
                end_date_placeholder_days=end_date_placeholder_days,
            )
            _set_item_date(
                project_id=project.project_id,
                item_id=item_id,
                field_id=project.end_date_field_id,
                date=end_date,
                headers=headers,
            )


@beartype.beartype
def update_project_item_members(*, project_url: str) -> None:
    """
    Update the Members text field on all items already added to a GitHub Project (v2).

    The members of an item are everyone involved in it the way ``historia update github`` records involvement. That
    covers its author, its assignees, the users with a pending review request on a pull request, and the users who
    submitted a review of it. They are merged with the item's current Members value, so no name is ever removed.
    Only users count, not bots or teams. An item whose value would not change is not written.

    Parameters
    ----------
    project_url : str
        The URL of the GitHub Project v2,
        e.g., ``https://github.com/users/username/projects/1``
        or ``https://github.com/orgs/orgname/projects/1``.

    Raises
    ------
    ValueError
        If the ``GITHUB_TOKEN`` environment variable is not set.

    """
    headers = get_github_headers()

    project = _get_project_info(
        project_url=project_url,
        headers=headers,
    )

    if project.members_field_id is None:
        warnings.warn(
            message=f"Project `{project_url}` has no 'Members' field. No member updates were performed.",
            stacklevel=2,
        )
        return

    owner_type, owner_login, project_number = _parse_project_url(project_url)
    all_items = _list_project_items_with_member_usernames(
        owner_type=owner_type,
        owner_login=owner_login,
        project_number=project_number,
        members_field_id=project.members_field_id,
        headers=headers,
    )

    for item_id, current_members, member_usernames in tqdm.tqdm(
        iterable=all_items,
        desc="Updating item members",
        unit="items",
        dynamic_ncols=True,
    ):
        _merge_existing_item_members(
            project_id=project.project_id,
            existing_item_info={"item_id": item_id, "members": current_members},
            usernames=member_usernames,
            members_field_id=project.members_field_id,
            headers=headers,
        )


def _list_project_item_content_urls(
    *,
    owner_type: str,
    owner_login: str,
    project_number: int,
    headers: dict[str, str],
) -> set[str]:
    """
    Return the set of content URLs for all items already in the project.

    Parameters
    ----------
    owner_type : str
        Either ``'users'`` or ``'orgs'``.
    owner_login : str
        The GitHub login of the project owner.
    project_number : int
        The number of the GitHub Project v2.
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    Returns
    -------
    set[str]
        A set of content URLs (PR or Issue URLs) for all items currently in the project.

    """
    root_field = _owner_root_field(owner_type)
    query = """
query GetItemUrls($login: String!, $number: Int!, $after: String) {
    {owner_root}(login: $login) {
        projectV2(number: $number) {
            items(first: 100, after: $after) {
                nodes {
                    content {
                        ... on PullRequest { url }
                        ... on Issue { url }
                    }
                }
                pageInfo { hasNextPage endCursor }
            }
        }
    }
}
""".replace("{owner_root}", root_field)

    existing_urls: set[str] = set()
    after_cursor = None

    while True:
        variables = {"login": owner_login, "number": project_number, "after": after_cursor}
        response = _post_graphql(query=query, variables=variables, headers=headers)
        result = _check_graphql_response(
            response=response,
            context=(
                f"Failed to list project item URLs for project {project_number}"
                f" (owner_type={owner_type!r}, owner_login={owner_login!r})."
            ),
        )
        items_data = result["data"][root_field]["projectV2"]["items"]

        for node in items_data["nodes"]:
            content = node.get("content")
            if content and "url" in content:
                existing_urls.add(content["url"])

        page_info = items_data["pageInfo"]
        if not page_info["hasNextPage"]:
            break
        after_cursor = page_info["endCursor"]

    return existing_urls


def _list_project_items_with_dates(
    *,
    owner_type: str,
    owner_login: str,
    project_number: int,
    headers: dict[str, str],
) -> list[dict]:
    """
    Return all project items with their content creation and close dates.

    Parameters
    ----------
    owner_type : str
        Either ``'users'`` or ``'orgs'``.
    owner_login : str
        The GitHub login of the project owner.
    project_number : int
        The number of the GitHub Project v2.
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    Returns
    -------
    list[dict]
        A list of dicts, each with keys ``id``, ``createdAt``, and optionally ``closedAt``.

    """
    root_field = _owner_root_field(owner_type)
    query = """
query GetItems($login: String!, $number: Int!, $after: String) {
    {owner_root}(login: $login) {
        projectV2(number: $number) {
            items(first: 100, after: $after) {
                nodes {
                    id
                    content {
                        ... on PullRequest { createdAt closedAt }
                        ... on Issue { createdAt closedAt }
                    }
                }
                pageInfo { hasNextPage endCursor }
            }
        }
    }
}
""".replace("{owner_root}", root_field)

    all_items = []
    after_cursor = None

    while True:
        variables = {"login": owner_login, "number": project_number, "after": after_cursor}
        response = _post_graphql(query=query, variables=variables, headers=headers)
        result = _check_graphql_response(
            response=response,
            context=f"Failed to list project items for project {project_number}.",
        )
        items_data = result["data"][root_field]["projectV2"]["items"]

        for node in items_data["nodes"]:
            content = node.get("content")
            if content and "createdAt" in content:
                all_items.append(
                    {
                        "id": node["id"],
                        "createdAt": content["createdAt"],
                        "closedAt": content.get("closedAt"),
                    },
                )

        page_info = items_data["pageInfo"]
        if not page_info["hasNextPage"]:
            break
        after_cursor = page_info["endCursor"]

    return all_items


def _list_project_items_with_member_values(
    *,
    owner_type: str,
    owner_login: str,
    project_number: int,
    members_field_id: str,
    headers: dict[str, str],
) -> dict[str, dict[str, str | None]]:
    """Return project item IDs and current Members text values indexed by content URL."""
    root_field = _owner_root_field(owner_type)
    query = """
query GetItemsWithMembers($login: String!, $number: Int!, $after: String) {
    {owner_root}(login: $login) {
        projectV2(number: $number) {
            items(first: 100, after: $after) {
                nodes {
                    id
                    content {
                        ... on PullRequest { url }
                        ... on Issue { url }
                    }
                    fieldValues(first: 100) {
                        nodes {text_field_value_selection}
                        pageInfo { hasNextPage endCursor }
                    }
                }
                pageInfo { hasNextPage endCursor }
            }
        }
    }
}
""".replace("{owner_root}", root_field).replace("{text_field_value_selection}", _TEXT_FIELD_VALUE_SELECTION)
    context = f"Failed to list project member values for project {project_number}."

    items_by_url: dict[str, dict[str, str | None]] = {}
    after_cursor = None

    while True:
        variables = {"login": owner_login, "number": project_number, "after": after_cursor}
        response = _post_graphql(query=query, variables=variables, headers=headers)
        result = _check_graphql_response(response=response, context=context)
        items_data = result["data"][root_field]["projectV2"]["items"]

        for node in items_data["nodes"]:
            content = node.get("content")
            if not content or "url" not in content:
                continue

            field_values = _all_connection_nodes(
                connection_data=node["fieldValues"],
                node_id=node["id"],
                node_type="ProjectV2Item",
                connection="fieldValues",
                selection=_TEXT_FIELD_VALUE_SELECTION,
                headers=headers,
                context=context,
            )
            members_value = None
            for field_value in field_values:
                field = field_value.get("field")
                if field and field.get("id") == members_field_id:
                    members_value = field_value.get("text")
                    break

            items_by_url[content["url"]] = {"item_id": node["id"], "members": members_value}

        page_info = items_data["pageInfo"]
        if not page_info["hasNextPage"]:
            break
        after_cursor = page_info["endCursor"]

    return items_by_url


def _list_project_items_with_member_usernames(
    *,
    owner_type: str,
    owner_login: str,
    project_number: int,
    members_field_id: str,
    headers: dict[str, str],
) -> list[tuple[str, str | None, set[str]]]:
    """
    Return each project item's ID, its current Members value, and the users involved in its issue or pull request.

    Parameters
    ----------
    owner_type : str
        Either ``'users'`` or ``'orgs'``.
    owner_login : str
        The GitHub login of the project owner.
    project_number : int
        The number of the GitHub Project v2.
    members_field_id : str
        The global node ID of the Members field.
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    Returns
    -------
    list[tuple[str, str or None, set[str]]]
        For each item with content, its node ID, its Members text or None, and the logins of the author, the
        assignees, the users with a pending review request, and the users who submitted a review.

    """
    root_field = _owner_root_field(owner_type)
    query = """
query GetItemsWithMembers($login: String!, $number: Int!, $after: String) {
    {owner_root}(login: $login) {
        projectV2(number: $number) {
            items(first: 100, after: $after) {
                nodes {
                    id
                    fieldValues(first: 100) {
                        nodes {text_field_value_selection}
                        pageInfo { hasNextPage endCursor }
                    }
                    content {
                        ... on PullRequest {
                            id
                            author { ... on User { login } }
                            assignees(first: 100) {
                                nodes {assignee_selection}
                                pageInfo { hasNextPage endCursor }
                            }
                            reviewRequests(first: 100) {
                                nodes {review_request_selection}
                                pageInfo { hasNextPage endCursor }
                            }
                            latestReviews(first: 100) {
                                nodes {review_selection}
                                pageInfo { hasNextPage endCursor }
                            }
                        }
                        ... on Issue {
                            id
                            author { ... on User { login } }
                            assignees(first: 100) {
                                nodes {assignee_selection}
                                pageInfo { hasNextPage endCursor }
                            }
                        }
                    }
                }
                pageInfo { hasNextPage endCursor }
            }
        }
    }
}
""".replace("{owner_root}", root_field)
    query = query.replace("{text_field_value_selection}", _TEXT_FIELD_VALUE_SELECTION)
    query = query.replace("{assignee_selection}", _ASSIGNEE_SELECTION)
    query = query.replace("{review_request_selection}", _REVIEW_REQUEST_SELECTION)
    query = query.replace("{review_selection}", _REVIEW_SELECTION)
    context = f"Failed to list project members for project {project_number}."

    items_with_members: list[tuple[str, str | None, set[str]]] = []
    after_cursor = None

    while True:
        variables = {"login": owner_login, "number": project_number, "after": after_cursor}
        response = _post_graphql(query=query, variables=variables, headers=headers)
        result = _check_graphql_response(response=response, context=context)
        items_data = result["data"][root_field]["projectV2"]["items"]

        for node in items_data["nodes"]:
            content = node.get("content")
            if content is None:
                continue

            assignees = _all_connection_nodes(
                connection_data=content.get("assignees", {}),
                node_id=content.get("id"),
                node_type="Assignable",
                connection="assignees",
                selection=_ASSIGNEE_SELECTION,
                headers=headers,
                context=context,
            )
            review_requests = _all_connection_nodes(
                connection_data=content.get("reviewRequests", {}),
                node_id=content.get("id"),
                node_type="PullRequest",
                connection="reviewRequests",
                selection=_REVIEW_REQUEST_SELECTION,
                headers=headers,
                context=context,
            )
            reviews = _all_connection_nodes(
                connection_data=content.get("latestReviews", {}),
                node_id=content.get("id"),
                node_type="PullRequest",
                connection="latestReviews",
                selection=_REVIEW_SELECTION,
                headers=headers,
                context=context,
            )
            field_values = _all_connection_nodes(
                connection_data=node.get("fieldValues", {}),
                node_id=node["id"],
                node_type="ProjectV2Item",
                connection="fieldValues",
                selection=_TEXT_FIELD_VALUE_SELECTION,
                headers=headers,
                context=context,
            )
            current_members = next(
                (
                    field_value.get("text")
                    for field_value in field_values
                    if field_value and (field_value.get("field") or {}).get("id") == members_field_id
                ),
                None,
            )

            member_usernames: set[str] = set()

            author_login = (content.get("author") or {}).get("login")
            if author_login is not None:
                member_usernames.add(author_login)

            for assignee in assignees:
                assignee_login = assignee.get("login")
                if assignee_login is not None:
                    member_usernames.add(assignee_login)

            for review_request in review_requests:
                requested_reviewer = review_request.get("requestedReviewer")
                if requested_reviewer is None:
                    continue
                reviewer_login = requested_reviewer.get("login")
                if reviewer_login is not None:
                    member_usernames.add(reviewer_login)

            for review in reviews:
                review_author_login = (review.get("author") or {}).get("login")
                if review_author_login is not None:
                    member_usernames.add(review_author_login)

            items_with_members.append((node["id"], current_members, member_usernames))

        page_info = items_data["pageInfo"]
        if not page_info["hasNextPage"]:
            break
        after_cursor = page_info["endCursor"]

    return items_with_members


def _list_project_items_with_status(
    *,
    owner_type: str,
    owner_login: str,
    project_number: int,
    status_field_id: str,
    headers: dict[str, str],
) -> list[dict]:
    """
    Return all project items together with their current status option ID.

    Parameters
    ----------
    owner_type : str
        Either ``'users'`` or ``'orgs'``.
    owner_login : str
        The GitHub login of the project owner.
    project_number : int
        The number of the GitHub Project v2.
    status_field_id : str
        The global node ID of the Status field.
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    Returns
    -------
    list[dict]
        A list of dicts, each with keys ``id`` and ``status_option_id``.
        Items whose status field value cannot be determined have ``status_option_id`` set to ``None``.

    """
    root_field = _owner_root_field(owner_type)
    query = """
query GetItemsWithStatus($login: String!, $number: Int!, $after: String) {
    {owner_root}(login: $login) {
        projectV2(number: $number) {
            items(first: 100, after: $after) {
                nodes {
                    id
                    fieldValues(first: 100) {
                        nodes {status_field_value_selection}
                        pageInfo { hasNextPage endCursor }
                    }
                }
                pageInfo { hasNextPage endCursor }
            }
        }
    }
}
""".replace("{owner_root}", root_field).replace("{status_field_value_selection}", _STATUS_FIELD_VALUE_SELECTION)
    context = f"Failed to list project items with status for project {project_number}."

    all_items = []
    after_cursor = None

    while True:
        variables = {"login": owner_login, "number": project_number, "after": after_cursor}
        response = _post_graphql(query=query, variables=variables, headers=headers)
        result = _check_graphql_response(response=response, context=context)
        items_data = result["data"][root_field]["projectV2"]["items"]

        for node in items_data["nodes"]:
            item_id = node["id"]
            field_values = _all_connection_nodes(
                connection_data=node.get("fieldValues", {}),
                node_id=item_id,
                node_type="ProjectV2Item",
                connection="fieldValues",
                selection=_STATUS_FIELD_VALUE_SELECTION,
                headers=headers,
                context=context,
            )
            status_option_id = None
            for field_value in field_values:
                if not field_value:
                    continue
                field = field_value.get("field", {})
                if field and field.get("id") == status_field_id:
                    status_option_id = field_value.get("optionId")
                    break
            all_items.append({"id": item_id, "status_option_id": status_option_id})

        page_info = items_data["pageInfo"]
        if not page_info["hasNextPage"]:
            break
        after_cursor = page_info["endCursor"]

    return all_items


def _get_project_closing_workflows(
    *,
    project_url: str,
    headers: dict[str, str],
) -> list[str]:
    """
    Return the names of enabled project workflows that close the underlying GitHub items when status changes.

    Parameters
    ----------
    project_url : str
        The URL of the GitHub Project v2.
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    Returns
    -------
    list[str]
        Names of enabled workflows whose names indicate they close underlying items.

    """
    owner_type, owner_login, project_number = _parse_project_url(project_url)

    root_field = _owner_root_field(owner_type)
    query = """
query GetProjectWorkflows($login: String!, $number: Int!, $after: String) {
    {owner_root}(login: $login) {
        projectV2(number: $number) {
            workflows(first: 100, after: $after) {
                nodes {
                    name
                    enabled
                }
                pageInfo { hasNextPage endCursor }
            }
        }
    }
}
""".replace("{owner_root}", root_field)

    workflow_nodes: list[dict] = []
    after_cursor = None
    while True:
        variables = {"login": owner_login, "number": project_number, "after": after_cursor}
        response = _post_graphql(query=query, variables=variables, headers=headers)
        result = _check_graphql_response(
            response=response,
            context=f"Failed to retrieve workflows for `{project_url}`.",
        )
        workflows = result["data"][root_field]["projectV2"].get("workflows", {})
        workflow_nodes.extend(workflows.get("nodes", []))
        page_info = workflows.get("pageInfo") or {}
        if not page_info.get("hasNextPage"):
            break
        after_cursor = page_info["endCursor"]

    return [
        node["name"]
        for node in workflow_nodes
        if node and node.get("enabled") is True and "auto-close" in node.get("name", "").lower()
    ]


@beartype.beartype
def get_project_info(project_url: str, /) -> ProjectInfo:
    """
    Retrieve the node ID of a GitHub Project and the IDs of the fields historia writes to.

    Parameters
    ----------
    project_url : str
        The URL of the GitHub Project v2,
        e.g., ``https://github.com/users/username/projects/1``
        or ``https://github.com/orgs/orgname/projects/1``.

    Returns
    -------
    ProjectInfo
        The project node ID and the IDs of its Status (with options), Start date, End date, and Members fields.
        A field the project lacks has None as its ID.

    Raises
    ------
    ValueError
        If the ``GITHUB_TOKEN`` environment variable is not set, or if the project has no ``Status`` field.

    """
    headers = get_github_headers()
    return _get_project_info(project_url=project_url, headers=headers)


@beartype.beartype
def get_project_closing_workflows(project_url: str, /) -> list[str]:
    """
    Return the names of enabled project workflows that close the underlying GitHub items when status changes.

    Parameters
    ----------
    project_url : str
        The URL of the GitHub Project v2,
        e.g., ``https://github.com/users/username/projects/1``
        or ``https://github.com/orgs/orgname/projects/1``.

    Returns
    -------
    list[str]
        Names of enabled workflows whose names indicate they close underlying items (e.g., ``Auto-close issue``).
        Returns an empty list when no such workflows are enabled.

    Raises
    ------
    ValueError
        If the ``GITHUB_TOKEN`` environment variable is not set.

    """
    headers = get_github_headers()
    return _get_project_closing_workflows(project_url=project_url, headers=headers)


@beartype.beartype
def transition_status(*, project_url: str, current_status: str, new_status: str) -> None:
    """
    Move all items with one Status value to another in a GitHub Project (v2).

    Parameters
    ----------
    project_url : str
        The URL of the GitHub Project v2,
        e.g., ``https://github.com/users/username/projects/1``
        or ``https://github.com/orgs/orgname/projects/1``.
    current_status : str
        The current Status value to match.
    new_status : str
        The destination Status value to apply.

    Raises
    ------
    ValueError
        If the ``GITHUB_TOKEN`` environment variable is not set, or if the project
        does not have one of the specified status options.

    """
    headers = get_github_headers()

    project = _get_project_info(
        project_url=project_url,
        headers=headers,
    )

    current_option_id = project.status_options.get(current_status)
    if current_option_id is None:
        message = (
            f"Status option '{current_status}' not found in project `{project_url}`. "
            f"Available options: {list(project.status_options.keys())}."
        )
        raise ValueError(message)

    new_option_id = project.status_options.get(new_status)
    if new_option_id is None:
        message = (
            f"Status option '{new_status}' not found in project `{project_url}`. "
            f"Available options: {list(project.status_options.keys())}."
        )
        raise ValueError(message)

    owner_type, owner_login, project_number = _parse_project_url(project_url)

    all_items = _list_project_items_with_status(
        owner_type=owner_type,
        owner_login=owner_login,
        project_number=project_number,
        status_field_id=project.status_field_id,
        headers=headers,
    )

    items_to_move = [item for item in all_items if item["status_option_id"] == current_option_id]

    for item in tqdm.tqdm(
        iterable=items_to_move,
        desc=f"Moving items from {current_status} to {new_status}",
        unit="items",
        dynamic_ncols=True,
    ):
        _set_item_status(
            project_id=project.project_id,
            item_id=item["id"],
            field_id=project.status_field_id,
            option_id=new_option_id,
            headers=headers,
        )
