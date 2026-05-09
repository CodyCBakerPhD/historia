import unittest.mock

import pytest

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
                        }
                    }
                ]
            }
        }
    }
    with unittest.mock.patch("requests.post", return_value=mock_response):
        test_info, hit_rate_limit = historia.fetch_info_for_date(
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

    with unittest.mock.patch("requests.post", return_value=mock_response):
        with pytest.warns(UserWarning):
            test_info, hit_rate_limit = historia.fetch_info_for_date(
                info_type="issues_opened",
                date="2026-01-05",
                username="codycbakerphd",
            )

    assert test_info == []
    assert hit_rate_limit is True


@pytest.mark.ai_generated
def test_fetch_info_graphql_validates_date(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    with pytest.raises(ValueError, match="correct format"):
        historia.fetch_info_for_date(
            info_type="issues_opened",
            date="2026/01/05",
            username="codycbakerphd",
        )


@pytest.mark.ai_generated
def test_fetch_info_graphql_requires_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(ValueError, match="GITHUB_TOKEN"):
        historia.fetch_info_for_date(
            info_type="issues_opened",
            date="2026-01-05",
            username="codycbakerphd",
        )


# TODO: add tests for
# - ensuring empty day folders are not created
# - error message for github token
# - ensure overwrite=True creates new file (when current file is empty or partial or incorrect)
# - ensure overwrite=False does not overwrite existing file (even if incorrect)
# - CLI and tests for update API; will require a 'start from date' kwarg to make deterministic
