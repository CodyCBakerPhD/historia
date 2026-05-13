import os
import warnings

import beartype
import requests

_DEFAULT_STATUS_OPTIONS = [
    {"name": "Incoming", "color": "BLUE", "description": ""},
    {"name": "Backlog", "color": "GRAY", "description": ""},
    {"name": "Todo", "color": "YELLOW", "description": ""},
    {"name": "Agenda", "color": "ORANGE", "description": ""},
    {"name": "Done", "color": "GREEN", "description": ""},
    {"name": "History", "color": "PURPLE", "description": ""},
]

_DEFAULT_VIEWS = [
    {"name": "Sort incoming", "layout": "BOARD_LAYOUT", "filter": "-status:History"},
    {"name": "Roadmap", "layout": "ROADMAP_LAYOUT", "filter": "-status:Done,History"},
    {"name": "History", "layout": "ROADMAP_LAYOUT", "filter": "status:History"},
    {"name": "All Items", "layout": "TABLE_LAYOUT", "filter": ""},
]


@beartype.beartype
def create_project_page(*, owner: str, title: str) -> dict[str, str]:
    """
    Create a GitHub Project (v2) page for the specified owner.

    Parameters
    ----------
    owner : str
        The GitHub user or organization login under which to create the project.
    title : str
        The title of the new GitHub Project.

    Returns
    -------
    dict[str, str]
        A dictionary containing the ``"id"`` and ``"url"`` of the created project.
        Returns an empty dictionary if the GitHub API rate limit was hit (HTTP 403);
        a warning is also issued in that case.

    """
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token is None:
        message = "\nPlease set the `GITHUB_TOKEN` environment variable with a valid GitHub Personal Access Token!\n\n"
        raise ValueError(message)

    headers = {"Authorization": f"token {github_token}"}

    # Resolve the owner's global node ID (works for both users and organizations)
    owner_id = _get_owner_node_id(owner=owner, headers=headers)

    # Create the GitHub Project v2 via the GraphQL API
    mutation = """
mutation CreateProject($ownerId: ID!, $title: String!) {
    createProjectV2(input: {ownerId: $ownerId, title: $title}) {
        projectV2 {
            id
            url
        }
    }
}
"""
    variables = {"ownerId": owner_id, "title": title}
    response = requests.post(
        url="https://api.github.com/graphql",
        json={"query": mutation, "variables": variables},
        headers=headers,
        timeout=30,
    )
    status = response.status_code
    result = response.json()

    message = f"GitHub GraphQL API mutation to create project `{title}` failed!\nStatus code {status}: {result}"
    if status == 403:
        warnings.warn(message=message, stacklevel=2)
        return {}
    if "errors" in result or status != 200:
        raise RuntimeError(message)

    project = result["data"]["createProjectV2"]["projectV2"]
    project_id = project["id"]

    # Create the canonical date fields expected by the populate / update-dates commands.
    # The returned field IDs are not used here because the GitHub GraphQL API does not
    # support configuring roadmap view timeline fields via updateProjectV2View.
    _create_date_field(project_id=project_id, field_name="Start date", headers=headers)
    _create_date_field(project_id=project_id, field_name="End date", headers=headers)

    # Replace the default Status options and create the default set of views
    _setup_default_statuses(project_id=project_id, headers=headers)
    _setup_default_views(project_id=project_id, headers=headers)

    return {"id": project_id, "url": project["url"]}


def _create_date_field(*, project_id: str, field_name: str, headers: dict[str, str]) -> str:
    """
    Create a DATE field with the given name on a GitHub Project (v2).

    Parameters
    ----------
    project_id : str
        The global node ID of the project.
    field_name : str
        The name to assign to the new DATE field (e.g. ``"Start date"``).
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    Returns
    -------
    str
        The global node ID of the newly created field.

    """
    mutation = """
mutation CreateField($projectId: ID!, $name: String!) {
    createProjectV2Field(input: {projectId: $projectId, dataType: DATE, name: $name}) {
        projectV2Field {
            ... on ProjectV2Field {
                id
                name
            }
        }
    }
}
"""
    variables = {"projectId": project_id, "name": field_name}
    response = requests.post(
        url="https://api.github.com/graphql",
        json={"query": mutation, "variables": variables},
        headers=headers,
        timeout=30,
    )
    status = response.status_code
    result = response.json()

    if "errors" in result or status != 200:
        message = f"GitHub GraphQL API mutation to create field `{field_name}` failed!\nStatus code {status}: {result}"
        raise RuntimeError(message)

    return result["data"]["createProjectV2Field"]["projectV2Field"]["id"]


