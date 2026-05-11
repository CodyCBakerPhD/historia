"""Sybil configuration for testing all code and CLI examples in the tutorial."""

import os
import shlex
import unittest.mock
from typing import Any

import click.testing
import pytest
import requests
import sybil
import sybil.parsers.myst

import historia

_TUTORIAL_GITHUB_OWNER = "CodyCBakerPhD"
_TUTORIAL_PROJECT_URL = "https://github.com/users/CodyCBakerPhD/projects/5"
_TUTORIAL_PROJECT_NUMBER = 5
_TUTORIAL_PROJECT_MOCK_RETURN: dict[str, str] = {
    "id": "PVT_tutorial_test_id",
    "url": _TUTORIAL_PROJECT_URL,
}

_cli_runner = click.testing.CliRunner()


def _graphql(*, query: str, variables: dict, headers: dict) -> dict:
    """Execute a GitHub GraphQL request and return the ``data`` payload."""
    response = requests.post(
        url="https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()
    result = response.json()
    if "errors" in result:
        message = f"GraphQL errors: {result['errors']}"
        raise RuntimeError(message)
    return result["data"]


def _get_project_node_id(*, headers: dict) -> str:
    """Return the node ID of the tutorial project."""
    data = _graphql(
        query="""
query($login: String!, $number: Int!) {
    user(login: $login) {
        projectV2(number: $number) {
            id
        }
    }
}
""",
        variables={"login": _TUTORIAL_GITHUB_OWNER, "number": _TUTORIAL_PROJECT_NUMBER},
        headers=headers,
    )
    return data["user"]["projectV2"]["id"]


def _list_project_item_ids(*, project_node_id: str, headers: dict) -> set[str]:
    """Return the set of project-item node IDs currently in the project."""
    item_ids: set[str] = set()
    after_cursor = None
    while True:
        data = _graphql(
            query="""
query($projectId: ID!, $after: String) {
    node(id: $projectId) {
        ... on ProjectV2 {
            items(first: 100, after: $after) {
                nodes { id }
                pageInfo { hasNextPage endCursor }
            }
        }
    }
}
""",
            variables={"projectId": project_node_id, "after": after_cursor},
            headers=headers,
        )
        items_data = data["node"]["items"]
        for node in items_data["nodes"]:
            item_ids.add(node["id"])
        if not items_data["pageInfo"]["hasNextPage"]:
            break
        after_cursor = items_data["pageInfo"]["endCursor"]
    return item_ids


def _delete_project_item(*, project_node_id: str, item_id: str, headers: dict) -> None:
    """Delete a single item from the project by its project-item node ID."""
    _graphql(
        query="""
mutation($projectId: ID!, $itemId: ID!) {
    deleteProjectV2Item(input: {projectId: $projectId, itemId: $itemId}) {
        deletedItemId
    }
}
""",
        variables={"projectId": project_node_id, "itemId": item_id},
        headers=headers,
    )


def _bash_evaluator(example: sybil.Example) -> str | None:
    """
    Evaluate a bash code block by running all ``historia`` commands via Click's test runner.

    Lines that are not ``historia`` commands (such as ``export``, ``curl``, ``git``,
    or comments) are silently skipped so that illustrative shell snippets do not
    cause the test to fail.

    ``$PROJECT_OWNER`` and ``$PROJECT_URL`` are expanded to their tutorial values
    before the command is parsed, mirroring how a user would set those variables
    in their shell before running the examples.
    """
    for raw_line in str(example.parsed).strip().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        line = line.replace("$PROJECT_OWNER", _TUTORIAL_GITHUB_OWNER)
        line = line.replace("$PROJECT_URL", _TUTORIAL_PROJECT_URL)
        if line.startswith("historia "):
            args = shlex.split(line[len("historia ") :])
            result = _cli_runner.invoke(historia.historia_cli, args)
            if result.exit_code != 0:
                return f"CLI command failed (exit code {result.exit_code}):\n{result.output}"
    return None


def _tutorial_setup(namespace: dict[str, Any]) -> None:
    """Patch only the project creation step; all other calls use the live network."""
    namespace["project_owner"] = _TUTORIAL_GITHUB_OWNER
    namespace["project_url"] = _TUTORIAL_PROJECT_URL
    patches = [
        unittest.mock.patch(
            "historia.project.create_project_page",
            return_value=_TUTORIAL_PROJECT_MOCK_RETURN,
        ),
        unittest.mock.patch(
            "historia._cli.create_project_page",
            return_value=_TUTORIAL_PROJECT_MOCK_RETURN,
        ),
    ]
    for patcher in patches:
        patcher.start()
    namespace["_patchers"] = patches

    github_token = os.getenv("GITHUB_TOKEN")
    if github_token:
        headers = {"Authorization": f"token {github_token}"}
        project_node_id = _get_project_node_id(headers=headers)
        namespace["_project_node_id"] = project_node_id
        namespace["_pre_test_item_ids"] = _list_project_item_ids(
            project_node_id=project_node_id,
            headers=headers,
        )
        namespace["_github_headers"] = headers


def _tutorial_teardown(namespace: dict[str, Any]) -> None:
    """Stop all patches and remove any project items added during the test run."""
    for patcher in namespace.get("_patchers", []):
        patcher.stop()

    project_node_id = namespace.get("_project_node_id")
    pre_test_item_ids = namespace.get("_pre_test_item_ids", set())
    headers = namespace.get("_github_headers", {})
    if project_node_id and headers:
        current_item_ids = _list_project_item_ids(project_node_id=project_node_id, headers=headers)
        for item_id in current_item_ids - pre_test_item_ids:
            _delete_project_item(project_node_id=project_node_id, item_id=item_id, headers=headers)


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    for item in items:
        if item.path.as_posix().endswith("docs/tutorial/index.md"):
            item.add_marker(pytest.mark.remote)


pytest_collect_file = sybil.Sybil(
    parsers=[
        sybil.parsers.myst.PythonCodeBlockParser(),
        sybil.parsers.myst.CodeBlockParser("bash", evaluator=_bash_evaluator),
        sybil.parsers.myst.SkipParser(),
    ],
    pattern="*.md",
    setup=_tutorial_setup,
    teardown=_tutorial_teardown,
).pytest()
