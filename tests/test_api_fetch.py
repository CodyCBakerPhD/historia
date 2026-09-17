import unittest.mock

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


@pytest.mark.ai_generated
def test_fetch_info_graphql_raises_on_non_json_response(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 502
    mock_response.text = ""
    mock_response.json.side_effect = requests.exceptions.JSONDecodeError("Expecting value", "<empty>", 0)

    with (
        unittest.mock.patch("requests.post", return_value=mock_response),
        pytest.raises(RuntimeError, match="non-JSON response body"),
    ):
        historia.data.github.fetch_info_for_date(
            info_type="issues_opened",
            date="2026-01-05",
            username="codycbakerphd",
        )


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
        ("prs_assigned", "assignee:codycbakerphd type:pr updated:>=2026-01-05"),
        ("issues_opened", "author:codycbakerphd type:issue created:2026-01-05..2026-01-05"),
        ("issues_assigned", "assignee:codycbakerphd type:issue updated:>=2026-01-05"),
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


def _assigned_search_response(*, nodes: list[dict], has_next_page: bool = False) -> unittest.mock.MagicMock:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "search": {
                "pageInfo": {"hasNextPage": has_next_page, "endCursor": "cursor-1" if has_next_page else None},
                "edges": [{"node": node} for node in nodes],
            },
        },
    }
    return mock_response


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("assigned_event", "expected_info"),
    [
        (
            {"createdAt": "2026-01-05T17:25:36Z", "assignee": {"login": "codycbakerphd"}},
            ["https://github.com/con/nwb2bids/issues/252"],
        ),
        (
            {"createdAt": "2026-01-05T17:25:36Z", "assignee": {"login": "CodyCBakerPhD"}},
            ["https://github.com/con/nwb2bids/issues/252"],
        ),
        ({"createdAt": "2026-01-04T23:59:59Z", "assignee": {"login": "codycbakerphd"}}, []),
        ({"createdAt": "2026-01-05T17:25:36Z", "assignee": {"login": "someoneelse"}}, []),
        ({"createdAt": "2026-01-05T17:25:36Z", "assignee": {}}, []),
    ],
)
def test_fetch_info_graphql_assigned_filters_by_assignment_event(
    monkeypatch: pytest.MonkeyPatch,
    assigned_event: dict,
    expected_info: list[str],
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    node = {
        "url": "https://github.com/con/nwb2bids/issues/252",
        "timelineItems": {"nodes": [assigned_event]},
    }
    mock_response = _assigned_search_response(nodes=[node])

    with unittest.mock.patch("requests.post", return_value=mock_response):
        test_info, hit_rate_limit = historia.data.github.fetch_info_for_date(
            info_type="issues_assigned",
            date="2026-01-05",
            username="codycbakerphd",
        )

    assert hit_rate_limit is False
    assert test_info == expected_info


@pytest.mark.ai_generated
def test_fetch_info_graphql_assigned_paginates(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    assigned_event = {"createdAt": "2026-01-05T17:25:36Z", "assignee": {"login": "codycbakerphd"}}
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
