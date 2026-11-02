"""Create a GitHub Project set up for historia."""

import collections.abc
import time

import beartype
import requests

from ._add_to_project import _check_graphql_response, _is_transient_failure, _post_graphql, _read_node_connection
from .._github import get_github_headers, post_graphql_once, retry_waits

_DATE_FIELD_NAMES = ("Start date", "End date")


@beartype.beartype
def create_project_page(*, owner: str, title: str, public: bool = False) -> dict[str, str]:
    """
    Create a GitHub Project (v2) page for the specified owner.

    The project gets the Start date and End date fields that the populate and update-dates commands fill in.
    If a step after creating the project fails, the project is deleted again, so a failed run leaves nothing behind.
    A request that fails on its way to or from GitHub is only repeated once GitHub shows it did not take effect,
    so a retry never makes a second project or field. Projects that already exist are never changed.

    Parameters
    ----------
    owner : str
        The GitHub user or organization login under which to create the project.
    title : str
        The title of the new GitHub Project.
    public : bool, default=False
        Whether the project should be publicly visible. GitHub's project-creation API always
        creates projects as private; when `public` is True, a follow-up mutation flips visibility
        immediately after creation.

    Returns
    -------
    dict[str, str]
        A dictionary containing the ``"id"`` and ``"url"`` of the created project.

    Raises
    ------
    ValueError
        If the ``GITHUB_TOKEN`` environment variable is not set, or if ``owner`` is neither a user nor an organization.
    RuntimeError
        If a request to GitHub fails. A rate limit (HTTP 403) is also issued as a warning. When the project was
        already created, the message says whether it was deleted again.

    """
    headers = get_github_headers()

    # Resolve the owner's global node ID (works for both users and organizations)
    owner_id = _get_owner_node_id(owner=owner, headers=headers)

    project = _create_project(owner_id=owner_id, title=title, headers=headers)
    try:
        for field_name in _DATE_FIELD_NAMES:
            _create_date_field(project_id=project["id"], field_name=field_name, headers=headers)
        if public:
            _set_project_visibility(project_id=project["id"], public=True, headers=headers)
    except Exception as exception:
        cleanup_outcome = _delete_unfinished_project(project=project, headers=headers)
        message = f"Setting up the new project `{title}` failed.\n{exception}\n{cleanup_outcome}"
        raise RuntimeError(message) from exception

    return project


def _create_project(*, owner_id: str, title: str, headers: dict[str, str]) -> dict[str, str]:
    """Create the project, adopting the one an attempt created when its response was lost instead of making another."""
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
    earlier_project_ids = {
        project["id"] for project in _list_projects_titled(owner_id=owner_id, title=title, headers=headers)
    }

    def _find_new_project() -> dict | None:
        projects = _list_projects_titled(owner_id=owner_id, title=title, headers=headers)
        return next((project for project in projects if project["id"] not in earlier_project_ids), None)

    project = _post_mutation_without_repeats(
        mutation=mutation,
        variables={"ownerId": owner_id, "title": title},
        headers=headers,
        context=f"GitHub GraphQL API mutation to create project `{title}` failed!",
        read_result=lambda data: data["createProjectV2"]["projectV2"],
        find_effect=_find_new_project,
    )
    return {"id": project["id"], "url": project["url"]}


def _create_date_field(*, project_id: str, field_name: str, headers: dict[str, str]) -> None:
    """
    Create a DATE field with the given name on a GitHub Project (v2), unless an earlier attempt already did.

    Parameters
    ----------
    project_id : str
        The global node ID of the project.
    field_name : str
        The name to assign to the new DATE field (e.g. ``"Start date"``).
    headers : dict[str, str]
        HTTP headers including the Authorization token.

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
    context = f"GitHub GraphQL API mutation to create field `{field_name}` failed!"

    def _find_field() -> dict | None:
        fields = _read_node_connection(
            node_id=project_id,
            node_type="ProjectV2",
            connection="fields",
            selection="{ ... on ProjectV2Field { id name } }",
            after_cursor=None,
            headers=headers,
            context=context,
        )
        return next((field for field in fields if field and field.get("name") == field_name), None)

    _post_mutation_without_repeats(
        mutation=mutation,
        variables={"projectId": project_id, "name": field_name},
        headers=headers,
        context=context,
        read_result=lambda data: data["createProjectV2Field"]["projectV2Field"],
        find_effect=_find_field,
    )


def _set_project_visibility(*, project_id: str, public: bool, headers: dict[str, str]) -> None:
    """Set the visibility of a GitHub Project (v2), which is safe to repeat."""
    mutation = """
