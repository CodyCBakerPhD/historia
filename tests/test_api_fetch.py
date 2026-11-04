import re
import unittest.mock
import warnings

import pytest
import requests

import historia


@pytest.mark.ai_generated
def test_fetch_info_graphql(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "search": {
                "edges": [
                    {
                        "node": {
                            "url": "https://github.com/con/nwb2bids/issues/252",
                        },
                    },
                ],
            },
        },
    }
    with unittest.mock.patch("requests.post", return_value=mock_response):
        test_info, hit_rate_limit = historia.data.github.fetch_info_for_date(
            info_type="issues_opened",
            date="2026-01-05",
            username="codycbakerphd",
        )

    assert hit_rate_limit is False
    expected_info = ["https://github.com/con/nwb2bids/issues/252"]
    assert test_info == expected_info


@pytest.mark.ai_generated
def test_fetch_info_graphql_warns_on_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 403
    mock_response.json.return_value = {"message": "API rate limit exceeded"}

    with (
        unittest.mock.patch("requests.post", return_value=mock_response),
        pytest.warns(UserWarning, match="GitHub GraphQL API query"),
    ):
        test_info, hit_rate_limit = historia.data.github.fetch_info_for_date(
            info_type="issues_opened",
            date="2026-01-05",
            username="codycbakerphd",
        )

    assert test_info == []
    assert hit_rate_limit is True


def _bad_gateway_response() -> unittest.mock.MagicMock:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 502
    mock_response.text = "<html><head><title>502 Bad Gateway</title></head></html>"
    mock_response.json.side_effect = requests.exceptions.JSONDecodeError("Expecting value", "<html>", 0)
    return mock_response


