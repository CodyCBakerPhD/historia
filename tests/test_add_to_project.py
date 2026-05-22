import json
import pathlib
import typing
import unittest.mock
import warnings as _warnings_module

import pytest
import requests

import historia
from historia._add_to_project import (
    _add_item_to_project,
    _check_graphql_response,
    _collect_unique_urls,
    _collect_url_member_usernames,
    _get_item_info,
    _get_project_info,
    _list_project_item_content_urls,
    _list_project_items_with_dates,
    _list_project_items_with_member_usernames,
    _list_project_items_with_member_values,
    _list_project_items_with_status,
    _merge_member_values,
    _parse_project_url,
    _resolve_latest_version_data_directory,
    _set_item_date,
    _set_item_status,
    _set_item_text,
    transition_status,
    update_project_item_dates,
    update_project_item_members,
)

_TEST_PROJECT_URL = "https://github.com/users/CodyCBakerPhD/projects/5"


# ---------------------------------------------------------------------------
# Unit tests – no network calls
# ---------------------------------------------------------------------------


@pytest.mark.ai_generated
def test_add_to_project_raises_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(ValueError, match="GITHUB_TOKEN"):
        historia.project.add_to_project(
            directory=pathlib.Path("/tmp/nonexistent"),
            project_url=_TEST_PROJECT_URL,
        )


@pytest.mark.ai_generated
def test_add_to_project_warns_when_no_urls(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    with pytest.warns(UserWarning, match="No URLs found"):
        historia.project.add_to_project(directory=tmp_path, project_url=_TEST_PROJECT_URL)


@pytest.mark.ai_generated
def test_collect_unique_urls_reads_json_files(tmp_path: pathlib.Path) -> None:
    urls_a = ["https://github.com/owner/repo/pull/1", "https://github.com/owner/repo/pull/2"]
    urls_b = ["https://github.com/owner/repo/pull/2", "https://github.com/owner/repo/issues/3"]

    sub = tmp_path / "sub"
    sub.mkdir()
    (tmp_path / "a.json").write_text(json.dumps(urls_a))
    (sub / "b.json").write_text(json.dumps(urls_b))

    result = _collect_unique_urls(tmp_path)

    assert set(result) == {
        "https://github.com/owner/repo/pull/1",
        "https://github.com/owner/repo/pull/2",
        "https://github.com/owner/repo/issues/3",
    }


@pytest.mark.ai_generated
def test_collect_unique_urls_ignores_non_list_json(tmp_path: pathlib.Path) -> None:
    """GraphQL-only collection should ignore legacy dict-shaped payloads."""
    legacy_rest_response = {
        "total_count": 2,
        "incomplete_results": False,
        "search_type": "lexical",
        "items": [
            {"html_url": "https://github.com/owner/repo/pull/10", "other_field": "ignored"},
            {"html_url": "https://github.com/owner/repo/issues/20", "other_field": "ignored"},
        ],
    }
    (tmp_path / "legacy-rest.json").write_text(json.dumps(legacy_rest_response))

    result = _collect_unique_urls(tmp_path)

    assert set(result) == set()


@pytest.mark.ai_generated
def test_collect_unique_urls_mixed_formats(tmp_path: pathlib.Path) -> None:
    """A directory with mixed payload shapes should only use GraphQL list URLs."""
    graphql_urls = ["https://github.com/owner/repo/pull/1"]
    legacy_rest_response = {
        "total_count": 1,
        "incomplete_results": False,
        "search_type": "lexical",
        "items": [{"html_url": "https://github.com/owner/repo/issues/2"}],
    }
    (tmp_path / "graphql.json").write_text(json.dumps(graphql_urls))
    (tmp_path / "legacy-rest.json").write_text(json.dumps(legacy_rest_response))

    result = _collect_unique_urls(tmp_path)

    assert set(result) == {"https://github.com/owner/repo/pull/1"}


@pytest.mark.ai_generated
def test_collect_url_member_usernames_from_directory_paths(tmp_path: pathlib.Path) -> None:
    cody_dir = tmp_path / "username-cody"
    alex_dir = tmp_path / "username-alex"
    cody_dir.mkdir()
    alex_dir.mkdir()

    shared_url = "https://github.com/owner/repo/pull/1"
    cody_only_url = "https://github.com/owner/repo/issues/2"
    alex_only_url = "https://github.com/owner/repo/pull/3"
    (cody_dir / "urls.json").write_text(json.dumps([shared_url, cody_only_url]))
    (alex_dir / "urls.json").write_text(json.dumps([shared_url, alex_only_url]))

    result = _collect_url_member_usernames(tmp_path)

    assert result == {
        shared_url: {"cody", "alex"},
        cody_only_url: {"cody"},
        alex_only_url: {"alex"},
    }


@pytest.mark.ai_generated
def test_resolve_data_directory_selects_latest_version_with_warning(
    tmp_path: pathlib.Path,
) -> None:
    version_one = tmp_path / "version-1"
    version_two = tmp_path / "version-2"
    version_one.mkdir()
    version_two.mkdir()

    with pytest.warns(
        UserWarning,
        match="Incompatible database versions detected! Using only the latest - please run database migration.",
    ):
        result = _resolve_latest_version_data_directory(tmp_path)

    assert result == version_two


@pytest.mark.ai_generated
def test_add_to_project_processes_latest_version_when_multiple_exist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    version_one = tmp_path / "version-1"
    version_one.mkdir()
    version_two = tmp_path / "version-2"
    version_two.mkdir()
    (version_one / "v1.json").write_text(json.dumps(["https://github.com/owner/repo/issues/1"]))
    latest_url = "https://github.com/owner/repo/issues/2"
    (version_two / "v2.json").write_text(json.dumps([latest_url]))

    seen_urls: list[str] = []

    def _mock_get_project_info(
        *,
        project_url: str,  # noqa: ARG001
        headers: dict[str, str],  # noqa: ARG001
    ) -> tuple[str, str, dict[str, str], None, None, None]:
        return ("project-id", "status-field", {"Todo": "opt-1"}, None, None, None)

    def _mock_list_project_item_content_urls(
        *,
        owner_type: str,  # noqa: ARG001
        owner_login: str,  # noqa: ARG001
        project_number: int,  # noqa: ARG001
        headers: dict[str, str],  # noqa: ARG001
    ) -> set[str]:
        return set()

    monkeypatch.setattr(
        "historia._add_to_project._get_project_info",
        _mock_get_project_info,
    )
    monkeypatch.setattr(
        "historia._add_to_project._list_project_item_content_urls",
        _mock_list_project_item_content_urls,
    )

    def _mock_get_item_info(*, url: str, headers: dict[str, str]) -> None:  # noqa: ARG001
        seen_urls.append(url)

    monkeypatch.setattr("historia._add_to_project._get_item_info", _mock_get_item_info)

    with pytest.warns(
        UserWarning,
        match="Incompatible database versions detected! Using only the latest - please run database migration.",
    ):
        historia.project.add_to_project(directory=tmp_path, project_url=_TEST_PROJECT_URL)

    assert seen_urls == [latest_url]


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("current_value", "new_usernames", "expected"),
    [
        (None, set(), None),
        (None, {"cody"}, "cody"),
        ("cody", {"alex"}, "alex,cody"),
        ("alex, cody", {"cody"}, "alex,cody"),
        ("", set(), None),
    ],
)
def test_merge_member_values(
    current_value: str | None,
    new_usernames: set[str],
    expected: str | None,
) -> None:
    result = _merge_member_values(current_value=current_value, usernames=new_usernames)

    assert result == expected