mutation UpdateProjectVisibility($projectId: ID!, $public: Boolean!) {
    updateProjectV2(input: {projectId: $projectId, public: $public}) {
        projectV2 {
            id
        }
    }
}
"""
    response = _post_graphql(query=mutation, variables={"projectId": project_id, "public": public}, headers=headers)
    _check_graphql_response(response=response, context="GitHub GraphQL API mutation to set project visibility failed!")


def _delete_unfinished_project(*, project: dict[str, str], headers: dict[str, str]) -> str:
    """Delete a project whose setup failed, returning a sentence that says whether that worked."""
    mutation = """
mutation DeleteProject($projectId: ID!) {
    deleteProjectV2(input: {projectId: $projectId}) {
        projectV2 {
            id
        }
    }
}
"""
    try:
        response = _post_graphql(query=mutation, variables={"projectId": project["id"]}, headers=headers)
        _check_graphql_response(response=response, context="GitHub GraphQL API mutation to delete the project failed!")
    except (RuntimeError, requests.exceptions.RequestException) as exception:
        return (
            f"Deleting the unfinished project at {project['url']} failed as well, "
            f"so check whether it still exists and delete it by hand.\n{exception}"
        )
    return f"The unfinished project at {project['url']} was deleted again, so nothing was left behind."


def _list_projects_titled(*, owner_id: str, title: str, headers: dict[str, str]) -> list[dict]:
    """Return the ID and URL of every project of the owner whose title is exactly the given one."""
    projects = _read_node_connection(
        node_id=owner_id,
        node_type="ProjectV2Owner",
        connection="projectsV2",
        selection="{ id title url }",
        after_cursor=None,
        headers=headers,
        context=f"Failed to list the projects of the owner while creating `{title}`.",
    )
    return [project for project in projects if project and project.get("title") == title]


def _post_mutation_without_repeats(  # noqa: PLR0913
    *,
    mutation: str,
    variables: dict,
    headers: dict[str, str],
    context: str,
    read_result: collections.abc.Callable[[dict], dict],
    find_effect: collections.abc.Callable[[], dict | None],
) -> dict:
    """
    Post a mutation that must not take effect twice, retrying a transient failure only once its effect is absent.

    A transient failure, such as a 502 or a dropped connection, can arrive after GitHub has already applied the
    mutation. So after each one, ``find_effect`` looks for the object the mutation creates, and that object is used
    instead of posting again.

    Parameters
    ----------
    mutation : str
        The GraphQL mutation.
    variables : dict
        The variables of the mutation.
    headers : dict[str, str]
        HTTP headers including the Authorization token.
    context : str
        A descriptive label used in error and warning messages.
    read_result : callable
        Takes the ``data`` of a successful response and returns the created object.
    find_effect : callable
        Returns the object an earlier attempt created, or ``None`` if there is none.

    Returns
    -------
    dict
        The created object.

    """
    for wait_seconds in retry_waits():
        try:
            response: requests.Response | None = post_graphql_once(query=mutation, variables=variables, headers=headers)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            response = None
        if response is not None and not _is_transient_failure(response):
            return read_result(_check_graphql_response(response=response, context=context)["data"])
        time.sleep(wait_seconds)
        created = find_effect()
        if created is not None:
            return created

    response = post_graphql_once(query=mutation, variables=variables, headers=headers)
    return read_result(_check_graphql_response(response=response, context=context)["data"])


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

    Raises
    ------
    ValueError
        If neither the users nor the organizations endpoint resolves ``owner``.

    """
    for endpoint in (f"https://api.github.com/users/{owner}", f"https://api.github.com/orgs/{owner}"):
        response = requests.get(url=endpoint, headers=headers, timeout=30)
        if response.status_code == 200:
            return response.json()["node_id"]

    message = f"Could not resolve GitHub node ID for owner `{owner}`. Please verify the login is correct."
    raise ValueError(message)
