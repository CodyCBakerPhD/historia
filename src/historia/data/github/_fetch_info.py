"""Fetch GitHub activity for a user and date through the GraphQL API."""

import functools
import re
import warnings

import beartype
import requests

from ..._github import format_request_id, get_github_headers, post_graphql_with_retries
from ..._globals import InfoType

_SEARCH_RESULT_LIMIT = 1000


@beartype.beartype
def fetch_info_for_date(
    *,
    info_type: InfoType,
    date: str,
    username: str,
) -> tuple[list[str], bool]:
    """
    Fetch GitHub info (issues, PRs, etc.) created by a specific user on a specific date.

    The `assigned` types instead match items with an assignment event to the user on that date, read from each
    item's timeline. GitHub search has no qualifier for the date of assignment, so the search only narrows the
    candidates to items the user is currently assigned to that were created on or before the date and updated on or
    after it. An item cannot be assigned before it exists, so the creation bound drops no candidate. It keeps an old
    date from matching every item made since then.
    The `prs_review_requested` and `prs_reviewed` types work the same way, matching a review request to the user or
    a review submitted by the user on that date.
    GitHub search returns at most 1,000 results. When more items match, a warning says that the rest were not
    checked.

    Parameters
    ----------
    info_type : InfoType
        The type of GitHub info to fetch. One of "prs_opened", "prs_assigned", "prs_review_requested",
        "prs_reviewed", "issues_opened", or "issues_assigned".
    date : str
        The date for which to fetch GitHub info, in ISO format (e.g., "2026-01-01"). It is a day in UTC.
    username : str
        The GitHub username for which to fetch info.

    Returns
    -------
    list[str]
        A list of GitHub issue or pull request URLs for the specified date and user.
    bool
        Whether or not the GitHub API rate limit was hit during the query.

    Raises
    ------
    ValueError
        If the ``GITHUB_TOKEN`` environment variable is not set, or if ``date`` is not in ISO format.

    """
    headers = get_github_headers()
    if re.match(pattern=r"^\d{4}-\d{2}-\d{2}$", string=date) is None:
        message = (
            f"\nDate `{date}` is not in the correct format!\n"
            "Please provide a date in ISO format (e.g., '2026-01-01').\n\n"
        )
        raise ValueError(message)

    result, hit_rate_limit = _fetch_info_for_date_graphql(
        info_type=info_type,
        date=date,
        username=username,
        headers=headers,
    )

    return result, hit_rate_limit


@functools.cache
def _format_graphql_queries(*, date: str, username: str) -> dict[str, str]:
    info_type_to_query_template = {
        "prs_opened": """
query OpenPRs($first: Int!) {
    search(
        query: "author:{username} type:pr created:{date}..{date}"
        type: ISSUE
        first: $first
    ) {
        edges {
            node {
                ... on PullRequest {
                    url
                }
            }
        }
    }
}
""",
        "prs_assigned": (
            """
query AssignedPRs($first: Int!, $after: String) {
    search(
        query: "assignee:{username} type:pr created:<={date} updated:>={date}"
        type: ISSUE
        first: $first
        after: $after
    ) {
        issueCount
        pageInfo { hasNextPage endCursor }
        edges {
            node {
                ... on PullRequest {
                    url
                    timelineItems(itemTypes: [ASSIGNED_EVENT], last: 100) {
                        nodes { ... on AssignedEvent { createdAt actor: assignee { ... on User { login } } } }
                    }
                }
            }
        }
    }
}
"""
        ),
        "prs_review_requested": (
            """
query ReviewRequestedPRs($first: Int!, $after: String) {
    search(
        query: "review-requested:{username} type:pr created:<={date} updated:>={date}"
        type: ISSUE
        first: $first
        after: $after
    ) {
        issueCount
        pageInfo { hasNextPage endCursor }
        edges {
            node {
                ... on PullRequest {
                    url
                    timelineItems(itemTypes: [REVIEW_REQUESTED_EVENT], last: 100) {
                        nodes {
                            ... on ReviewRequestedEvent { createdAt actor: requestedReviewer { ... on User { login } } }
                        }
                    }
                }
            }
        }
    }
}
"""
        ),
        "prs_reviewed": (
            """
query ReviewedPRs($first: Int!, $after: String) {
    search(
        query: "reviewed-by:{username} type:pr created:<={date} updated:>={date}"
        type: ISSUE
        first: $first
        after: $after
    ) {
        issueCount
        pageInfo { hasNextPage endCursor }
        edges {
            node {
                ... on PullRequest {
                    url
                    timelineItems(itemTypes: [PULL_REQUEST_REVIEW], last: 100) {
                        nodes { ... on PullRequestReview { createdAt: submittedAt actor: author { login } } }
                    }
                }
            }
        }
    }
}
"""
        ),
        "issues_opened": (
            """
query OpenIssues($first: Int!) {
    search(
        query: "author:{username} type:issue created:{date}..{date}"
        type: ISSUE
        first: $first
    ) {
        edges { node { ... on Issue { url } } }
    }
}
"""
        ),
        "issues_assigned": (
            """
query AssignedIssues($first: Int!, $after: String) {
    search(
        query: "assignee:{username} type:issue created:<={date} updated:>={date}"
        type: ISSUE
        first: $first
        after: $after
    ) {
        issueCount
        pageInfo { hasNextPage endCursor }
        edges {
            node {
                ... on Issue {
                    url
                    timelineItems(itemTypes: [ASSIGNED_EVENT], last: 100) {
                        nodes { ... on AssignedEvent { createdAt actor: assignee { ... on User { login } } } }
                    }
                }
            }
        }
    }
}
"""
        ),
    }

    info_type_to_query = {}
    for info_type, query_template in info_type_to_query_template.items():
        query = query_template.replace("{username}", username).replace("{date}", date)
        info_type_to_query[info_type] = query

    return info_type_to_query