@pytest.mark.ai_generated
def test_check_graphql_response_returns_result_on_success() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"foo": "bar"}}

    result = _check_graphql_response(response=mock_response, context="test")

    assert result == {"data": {"foo": "bar"}}


@pytest.mark.ai_generated
def test_check_graphql_response_warns_on_403() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 403
    mock_response.json.return_value = {"message": "Forbidden"}

    with pytest.warns(UserWarning, match="Status code 403"), pytest.raises(RuntimeError):
        _check_graphql_response(response=mock_response, context="test 403")


@pytest.mark.ai_generated
def test_check_graphql_response_raises_on_errors_key() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"errors": [{"message": "some error"}]}

    with pytest.raises(RuntimeError):
        _check_graphql_response(response=mock_response, context="test errors")


@pytest.mark.ai_generated
def test_check_graphql_response_raises_on_non_json_response() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 500
    mock_response.text = ""
    mock_response.json.side_effect = requests.exceptions.JSONDecodeError("Expecting value", "<empty>", 0)

    with pytest.raises(RuntimeError, match="not valid JSON"):
        _check_graphql_response(response=mock_response, context="test non-json")


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("url", "expected_owner_type", "expected_login", "expected_number"),
    [
        (
            "https://github.com/users/myuser/projects/3",
            "users",
            "myuser",
            3,
        ),
        (
            "https://github.com/orgs/myorg/projects/7",
            "orgs",
            "myorg",
            7,
        ),
        (
            "https://github.com/myuser/projects/7",
            "users",
            "myuser",
            7,
        ),
        (
            "https://github.com/myuser/projects/7/",
            "users",
            "myuser",
            7,
        ),
    ],
)
def test_parse_project_url(
    url: str,
    expected_owner_type: str,
    expected_login: str,
    expected_number: int,
) -> None:
    owner_type, owner_login, project_number = _parse_project_url(url)

    assert owner_type == expected_owner_type
    assert owner_login == expected_login
    assert project_number == expected_number


@pytest.mark.ai_generated
def test_collect_unique_urls_rejects_keyword_call() -> None:
    function = typing.cast("typing.Any", _collect_unique_urls)
    with pytest.raises(TypeError, match="positional-only arguments"):
        function(directory=pathlib.Path("/tmp"))


@pytest.mark.ai_generated
def test_parse_project_url_rejects_keyword_call() -> None:
    function = typing.cast("typing.Any", _parse_project_url)
    with pytest.raises(TypeError, match="positional-only arguments"):
        function(project_url="https://github.com/users/testuser/projects/1")


@pytest.mark.ai_generated
def test_get_project_info_parses_user_url() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_kwDOA",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_id",
                                "name": "Status",
                                "options": [
                                    {"id": "opt1", "name": "Todo"},
                                    {"id": "opt2", "name": "In Progress"},
                                    {"id": "opt3", "name": "Done"},
                                ],
                            },
                            {"id": "PVTF_start", "name": "Start date", "dataType": "DATE"},
                            {"id": "PVTF_end", "name": "End date", "dataType": "DATE"},
                        ],
                    },
                },
            },
        },
    }

    headers = {"Authorization": "token fake-token"}
    with unittest.mock.patch("requests.post", return_value=mock_response):
        (
            project_id,
            status_field_id,
            status_options,
            start_date_field_id,
            end_date_field_id,
            members_field_id,
        ) = _get_project_info(project_url="https://github.com/users/testuser/projects/1", headers=headers)

    assert project_id == "PVT_kwDOA"
    assert status_field_id == "PVTSSF_id"
    assert status_options == {"Todo": "opt1", "In Progress": "opt2", "Done": "opt3"}
    assert start_date_field_id == "PVTF_start"
    assert end_date_field_id == "PVTF_end"
    assert members_field_id is None


@pytest.mark.ai_generated
def test_get_project_info_parses_short_user_url() -> None:
    """Short URL format `https://github.com/{login}/projects/{number}` should work."""
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_kwDOB",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_id2",
                                "name": "Status",
                                "options": [
                                    {"id": "opt1", "name": "Todo"},
                                ],
                            },
                        ],
                    },
                },
            },
        },
    }

    headers = {"Authorization": "token fake-token"}
    with unittest.mock.patch("requests.post", return_value=mock_response):
        (
            project_id,
            status_field_id,
            status_options,
            start_date_field_id,
            end_date_field_id,
            members_field_id,
        ) = _get_project_info(project_url="https://github.com/testuser/projects/7", headers=headers)

    assert project_id == "PVT_kwDOB"
    assert status_field_id == "PVTSSF_id2"
    assert status_options == {"Todo": "opt1"}
    assert start_date_field_id is None
    assert end_date_field_id is None
    assert members_field_id is None


@pytest.mark.ai_generated
def test_get_project_info_returns_none_for_missing_date_fields() -> None:
    """When the project has no Start date / End date fields, their IDs are None."""
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_kwDOA",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_id",
                                "name": "Status",
                                "options": [{"id": "opt1", "name": "Todo"}],
                            },
                        ],
                    },
                },
            },
        },
    }

    headers = {"Authorization": "token fake-token"}
    with unittest.mock.patch("requests.post", return_value=mock_response):
        _, _, _, _, _, _ = _get_project_info(
            project_url="https://github.com/users/testuser/projects/1",
            headers=headers,
        )


@pytest.mark.ai_generated
def test_get_project_info_raises_when_no_status_field() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_kwDOA",
                    "fields": {"nodes": []},
                },
            },
        },
    }

    headers = {"Authorization": "token fake-token"}
    with (
        unittest.mock.patch("requests.post", return_value=mock_response),
        pytest.raises(ValueError, match="No 'Status' field"),
    ):
        _get_project_info(
            project_url="https://github.com/users/testuser/projects/1",
            headers=headers,
        )


@pytest.mark.ai_generated
def test_get_item_info_returns_none_when_resource_is_null() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"resource": None}}

    headers = {"Authorization": "token fake-token"}
    with unittest.mock.patch("requests.post", return_value=mock_response):
        result = _get_item_info(url="https://github.com/owner/repo/pull/999", headers=headers)

    assert result is None


@pytest.mark.ai_generated
def test_get_item_info_classifies_pull_request() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "resource": {
                "id": "PR_node_id",
                "state": "CLOSED",
                "createdAt": "2023-01-10T12:00:00Z",
                "closedAt": "2023-02-01T09:00:00Z",
            },
        },
    }

    headers = {"Authorization": "token fake-token"}
    with unittest.mock.patch("requests.post", return_value=mock_response):
        result = _get_item_info(url="https://github.com/owner/repo/pull/1", headers=headers)

    assert result is not None
    node_id, item_type, item_state, created_at, closed_at = result

    assert node_id == "PR_node_id"
    assert item_type == "PullRequest"
    assert item_state == "closed"
    assert created_at == "2023-01-10T12:00:00Z"
    assert closed_at == "2023-02-01T09:00:00Z"


