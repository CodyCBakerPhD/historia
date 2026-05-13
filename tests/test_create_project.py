import unittest.mock

import pytest

import historia
from historia._create_project import (
    _DEFAULT_STATUS_OPTIONS,
    _DEFAULT_VIEWS,
    _create_project_view,
    _get_default_view_id,
    _get_status_field_id,
    _setup_default_statuses,
    _setup_default_views,
    _update_project_view,
    _update_status_field_options,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


@pytest.mark.ai_generated
def test_default_status_options_names() -> None:
    """The canonical status option names match the specification."""
    names = [opt["name"] for opt in _DEFAULT_STATUS_OPTIONS]
    assert names == ["Incoming", "Backlog", "Todo", "Agenda", "Done", "History"]


@pytest.mark.ai_generated
@pytest.mark.parametrize("opt", _DEFAULT_STATUS_OPTIONS, ids=[opt["name"] for opt in _DEFAULT_STATUS_OPTIONS])
def test_default_status_option_has_required_keys(opt: dict) -> None:
    """Every status option has name, color, and description keys."""
    assert "name" in opt
    assert "color" in opt
    assert "description" in opt


@pytest.mark.ai_generated
def test_default_views_names_and_layouts() -> None:
    """The four default views have the expected names and layouts."""
    expected = [
        ("Sort incoming", "BOARD_LAYOUT"),
        ("Roadmap", "ROADMAP_LAYOUT"),
        ("History", "ROADMAP_LAYOUT"),
        ("All Items", "TABLE_LAYOUT"),
    ]
    actual = [(v["name"], v["layout"]) for v in _DEFAULT_VIEWS]
    assert actual == expected


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("view_name", "expected_filter"),
    [
        ("Sort incoming", "-status:History"),
        ("Roadmap", "-status:Done,History"),
        ("History", "status:History"),
        ("All Items", ""),
    ],
)
def test_default_view_filter(view_name: str, expected_filter: str) -> None:
    """Each default view carries the expected filter string."""
    filters = {v["name"]: v["filter"] for v in _DEFAULT_VIEWS}
    assert filters[view_name] == expected_filter


# ---------------------------------------------------------------------------
# _get_status_field_id
# ---------------------------------------------------------------------------


@pytest.mark.ai_generated
def test_get_status_field_id_returns_id_for_status_field() -> None:
    """Returns the ID of the field named 'Status'."""
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "node": {
                "fields": {
                    "nodes": [
                        {"id": "PVTF_title", "name": "Title"},
                        {"id": "PVTSSF_status", "name": "Status"},
                    ],
                },
            },
        },
    }

    with unittest.mock.patch("requests.post", return_value=mock_response):
        field_id = _get_status_field_id(
            project_id="PVT_project",
            headers={"Authorization": "token fake"},
        )

    assert field_id == "PVTSSF_status"


@pytest.mark.ai_generated
def test_get_status_field_id_raises_when_not_found() -> None:
    """Raises ValueError when no field named 'Status' is found."""
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "node": {
                "fields": {
                    "nodes": [
                        {"id": "PVTF_title", "name": "Title"},
                    ],
                },
            },
        },
    }

    with (
        unittest.mock.patch("requests.post", return_value=mock_response),
        pytest.raises(ValueError, match="Status"),
    ):
        _get_status_field_id(
            project_id="PVT_project",
            headers={"Authorization": "token fake"},
        )


@pytest.mark.ai_generated
def test_get_status_field_id_raises_on_api_error() -> None:
    """Raises RuntimeError when the API returns an error."""
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"errors": [{"message": "Something went wrong"}]}

    with (
        unittest.mock.patch("requests.post", return_value=mock_response),
        pytest.raises(RuntimeError, match="project fields failed"),
    ):
        _get_status_field_id(
            project_id="PVT_project",
            headers={"Authorization": "token fake"},
        )


# ---------------------------------------------------------------------------
# _update_status_field_options
# ---------------------------------------------------------------------------


