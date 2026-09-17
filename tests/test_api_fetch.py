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
        ("prs_assigned", "assignee:codycbakerphd -author:codycbakerphd type:pr updated:2026-01-05..2026-01-05"),
        ("issues_opened", "author:codycbakerphd type:issue created:2026-01-05..2026-01-05"),
        ("issues_assigned", "assignee:codycbakerphd -author:codycbakerphd type:issue updated:2026-01-05..2026-01-05"),
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