def _empty_ok_response() -> unittest.mock.MagicMock:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.text = ""
    mock_response.json.side_effect = requests.exceptions.JSONDecodeError("Expecting value", "", 0)
    return mock_response


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("non_json_response", "expected_message"),
    [
        (_bad_gateway_response(), "Status code 502: GitHub returned a non-JSON response body: <html>"),
        (_empty_ok_response(), "Status code 200: GitHub returned a non-JSON response body: <empty response body>"),
    ],
    ids=["bad_gateway", "empty_ok"],
)
def test_fetch_info_graphql_raises_on_persistent_non_json_response(
    monkeypatch: pytest.MonkeyPatch,
    non_json_response: unittest.mock.MagicMock,
    expected_message: str,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    with (
        unittest.mock.patch("requests.post", return_value=non_json_response) as mock_post,
        unittest.mock.patch("time.sleep") as mock_sleep,
        pytest.raises(RuntimeError, match=re.escape(expected_message)),
    ):
        historia.data.github.fetch_info_for_date(
            info_type="issues_opened",
            date="2026-01-05",
            username="codycbakerphd",
        )

    assert mock_post.call_count == 5
    slept_seconds = [call.args[0] for call in mock_sleep.call_args_list]
    assert slept_seconds == [2.0, 4.0, 8.0, 16.0]


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "transient_failure",
    [
        _bad_gateway_response(),
        _empty_ok_response(),
        requests.exceptions.ConnectionError("connection reset"),
        requests.exceptions.ReadTimeout("read timed out"),
    ],
    ids=["bad_gateway", "empty_ok", "connection_error", "timeout"],
)
def test_fetch_info_graphql_retries_transient_failures(
    monkeypatch: pytest.MonkeyPatch,
    transient_failure: unittest.mock.MagicMock | Exception,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    success_response = unittest.mock.MagicMock()
    success_response.status_code = 200
    success_response.json.return_value = {
        "data": {"search": {"edges": [{"node": {"url": "https://github.com/con/nwb2bids/issues/252"}}]}},
    }

    with (
        unittest.mock.patch("requests.post", side_effect=[transient_failure, success_response]) as mock_post,
        unittest.mock.patch("time.sleep") as mock_sleep,
    ):
        test_info, hit_rate_limit = historia.data.github.fetch_info_for_date(
            info_type="issues_opened",
            date="2026-01-05",
            username="codycbakerphd",
        )

    assert hit_rate_limit is False
    expected_info = ["https://github.com/con/nwb2bids/issues/252"]
    assert test_info == expected_info
    assert mock_post.call_count == 2
    slept_seconds = [call.args[0] for call in mock_sleep.call_args_list]
    assert slept_seconds == [2.0]


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("status_code", "payload"),
    [
        (200, None),
        (401, {"message": "Bad credentials"}),
        (200, {"errors": [{"message": 'Parse error on "}" (RCURLY)'}]}),
        (200, {"data": None}),
    ],
    ids=["empty_ok", "bad_credentials", "graphql_errors", "unexpected_payload"],
)
@pytest.mark.parametrize(
    ("headers", "expected_last_line"),
    [
        (
            {"X-GitHub-Request-Id": "F469:1E5255:A85622:22BFE56:6ABB0329"},
            "GitHub request ID: F469:1E5255:A85622:22BFE56:6ABB0329",
        ),
        ({}, "GitHub request ID: <not given>"),
    ],
    ids=["request_id", "no_request_id"],
)
def test_fetch_info_graphql_error_ends_with_the_github_request_id(
    monkeypatch: pytest.MonkeyPatch,
    status_code: int,
    payload: dict | None,
    headers: dict[str, str],
    expected_last_line: str,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = status_code
    mock_response.headers = requests.structures.CaseInsensitiveDict(headers)
    if payload is None:
        mock_response.text = ""
        mock_response.json.side_effect = requests.exceptions.JSONDecodeError("Expecting value", "", 0)
    else:
        mock_response.json.return_value = payload

    with (
        unittest.mock.patch("requests.post", return_value=mock_response),
        unittest.mock.patch("time.sleep"),
        pytest.raises(RuntimeError) as caught,
    ):
        historia.data.github.fetch_info_for_date(
            info_type="issues_opened",
            date="2026-01-05",
            username="codycbakerphd",
        )

    assert str(caught.value).splitlines()[-1] == expected_last_line


@pytest.mark.ai_generated
def test_fetch_info_graphql_raises_on_persistent_connection_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    with (
        unittest.mock.patch(
            "requests.post",
            side_effect=requests.exceptions.ConnectionError("connection reset"),
        ) as mock_post,
        unittest.mock.patch("time.sleep"),
        pytest.raises(requests.exceptions.ConnectionError, match="connection reset"),
    ):
        historia.data.github.fetch_info_for_date(
            info_type="issues_opened",
            date="2026-01-05",
            username="codycbakerphd",
        )

    assert mock_post.call_count == 5


@pytest.mark.ai_generated
def test_fetch_info_graphql_does_not_retry_client_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {"message": "Bad credentials"}

    with (
        unittest.mock.patch("requests.post", return_value=mock_response) as mock_post,
        unittest.mock.patch("time.sleep") as mock_sleep,
        pytest.raises(RuntimeError, match="Status code 401"),
    ):
        historia.data.github.fetch_info_for_date(
            info_type="issues_opened",
            date="2026-01-05",
            username="codycbakerphd",
        )

    assert mock_post.call_count == 1
    assert mock_sleep.call_count == 0


@pytest.mark.ai_generated
def test_fetch_info_graphql_validates_date(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    with pytest.raises(ValueError, match="correct format"):
        historia.data.github.fetch_info_for_date(
            info_type="issues_opened",
            date="2026/01/05",
            username="codycbakerphd",
        )


@pytest.mark.ai_generated
def test_fetch_info_graphql_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(ValueError, match="GITHUB_TOKEN"):
        historia.data.github.fetch_info_for_date(
            info_type="issues_opened",
            date="2026-01-05",
            username="codycbakerphd",
        )


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("info_type", "expected_search_query"),
    [
        ("prs_opened", "author:codycbakerphd type:pr created:2026-01-05..2026-01-05"),
        ("prs_assigned", "assignee:codycbakerphd type:pr created:<=2026-01-05 updated:>=2026-01-05"),
        ("prs_review_requested", "review-requested:codycbakerphd type:pr created:<=2026-01-05 updated:>=2026-01-05"),
        ("prs_reviewed", "reviewed-by:codycbakerphd type:pr created:<=2026-01-05 updated:>=2026-01-05"),
        ("issues_opened", "author:codycbakerphd type:issue created:2026-01-05..2026-01-05"),
        ("issues_assigned", "assignee:codycbakerphd type:issue created:<=2026-01-05 updated:>=2026-01-05"),
    ],
)
def test_fetch_info_graphql_search_query(
    monkeypatch: pytest.MonkeyPatch,
    info_type: str,
    expected_search_query: str,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"search": {"edges": []}}}

    with unittest.mock.patch("requests.post", return_value=mock_response) as mock_post:
        historia.data.github.fetch_info_for_date(
            info_type=info_type,
            date="2026-01-05",
            username="codycbakerphd",
        )

    sent_graphql_query = mock_post.call_args.kwargs["json"]["query"]
    assert f'query: "{expected_search_query}"' in sent_graphql_query


def _assigned_search_response(
    *,
    nodes: list[dict],
    has_next_page: bool = False,
    issue_count: int = 1,
) -> unittest.mock.MagicMock:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "search": {
                "issueCount": issue_count,
                "pageInfo": {"hasNextPage": has_next_page, "endCursor": "cursor-1" if has_next_page else None},
                "edges": [{"node": node} for node in nodes],
            },
        },
    }
    return mock_response