@pytest.mark.ai_generated
def test_get_item_info_classifies_issue() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "resource": {
                "id": "ISSUE_node_id",
                "state": "OPEN",
                "createdAt": "2023-03-05T08:00:00Z",
                "closedAt": None,
            },
        },
    }

    headers = {"Authorization": "token fake-token"}
    with unittest.mock.patch("requests.post", return_value=mock_response):
        result = _get_item_info(url="https://github.com/owner/repo/issues/5", headers=headers)

    assert result is not None
    node_id, item_type, item_state, created_at, closed_at = result

    assert node_id == "ISSUE_node_id"
    assert item_type == "Issue"
    assert item_state == "open"
    assert created_at == "2023-03-05T08:00:00Z"
    assert closed_at is None


@pytest.mark.ai_generated
def test_add_item_to_project_returns_item_id() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"addProjectV2ItemById": {"item": {"id": "PVTI_item_id"}}}}

    headers = {"Authorization": "token fake-token"}
    with unittest.mock.patch("requests.post", return_value=mock_response):
        item_id = _add_item_to_project(project_id="PVT_kwDOA", content_id="PR_node_id", headers=headers)

    assert item_id == "PVTI_item_id"


@pytest.mark.ai_generated
def test_add_item_to_project_returns_none_on_403() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 403
    mock_response.json.return_value = {"message": "Forbidden"}

    headers = {"Authorization": "token fake-token"}
    with (
        unittest.mock.patch("requests.post", return_value=mock_response),
        pytest.warns(UserWarning, match="Failed to add item"),
    ):
        item_id = _add_item_to_project(project_id="PVT_kwDOA", content_id="PR_node_id", headers=headers)

    assert item_id is None


@pytest.mark.ai_generated
def test_set_item_status_calls_mutation() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "PVTI_item_id"}}},
    }

    headers = {"Authorization": "token fake-token"}
    with unittest.mock.patch("requests.post", return_value=mock_response) as mock_post:
        _set_item_status(
            project_id="PVT_kwDOA",
            item_id="PVTI_item_id",
            field_id="PVTSSF_id",
            option_id="opt_done",
            headers=headers,
        )

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args.kwargs
    variables = call_kwargs["json"]["variables"]
    assert variables["projectId"] == "PVT_kwDOA"
    assert variables["itemId"] == "PVTI_item_id"
    assert variables["fieldId"] == "PVTSSF_id"
    assert variables["optionId"] == "opt_done"


@pytest.mark.ai_generated
def test_set_item_text_calls_mutation() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "PVTI_item_id"}}},
    }

    headers = {"Authorization": "token fake-token"}
    with unittest.mock.patch("requests.post", return_value=mock_response) as mock_post:
        _set_item_text(
            project_id="PVT_kwDOA",
            item_id="PVTI_item_id",
            field_id="PVTF_members",
            text="cody",
            headers=headers,
        )

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args.kwargs
    variables = call_kwargs["json"]["variables"]
    assert variables["projectId"] == "PVT_kwDOA"
    assert variables["itemId"] == "PVTI_item_id"
    assert variables["fieldId"] == "PVTF_members"
    assert variables["text"] == "cody"


@pytest.mark.ai_generated
def test_add_to_project_end_to_end(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    """Full flow test using mocked HTTP calls."""
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    pr_url = "https://github.com/owner/repo/pull/1"
    (tmp_path / "urls.json").write_text(json.dumps([pr_url]))

    project_info_response = unittest.mock.MagicMock()
    project_info_response.status_code = 200
    project_info_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_project",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_status",
                                "name": "Status",
                                "options": [
                                    {"id": "opt_done", "name": "Done"},
                                    {"id": "opt_progress", "name": "In Progress"},
                                    {"id": "opt_todo", "name": "Todo"},
                                ],
                            },
                        ],
                    },
                },
            },
        },
    }

    item_info_response = unittest.mock.MagicMock()
    item_info_response.status_code = 200
    item_info_response.json.return_value = {
        "data": {
            "resource": {
                "id": "PR_node_id",
                "state": "CLOSED",
                "createdAt": "2023-01-10T12:00:00Z",
                "closedAt": "2023-02-01T09:00:00Z",
            },
        },
    }

    add_item_response = unittest.mock.MagicMock()
    add_item_response.status_code = 200
    add_item_response.json.return_value = {"data": {"addProjectV2ItemById": {"item": {"id": "PVTI_new"}}}}

    set_status_response = unittest.mock.MagicMock()
    set_status_response.status_code = 200
    set_status_response.json.return_value = {
        "data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "PVTI_new"}}},
    }

    empty_project_response = unittest.mock.MagicMock()
    empty_project_response.status_code = 200
    empty_project_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
            },
        },
    }

    response_sequence = [
        project_info_response,
        empty_project_response,
        item_info_response,
        add_item_response,
        set_status_response,
    ]

    with unittest.mock.patch("requests.post", side_effect=response_sequence):
        historia.project.add_to_project(
            directory=tmp_path,
            project_url="https://github.com/users/testuser/projects/1",
        )


@pytest.mark.ai_generated
def test_add_to_project_skips_url_with_null_resource(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    """Items that return a null resource are silently skipped."""
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    (tmp_path / "urls.json").write_text(json.dumps(["https://github.com/owner/repo/pull/999"]))

    project_info_response = unittest.mock.MagicMock()
    project_info_response.status_code = 200
    project_info_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_project",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_status",
                                "name": "Status",
                                "options": [{"id": "opt_done", "name": "Done"}],
                            },
                        ],
                    },
                },
            },
        },
    }

    null_resource_response = unittest.mock.MagicMock()
    null_resource_response.status_code = 200
    null_resource_response.json.return_value = {"data": {"resource": None}}

    empty_project_response = unittest.mock.MagicMock()
    empty_project_response.status_code = 200
    empty_project_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
            },
        },
    }

    with (
        unittest.mock.patch(
            "requests.post",
            side_effect=[project_info_response, empty_project_response, null_resource_response],
        ),
        _warnings_module.catch_warnings(),
    ):
        _warnings_module.simplefilter("error")
        historia.project.add_to_project(
            directory=tmp_path,
            project_url="https://github.com/users/testuser/projects/1",
        )