def _get_owner_node_id(*, owner: str, headers: dict[str, str]) -> str:
    """
    Resolve the GitHub node ID for a user or organization login.

    Parameters
    ----------
    owner : str
        The GitHub user or organization login.
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    Returns
    -------
    str
        The global node ID of the owner.

    """
    # Try user endpoint first, then organization endpoint
    for endpoint in (f"https://api.github.com/users/{owner}", f"https://api.github.com/orgs/{owner}"):
        response = requests.get(url=endpoint, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json()["node_id"]

    message = f"Could not resolve GitHub node ID for owner `{owner}`. Please verify the login is correct."
    raise ValueError(message)


def _get_status_field_id(*, project_id: str, headers: dict[str, str]) -> str:
    """
    Query the project for its built-in ``Status`` single-select field ID.

    Parameters
    ----------
    project_id : str
        The global node ID of the GitHub Project v2.
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    Returns
    -------
    str
        The global node ID of the Status field.

    """
    query = """
query GetProjectStatusField($projectId: ID!) {
    node(id: $projectId) {
        ... on ProjectV2 {
            fields(first: 20) {
                nodes {
                    ... on ProjectV2SingleSelectField {
                        id
                        name
                    }
                }
            }
        }
    }
}
"""
    response = requests.post(
        url="https://api.github.com/graphql",
        json={"query": query, "variables": {"projectId": project_id}},
        headers=headers,
        timeout=30,
    )
    status = response.status_code
    result = response.json()

    if "errors" in result or status != 200:
        message = f"GitHub GraphQL API query for project fields failed!\nStatus code {status}: {result}"
        raise RuntimeError(message)

    nodes = result["data"]["node"]["fields"]["nodes"]
    for node in nodes:
        if node.get("name") == "Status":
            return node["id"]

    message = "Could not find a 'Status' single-select field in the project."
    raise ValueError(message)


def _update_status_field_options(
    *,
    project_id: str,
    field_id: str,
    options: list[dict[str, str]],
    headers: dict[str, str],
) -> None:
    """
    Replace all options on a single-select field using ``updateProjectV2Field``.

    Parameters
    ----------
    project_id : str
        The global node ID of the GitHub Project v2.
    field_id : str
        The global node ID of the single-select field to update.
    options : list[dict[str, str]]
        Each entry must have ``"name"``, ``"color"``, and ``"description"`` keys.
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    """
    mutation = """
mutation UpdateStatusField(
    $projectId: ID!,
    $fieldId: ID!,
    $options: [ProjectV2SingleSelectFieldOptionInput!]!
) {
    updateProjectV2Field(input: {
        projectId: $projectId
        fieldId: $fieldId
        singleSelectOptions: $options
    }) {
        projectV2Field {
            ... on ProjectV2SingleSelectField {
                id
                name
            }
        }
    }
}
"""
    variables = {"projectId": project_id, "fieldId": field_id, "options": options}
    response = requests.post(
        url="https://api.github.com/graphql",
        json={"query": mutation, "variables": variables},
        headers=headers,
        timeout=30,
    )
    status = response.status_code
    result = response.json()

    if "errors" in result or status != 200:
        message = f"GitHub GraphQL API mutation to update Status field options failed!\nStatus code {status}: {result}"
        raise RuntimeError(message)


def _setup_default_statuses(*, project_id: str, headers: dict[str, str]) -> None:
    """
    Replace the default project Status options with the Historia canonical set.

    The options created (in order) are:
    Incoming, Backlog, Todo, Agenda, Done, History.

    Parameters
    ----------
    project_id : str
        The global node ID of the GitHub Project v2.
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    """
    field_id = _get_status_field_id(project_id=project_id, headers=headers)
    _update_status_field_options(
        project_id=project_id,
        field_id=field_id,
        options=_DEFAULT_STATUS_OPTIONS,
        headers=headers,
    )


def _get_default_view_id(*, project_id: str, headers: dict[str, str]) -> str | None:
    """
    Return the ID of the first existing view on the project, or ``None``.

    Parameters
    ----------
    project_id : str
        The global node ID of the GitHub Project v2.
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    Returns
    -------
    str or None
        The global node ID of the first project view, or ``None`` if no views exist.

    """
    query = """
query GetDefaultView($projectId: ID!) {
    node(id: $projectId) {
        ... on ProjectV2 {
            views(first: 1) {
                nodes {
                    id
                    name
                }
            }
        }
    }
}
"""
    response = requests.post(
        url="https://api.github.com/graphql",
        json={"query": query, "variables": {"projectId": project_id}},
        headers=headers,
        timeout=30,
    )
    status = response.status_code
    result = response.json()

    if "errors" in result or status != 200:
        message = f"GitHub GraphQL API query for project views failed!\nStatus code {status}: {result}"
        raise RuntimeError(message)

    nodes = result["data"]["node"]["views"]["nodes"]
    if nodes:
        return nodes[0]["id"]
    return None


def _update_project_view(
    *,
    project_id: str,
    view_id: str,
    name: str,
    layout: str,
    filter_text: str,
    headers: dict[str, str],
) -> None:
    """
    Update the name, layout, and filter of an existing project view.

    Parameters
    ----------
    project_id : str
        The global node ID of the GitHub Project v2.
    view_id : str
        The global node ID of the view to update.
    name : str
        The new name for the view.
    layout : str
        The new layout for the view (e.g. ``"BOARD_LAYOUT"``).
    filter_text : str
        The filter string to apply to the view (empty string for no filter).
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    """
    variables: dict = {
        "projectId": project_id,
        "viewId": view_id,
        "name": name,
        "layout": layout,
        "filterText": filter_text,
    }

    mutation = """
mutation UpdateView(
    $projectId: ID!,
    $viewId: ID!,
    $name: String!,
    $layout: ProjectV2ViewLayout!,
    $filterText: String!
) {
    updateProjectV2View(input: {
        projectId: $projectId
        viewId: $viewId
        name: $name
        layout: $layout
        filterBy: { text: $filterText }
    }) {
        projectV2View {
            id
            name
        }
    }
}
"""
    response = requests.post(
        url="https://api.github.com/graphql",
        json={"query": mutation, "variables": variables},
        headers=headers,
        timeout=30,
    )
    status = response.status_code
    result = response.json()

    if "errors" in result or status != 200:
        message = f"GitHub GraphQL API mutation to update view `{name}` failed!\nStatus code {status}: {result}"
        raise RuntimeError(message)


def _create_project_view(
    *,
    project_id: str,
    name: str,
    layout: str,
    filter_text: str,
    headers: dict[str, str],
) -> None:
    """
    Create a new project view and optionally apply a filter to it.

    Parameters
    ----------
    project_id : str
        The global node ID of the GitHub Project v2.
    name : str
        The name for the new view.
    layout : str
        The layout for the new view (e.g. ``"ROADMAP_LAYOUT"``).
    filter_text : str
        The filter string to apply (empty string for no filter).
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    """
    create_mutation = """
mutation CreateView($projectId: ID!, $name: String!, $layout: ProjectV2ViewLayout!) {
    createProjectV2View(input: {
        projectId: $projectId
        name: $name
        layout: $layout
    }) {
        projectV2View {
            id
            name
        }
    }
}
"""
    variables = {"projectId": project_id, "name": name, "layout": layout}
    response = requests.post(
        url="https://api.github.com/graphql",
        json={"query": create_mutation, "variables": variables},
        headers=headers,
        timeout=30,
    )
    status = response.status_code
    result = response.json()

    if "errors" in result or status != 200:
        message = f"GitHub GraphQL API mutation to create view `{name}` failed!\nStatus code {status}: {result}"
        raise RuntimeError(message)

    needs_update = filter_text != ""
    if not needs_update:
        return

    view_id = result["data"]["createProjectV2View"]["projectV2View"]["id"]
    _update_project_view(
        project_id=project_id,
        view_id=view_id,
        name=name,
        layout=layout,
        filter_text=filter_text,
        headers=headers,
    )


def _setup_default_views(*, project_id: str, headers: dict[str, str]) -> None:
    """
    Configure the default set of views for a newly created Historia project.

    If the project already has a view, it is repurposed as "Sort incoming"
    (Kanban board, filter ``-status:History``).  The remaining three views
    are always created fresh:

    - Roadmap (Roadmap layout, filter ``-status:Done,History``)
    - History (Roadmap layout, filter ``status:History``)
    - All Items (Table layout, no filter)

    Parameters
    ----------
    project_id : str
        The global node ID of the GitHub Project v2.
    headers : dict[str, str]
        HTTP headers including the Authorization token.

    """
    sort_incoming = _DEFAULT_VIEWS[0]
    remaining_views = _DEFAULT_VIEWS[1:]

    default_view_id = _get_default_view_id(project_id=project_id, headers=headers)
    if default_view_id is not None:
        _update_project_view(
            project_id=project_id,
            view_id=default_view_id,
            name=sort_incoming["name"],
            layout=sort_incoming["layout"],
            filter_text=sort_incoming["filter"],
            headers=headers,
        )
    else:
        _create_project_view(
            project_id=project_id,
            name=sort_incoming["name"],
            layout=sort_incoming["layout"],
            filter_text=sort_incoming["filter"],
            headers=headers,
        )

    for view in remaining_views:
        _create_project_view(
            project_id=project_id,
            name=view["name"],
            layout=view["layout"],
            filter_text=view["filter"],
            headers=headers,
        )
