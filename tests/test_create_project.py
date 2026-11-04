import unittest.mock
import warnings

import pytest
import requests

import historia

_OWNER_LOOKUP_RESPONSE = unittest.mock.MagicMock(status_code=200, json=lambda: {"node_id": "MDQ6VXNlcg=="})


def _response(
    *,
    status_code: int,
    payload: object | None = None,
    text: str = "",
    request_id: str | None = None,
) -> unittest.mock.MagicMock:
    response = unittest.mock.MagicMock()
    response.status_code = status_code
    response.headers = requests.structures.CaseInsensitiveDict()
    if request_id is not None:
        response.headers["X-GitHub-Request-Id"] = request_id
    if payload is None:
        response.json.side_effect = requests.exceptions.JSONDecodeError("Expecting value", text, 0)
        response.text = text
    else:
        response.json.return_value = payload
    return response


class _FakeProjects:
    """
    Answer the requests of ``create_project_page`` from an in-memory model of one owner's projects.

    ``outcomes`` maps a mutation's operation name to what each call does in turn. ``"ok"`` applies it and answers
    normally, ``"lost"`` applies it but answers with a 502 as if the response were lost, ``"empty"`` applies it but
    answers with a 200 and an empty body, ``"502"`` answers with a 502 without applying it, ``"connection"`` raises a
    dropped connection without applying it, and an integer answers with that status and an error. Calls beyond the
    listed outcomes are ``"ok"``.
    """

    def __init__(
        self,
        *,
        projects: list[dict] | None = None,
        outcomes: dict[str, list[str | int]] | None = None,
    ) -> None:
        self.projects: list[dict] = projects or []
        self.outcomes = outcomes or {}
        self.operations: list[str] = []
        self.visibility_updates: list[dict] = []

    def post(self, *, json: dict, **_kwargs: object) -> unittest.mock.MagicMock:
        operation = json["query"].split("(")[0].split()[-1]
        variables = json["variables"]
        self.operations.append(operation)
        if operation == "GetConnectionNodes":
            return _response(status_code=200, payload={"data": {"node": self._connection(json["query"], variables)}})

        planned = self.outcomes.get(operation, [])
        outcome = planned.pop(0) if planned else "ok"
        if outcome == "connection":
            message = "Connection reset by peer"
            raise requests.exceptions.ConnectionError(message)
        if isinstance(outcome, int):
            return _response(status_code=outcome, payload={"errors": [{"message": f"{operation} refused"}]})
        if outcome == "502":
            return _response(status_code=502, text="<html>502 Bad Gateway</html>", request_id="F469:1E5255:A85622")

        data = self._apply(operation, variables)
        if outcome == "lost":
            return _response(status_code=502, text="<html>502 Bad Gateway</html>")
        if outcome == "empty":
            return _response(status_code=200)
        return _response(status_code=200, payload={"data": data})

    def _connection(self, query: str, variables: dict) -> dict:
        page_info = {"hasNextPage": False, "endCursor": None}
        if "projectsV2(" in query:
            nodes = [
                {"id": project["id"], "title": project["title"], "url": project["url"]} for project in self.projects
            ]
            return {"projectsV2": {"nodes": nodes, "pageInfo": page_info}}
        project = next(project for project in self.projects if project["id"] == variables["id"])
        nodes = [{"id": f"PVTF_{name}", "name": name} for name in project["fields"]]
        return {"fields": {"nodes": nodes, "pageInfo": page_info}}

    def _apply(self, operation: str, variables: dict) -> dict:
        if operation == "CreateProject":
            number = len(self.projects) + 1
            project = {
                "id": f"PVT_{number}",
                "title": variables["title"],
                "url": f"https://github.com/users/octocat/projects/{number}",
                "fields": ["Title", "Status"],
            }
            self.projects.append(project)
            return {"createProjectV2": {"projectV2": {"id": project["id"], "url": project["url"]}}}
        if operation == "CreateField":
            project = next(project for project in self.projects if project["id"] == variables["projectId"])
            project["fields"].append(variables["name"])
            field = {"id": f"PVTF_{variables['name']}", "name": variables["name"]}
            return {"createProjectV2Field": {"projectV2Field": field}}
        if operation == "UpdateProjectVisibility":
            self.visibility_updates.append(variables)
            return {"updateProjectV2": {"projectV2": {"id": variables["projectId"]}}}
        if operation == "DeleteProject":
            self.projects = [project for project in self.projects if project["id"] != variables["projectId"]]
            return {"deleteProjectV2": {"projectV2": {"id": variables["projectId"]}}}
        message = f"_FakeProjects does not model the {operation} operation"
        raise AssertionError(message)

    def titled(self, title: str, /) -> list[dict]:
        return [project for project in self.projects if project["title"] == title]


