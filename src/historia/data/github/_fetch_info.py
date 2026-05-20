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
query AssignedPRs($first: Int!) {
    search(
        query: "assignee:{username} type:pr assigned:{date}..{date}"
        type: ISSUE
        first: $first
    ) {
        edges { node { ... on PullRequest { url } } }
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
query AssignedIssues($first: Int!) {
    search(
        query: "assignee:{username} type:issue assigned:{date}..{date}"
        type: ISSUE
        first: $first
    ) {
        edges { node { ... on Issue { url } } }
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
    variables = {
        "user": username,
        "date": date,
        "first": 100,  # Required by query, should be good enough for a single day
    }
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
        return [], hit_rate_limit
    try:
        result = typing.cast("dict[str, typing.Any]", response.json())
    except requests.exceptions.JSONDecodeError as exception:
        response_body = response.text.strip() or "<empty response body>"
        message = (
            f"GitHub GraphQL API query `{query}` failed!\n"
            f"Status code {status}: GitHub returned a non-JSON response body: {response_body}"
        )
        raise RuntimeError(message) from exception

    message = f"GitHub GraphQL API query `{query}` failed!\nStatus code {status}: {result}"
    hit_rate_limit = False
    if "errors" in result or status != 200:
        raise RuntimeError(message)

    unpacked_result = [node["node"]["url"] for node in result["data"]["search"]["edges"]]
    return unpacked_result, hit_rate_limit