@pytest.mark.ai_generated
def test_update_status_field_options_posts_correct_mutation() -> None:
    """Calls the GitHub GraphQL API with the updateProjectV2Field mutation."""
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {"updateProjectV2Field": {"projectV2Field": {"id": "PVTSSF_status", "name": "Status"}}},
    }

    with unittest.mock.patch("requests.post", return_value=mock_response) as mock_post:
        _update_status_field_options(
            project_id="PVT_project",
            field_id="PVTSSF_status",
            options=_DEFAULT_STATUS_OPTIONS,
            headers={"Authorization": "token fake"},
        )

    call_body = mock_post.call_args.kwargs["json"]
    assert "updateProjectV2Field" in call_body["query"]
    assert call_body["variables"]["projectId"] == "PVT_project"
    assert call_body["variables"]["fieldId"] == "PVTSSF_status"
    assert call_body["variables"]["options"] == _DEFAULT_STATUS_OPTIONS


@pytest.mark.ai_generated
def test_update_status_field_options_raises_on_api_error() -> None:
    """Raises RuntimeError when the API returns an error."""
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"errors": [{"message": "Bad request"}]}

    with (
        unittest.mock.patch("requests.post", return_value=mock_response),
        pytest.raises(RuntimeError, match="Status field options failed"),
    ):
        _update_status_field_options(
            project_id="PVT_project",
            field_id="PVTSSF_status",
            options=_DEFAULT_STATUS_OPTIONS,
            headers={"Authorization": "token fake"},
        )


# ---------------------------------------------------------------------------
# _setup_default_statuses
# ---------------------------------------------------------------------------


@pytest.mark.ai_generated
def test_setup_default_statuses_calls_get_then_update(monkeypatch: pytest.MonkeyPatch) -> None:
    """Calls _get_status_field_id and _update_status_field_options in sequence."""
    captured: dict = {}

    def _fake_get_id(*, project_id: str, headers: dict) -> str:
        captured["get_project_id"] = project_id
        return "PVTSSF_status"

    def _fake_update(*, project_id: str, field_id: str, options: list, headers: dict) -> None:
        captured["update_project_id"] = project_id
        captured["update_field_id"] = field_id
        captured["update_options"] = options

    monkeypatch.setattr("historia._create_project._get_status_field_id", _fake_get_id)
    monkeypatch.setattr("historia._create_project._update_status_field_options", _fake_update)

    _setup_default_statuses(project_id="PVT_project", headers={"Authorization": "token fake"})

    assert captured["get_project_id"] == "PVT_project"
    assert captured["update_project_id"] == "PVT_project"
    assert captured["update_field_id"] == "PVTSSF_status"
    assert captured["update_options"] == _DEFAULT_STATUS_OPTIONS


# ---------------------------------------------------------------------------
# _get_default_view_id
# ---------------------------------------------------------------------------


@pytest.mark.ai_generated
def test_get_default_view_id_returns_first_view_id() -> None:
    """Returns the ID of the first view when the project has views."""
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {
            "node": {
                "views": {
                    "nodes": [
                        {"id": "PVV_board", "name": "Board 1"},
                    ],
                },
            },
        },
    }

    with unittest.mock.patch("requests.post", return_value=mock_response):
        view_id = _get_default_view_id(
            project_id="PVT_project",
            headers={"Authorization": "token fake"},
        )

    assert view_id == "PVV_board"


@pytest.mark.ai_generated
def test_get_default_view_id_returns_none_when_no_views() -> None:
    """Returns None when the project has no views."""
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"data": {"node": {"views": {"nodes": []}}}}

    with unittest.mock.patch("requests.post", return_value=mock_response):
        view_id = _get_default_view_id(
            project_id="PVT_project",
            headers={"Authorization": "token fake"},
        )

    assert view_id is None


@pytest.mark.ai_generated
def test_get_default_view_id_raises_on_api_error() -> None:
    """Raises RuntimeError when the API returns an error."""
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 500
    mock_response.json.return_value = {}

    with (
        unittest.mock.patch("requests.post", return_value=mock_response),
        pytest.raises(RuntimeError, match="project views failed"),
    ):
        _get_default_view_id(
            project_id="PVT_project",
            headers={"Authorization": "token fake"},
        )


# ---------------------------------------------------------------------------
# _update_project_view
# ---------------------------------------------------------------------------