def _create(github: _FakeProjects, *, public: bool = False) -> dict[str, str]:
    with (
        unittest.mock.patch("requests.get", return_value=_OWNER_LOOKUP_RESPONSE),
        unittest.mock.patch("requests.post", side_effect=github.post),
        unittest.mock.patch("time.sleep"),
    ):
        return historia.project.create_project_page(owner="octocat", title="Work History", public=public)


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("public", "expected_visibility_updates"),
    [
        pytest.param(False, [], id="private"),
        pytest.param(True, [{"projectId": "PVT_1", "public": True}], id="public"),
    ],
)
def test_create_project_page_creates_project_with_date_fields(
    monkeypatch: pytest.MonkeyPatch,
    public: bool,
    expected_visibility_updates: list[dict],
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    github = _FakeProjects()

    project = _create(github, public=public)

    assert project == {"id": "PVT_1", "url": "https://github.com/users/octocat/projects/1"}
    assert github.titled("Work History")[0]["fields"] == ["Title", "Status", "Start date", "End date"]
    assert github.visibility_updates == expected_visibility_updates


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("outcomes", "public", "expected_message"),
    [
        pytest.param({"CreateField": [422]}, False, "create field `Start date`", id="field-refused"),
        pytest.param({"CreateField": ["ok", 422]}, False, "create field `End date`", id="second-field-refused"),
        pytest.param({"UpdateProjectVisibility": [422]}, True, "set project visibility", id="visibility-refused"),
        pytest.param({"CreateField": ["502"] * 5}, False, "create field `Start date`", id="field-persistent-502"),
    ],
)
def test_create_project_page_deletes_project_when_setup_fails(
    monkeypatch: pytest.MonkeyPatch,
    outcomes: dict[str, list[str | int]],
    public: bool,
    expected_message: str,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    github = _FakeProjects(outcomes=outcomes)

    with pytest.raises(RuntimeError, match="was deleted again, so nothing was left behind") as caught:
        _create(github, public=public)

    assert expected_message in str(caught.value)
    assert github.projects == []


@pytest.mark.ai_generated
def test_create_project_page_names_the_project_when_cleanup_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    github = _FakeProjects(outcomes={"CreateField": [422], "DeleteProject": [422]})

    with pytest.raises(RuntimeError, match="delete it by hand") as caught:
        _create(github)

    assert "https://github.com/users/octocat/projects/1" in str(caught.value)
    assert len(github.titled("Work History")) == 1


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("outcomes", "expected_calls"),
    [
        pytest.param({"CreateProject": ["lost"]}, 1, id="project-response-lost"),
        pytest.param({"CreateProject": ["empty"]}, 1, id="project-response-empty"),
        pytest.param({"CreateProject": ["502", "connection"]}, 3, id="project-not-applied"),
        pytest.param({"CreateField": ["lost"]}, 2, id="field-response-lost"),
        pytest.param({"CreateField": ["connection"]}, 3, id="field-not-applied"),
    ],
)
def test_create_project_page_never_repeats_a_mutation_that_took_effect(
    monkeypatch: pytest.MonkeyPatch,
    outcomes: dict[str, list[str | int]],
    expected_calls: int,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    github = _FakeProjects(outcomes=outcomes)
    operation = next(iter(outcomes))

    project = _create(github)

    assert project["id"] == "PVT_1"
    assert len(github.titled("Work History")) == 1
    assert github.titled("Work History")[0]["fields"] == ["Title", "Status", "Start date", "End date"]
    assert github.operations.count(operation) == expected_calls


@pytest.mark.ai_generated
def test_create_project_page_leaves_an_existing_project_with_the_same_title_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    existing = {
        "id": "PVT_old",
        "title": "Work History",
        "url": "https://github.com/users/octocat/projects/9",
        "fields": [],
    }
    github = _FakeProjects(projects=[existing], outcomes={"CreateProject": ["502"]})

    project = _create(github)

    assert project["id"] != "PVT_old"
    assert existing["fields"] == []
    assert len(github.titled("Work History")) == 2


@pytest.mark.ai_generated
def test_create_project_page_raises_and_warns_when_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    github = _FakeProjects(outcomes={"CreateProject": [403]})

    with warnings.catch_warnings(record=True) as caught_warnings:
        warnings.simplefilter("always")
        with pytest.raises(RuntimeError, match="Status code 403"):
            _create(github)

    assert [str(warning.message).splitlines()[0] for warning in caught_warnings] == [
        "GitHub GraphQL API mutation to create project `Work History` failed!",
    ]
    assert [str(warning.message).splitlines()[-1] for warning in caught_warnings] == [
        "GitHub request ID: <not given>",
    ]
    assert github.projects == []


@pytest.mark.ai_generated
def test_create_project_page_reports_a_non_json_response_clearly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    github = _FakeProjects(outcomes={"CreateProject": ["502"] * 5})

    with pytest.raises(RuntimeError, match="not valid JSON: <html>502 Bad Gateway</html>") as caught:
        _create(github)

    assert str(caught.value).splitlines()[-1] == "GitHub request ID: F469:1E5255:A85622"
    assert github.operations.count("CreateProject") == 5
    assert github.projects == []