@pytest.mark.ai_generated
def test_add_to_project_status_override(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    """When a custom status is provided, all items receive that status regardless of their type/state."""
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    # Use an open issue URL – without override it would get 'Todo', with override it should get 'In Progress'.
    issue_url = "https://github.com/owner/repo/issues/10"
    (tmp_path / "urls.json").write_text(json.dumps([issue_url]))

    project_info_response = unittest.mock.MagicMock()
    project_info_response.status_code = 200
    project_info_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_project",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_status",
                                "name": "Status",
                                "options": [
                                    {"id": "opt_done", "name": "Done"},
                                    {"id": "opt_progress", "name": "In Progress"},
                                    {"id": "opt_todo", "name": "Todo"},
                                ],
                            },
                        ],
                    },
                },
            },
        },
    }

    item_info_response = unittest.mock.MagicMock()
    item_info_response.status_code = 200
    item_info_response.json.return_value = {
        "data": {
            "resource": {
                "id": "ISSUE_node_id",
                "state": "OPEN",
                "createdAt": "2023-03-05T08:00:00Z",
                "closedAt": None,
            },
        },
    }

    add_item_response = unittest.mock.MagicMock()
    add_item_response.status_code = 200
    add_item_response.json.return_value = {"data": {"addProjectV2ItemById": {"item": {"id": "PVTI_new"}}}}

    set_status_response = unittest.mock.MagicMock()
    set_status_response.status_code = 200
    set_status_response.json.return_value = {
        "data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "PVTI_new"}}},
    }

    empty_project_response = unittest.mock.MagicMock()
    empty_project_response.status_code = 200
    empty_project_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
            },
        },
    }

    response_sequence = [
        project_info_response,
        empty_project_response,
        item_info_response,
        add_item_response,
        set_status_response,
    ]

    with unittest.mock.patch("requests.post", side_effect=response_sequence) as mock_post:
        historia.project.add_to_project(
            directory=tmp_path,
            project_url="https://github.com/users/testuser/projects/1",
            status="In Progress",
        )

    # The last call should be the set_status mutation; verify the option ID corresponds to 'In Progress'.
    set_status_call = mock_post.call_args_list[-1]
    variables = set_status_call.kwargs["json"]["variables"]
    assert variables["optionId"] == "opt_progress"


@pytest.mark.ai_generated
def test_add_to_project_status_override_unknown_status_warns(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    """When the overriding status value is not found in the project, a warning is emitted."""
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    pr_url = "https://github.com/owner/repo/pull/1"
    (tmp_path / "urls.json").write_text(json.dumps([pr_url]))

    project_info_response = unittest.mock.MagicMock()
    project_info_response.status_code = 200
    project_info_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_project",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_status",
                                "name": "Status",
                                "options": [{"id": "opt_done", "name": "Done"}],
                            },
                        ],
                    },
                },
            },
        },
    }

    item_info_response = unittest.mock.MagicMock()
    item_info_response.status_code = 200
    item_info_response.json.return_value = {
        "data": {
            "resource": {
                "id": "PR_node_id",
                "state": "OPEN",
                "createdAt": "2023-04-01T10:00:00Z",
                "closedAt": None,
            },
        },
    }

    add_item_response = unittest.mock.MagicMock()
    add_item_response.status_code = 200
    add_item_response.json.return_value = {"data": {"addProjectV2ItemById": {"item": {"id": "PVTI_new"}}}}

    empty_project_response = unittest.mock.MagicMock()
    empty_project_response.status_code = 200
    empty_project_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
            },
        },
    }

    response_sequence = [project_info_response, empty_project_response, item_info_response, add_item_response]

    with (
        unittest.mock.patch("requests.post", side_effect=response_sequence),
        pytest.warns(UserWarning, match="not found in project"),
    ):
        historia.project.add_to_project(
            directory=tmp_path,
            project_url="https://github.com/users/testuser/projects/1",
            status="NonExistentStatus",
        )


@pytest.mark.ai_generated
def test_set_item_date_calls_mutation() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "PVTI_item_id"}}},
    }

    headers = {"Authorization": "token fake-token"}
    with unittest.mock.patch("requests.post", return_value=mock_response) as mock_post:
        _set_item_date(
            project_id="PVT_kwDOA",
            item_id="PVTI_item_id",
            field_id="PVTF_date",
            date="2023-01-15",
            headers=headers,
        )

    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args.kwargs
    variables = call_kwargs["json"]["variables"]
    assert variables["projectId"] == "PVT_kwDOA"
    assert variables["itemId"] == "PVTI_item_id"
    assert variables["fieldId"] == "PVTF_date"
    assert variables["date"] == "2023-01-15"


@pytest.mark.ai_generated
def test_set_item_date_skips_missing_project_item() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {"updateProjectV2ItemFieldValue": None},
        "errors": [
            {
                "type": "NOT_FOUND",
                "message": "Could not resolve to a node with the global id of 'PVTI_item_id'.",
            },
        ],
    }

    headers = {"Authorization": "token fake-token"}
    with (
        unittest.mock.patch("requests.post", return_value=mock_response),
        pytest.warns(UserWarning, match="Skipping date update for missing project item"),
    ):
        _set_item_date(
            project_id="PVT_kwDOA",
            item_id="PVTI_item_id",
            field_id="PVTF_date",
            date="2023-01-15",
            headers=headers,
        )


@pytest.mark.ai_generated
def test_set_item_date_raises_for_non_missing_item_errors() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {"updateProjectV2ItemFieldValue": None},
        "errors": [
            {
                "type": "SOMETHING_ELSE",
                "message": "Some other GraphQL error.",
            },
        ],
    }

    headers = {"Authorization": "token fake-token"}
    with (
        unittest.mock.patch("requests.post", return_value=mock_response),
        pytest.raises(RuntimeError, match="Failed to set date for item"),
    ):
        _set_item_date(
            project_id="PVT_kwDOA",
            item_id="PVTI_item_id",
            field_id="PVTF_date",
            date="2023-01-15",
            headers=headers,
        )


@pytest.mark.ai_generated
def test_add_to_project_sets_dates_when_fields_present(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    """When the project has Start date / End date fields, they are set on added items."""
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    pr_url = "https://github.com/owner/repo/pull/1"
    (tmp_path / "urls.json").write_text(json.dumps([pr_url]))

    project_info_response = unittest.mock.MagicMock()
    project_info_response.status_code = 200
    project_info_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_project",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_status",
                                "name": "Status",
                                "options": [{"id": "opt_done", "name": "Done"}],
                            },
                            {"id": "PVTF_start", "name": "Start date", "dataType": "DATE"},
                            {"id": "PVTF_end", "name": "End date", "dataType": "DATE"},
                        ],
                    },
                },
            },
        },
    }

    item_info_response = unittest.mock.MagicMock()
    item_info_response.status_code = 200
    item_info_response.json.return_value = {
        "data": {
            "resource": {
                "id": "PR_node_id",
                "state": "CLOSED",
                "createdAt": "2023-01-10T12:00:00Z",
                "closedAt": "2023-02-01T09:00:00Z",
            },
        },
    }

    add_item_response = unittest.mock.MagicMock()
    add_item_response.status_code = 200
    add_item_response.json.return_value = {"data": {"addProjectV2ItemById": {"item": {"id": "PVTI_new"}}}}

    set_field_response = unittest.mock.MagicMock()
    set_field_response.status_code = 200
    set_field_response.json.return_value = {
        "data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "PVTI_new"}}},
    }

    empty_project_response = unittest.mock.MagicMock()
    empty_project_response.status_code = 200
    empty_project_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
            },
        },
    }

    # project_info, list_project_item_content_urls, item_info, add_item, set_status, set_start_date, set_end_date
    response_sequence = [
        project_info_response,
        empty_project_response,
        item_info_response,
        add_item_response,
        set_field_response,  # set_status
        set_field_response,  # set_start_date
        set_field_response,  # set_end_date
    ]

    with unittest.mock.patch("requests.post", side_effect=response_sequence) as mock_post:
        historia.project.add_to_project(
            directory=tmp_path,
            project_url="https://github.com/users/testuser/projects/1",
        )

    # 7 calls total: project_info, list_project_item_content_urls, item_info,
    # add_item, set_status, set_start_date, set_end_date
    assert mock_post.call_count == 7
    # Check start date call (6th call, index 5)
    start_date_call = mock_post.call_args_list[5]
    start_vars = start_date_call.kwargs["json"]["variables"]
    assert start_vars["fieldId"] == "PVTF_start"
    assert start_vars["date"] == "2023-01-10"
    # Check end date call (7th call, index 6)
    end_date_call = mock_post.call_args_list[6]
    end_vars = end_date_call.kwargs["json"]["variables"]
    assert end_vars["fieldId"] == "PVTF_end"
    assert end_vars["date"] == "2023-02-01"