@pytest.mark.ai_generated
def test_update_project_view_posts_correct_mutation() -> None:
    """Calls the GitHub GraphQL API with the updateProjectV2View mutation."""
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {"updateProjectV2View": {"projectV2View": {"id": "PVV_board", "name": "Sort incoming"}}},
    }

    with unittest.mock.patch("requests.post", return_value=mock_response) as mock_post:
        _update_project_view(
            project_id="PVT_project",
            view_id="PVV_board",
            name="Sort incoming",
            layout="BOARD_LAYOUT",
            filter_text="-status:History",
            headers={"Authorization": "token fake"},
        )

    call_body = mock_post.call_args.kwargs["json"]
    assert "updateProjectV2View" in call_body["query"]
    variables = call_body["variables"]
    assert variables["projectId"] == "PVT_project"
    assert variables["viewId"] == "PVV_board"
    assert variables["name"] == "Sort incoming"
    assert variables["layout"] == "BOARD_LAYOUT"
    assert variables["filter"] == "-status:History"


@pytest.mark.ai_generated
def test_update_project_view_raises_on_api_error() -> None:
    """Raises RuntimeError when the API returns an error."""
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"errors": [{"message": "Forbidden"}]}

    with (
        unittest.mock.patch("requests.post", return_value=mock_response),
        pytest.raises(RuntimeError, match="update view"),
    ):
        _update_project_view(
            project_id="PVT_project",
            view_id="PVV_board",
            name="Sort incoming",
            layout="BOARD_LAYOUT",
            filter_text="-status:History",
            headers={"Authorization": "token fake"},
        )


# ---------------------------------------------------------------------------
# _create_project_view
# ---------------------------------------------------------------------------


@pytest.mark.ai_generated
def test_create_project_view_without_filter_calls_create_only() -> None:
    """For views with an empty filter, only the create mutation is called."""
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "data": {"createProjectV2View": {"projectV2View": {"id": "PVV_table", "name": "All Items"}}},
    }

    with unittest.mock.patch("requests.post", return_value=mock_response) as mock_post:
        _create_project_view(
            project_id="PVT_project",
            name="All Items",
            layout="TABLE_LAYOUT",
            filter_text="",
            headers={"Authorization": "token fake"},
        )

    assert mock_post.call_count == 1
    call_body = mock_post.call_args.kwargs["json"]
    assert "createProjectV2View" in call_body["query"]
    assert call_body["variables"]["name"] == "All Items"
    assert call_body["variables"]["layout"] == "TABLE_LAYOUT"


@pytest.mark.ai_generated
def test_create_project_view_with_filter_calls_create_then_update() -> None:
    """For views with a non-empty filter, create is followed by an update call."""
    create_response = unittest.mock.MagicMock()
    create_response.status_code = 200
    create_response.json.return_value = {
        "data": {"createProjectV2View": {"projectV2View": {"id": "PVV_roadmap", "name": "Roadmap"}}},
    }

    update_response = unittest.mock.MagicMock()
    update_response.status_code = 200
    update_response.json.return_value = {
        "data": {"updateProjectV2View": {"projectV2View": {"id": "PVV_roadmap", "name": "Roadmap"}}},
    }

    with unittest.mock.patch("requests.post", side_effect=[create_response, update_response]) as mock_post:
        _create_project_view(
            project_id="PVT_project",
            name="Roadmap",
            layout="ROADMAP_LAYOUT",
            filter_text="-status:Done,History",
            headers={"Authorization": "token fake"},
        )

    assert mock_post.call_count == 2
    create_body = mock_post.call_args_list[0].kwargs["json"]
    assert "createProjectV2View" in create_body["query"]
    update_body = mock_post.call_args_list[1].kwargs["json"]
    assert "updateProjectV2View" in update_body["query"]
    assert update_body["variables"]["filter"] == "-status:Done,History"
    assert update_body["variables"]["viewId"] == "PVV_roadmap"