def _fetch_info_for_date_graphql(
    *,
    info_type: InfoType,
    date: str,
    username: str,
    headers: dict[str, str],
) -> tuple[list[str], bool]:
    info_type_to_query = _format_graphql_queries(date=date, username=username)
    query = info_type_to_query[info_type]

    if info_type in ("prs_assigned", "prs_review_requested", "prs_reviewed", "issues_assigned"):
        urls, hit_rate_limit = _fetch_event_urls(query=query, date=date, username=username, headers=headers)
        return urls, hit_rate_limit

    # The query requires a page size. 100 should be enough for a single day
    nodes, _, _, hit_rate_limit = _post_search_query(query=query, variables={"first": 100}, headers=headers)
    if hit_rate_limit:
        return [], hit_rate_limit
    urls = [node["url"] for node in nodes]
    return urls, False


def _fetch_event_urls(*, query: str, date: str, username: str, headers: dict[str, str]) -> tuple[list[str], bool]:
    urls: list[str] = []
    after_cursor = None
    while True:
        variables = {"first": 100, "after": after_cursor}
        nodes, after_cursor, issue_count, hit_rate_limit = _post_search_query(
            query=query,
            variables=variables,
            headers=headers,
        )
        if hit_rate_limit:
            return [], hit_rate_limit
        urls.extend(node["url"] for node in nodes if _has_event_on_date(node=node, date=date, username=username))
        if after_cursor is None:
            if (issue_count or 0) > _SEARCH_RESULT_LIMIT:
                message = (
                    f"GitHub GraphQL API query `{query}` matched {issue_count} items, but GitHub search returns only "
                    f"the first {_SEARCH_RESULT_LIMIT}. "
                    f"The rest were not checked, so activity on {date} may be missing."
                )
                warnings.warn(message=message, stacklevel=2)
            return urls, False


def _has_event_on_date(*, node: dict, date: str, username: str) -> bool:
    """Whether a timeline event on the date names the user, under the `createdAt` and `actor` aliases of each query."""
    for event in node["timelineItems"]["nodes"]:
        actor = event.get("actor") or {}
        login = actor.get("login", "")
        # A pending review the user has not yet submitted has no submission date
        created_at = event.get("createdAt") or ""
        if login.lower() == username.lower() and created_at.startswith(date):
            return True
    return False


def _post_search_query(
    *,
    query: str,
    variables: dict,
    headers: dict[str, str],
) -> tuple[list[dict], str | None, int | None, bool]:
    """Run one page of a GraphQL search, returning its nodes, next page cursor, match count, and a rate limit flag."""
    response = post_graphql_with_retries(query=query, variables=variables, headers=headers)
    status = response.status_code
    request_id = format_request_id(response)
    if status == 403:
        hit_rate_limit = True
        try:
            rate_limit_result = response.json()
        except requests.exceptions.JSONDecodeError:
            rate_limit_result = response.text.strip() or "<empty response body>"
        message = f"GitHub GraphQL API query `{query}` failed!\nStatus code {status}: {rate_limit_result}\n{request_id}"
        warnings.warn(message=message, stacklevel=2)
        return [], None, None, hit_rate_limit
    try:
        result = response.json()
    except requests.exceptions.JSONDecodeError as exception:
        response_body = response.text.strip() or "<empty response body>"
        message = (
            f"GitHub GraphQL API query `{query}` failed!\n"
            f"Status code {status}: GitHub returned a non-JSON response body: {response_body}\n"
            f"{request_id}"
        )
        raise RuntimeError(message) from exception
    message = f"GitHub GraphQL API query `{query}` failed!\nStatus code {status}: {result}\n{request_id}"
    if status != 200:
        raise RuntimeError(message)
    try:
        if result.get("errors") is not None:
            raise RuntimeError(message)
        search = result["data"]["search"]
        nodes = [edge["node"] for edge in search["edges"]]
        page_info = search.get("pageInfo") or {}
        next_cursor = page_info["endCursor"] if page_info.get("hasNextPage") else None
        issue_count = search.get("issueCount")
    except (AttributeError, KeyError, TypeError) as exception:
        unexpected_payload_message = (
            f"GitHub GraphQL API query `{query}` failed!\n"
            f"Status code {status}: GitHub returned an unexpected JSON payload: {result}\n"
            f"{request_id}"
        )
        raise RuntimeError(unexpected_payload_message) from exception
    return nodes, next_cursor, issue_count, False