@pytest.mark.ai_generated
def test_add_to_project_uses_placeholder_end_date_for_open_item(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    """For open items, the end date is set to creation date + end_date_placeholder_days."""
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    issue_url = "https://github.com/owner/repo/issues/5"
    (tmp_path / "urls.json").write_text(json.dumps([issue_url]))

    project_info_response = unittest.mock.MagicMock()
    project_info_response.status_code = 200
    project_info_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_project",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_status",
                                "name": "Status",
                                "options": [{"id": "opt_todo", "name": "Todo"}],
                            },
                            {"id": "PVTF_end", "name": "End date", "dataType": "DATE"},
                        ],
                    },
                },
            },
        },
    }

    item_info_response = unittest.mock.MagicMock()
    item_info_response.status_code = 200
    item_info_response.json.return_value = {
        "data": {
            "resource": {
                "id": "ISSUE_node_id",
                "state": "OPEN",
                "createdAt": "2023-06-01T00:00:00Z",
                "closedAt": None,
            },
        },
    }

    add_item_response = unittest.mock.MagicMock()
    add_item_response.status_code = 200
    add_item_response.json.return_value = {"data": {"addProjectV2ItemById": {"item": {"id": "PVTI_new"}}}}

    set_field_response = unittest.mock.MagicMock()
    set_field_response.status_code = 200
    set_field_response.json.return_value = {
        "data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "PVTI_new"}}},
    }

    empty_project_response = unittest.mock.MagicMock()
    empty_project_response.status_code = 200
    empty_project_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
            },
        },
    }

    response_sequence = [
        project_info_response,
        empty_project_response,
        item_info_response,
        add_item_response,
        set_field_response,  # set_status
        set_field_response,  # set_end_date (no start date field in this project)
    ]

    with unittest.mock.patch("requests.post", side_effect=response_sequence) as mock_post:
        historia.project.add_to_project(
            directory=tmp_path,
            project_url="https://github.com/users/testuser/projects/1",
            end_date_placeholder_days=30,
        )

    # Check end date uses the placeholder (2023-06-01 + 30 days = 2023-07-01)
    end_date_call = mock_post.call_args_list[-1]
    end_vars = end_date_call.kwargs["json"]["variables"]
    assert end_vars["fieldId"] == "PVTF_end"
    assert end_vars["date"] == "2023-07-01"


@pytest.mark.ai_generated
def test_update_project_item_dates_raises_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(ValueError, match="GITHUB_TOKEN"):
        update_project_item_dates(project_url="https://github.com/users/testuser/projects/1")


