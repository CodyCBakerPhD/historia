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


def is_server_error_or_not_json(response: requests.Response, /) -> bool:
    """
    Whether a response is a server error (5xx), or a 200 whose body is not JSON.

    GitHub occasionally answers a GraphQL request with 200 and an empty body. That carries no GraphQL payload at all,
    so it is as transient as a 502.

    Parameters
    ----------
    response : requests.Response
        The response to classify.

    Returns
    -------
    bool
        Whether the response is a server error or a 200 without a JSON body.

    """
    if response.status_code >= 500:
        return True
    if response.status_code != 200:
        return False
    try:
        response.json()
    except requests.exceptions.JSONDecodeError:
        return True
    return False


def format_request_id(response: requests.Response, /) -> str:
    """
    Name the ID that GitHub gave a request, as the last line of an error message about its response.

    GitHub sends this ID in the ``X-GitHub-Request-Id`` header. GitHub Support can use it to trace the request.

    Parameters
    ----------
    response : requests.Response
        The response from GitHub.

    Returns
    -------
    str
        A line such as ``GitHub request ID: F469:1E5255:A85622:22BFE56:6ABB0329``.

    """
    request_id = response.headers.get("X-GitHub-Request-Id") or "<not given>"
    return f"GitHub request ID: {request_id}"


def post_graphql_with_retries(
    *,
    query: str,
    variables: dict,
    headers: dict[str, str],
    is_transient: collections.abc.Callable[[requests.Response], bool] = is_server_error_or_not_json,
) -> requests.Response:
    """
    Post a GraphQL query, retrying with exponential backoff on transient failures and dropped connections.

    GitHub occasionally fails a single request for a moment. Its edge answers with a 502 or 503 whose body is an
    HTML page rather than a GraphQL payload, the API answers 200 with an empty body, or the connection drops. A
    repeat of the same request usually succeeds. Up to five attempts are made, with waits of 2, 4, 8, and 16 seconds
    between them.

    Parameters
    ----------
    query : str
        The GraphQL query or mutation.
    variables : dict
        The variables of the query.
    headers : dict[str, str]
        The request headers, including the Authorization token.
    is_transient : callable, optional
        Whether a response is a transient failure worth repeating. By default, a server error (5xx) or a 200 whose
        body is not JSON is.

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
    for wait_seconds in retry_waits():
        try:
            response: requests.Response | None = post_graphql_once(query=query, variables=variables, headers=headers)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            response = None
        if response is not None and not is_transient(response):
            return response
        time.sleep(wait_seconds)
    return post_graphql_once(query=query, variables=variables, headers=headers)


def retry_waits() -> collections.abc.Iterator[float]:
    """
    Yield the wait in seconds before each retry of a GitHub request, doubling each time.

    Yields
    ------
    float
        The seconds to wait before the next attempt: 2, 4, 8, and 16, for five attempts in all.

    """
    wait_seconds = _INITIAL_BACKOFF_SECONDS
    for _ in range(_MAXIMUM_ATTEMPTS - 1):
        yield wait_seconds
        wait_seconds *= 2


def post_graphql_once(*, query: str, variables: dict, headers: dict[str, str]) -> requests.Response:
    """
    Post a GraphQL query or mutation once, without retrying.

    Parameters
    ----------
    query : str
        The GraphQL query or mutation.
    variables : dict
        The variables of the query.
    headers : dict[str, str]
        The request headers, including the Authorization token.

    Returns
    -------
    requests.Response
        The response, whatever its status.

    """
    return requests.post(
        url="https://api.github.com/graphql",
        json={"query": query, "variables": variables},
        headers=headers,
        timeout=30,
    )