@pytest.mark.ai_generated
def test_create_project_view_raises_on_create_error() -> None:
    """Raises RuntimeError when the create API call fails."""
    mock_response = unittest.mock.MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {"errors": [{"message": "Bad input"}]}

    with (
        unittest.mock.patch("requests.post", return_value=mock_response),
        pytest.raises(RuntimeError, match="create view"),
    ):
        _create_project_view(
            project_id="PVT_project",
            name="Roadmap",
            layout="ROADMAP_LAYOUT",
            filter_text="-status:Done,History",
            headers={"Authorization": "token fake"},
        )


# ---------------------------------------------------------------------------
# _setup_default_views
# ---------------------------------------------------------------------------


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("existing_view_id", "expected_updated", "expected_created"),
    [
        ("PVV_existing", ["Sort incoming"], ["Roadmap", "History", "All Items"]),
        (None, [], ["Sort incoming", "Roadmap", "History", "All Items"]),
    ],
    ids=["existing_default_view", "no_default_view"],
)
def test_setup_default_views_update_and_create(
    monkeypatch: pytest.MonkeyPatch,
    existing_view_id: str | None,
    expected_updated: list[str],
    expected_created: list[str],
) -> None:
    """Updates the existing view (if present) and creates the remaining views."""
    captured: dict = {"updated": [], "created": []}

    monkeypatch.setattr(
        "historia._create_project._get_default_view_id",
        lambda *, project_id, headers: existing_view_id,
    )

    def _fake_update(
        *,
        project_id: str,
        view_id: str,
        name: str,
        layout: str,
        filter_text: str,
        headers: dict,
    ) -> None:
        captured["updated"].append(name)

    def _fake_create(
        *,
        project_id: str,
        name: str,
        layout: str,
        filter_text: str,
        headers: dict,
    ) -> None:
        captured["created"].append(name)

    monkeypatch.setattr("historia._create_project._update_project_view", _fake_update)
    monkeypatch.setattr("historia._create_project._create_project_view", _fake_create)

    _setup_default_views(project_id="PVT_project", headers={"Authorization": "token fake"})

    assert captured["updated"] == expected_updated
    assert captured["created"] == expected_created


# ---------------------------------------------------------------------------
# create_project_page integration (full mock)
# ---------------------------------------------------------------------------


@pytest.mark.ai_generated
def test_create_project_page_calls_setup_statuses_and_views(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """create_project_page calls _setup_default_statuses and _setup_default_views after creating date fields."""
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    captured: dict = {"statuses": False, "views": False}

    owner_response = unittest.mock.MagicMock()
    owner_response.status_code = 200
    owner_response.json.return_value = {"node_id": "U_owner"}

    create_project_response = unittest.mock.MagicMock()
    create_project_response.status_code = 200
    create_project_response.json.return_value = {
        "data": {
            "createProjectV2": {
                "projectV2": {
                    "id": "PVT_project",
                    "url": "https://github.com/users/octocat/projects/1",
                },
            },
        },
    }

    start_date_field_response = unittest.mock.MagicMock()
    start_date_field_response.status_code = 200
    start_date_field_response.json.return_value = {
        "data": {"createProjectV2Field": {"projectV2Field": {"id": "PVTF_start", "name": "Start date"}}},
    }

    end_date_field_response = unittest.mock.MagicMock()
    end_date_field_response.status_code = 200
    end_date_field_response.json.return_value = {
        "data": {"createProjectV2Field": {"projectV2Field": {"id": "PVTF_end", "name": "End date"}}},
    }

    def _fake_setup_statuses(*, project_id: str, headers: dict) -> None:
        captured["statuses"] = True

    def _fake_setup_views(*, project_id: str, headers: dict) -> None:
        captured["views"] = True

    monkeypatch.setattr("historia._create_project._setup_default_statuses", _fake_setup_statuses)
    monkeypatch.setattr("historia._create_project._setup_default_views", _fake_setup_views)

    with (
        unittest.mock.patch(
            "requests.post",
            side_effect=[create_project_response, start_date_field_response, end_date_field_response],
        ),
        unittest.mock.patch("requests.get", return_value=owner_response),
    ):
        result = historia.project.create_project_page(owner="octocat", title="My Project")

    assert result == {
        "id": "PVT_project",
        "url": "https://github.com/users/octocat/projects/1",
    }
    assert captured["statuses"] is True
    assert captured["views"] is True