@pytest.mark.ai_generated
def test_update_project_item_dates_warns_when_no_date_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the project has no Start date / End date fields, a warning is emitted and no updates are made."""
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    project_info_response = unittest.mock.MagicMock()
    project_info_response.status_code = 200
    project_info_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_project",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_status",
                                "name": "Status",
                                "options": [{"id": "opt_done", "name": "Done"}],
                            },
                        ],
                    },
                },
            },
        },
    }

    with (
        unittest.mock.patch("requests.post", return_value=project_info_response),
        pytest.warns(UserWarning, match="no 'Start date' or 'End date' fields"),
    ):
        update_project_item_dates(project_url="https://github.com/users/testuser/projects/1")


@pytest.mark.ai_generated
def test_update_project_item_dates_updates_items(monkeypatch: pytest.MonkeyPatch) -> None:
    """update_project_item_dates sets dates on all items already in the project."""
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    project_info_response = unittest.mock.MagicMock()
    project_info_response.status_code = 200
    project_info_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_project",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_status",
                                "name": "Status",
                                "options": [{"id": "opt_done", "name": "Done"}],
                            },
                            {"id": "PVTF_start", "name": "Start date", "dataType": "DATE"},
                            {"id": "PVTF_end", "name": "End date", "dataType": "DATE"},
                        ],
                    },
                },
            },
        },
    }

    list_items_response = unittest.mock.MagicMock()
    list_items_response.status_code = 200
    list_items_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [
                            {
                                "id": "PVTI_closed",
                                "content": {
                                    "createdAt": "2023-01-10T12:00:00Z",
                                    "closedAt": "2023-02-01T09:00:00Z",
                                },
                            },
                            {
                                "id": "PVTI_open",
                                "content": {
                                    "createdAt": "2023-03-05T08:00:00Z",
                                    "closedAt": None,
                                },
                            },
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
            },
        },
    }

    set_field_response = unittest.mock.MagicMock()
    set_field_response.status_code = 200
    set_field_response.json.return_value = {
        "data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "PVTI_closed"}}},
    }

    # project_info, list_items, then 4 date sets (2 items × 2 fields each)
    response_sequence = [
        project_info_response,
        list_items_response,
        set_field_response,  # item1 start date
        set_field_response,  # item1 end date
        set_field_response,  # item2 start date
        set_field_response,  # item2 end date
    ]

    with unittest.mock.patch("requests.post", side_effect=response_sequence) as mock_post:
        update_project_item_dates(
            project_url="https://github.com/users/testuser/projects/1",
            end_date_placeholder_days=30,
        )

    # 6 total calls
    assert mock_post.call_count == 6

    # Verify item1 (closed) dates
    item1_start = mock_post.call_args_list[2].kwargs["json"]["variables"]
    assert item1_start["itemId"] == "PVTI_closed"
    assert item1_start["fieldId"] == "PVTF_start"
    assert item1_start["date"] == "2023-01-10"

    item1_end = mock_post.call_args_list[3].kwargs["json"]["variables"]
    assert item1_end["itemId"] == "PVTI_closed"
    assert item1_end["fieldId"] == "PVTF_end"
    assert item1_end["date"] == "2023-02-01"

    # Verify item2 (open) uses placeholder end date (2023-03-05 + 30 = 2023-04-04)
    item2_start = mock_post.call_args_list[4].kwargs["json"]["variables"]
    assert item2_start["itemId"] == "PVTI_open"
    assert item2_start["fieldId"] == "PVTF_start"
    assert item2_start["date"] == "2023-03-05"

    item2_end = mock_post.call_args_list[5].kwargs["json"]["variables"]
    assert item2_end["itemId"] == "PVTI_open"
    assert item2_end["fieldId"] == "PVTF_end"
    assert item2_end["date"] == "2023-04-04"


@pytest.mark.ai_generated
def test_update_project_item_members_raises_without_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)

    with pytest.raises(ValueError, match="GITHUB_TOKEN"):
        update_project_item_members(project_url="https://github.com/users/testuser/projects/1")


@pytest.mark.ai_generated
def test_update_project_item_members_warns_when_no_members_field(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    project_info_response = unittest.mock.MagicMock()
    project_info_response.status_code = 200
    project_info_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_project",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_status",
                                "name": "Status",
                                "options": [{"id": "opt_done", "name": "Done"}],
                            },
                        ],
                    },
                },
            },
        },
    }

    with (
        unittest.mock.patch("requests.post", return_value=project_info_response),
        pytest.warns(UserWarning, match="has no 'Members' field"),
    ):
        update_project_item_members(project_url="https://github.com/users/testuser/projects/1")


@pytest.mark.ai_generated
def test_update_project_item_members_updates_items(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    project_info_response = unittest.mock.MagicMock()
    project_info_response.status_code = 200
    project_info_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_project",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_status",
                                "name": "Status",
                                "options": [{"id": "opt_done", "name": "Done"}],
                            },
                            {"id": "PVTF_members", "name": "Members", "dataType": "TEXT"},
                        ],
                    },
                },
            },
        },
    }

    list_items_response = unittest.mock.MagicMock()
    list_items_response.status_code = 200
    list_items_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [
                            {
                                "id": "PVTI_issue",
                                "content": {
                                    "assignees": {"nodes": [{"login": "alex"}, {"login": "cody"}]},
                                },
                            },
                            {
                                "id": "PVTI_pr",
                                "content": {
                                    "assignees": {"nodes": [{"login": "cody"}]},
                                    "reviewRequests": {
                                        "nodes": [
                                            {"requestedReviewer": {"login": "zeus"}},
                                            {"requestedReviewer": {"name": "infra-team"}},
                                        ],
                                    },
                                },
                            },
                            {
                                "id": "PVTI_none",
                                "content": {
                                    "assignees": {"nodes": []},
                                    "reviewRequests": {"nodes": []},
                                },
                            },
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
            },
        },
    }

    set_members_response = unittest.mock.MagicMock()
    set_members_response.status_code = 200
    set_members_response.json.return_value = {
        "data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "PVTI_issue"}}},
    }

    response_sequence = [
        project_info_response,
        list_items_response,
        set_members_response,
        set_members_response,
    ]

    with unittest.mock.patch("requests.post", side_effect=response_sequence) as mock_post:
        update_project_item_members(project_url="https://github.com/users/testuser/projects/1")

    assert mock_post.call_count == 4

    issue_members = mock_post.call_args_list[2].kwargs["json"]["variables"]
    assert issue_members["itemId"] == "PVTI_issue"
    assert issue_members["fieldId"] == "PVTF_members"
    assert issue_members["text"] == "alex,cody"

    pr_members = mock_post.call_args_list[3].kwargs["json"]["variables"]
    assert pr_members["itemId"] == "PVTI_pr"
    assert pr_members["fieldId"] == "PVTF_members"
    assert pr_members["text"] == "cody,zeus"
    assert {issue_members["itemId"], pr_members["itemId"]} == {"PVTI_issue", "PVTI_pr"}


@pytest.mark.ai_generated
def test_list_project_items_with_dates_returns_items() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [
                            {
                                "id": "PVTI_1",
                                "content": {
                                    "createdAt": "2023-01-01T00:00:00Z",
                                    "closedAt": "2023-06-01T00:00:00Z",
                                },
                            },
                            {"id": "PVTI_no_content", "content": None},
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
            },
        },
    }

    with unittest.mock.patch("requests.post", return_value=mock_response):
        items = _list_project_items_with_dates(
            owner_type="users",
            owner_login="testuser",
            project_number=1,
            headers={"Authorization": "token fake-token"},
        )

    assert len(items) == 1
    assert items[0]["id"] == "PVTI_1"
    assert items[0]["createdAt"] == "2023-01-01T00:00:00Z"
    assert items[0]["closedAt"] == "2023-06-01T00:00:00Z"


@pytest.mark.ai_generated
def test_list_project_items_with_member_usernames_returns_items() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [
                            {
                                "id": "PVTI_1",
                                "content": {
                                    "assignees": {"nodes": [{"login": "alex"}]},
                                    "reviewRequests": {"nodes": [{"requestedReviewer": {"login": "cody"}}]},
                                },
                            },
                            {
                                "id": "PVTI_empty",
                                "content": {
                                    "assignees": {"nodes": []},
                                    "reviewRequests": {"nodes": []},
                                },
                            },
                            {"id": "PVTI_no_content", "content": None},
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
            },
        },
    }

    with unittest.mock.patch("requests.post", return_value=mock_response):
        items = _list_project_items_with_member_usernames(
            owner_type="users",
            owner_login="testuser",
            project_number=1,
            headers={"Authorization": "token fake-token"},
        )

    assert len(items) == 1
    assert items[0][0] == "PVTI_1"
    assert items[0][1] == {"alex", "cody"}


@pytest.mark.ai_generated
def test_list_project_item_content_urls_returns_urls() -> None:
    """_list_project_item_content_urls returns the set of content URLs already in the project."""
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [
                            {"content": {"url": "https://github.com/owner/repo/pull/1"}},
                            {"content": {"url": "https://github.com/owner/repo/issues/2"}},
                            {"content": None},
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
            },
        },
    }

    with unittest.mock.patch("requests.post", return_value=mock_response):
        urls = _list_project_item_content_urls(
            owner_type="users",
            owner_login="testuser",
            project_number=1,
            headers={"Authorization": "token fake-token"},
        )

    assert urls == {
        "https://github.com/owner/repo/pull/1",
        "https://github.com/owner/repo/issues/2",
    }


@pytest.mark.ai_generated
def test_list_project_item_content_urls_returns_empty_set_when_no_items() -> None:
    """_list_project_item_content_urls returns an empty set when the project has no items."""
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
            },
        },
    }

    with unittest.mock.patch("requests.post", return_value=mock_response):
        urls = _list_project_item_content_urls(
            owner_type="users",
            owner_login="testuser",
            project_number=1,
            headers={"Authorization": "token fake-token"},
        )

    assert urls == set()


@pytest.mark.ai_generated
def test_list_project_items_with_member_values_returns_items() -> None:
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [
                            {
                                "id": "PVTI_1",
                                "content": {"url": "https://github.com/owner/repo/pull/1"},
                                "fieldValues": {
                                    "nodes": [
                                        {"text": "cody", "field": {"id": "PVTF_members"}},
                                    ],
                                },
                            },
                            {
                                "id": "PVTI_2",
                                "content": {"url": "https://github.com/owner/repo/issues/2"},
                                "fieldValues": {"nodes": []},
                            },
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
            },
        },
    }

    with unittest.mock.patch("requests.post", return_value=mock_response):
        items = _list_project_items_with_member_values(
            owner_type="users",
            owner_login="testuser",
            project_number=1,
            members_field_id="PVTF_members",
            headers={"Authorization": "token fake-token"},
        )

    assert items == {
        "https://github.com/owner/repo/pull/1": {"item_id": "PVTI_1", "members": "cody"},
        "https://github.com/owner/repo/issues/2": {"item_id": "PVTI_2", "members": None},
    }


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("owner_key", "project_url"),
    [
        ("user", "https://github.com/users/testuser/projects/1"),
        ("organization", "https://github.com/orgs/testorg/projects/1"),
    ],
)
def test_add_to_project_skips_items_already_in_project(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    owner_key: str,
    project_url: str,
) -> None:
    """Items whose URLs are already in the project are excluded and not re-added."""
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    existing_pr_url = "https://github.com/owner/repo/pull/1"
    new_pr_url = "https://github.com/owner/repo/pull/2"
    (tmp_path / "urls.json").write_text(json.dumps([existing_pr_url, new_pr_url]))

    project_info_response = unittest.mock.MagicMock()
    project_info_response.status_code = 200
    project_info_response.json.return_value = {
        "data": {
            owner_key: {
                "projectV2": {
                    "id": "PVT_project",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_status",
                                "name": "Status",
                                "options": [{"id": "opt_done", "name": "Done"}],
                            },
                        ],
                    },
                },
            },
        },
    }

    list_urls_response = unittest.mock.MagicMock()
    list_urls_response.status_code = 200
    list_urls_response.json.return_value = {
        "data": {
            owner_key: {
                "projectV2": {
                    "items": {
                        "nodes": [
                            {"content": {"url": existing_pr_url}},
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
            },
        },
    }

    item_info_response = unittest.mock.MagicMock()
    item_info_response.status_code = 200
    item_info_response.json.return_value = {
        "data": {
            "resource": {
                "id": "PR2_node_id",
                "state": "CLOSED",
                "createdAt": "2023-05-01T00:00:00Z",
                "closedAt": "2023-06-01T00:00:00Z",
            },
        },
    }

    add_item_response = unittest.mock.MagicMock()
    add_item_response.status_code = 200
    add_item_response.json.return_value = {"data": {"addProjectV2ItemById": {"item": {"id": "PVTI_new"}}}}

    set_status_response = unittest.mock.MagicMock()
    set_status_response.status_code = 200
    set_status_response.json.return_value = {
        "data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "PVTI_new"}}},
    }

    # Only new_pr_url should be processed: project_info, list_urls, item_info, add_item, set_status
    response_sequence = [
        project_info_response,
        list_urls_response,
        item_info_response,
        add_item_response,
        set_status_response,
    ]

    with (
        unittest.mock.patch("requests.post", side_effect=response_sequence) as mock_post,
        unittest.mock.patch("tqdm.tqdm", side_effect=lambda iterable, **_: list(iterable)) as mock_tqdm,
    ):
        historia.project.add_to_project(
            directory=tmp_path,
            project_url=project_url,
        )

    assert mock_tqdm.call_args is not None
    tqdm_kwargs = mock_tqdm.call_args.kwargs
    tqdm_iterable = tqdm_kwargs["iterable"] if "iterable" in tqdm_kwargs else mock_tqdm.call_args.args[0]
    assert set(tqdm_iterable) == {new_pr_url}
    assert tqdm_kwargs["desc"] == "Adding items to project"
    assert tqdm_kwargs["unit"] == "items"
    assert tqdm_kwargs["dynamic_ncols"] is True

    # 5 calls: project_info, list_urls, item_info (for new_pr only), add_item, set_status
    assert mock_post.call_count == 5

    # Verify the item_info call was for new_pr_url, not existing_pr_url
    item_info_call = mock_post.call_args_list[2]
    assert item_info_call.kwargs["json"]["variables"]["url"] == new_pr_url

    # Verify add_item was called with the node ID for the new item only
    add_item_call = mock_post.call_args_list[3]
    assert add_item_call.kwargs["json"]["variables"]["contentId"] == "PR2_node_id"


@pytest.mark.ai_generated
def test_add_to_project_members_mode_sets_members_for_new_item(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    user_directory = tmp_path / "username-cody"
    user_directory.mkdir()
    new_pr_url = "https://github.com/owner/repo/pull/2"
    (user_directory / "urls.json").write_text(json.dumps([new_pr_url]))

    project_info_response = unittest.mock.MagicMock()
    project_info_response.status_code = 200
    project_info_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_project",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_status",
                                "name": "Status",
                                "options": [{"id": "opt_done", "name": "Done"}],
                            },
                            {"id": "PVTF_members", "name": "Members", "dataType": "TEXT"},
                        ],
                    },
                },
            },
        },
    }

    list_members_response = unittest.mock.MagicMock()
    list_members_response.status_code = 200
    list_members_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
            },
        },
    }

    item_info_response = unittest.mock.MagicMock()
    item_info_response.status_code = 200
    item_info_response.json.return_value = {
        "data": {
            "resource": {
                "id": "PR2_node_id",
                "state": "CLOSED",
                "createdAt": "2023-05-01T00:00:00Z",
                "closedAt": "2023-06-01T00:00:00Z",
            },
        },
    }

    add_item_response = unittest.mock.MagicMock()
    add_item_response.status_code = 200
    add_item_response.json.return_value = {"data": {"addProjectV2ItemById": {"item": {"id": "PVTI_new"}}}}

    set_field_response = unittest.mock.MagicMock()
    set_field_response.status_code = 200
    set_field_response.json.return_value = {
        "data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "PVTI_new"}}},
    }

    response_sequence = [
        project_info_response,
        list_members_response,
        item_info_response,
        add_item_response,
        set_field_response,
        set_field_response,
    ]

    with unittest.mock.patch("requests.post", side_effect=response_sequence) as mock_post:
        historia.project.add_to_project(
            directory=tmp_path,
            project_url="https://github.com/users/testuser/projects/1",
            assign_members=True,
        )

    assert mock_post.call_count == 6
    members_call = mock_post.call_args_list[-1]
    members_variables = members_call.kwargs["json"]["variables"]
    assert members_variables["fieldId"] == "PVTF_members"
    assert members_variables["itemId"] == "PVTI_new"
    assert members_variables["text"] == "cody"


@pytest.mark.ai_generated
def test_add_to_project_members_mode_updates_existing_item(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    user_directory = tmp_path / "username-alex"
    user_directory.mkdir()
    existing_pr_url = "https://github.com/owner/repo/pull/1"
    (user_directory / "urls.json").write_text(json.dumps([existing_pr_url]))

    project_info_response = unittest.mock.MagicMock()
    project_info_response.status_code = 200
    project_info_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_project",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_status",
                                "name": "Status",
                                "options": [{"id": "opt_done", "name": "Done"}],
                            },
                            {"id": "PVTF_members", "name": "Members", "dataType": "TEXT"},
                        ],
                    },
                },
            },
        },
    }

    list_members_response = unittest.mock.MagicMock()
    list_members_response.status_code = 200
    list_members_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [
                            {
                                "id": "PVTI_existing",
                                "content": {"url": existing_pr_url},
                                "fieldValues": {
                                    "nodes": [
                                        {
                                            "text": "cody",
                                            "field": {"id": "PVTF_members"},
                                        },
                                    ],
                                },
                            },
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
            },
        },
    }

    set_members_response = unittest.mock.MagicMock()
    set_members_response.status_code = 200
    set_members_response.json.return_value = {
        "data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "PVTI_existing"}}},
    }

    response_sequence = [
        project_info_response,
        list_members_response,
        set_members_response,
    ]

    with unittest.mock.patch("requests.post", side_effect=response_sequence) as mock_post:
        historia.project.add_to_project(
            directory=tmp_path,
            project_url="https://github.com/users/testuser/projects/1",
            assign_members=True,
        )

    assert mock_post.call_count == 3
    members_call = mock_post.call_args_list[-1]
    members_variables = members_call.kwargs["json"]["variables"]
    assert members_variables["fieldId"] == "PVTF_members"
    assert members_variables["itemId"] == "PVTI_existing"
    assert members_variables["text"] == "alex,cody"


@pytest.mark.ai_generated
def test_members_mode_skips_unchanged_member_updates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    user_directory = tmp_path / "username-alex"
    user_directory.mkdir()
    existing_pr_url = "https://github.com/owner/repo/pull/1"
    (user_directory / "urls.json").write_text(json.dumps([existing_pr_url]))

    project_info_response = unittest.mock.MagicMock()
    project_info_response.status_code = 200
    project_info_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_project",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_status",
                                "name": "Status",
                                "options": [{"id": "opt_done", "name": "Done"}],
                            },
                            {"id": "PVTF_members", "name": "Members", "dataType": "TEXT"},
                        ],
                    },
                },
            },
        },
    }

    list_members_response = unittest.mock.MagicMock()
    list_members_response.status_code = 200
    list_members_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [
                            {
                                "id": "PVTI_existing",
                                "content": {"url": existing_pr_url},
                                "fieldValues": {
                                    "nodes": [
                                        {
                                            "text": "alex",
                                            "field": {"id": "PVTF_members"},
                                        },
                                    ],
                                },
                            },
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
            },
        },
    }

    response_sequence = [
        project_info_response,
        list_members_response,
    ]

    with unittest.mock.patch("requests.post", side_effect=response_sequence) as mock_post:
        historia.project.add_to_project(
            directory=tmp_path,
            project_url="https://github.com/users/testuser/projects/1",
            assign_members=True,
        )

    assert mock_post.call_count == 2
    assert all("updateProjectV2ItemFieldValue" not in call.kwargs["json"]["query"] for call in mock_post.call_args_list)


@pytest.mark.ai_generated
def test_list_project_items_with_status_returns_items() -> None:
    """_list_project_items_with_status returns item IDs with their status option IDs."""
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [
                            {
                                "id": "PVTI_done",
                                "fieldValues": {
                                    "nodes": [
                                        {
                                            "optionId": "opt_done",
                                            "field": {"id": "PVTSSF_status"},
                                        },
                                    ],
                                },
                            },
                            {
                                "id": "PVTI_progress",
                                "fieldValues": {
                                    "nodes": [
                                        {
                                            "optionId": "opt_progress",
                                            "field": {"id": "PVTSSF_status"},
                                        },
                                    ],
                                },
                            },
                            {
                                "id": "PVTI_no_status",
                                "fieldValues": {"nodes": []},
                            },
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
            },
        },
    }

    with unittest.mock.patch("requests.post", return_value=mock_response):
        items = _list_project_items_with_status(
            owner_type="users",
            owner_login="testuser",
            project_number=1,
            status_field_id="PVTSSF_status",
            headers={"Authorization": "token fake-token"},
        )

    assert len(items) == 3
    assert items[0] == {"id": "PVTI_done", "status_option_id": "opt_done"}
    assert items[1] == {"id": "PVTI_progress", "status_option_id": "opt_progress"}
    assert items[2] == {"id": "PVTI_no_status", "status_option_id": None}


@pytest.mark.ai_generated
def test_transition_status_moves_only_matching_items(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    project_info_response = unittest.mock.MagicMock()
    project_info_response.status_code = 200
    project_info_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "id": "PVT_project",
                    "fields": {
                        "nodes": [
                            {
                                "id": "PVTSSF_status",
                                "name": "Status",
                                "options": [
                                    {"id": "opt_done", "name": "DONE"},
                                    {"id": "opt_history", "name": "History"},
                                    {"id": "opt_progress", "name": "In Progress"},
                                ],
                            },
                        ],
                    },
                },
            },
        },
    }

    list_items_response = unittest.mock.MagicMock()
    list_items_response.status_code = 200
    list_items_response.json.return_value = {
        "data": {
            "user": {
                "projectV2": {
                    "items": {
                        "nodes": [
                            {
                                "id": "PVTI_progress_1",
                                "fieldValues": {
                                    "nodes": [{"optionId": "opt_progress", "field": {"id": "PVTSSF_status"}}],
                                },
                            },
                            {
                                "id": "PVTI_progress_2",
                                "fieldValues": {
                                    "nodes": [{"optionId": "opt_progress", "field": {"id": "PVTSSF_status"}}],
                                },
                            },
                            {
                                "id": "PVTI_done",
                                "fieldValues": {"nodes": [{"optionId": "opt_done", "field": {"id": "PVTSSF_status"}}]},
                            },
                        ],
                        "pageInfo": {"hasNextPage": False, "endCursor": None},
                    },
                },
            },
        },
    }

    set_status_response = unittest.mock.MagicMock()
    set_status_response.status_code = 200
    set_status_response.json.return_value = {
        "data": {"updateProjectV2ItemFieldValue": {"projectV2Item": {"id": "PVTI_progress_1"}}},
    }

    response_sequence = [
        project_info_response,
        list_items_response,
        set_status_response,
        set_status_response,
    ]

    with unittest.mock.patch("requests.post", side_effect=response_sequence) as mock_post:
        transition_status(
            project_url="https://github.com/users/testuser/projects/1",
            current_status="In Progress",
            new_status="DONE",
        )

    assert mock_post.call_count == 4

    for call in mock_post.call_args_list[2:]:
        variables = call.kwargs["json"]["variables"]
        assert variables["optionId"] == "opt_done"
        assert variables["fieldId"] == "PVTSSF_status"

    moved_item_ids = {
        mock_post.call_args_list[2].kwargs["json"]["variables"]["itemId"],
        mock_post.call_args_list[3].kwargs["json"]["variables"]["itemId"],
    }
    assert moved_item_ids == {"PVTI_progress_1", "PVTI_progress_2"}
