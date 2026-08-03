import unittest.mock

import pytest

from historia.project._create_project import create_project_page

_CREATE_PROJECT_RESPONSE = {
    "data": {
        "createProjectV2": {
            "projectV2": {
                "id": "PVT_kwDOA",
                "url": "https://github.com/users/octocat/projects/1",
            },
        },
    },
}
_CREATE_FIELD_RESPONSE = {
    "data": {
        "createProjectV2Field": {
            "projectV2Field": {"id": "PVTF_1", "name": "Start date"},
        },
    },
}
_UPDATE_VISIBILITY_RESPONSE = {
    "data": {"updateProjectV2": {"projectV2": {"id": "PVT_kwDOA"}}},
}
_OWNER_LOOKUP_RESPONSE = unittest.mock.MagicMock(status_code=200, json=lambda: {"node_id": "MDQ6VXNlcg=="})


@pytest.mark.ai_generated
def test_create_project_page_defaults_to_private(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    responses = [
        unittest.mock.MagicMock(status_code=200, json=lambda: _CREATE_PROJECT_RESPONSE),
        unittest.mock.MagicMock(status_code=200, json=lambda: _CREATE_FIELD_RESPONSE),
        unittest.mock.MagicMock(status_code=200, json=lambda: _CREATE_FIELD_RESPONSE),
    ]

    with (
        unittest.mock.patch("requests.get", return_value=_OWNER_LOOKUP_RESPONSE),
        unittest.mock.patch("requests.post", side_effect=responses) as mock_post,
    ):
        project = create_project_page(owner="octocat", title="Work History")

    assert project == {"id": "PVT_kwDOA", "url": "https://github.com/users/octocat/projects/1"}
    # Only the create-project mutation plus the two date-field mutations; no visibility mutation.
    assert mock_post.call_count == 3


@pytest.mark.ai_generated
def test_create_project_page_sets_visibility_when_public(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    responses = [
        unittest.mock.MagicMock(status_code=200, json=lambda: _CREATE_PROJECT_RESPONSE),
        unittest.mock.MagicMock(status_code=200, json=lambda: _CREATE_FIELD_RESPONSE),
        unittest.mock.MagicMock(status_code=200, json=lambda: _CREATE_FIELD_RESPONSE),
        unittest.mock.MagicMock(status_code=200, json=lambda: _UPDATE_VISIBILITY_RESPONSE),
    ]

    with (
        unittest.mock.patch("requests.get", return_value=_OWNER_LOOKUP_RESPONSE),
        unittest.mock.patch("requests.post", side_effect=responses) as mock_post,
    ):
        project = create_project_page(owner="octocat", title="Work History", public=True)

    assert project == {"id": "PVT_kwDOA", "url": "https://github.com/users/octocat/projects/1"}
    assert mock_post.call_count == 4
    _, last_call_kwargs = mock_post.call_args_list[-1]
    assert last_call_kwargs["json"]["variables"] == {"projectId": "PVT_kwDOA", "public": True}


@pytest.mark.ai_generated
def test_create_project_page_raises_when_visibility_mutation_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    responses = [
        unittest.mock.MagicMock(status_code=200, json=lambda: _CREATE_PROJECT_RESPONSE),
        unittest.mock.MagicMock(status_code=200, json=lambda: _CREATE_FIELD_RESPONSE),
        unittest.mock.MagicMock(status_code=200, json=lambda: _CREATE_FIELD_RESPONSE),
        unittest.mock.MagicMock(status_code=422, json=lambda: {"errors": ["nope"]}),
    ]

    with (
        unittest.mock.patch("requests.get", return_value=_OWNER_LOOKUP_RESPONSE),
        unittest.mock.patch("requests.post", side_effect=responses),
        pytest.raises(RuntimeError, match="visibility"),
    ):
        create_project_page(owner="octocat", title="Work History", public=True)