@pytest.mark.ai_generated
@pytest.mark.parametrize("info_type", ["prs_assigned", "prs_review_requested", "prs_reviewed", "issues_assigned"])
@pytest.mark.parametrize(
    ("event", "expected_info"),
    [
        (
            {"createdAt": "2026-01-05T17:25:36Z", "actor": {"login": "codycbakerphd"}},
            ["https://github.com/con/nwb2bids/issues/252"],
        ),
        (
            {"createdAt": "2026-01-05T17:25:36Z", "actor": {"login": "CodyCBakerPhD"}},
            ["https://github.com/con/nwb2bids/issues/252"],
        ),
        ({"createdAt": "2026-01-04T23:59:59Z", "actor": {"login": "codycbakerphd"}}, []),
        ({"createdAt": "2026-01-05T17:25:36Z", "actor": {"login": "someoneelse"}}, []),
        ({"createdAt": "2026-01-05T17:25:36Z", "actor": {}}, []),
        ({"createdAt": None, "actor": {"login": "codycbakerphd"}}, []),
    ],
)
def test_fetch_info_graphql_filters_by_timeline_event(
    monkeypatch: pytest.MonkeyPatch,
    info_type: str,
    event: dict,
    expected_info: list[str],
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    node = {
        "url": "https://github.com/con/nwb2bids/issues/252",
        "timelineItems": {"nodes": [event]},
    }
    mock_response = _assigned_search_response(nodes=[node])

    with unittest.mock.patch("requests.post", return_value=mock_response):
        test_info, hit_rate_limit = historia.data.github.fetch_info_for_date(
            info_type=info_type,
            date="2026-01-05",
            username="codycbakerphd",
        )

    assert hit_rate_limit is False
    assert test_info == expected_info


@pytest.mark.ai_generated
def test_fetch_info_graphql_assigned_paginates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    assigned_event = {"createdAt": "2026-01-05T17:25:36Z", "actor": {"login": "codycbakerphd"}}
    first_page = _assigned_search_response(
        nodes=[{"url": "https://github.com/con/nwb2bids/pull/1", "timelineItems": {"nodes": [assigned_event]}}],
        has_next_page=True,
    )
    second_page = _assigned_search_response(
        nodes=[{"url": "https://github.com/con/nwb2bids/pull/2", "timelineItems": {"nodes": [assigned_event]}}],
    )

    with unittest.mock.patch("requests.post", side_effect=[first_page, second_page]) as mock_post:
        test_info, hit_rate_limit = historia.data.github.fetch_info_for_date(
            info_type="prs_assigned",
            date="2026-01-05",
            username="codycbakerphd",
        )

    assert hit_rate_limit is False
    expected_info = ["https://github.com/con/nwb2bids/pull/1", "https://github.com/con/nwb2bids/pull/2"]
    assert test_info == expected_info
    sent_after_cursors = [call.kwargs["json"]["variables"]["after"] for call in mock_post.call_args_list]
    assert sent_after_cursors == [None, "cursor-1"]


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("issue_count", "expected_warning_lines"),
    [
        (1000, []),
        (
            2463,
            [
                (
                    "` matched 2463 items, but GitHub search returns only the first 1000. "
                    "The rest were not checked, so activity on 2026-01-05 may be missing."
                ),
            ],
        ),
    ],
    ids=["at_limit", "over_limit"],
)
def test_fetch_info_graphql_warns_once_when_a_search_passes_the_result_limit(
    monkeypatch: pytest.MonkeyPatch,
    issue_count: int,
    expected_warning_lines: list[str],
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    assigned_event = {"createdAt": "2026-01-05T17:25:36Z", "actor": {"login": "codycbakerphd"}}
    first_page = _assigned_search_response(
        nodes=[{"url": "https://github.com/con/nwb2bids/pull/1", "timelineItems": {"nodes": [assigned_event]}}],
        has_next_page=True,
        issue_count=issue_count,
    )
    second_page = _assigned_search_response(
        nodes=[{"url": "https://github.com/con/nwb2bids/pull/2", "timelineItems": {"nodes": [assigned_event]}}],
        issue_count=issue_count,
    )

    with (
        unittest.mock.patch("requests.post", side_effect=[first_page, second_page]),
        warnings.catch_warnings(record=True) as caught_warnings,
    ):
        warnings.simplefilter("always")
        test_info, hit_rate_limit = historia.data.github.fetch_info_for_date(
            info_type="prs_assigned",
            date="2026-01-05",
            username="codycbakerphd",
        )

    assert hit_rate_limit is False
    expected_info = ["https://github.com/con/nwb2bids/pull/1", "https://github.com/con/nwb2bids/pull/2"]
    assert test_info == expected_info
    assert [str(warning.message).splitlines()[-1] for warning in caught_warnings] == expected_warning_lines
