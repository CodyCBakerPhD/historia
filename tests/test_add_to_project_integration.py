import json
import os
import pathlib
import time
import warnings as _warnings_module

import pytest
import requests

import historia
from historia._add_to_project import _get_project_info

_TEST_PROJECT_URL = "https://github.com/users/CodyCBakerPhD/projects/5"
_KNOWN_CLOSED_PR_URL = "https://github.com/CodyCBakerPhD/work-history-data/pull/1"


def _has_valid_github_token() -> bool:
    token = os.getenv("GITHUB_TOKEN", "")
    return bool(token) and not token.startswith("fake")


def _make_headers() -> dict[str, str]:
    return {"Authorization": f"token {os.environ['GITHUB_TOKEN']}"}


def _list_project_items_with_urls(headers: dict[str, str]) -> dict[str, str]:
    """
    Return a mapping of {content_url: item_id} for ALL items in the test project.

    Uses cursor-based pagination to retrieve items beyond the first page.
    """
    query = """
query($login: String!, $number: Int!, $after: String) {
    user(login: $login) {
        projectV2(number: $number) {
            items(first: 100, after: $after) {
                nodes {
                    id
                    content {
                        ... on PullRequest { url }
                        ... on Issue { url }
                    }
                }
                pageInfo {
                    hasNextPage
                    endCursor
                }
            }
        }
    }
}
"""
    all_items: dict[str, str] = {}
    after_cursor = None

    while True:
        variables: dict = {"login": "CodyCBakerPhD", "number": 5, "after": after_cursor}
        response = requests.post(
            url="https://api.github.com/graphql",
            json={"query": query, "variables": variables},
            headers=headers,
            timeout=30,
        )
        if response.status_code == 403:
            error_message = "GitHub token lacks project permissions (403)"
            raise PermissionError(error_message)
        result = response.json()
        items_data = result["data"]["user"]["projectV2"]["items"]
        for node in items_data["nodes"]:
            if node.get("content") and node["content"].get("url"):
                all_items[node["content"]["url"]] = node["id"]
        page_info = items_data["pageInfo"]
        if not page_info["hasNextPage"]:
            break
        after_cursor = page_info["endCursor"]

    return all_items


def _delete_project_item(project_id: str, item_id: str, headers: dict[str, str]) -> None:
    """Delete a single item from the test project."""
    mutation = """
mutation($projectId: ID!, $itemId: ID!) {
    deleteProjectV2Item(input: {projectId: $projectId, itemId: $itemId}) {
        deletedItemId
    }
}
"""
    requests.post(
        url="https://api.github.com/graphql",
        json={"query": mutation, "variables": {"projectId": project_id, "itemId": item_id}},
        headers=headers,
        timeout=30,
    )


_SKIP_INTEGRATION = pytest.mark.skipif(
    (not _has_valid_github_token()) or os.getenv("RUN_INTEGRATION_TESTS") != "1",
    reason="Integration tests require a real GITHUB_TOKEN and RUN_INTEGRATION_TESTS=1",
)


@_SKIP_INTEGRATION
@pytest.mark.remote
@pytest.mark.ai_generated
def test_add_to_project_integration(tmp_path: pathlib.Path) -> None:
    """Integration test: adds a known closed PR to the test project, verifies it was added, then removes it."""
    headers = _make_headers()

    # Resolve the project node ID (needed for cleanup mutations).
    try:
        project_id, _, _, _, _, _ = _get_project_info(project_url=_TEST_PROJECT_URL, headers=headers)
    except (PermissionError, RuntimeError) as exc:
        pytest.skip(str(exc))

    # Pre-clean: remove the test PR from the project if it is already present
    # (e.g. from a previous run where cleanup was skipped).
    try:
        items_with_urls = _list_project_items_with_urls(headers=headers)
    except PermissionError as exc:
        pytest.skip(str(exc))
    if _KNOWN_CLOSED_PR_URL in items_with_urls:
        _delete_project_item(
            project_id=project_id,
            item_id=items_with_urls[_KNOWN_CLOSED_PR_URL],
            headers=headers,
        )
        time.sleep(1)  # Brief pause to let the delete propagate.

    (tmp_path / "urls.json").write_text(json.dumps([_KNOWN_CLOSED_PR_URL]))

    # Capture warnings so they appear in the failure message if the assertion fails.
    with _warnings_module.catch_warnings(record=True) as caught_warnings:
        _warnings_module.simplefilter("always")
        historia.project.add_to_project(directory=tmp_path, project_url=_TEST_PROJECT_URL)
    warning_messages = [str(w.message) for w in caught_warnings]

    # Poll for the newly-added item with retries to handle GitHub API replication lag.
    added_item_id = None
    items_after: dict[str, str] = {}
    for _ in range(6):
        items_after = _list_project_items_with_urls(headers=headers)
        added_item_id = items_after.get(_KNOWN_CLOSED_PR_URL)
        if added_item_id is not None:
            break
        time.sleep(2)

    diagnostic = (
        f"Warnings during add_to_project: {warning_messages}\n"
        f"URLs in project after (first 10): {list(items_after.keys())[:10]}"
    )

    try:
        assert (
            added_item_id is not None
        ), f"Expected {_KNOWN_CLOSED_PR_URL!r} to be present in the project after add_to_project.\n{diagnostic}"
    finally:
        # Always clean up, even if the assertion fails.
        if added_item_id is not None:
            _delete_project_item(project_id=project_id, item_id=added_item_id, headers=headers)
