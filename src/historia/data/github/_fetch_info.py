import functools
import os
import re
import typing
import warnings

import beartype
import requests


@beartype.beartype
def fetch_info_for_date(
    *,
    info_type: typing.Literal["prs_opened", "prs_assigned", "issues_opened", "issues_assigned"],
    date: str,
    username: str,
) -> tuple[list[str], bool]:
    """
    Fetch GitHub info (issues, PRs, etc.) created by a specific user on a specific date.

    The `assigned` types instead match items with an assignment event to the user on that date, read from each
    item's timeline. GitHub search has no qualifier for the date of assignment, so the search only narrows the
    candidates to items the user is currently assigned to and that were updated on or after the date.

    Parameters
    ----------
    info_type : Literal["prs_opened", "prs_assigned", "issues_opened", "issues_assigned"]
        The type of GitHub info to fetch.
    date : str
        The date for which to fetch GitHub info, in ISO format (e.g., "2026-01-01").
    username : str
        The GitHub username for which to fetch info.

    Returns
    -------
    list[str]
        A list of GitHub issue or pull request URLs for the specified date and user.
    bool
        Whether or not the GitHub API rate limit was hit during the query.

    """
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token is None:
        message = "\nPlease set the `GITHUB_TOKEN` environment variable with a valid GitHub Personal Access Token!\n\n"
        raise ValueError(message)
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
        token=github_token,
    )

    return result, hit_rate_limit


@functools.cache
def _format_graphql_queries(*, date: str, username: str) -> dict[str, str]:
    entities_to_graphql_query_template = {
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
        query: "assignee:{username} type:pr updated:>={date}"
        type: ISSUE
        first: $first
        after: $after
    ) {
        pageInfo { hasNextPage endCursor }
        edges {
            node {
                ... on PullRequest {
                    url
                    timelineItems(itemTypes: [ASSIGNED_EVENT], last: 20) {
                        nodes { ... on AssignedEvent { createdAt assignee { ... on User { login } } } }
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
        query: "assignee:{username} type:issue updated:>={date}"
        type: ISSUE
        first: $first
        after: $after
    ) {
        pageInfo { hasNextPage endCursor }
        edges {
            node {
                ... on Issue {
                    url
                    timelineItems(itemTypes: [ASSIGNED_EVENT], last: 20) {
                        nodes { ... on AssignedEvent { createdAt assignee { ... on User { login } } } }
                    }
                }
            }
        }
    }
}
"""
        ),
    }

    entities_to_graphql_query_mapping = {}
    for entity, query_template in entities_to_graphql_query_template.items():
        query = query_template.replace("{username}", username).replace("{date}", date)
        entities_to_graphql_query_mapping[entity] = query

    return entities_to_graphql_query_mapping


def _fetch_info_for_date_graphql(
    *,
    info_type: typing.Literal["prs_opened", "prs_assigned", "issues_opened", "issues_assigned"],
    date: str,
    username: str,
    token: str,
) -> tuple[list[str], bool]:
    entities_to_graphql_query_mapping = _format_graphql_queries(date=date, username=username)
    query = entities_to_graphql_query_mapping[info_type]

    if info_type in ("prs_assigned", "issues_assigned"):
        urls, hit_rate_limit = _fetch_assigned_urls(query=query, date=date, username=username, token=token)
        return urls, hit_rate_limit

    # 100 per page is required by the query and should be good enough for a single day
    nodes, _, hit_rate_limit = _post_search_query(query=query, variables={"first": 100}, token=token)
    if hit_rate_limit:
        return [], hit_rate_limit
    urls = [node["url"] for node in nodes]
    return urls, False


def _fetch_assigned_urls(*, query: str, date: str, username: str, token: str) -> tuple[list[str], bool]:
    urls: list[str] = []
    after_cursor = None
    while True:
        variables = {"first": 100, "after": after_cursor}
        nodes, after_cursor, hit_rate_limit = _post_search_query(query=query, variables=variables, token=token)
        if hit_rate_limit:
            return [], hit_rate_limit
        urls.extend(node["url"] for node in nodes if _was_assigned_on_date(node=node, date=date, username=username))
        if after_cursor is None:
            return urls, False


def _was_assigned_on_date(*, node: dict, date: str, username: str) -> bool:
    for event in node["timelineItems"]["nodes"]:
        assignee = event.get("assignee") or {}
        login = assignee.get("login", "")
        if login.lower() == username.lower() and event["createdAt"].startswith(date):
            return True
    return False


def _post_search_query(*, query: str, variables: dict, token: str) -> tuple[list[dict], str | None, bool]:
    """Run one page of a GraphQL search, returning its nodes, the next page cursor (if any), and a rate limit flag."""
    headers = {"Authorization": f"token {token}"}
    response = requests.post(
        url="https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        headers=headers,
        timeout=30,
    )
    status = response.status_code
    if status == 403:
        hit_rate_limit = True
        try:
            rate_limit_result = response.json()
        except requests.exceptions.JSONDecodeError:
            rate_limit_result = response.text.strip() or "<empty response body>"
        message = f"GitHub GraphQL API query `{query}` failed!\nStatus code {status}: {rate_limit_result}"
        warnings.warn(message=message, stacklevel=2)
        return [], None, hit_rate_limit
    try:
        result = response.json()
    except requests.exceptions.JSONDecodeError as exception:
        response_body = response.text.strip() or "<empty response body>"
        message = (
            f"GitHub GraphQL API query `{query}` failed!\n"
            f"Status code {status}: GitHub returned a non-JSON response body: {response_body}"
        )
        raise RuntimeError(message) from exception
    message = f"GitHub GraphQL API query `{query}` failed!\nStatus code {status}: {result}"
    if status != 200:
        raise RuntimeError(message)
    try:
        if result.get("errors") is not None:
            raise RuntimeError(message)
        search = result["data"]["search"]
        nodes = [edge["node"] for edge in search["edges"]]
        page_info = search.get("pageInfo") or {}
        next_cursor = page_info["endCursor"] if page_info.get("hasNextPage") else None
    except (AttributeError, KeyError, TypeError) as exception:
        unexpected_payload_message = (
            f"GitHub GraphQL API query `{query}` failed!\n"
            f"Status code {status}: GitHub returned an unexpected JSON payload: {result}"
        )
        raise RuntimeError(unexpected_payload_message) from exception
    return nodes, next_cursor, False
