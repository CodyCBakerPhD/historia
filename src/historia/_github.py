"""Shared plumbing for GitHub API requests: the authentication headers and GraphQL posts with retries."""

import collections.abc
import os
import time

import requests

_MAXIMUM_ATTEMPTS = 5
_INITIAL_BACKOFF_SECONDS = 2.0


def get_github_headers() -> dict[str, str]:
    """
    Build the request headers that authenticate with the token in the ``GITHUB_TOKEN`` environment variable.

    Returns
    -------
    dict[str, str]
        The ``Authorization`` header for the GitHub API.

    Raises
    ------
    ValueError
        If the ``GITHUB_TOKEN`` environment variable is not set.

    """
    github_token = os.getenv("GITHUB_TOKEN")
    if github_token is None:
        message = "\nPlease set the `GITHUB_TOKEN` environment variable with a valid GitHub Personal Access Token!\n\n"
        raise ValueError(message)

    return {"Authorization": f"token {github_token}"}


def _is_server_error(response: requests.Response, /) -> bool:
    return response.status_code >= 500


def post_graphql_with_retries(
    *,
    query: str,
    variables: dict,
    headers: dict[str, str],
    is_transient: collections.abc.Callable[[requests.Response], bool] = _is_server_error,
) -> requests.Response:
    """
    Post a GraphQL query, retrying with exponential backoff on transient failures and dropped connections.

    GitHub occasionally fails a single request for a moment. Its edge answers with a 502 or 503 whose body is an
    HTML page rather than a GraphQL payload, or the connection drops, and a repeat of the same request usually
    succeeds. Up to five attempts are made, with waits of 2, 4, 8, and 16 seconds between them.

    Parameters
    ----------
    query : str
        The GraphQL query or mutation.
    variables : dict
        The variables of the query.
    headers : dict[str, str]
        The request headers, including the Authorization token.
    is_transient : callable, optional
        Whether a response is a transient failure worth repeating. By default, only a server error (5xx) is.

    Returns
    -------
    requests.Response
        The last response received, whatever its status, so the caller can report it.

    Raises
    ------
    requests.exceptions.ConnectionError
        If the last attempt fails to connect.
    requests.exceptions.Timeout
        If the last attempt times out.

    """
    backoff_seconds = _INITIAL_BACKOFF_SECONDS
    for _ in range(_MAXIMUM_ATTEMPTS - 1):
        try:
            response: requests.Response | None = _post_once(query=query, variables=variables, headers=headers)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            response = None
        if response is not None and not is_transient(response):
            return response
        time.sleep(backoff_seconds)
        backoff_seconds *= 2
    return _post_once(query=query, variables=variables, headers=headers)


def _post_once(*, query: str, variables: dict, headers: dict[str, str]) -> requests.Response:
    return requests.post(
        url="https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        headers=headers,
        timeout=30,
    )
