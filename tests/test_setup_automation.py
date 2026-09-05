# ruff: noqa: S106 -- fixtures pass literal placeholder tokens/secrets as `token`/`secret_*`
# keyword args to match the signatures under test; none of these are real credentials.
import base64
import unittest.mock

import nacl.public
import pytest
import yaml

from historia.setup import provision_automation
from historia.setup._automation import (
    _create_data_repository,
    _extract_supported_python_versions,
    _get_authenticated_username,
    _get_latest_pypi_version,
    _render_workflow_yaml,
    _resolve_cron_schedule,
    _upsert_repository_secret,
    _upsert_workflow_file,
    _validate_historia_spec,
    _validate_python_version,
)

_RENDER_KWARGS = {
    "username": "octocat",
    "project_number": 7,
    "python_version": "3.13",
    "historia_spec": "historia==1.2.3",
    "secret_name": "GH_PAT",
    "cron_schedule": "0 0 * * *",
    "recency_days": 2,
    "default_branch": "main",
}

_REPOSITORY_PAYLOAD = {
    "name": "work-history-data",
    "full_name": "octocat/work-history-data",
    "html_url": "https://github.com/octocat/work-history-data",
    "default_branch": "main",
}


def _mock_response(status_code: int, payload: dict) -> unittest.mock.MagicMock:
    response = unittest.mock.MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    return response


def _fake_public_key() -> tuple:
    private_key = nacl.public.PrivateKey.generate()
    encoded = base64.b64encode(bytes(private_key.public_key)).decode("utf-8")
    return private_key, encoded


# ---------------------------------------------------------------------------
# provision_automation – the public entrypoint
# ---------------------------------------------------------------------------


@pytest.mark.ai_generated
def test_provision_automation_rejects_both_project_title_and_url() -> None:
    with pytest.raises(ValueError, match="Exactly one of"):
        provision_automation(
            token="fake-token",
            username="octocat",
            owner="octocat",
            repository_name="work-history-data",
            private=False,
            secret_name="GH_PAT",
            recency_days=2,
            python_version="3.13",
            historia_spec="historia==1.2.3",
            cron_schedule="0 0 * * *",
            project_title="Work History",
            project_url="https://github.com/users/octocat/projects/1",
        )


@pytest.mark.ai_generated
def test_provision_automation_rejects_neither_project_title_nor_url() -> None:
    with pytest.raises(ValueError, match="Exactly one of"):
        provision_automation(
            token="fake-token",
            username="octocat",
            owner="octocat",
            repository_name="work-history-data",
            private=False,
            secret_name="GH_PAT",
            recency_days=2,
            python_version="3.13",
            historia_spec="historia==1.2.3",
            cron_schedule="0 0 * * *",
        )


@pytest.mark.ai_generated
def test_provision_automation_creates_new_project(monkeypatch: pytest.MonkeyPatch) -> None:
    create_project_calls: dict[str, object] = {}

    monkeypatch.setattr(
        "historia.setup._automation._validate_historia_spec",
        lambda **kwargs: (kwargs["historia_spec"], None, []),
    )
    monkeypatch.setattr(
        "historia.setup._automation._get_authenticated_username",
        lambda *, token: "octocat",  # noqa: ARG005
    )
    monkeypatch.setattr(
        "historia.setup._automation._create_data_repository",
        lambda **_kwargs: {**_REPOSITORY_PAYLOAD, "created": "true"},
    )

    def _fake_create_project_page(*, owner: str, title: str, public: bool) -> dict[str, str]:  # noqa: ARG001
        create_project_calls["public"] = public
        return {"id": "PVT_1", "url": "https://github.com/users/octocat/projects/1"}

    monkeypatch.setattr("historia.setup._automation.create_project_page", _fake_create_project_page)
    upserted_workflow: dict[str, object] = {}
    monkeypatch.setattr(
        "historia.setup._automation._upsert_workflow_file",
        lambda **kwargs: upserted_workflow.update(kwargs),
    )
    monkeypatch.setattr("historia.setup._automation._upsert_repository_secret", lambda **_kwargs: None)

    result = provision_automation(
        token="fake-token",
        username="octocat",
        owner="octocat",
        repository_name="work-history-data",
        private=False,
        secret_name="GH_PAT",
        recency_days=2,
        python_version="3.13",
        historia_spec="historia==1.2.3",
        cron_schedule="0 0 * * *",
        project_title="Work History",
    )

    assert result == {
        "repository_url": "https://github.com/octocat/work-history-data",
        "repository_created": "true",
        "project_url": "https://github.com/users/octocat/projects/1",
        "workflow_url": "https://github.com/octocat/work-history-data/actions/workflows/update.yml",
    }
    workflow_content = upserted_workflow["content"]
    assert isinstance(workflow_content, str)
    assert "PROJECT_NUMBER: 1" in workflow_content
    assert create_project_calls["public"] is False


@pytest.mark.ai_generated
def test_provision_automation_passes_project_public_through(monkeypatch: pytest.MonkeyPatch) -> None:
    create_project_calls: dict[str, object] = {}

    monkeypatch.setattr(
        "historia.setup._automation._validate_historia_spec",
        lambda **kwargs: (kwargs["historia_spec"], None, []),
    )
    monkeypatch.setattr(
        "historia.setup._automation._get_authenticated_username",
        lambda *, token: "octocat",  # noqa: ARG005
    )
    monkeypatch.setattr(
        "historia.setup._automation._create_data_repository",
        lambda **_kwargs: {**_REPOSITORY_PAYLOAD, "created": "true"},
    )
    monkeypatch.setattr("historia.setup._automation._upsert_workflow_file", lambda **_kwargs: None)
    monkeypatch.setattr("historia.setup._automation._upsert_repository_secret", lambda **_kwargs: None)

    def _fake_create_project_page(*, owner: str, title: str, public: bool) -> dict[str, str]:  # noqa: ARG001
        create_project_calls["public"] = public
        return {"id": "PVT_1", "url": "https://github.com/users/octocat/projects/1"}

    monkeypatch.setattr("historia.setup._automation.create_project_page", _fake_create_project_page)

    provision_automation(
        token="fake-token",
        username="octocat",
        owner="octocat",
        repository_name="work-history-data",
        private=False,
        secret_name="GH_PAT",
        recency_days=2,
        python_version="3.13",
        historia_spec="historia==1.2.3",
        cron_schedule="0 0 * * *",
        project_title="Work History",
        project_public=True,
    )

    assert create_project_calls["public"] is True


@pytest.mark.ai_generated
def test_provision_automation_reuses_existing_project(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "historia.setup._automation._validate_historia_spec",
        lambda **kwargs: (kwargs["historia_spec"], None, []),
    )
    monkeypatch.setattr(
        "historia.setup._automation._get_authenticated_username",
        lambda *, token: "octocat",  # noqa: ARG005
    )
    monkeypatch.setattr(
        "historia.setup._automation._create_data_repository",
        lambda **_kwargs: {**_REPOSITORY_PAYLOAD, "created": "false"},
    )

    def _fail_if_called(*, owner: str, title: str, public: bool) -> None:  # noqa: ARG001
        error_message = "create_project_page should not be called when reusing an existing project"
        raise AssertionError(error_message)

    monkeypatch.setattr("historia.setup._automation.create_project_page", _fail_if_called)
    upserted_workflow: dict[str, object] = {}
    monkeypatch.setattr(
        "historia.setup._automation._upsert_workflow_file",
        lambda **kwargs: upserted_workflow.update(kwargs),
    )
    monkeypatch.setattr("historia.setup._automation._upsert_repository_secret", lambda **_kwargs: None)

    result = provision_automation(
        token="fake-token",
        username="octocat",
        owner="octocat",
        repository_name="work-history-data",
        private=False,
        secret_name="GH_PAT",
        recency_days=2,
        python_version="3.13",
        historia_spec="historia==1.2.3",
        cron_schedule="0 0 * * *",
        project_url="https://github.com/users/octocat/projects/5",
    )

    assert result["repository_created"] == "false"
    assert result["project_url"] == "https://github.com/users/octocat/projects/5"
    workflow_content = upserted_workflow["content"]
    assert isinstance(workflow_content, str)
    assert "PROJECT_NUMBER: 5" in workflow_content


@pytest.mark.ai_generated
def test_provision_automation_raises_when_project_creation_rate_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "historia.setup._automation._validate_historia_spec",
        lambda **kwargs: (kwargs["historia_spec"], None, []),
    )
    monkeypatch.setattr(
        "historia.setup._automation._get_authenticated_username",
        lambda *, token: "octocat",  # noqa: ARG005
    )
    monkeypatch.setattr(
        "historia.setup._automation._create_data_repository",
        lambda **_kwargs: {**_REPOSITORY_PAYLOAD, "created": "true"},
    )
    monkeypatch.setattr(
        "historia.setup._automation.create_project_page",
        lambda *, owner, title, public: {},  # noqa: ARG005
    )

    with pytest.raises(RuntimeError, match="rate limiting"):
        provision_automation(
            token="fake-token",
            username="octocat",
            owner="octocat",
            repository_name="work-history-data",
            private=False,
            secret_name="GH_PAT",
            recency_days=2,
            python_version="3.13",
            historia_spec="historia==1.2.3",
            cron_schedule="0 0 * * *",
            project_title="Work History",
        )


@pytest.mark.ai_generated
def test_provision_automation_propagates_authentication_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_runtime_error(*, token: str) -> str:  # noqa: ARG001
        error_message = "Could not authenticate with the provided GitHub token."
        raise RuntimeError(error_message)

    monkeypatch.setattr(
        "historia.setup._automation._validate_historia_spec",
        lambda **kwargs: (kwargs["historia_spec"], None, []),
    )
    monkeypatch.setattr("historia.setup._automation._get_authenticated_username", _raise_runtime_error)

    with pytest.raises(RuntimeError, match="authenticate"):
        provision_automation(
            token="bad-token",
            username="octocat",
            owner="octocat",
            repository_name="work-history-data",
            private=False,
            secret_name="GH_PAT",
            recency_days=2,
            python_version="3.13",
            historia_spec="historia==1.2.3",
            cron_schedule="0 0 * * *",
            project_url="https://github.com/users/octocat/projects/5",
        )


# ---------------------------------------------------------------------------
# _render_workflow_yaml – no network calls
# ---------------------------------------------------------------------------


@pytest.mark.ai_generated
def test_render_workflow_yaml_substitutes_all_placeholders() -> None:
    rendered = _render_workflow_yaml(**_RENDER_KWARGS)

    for placeholder in (
        "USERNAME",
        "PROJECT_NUMBER",
        "PYTHON_VERSION",
        "HISTORIA_SPEC",
        "SECRET_NAME",
        "CRON_SCHEDULE",
        "RECENCY_DAYS",
        "DEFAULT_BRANCH",
    ):
        assert "{{" + placeholder + "}}" not in rendered
    assert "USERNAME: octocat" in rendered
    assert "PROJECT_NUMBER: 7" in rendered
    assert 'PYTHON_VERSION: "3.13"' in rendered
    assert "HISTORIA_SPEC: historia==1.2.3" in rendered
    assert "secrets.GH_PAT" in rendered
    assert 'cron: "0 0 * * *"' in rendered
    assert "--recency 2" in rendered
    assert "HEAD:main" in rendered


@pytest.mark.ai_generated
def test_render_workflow_yaml_produces_valid_yaml() -> None:
    rendered = _render_workflow_yaml(**_RENDER_KWARGS)

    document = yaml.safe_load(rendered)

    assert document["name"] == "Update work history data"
    assert document["jobs"]["Update"]["runs-on"] == "ubuntu-latest"
    step_names = [step["name"] for step in document["jobs"]["Update"]["steps"]]
    assert "Run update" in step_names
    assert "Push to GitHub project" in step_names


@pytest.mark.ai_generated
def test_render_workflow_yaml_respects_custom_default_branch() -> None:
    kwargs = {**_RENDER_KWARGS, "default_branch": "trunk"}

    rendered = _render_workflow_yaml(**kwargs)

    assert "git fetch origin trunk" in rendered
    assert "git clone -b trunk" in rendered
    assert "HEAD:trunk" in rendered


@pytest.mark.ai_generated
def test_render_workflow_yaml_always_installs_historia() -> None:
    rendered = _render_workflow_yaml(**_RENDER_KWARGS)

    document = yaml.safe_load(rendered)
    steps = document["jobs"]["Update"]["steps"]
    install_step = next(step for step in steps if step["name"] == "Install historia")
    cache_step = next(step for step in steps if step["name"] == "Restore pip cache")

    assert "if" not in install_step
    assert "~/.local" not in cache_step["with"]["path"]
    assert "hashFiles" not in rendered


# ---------------------------------------------------------------------------
# _get_latest_pypi_version / _validate_historia_spec
# ---------------------------------------------------------------------------


@pytest.mark.ai_generated
def test_get_latest_pypi_version_returns_latest() -> None:
    response = _mock_response(200, {"info": {"version": "0.10.11"}, "releases": {}})

    with unittest.mock.patch("requests.get", return_value=response) as mock_get:
        version = _get_latest_pypi_version(package_name="historia")

    assert version == "0.10.11"
    _, kwargs = mock_get.call_args
    assert kwargs["url"] == "https://pypi.org/pypi/historia/json"


@pytest.mark.ai_generated
def test_get_latest_pypi_version_raises_on_lookup_failure() -> None:
    response = _mock_response(404, {"message": "Not Found"})
    response.text = "Not Found"

    with unittest.mock.patch("requests.get", return_value=response), pytest.raises(RuntimeError, match="PyPI"):
        _get_latest_pypi_version(package_name="not-a-real-package")


@pytest.mark.ai_generated
def test_validate_historia_spec_accepts_published_version() -> None:
    response = _mock_response(200, {"info": {"version": "0.10.11"}, "releases": {"0.10.11": [], "0.10.8": []}})

    with unittest.mock.patch("requests.get", return_value=response):
        spec, requires_python, supported_python_versions = _validate_historia_spec(historia_spec="historia==0.10.8")

    assert spec == "historia==0.10.8"
    assert requires_python is None
    assert supported_python_versions == []


@pytest.mark.ai_generated
def test_validate_historia_spec_rejects_unpublished_version() -> None:
    response = _mock_response(200, {"info": {"version": "0.10.11"}, "releases": {"0.10.11": []}})

    with (
        unittest.mock.patch("requests.get", return_value=response),
        pytest.raises(ValueError, match="not a published release"),
    ):
        _validate_historia_spec(historia_spec="historia==0.10.12")


@pytest.mark.ai_generated
def test_validate_historia_spec_normalizes_bare_version() -> None:
    """A bare `X.Y.Z` (missing the `historia==` prefix) is a common slip and should be caught, not ignored."""
    response = _mock_response(
        200,
        {
            "info": {
                "version": "0.10.11",
                "requires_python": ">=3.10",
                "classifiers": [
                    "Programming Language :: Python :: 3.10",
                    "Programming Language :: Python :: 3.13",
                    "Programming Language :: Python :: 3.11",
                ],
            },
            "releases": {"0.10.11": []},
        },
    )

    with unittest.mock.patch("requests.get", return_value=response):
        spec, requires_python, supported_python_versions = _validate_historia_spec(historia_spec="0.10.11")

    assert spec == "historia==0.10.11"
    assert requires_python == ">=3.10"
    assert supported_python_versions == ["3.10", "3.11", "3.13"]


@pytest.mark.ai_generated
def test_validate_historia_spec_rejects_unpublished_bare_version() -> None:
    response = _mock_response(200, {"info": {"version": "0.10.11"}, "releases": {"0.10.11": []}})

    with (
        unittest.mock.patch("requests.get", return_value=response),
        pytest.raises(ValueError, match="not a published release"),
    ):
        _validate_historia_spec(historia_spec="0.10.12")


@pytest.mark.ai_generated
def test_validate_historia_spec_looks_up_requires_python_for_a_non_latest_pin() -> None:
    project_response = _mock_response(
        200,
        {"info": {"version": "0.10.11", "requires_python": ">=3.10"}, "releases": {"0.10.11": [], "0.10.8": []}},
    )
    release_response = _mock_response(200, {"info": {"requires_python": ">=3.9"}})

    def _fake_get(*, url: str, timeout: int) -> unittest.mock.MagicMock:  # noqa: ARG001
        return release_response if url == "https://pypi.org/pypi/historia/0.10.8/json" else project_response

    with unittest.mock.patch("requests.get", side_effect=_fake_get):
        spec, requires_python, supported_python_versions = _validate_historia_spec(historia_spec="historia==0.10.8")

    assert spec == "historia==0.10.8"
    assert requires_python == ">=3.9"
    assert supported_python_versions == []


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "historia_spec",
    ["historia", "historia>=0.10.0", "historia[extra]==0.10.11", "some-other-package==1.0.0"],
)
def test_validate_historia_spec_skips_specs_it_cannot_confidently_check(historia_spec: str) -> None:
    with unittest.mock.patch("requests.get") as mock_get:
        spec, requires_python, supported_python_versions = _validate_historia_spec(historia_spec=historia_spec)

    mock_get.assert_not_called()
    assert spec == historia_spec
    assert requires_python is None
    assert supported_python_versions == []


@pytest.mark.ai_generated
def test_extract_supported_python_versions_sorts_and_filters_classifiers() -> None:
    classifiers = [
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3.13",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
    ]

    assert _extract_supported_python_versions(classifiers=classifiers) == ["3.10", "3.12", "3.13"]


@pytest.mark.ai_generated
def test_extract_supported_python_versions_handles_no_classifiers() -> None:
    assert _extract_supported_python_versions(classifiers=[]) == []


# ---------------------------------------------------------------------------
# _validate_python_version
# ---------------------------------------------------------------------------


@pytest.mark.ai_generated
def test_validate_python_version_accepts_compatible_version() -> None:
    _validate_python_version(python_version="3.13", requires_python=">=3.10")


@pytest.mark.ai_generated
def test_validate_python_version_skips_compatibility_check_when_requires_python_unknown() -> None:
    _validate_python_version(python_version="3.7", requires_python=None)


@pytest.mark.ai_generated
def test_validate_python_version_rejects_incompatible_version() -> None:
    with pytest.raises(ValueError, match="does not satisfy"):
        _validate_python_version(python_version="3.7", requires_python=">=3.10")


@pytest.mark.ai_generated
def test_validate_python_version_rejects_malformed_version() -> None:
    with pytest.raises(ValueError, match="not a valid Python version"):
        _validate_python_version(python_version="not-a-version", requires_python=None)


@pytest.mark.ai_generated
def test_provision_automation_raises_on_incompatible_python_version() -> None:
    response = _mock_response(
        200,
        {"info": {"version": "0.10.11", "requires_python": ">=3.10"}, "releases": {"0.10.11": []}},
    )

    with (
        unittest.mock.patch("requests.get", return_value=response),
        pytest.raises(ValueError, match="does not satisfy"),
    ):
        provision_automation(
            token="fake-token",
            username="octocat",
            owner="octocat",
            repository_name="work-history-data",
            private=False,
            secret_name="GH_PAT",
            recency_days=2,
            python_version="3.7",
            historia_spec="historia==0.10.11",
            cron_schedule="0 0 * * *",
            project_title="Work History",
        )


@pytest.mark.ai_generated
def test_provision_automation_raises_on_unpublished_historia_spec() -> None:
    response = _mock_response(200, {"info": {"version": "0.10.11"}, "releases": {"0.10.11": []}})

    with (
        unittest.mock.patch("requests.get", return_value=response),
        pytest.raises(ValueError, match="not a published release"),
    ):
        provision_automation(
            token="fake-token",
            username="octocat",
            owner="octocat",
            repository_name="work-history-data",
            private=False,
            secret_name="GH_PAT",
            recency_days=2,
            python_version="3.13",
            historia_spec="historia==0.10.12",
            cron_schedule="0 0 * * *",
            project_title="Work History",
        )


# ---------------------------------------------------------------------------
# _resolve_cron_schedule
# ---------------------------------------------------------------------------


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("shorthand", "expected"),
    [
        ("daily", "0 0 * * *"),
        ("Weekly", "0 0 * * 0"),
        ("  MONTHLY  ", "0 0 1 * *"),
    ],
)
def test_resolve_cron_schedule_expands_shorthands(shorthand: str, expected: str) -> None:
    assert _resolve_cron_schedule(cron_schedule=shorthand) == expected


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "cron_expression",
    ["0 0 * * *", "*/15 * * * *", "0 9-17 * * 1-5", "0,30 * * * *", "0 0 1 1 *"],
)
def test_resolve_cron_schedule_accepts_valid_custom_expressions(cron_expression: str) -> None:
    assert _resolve_cron_schedule(cron_schedule=cron_expression) == cron_expression


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "cron_expression",
    [
        "0 0 * *",  # too few fields
        "60 0 * * *",  # minute out of range
        "0 0 * * 8",  # day-of-week out of range
        "0 0 32 * *",  # day-of-month out of range
        "not a cron",
    ],
)
def test_resolve_cron_schedule_rejects_invalid_custom_expressions(cron_expression: str) -> None:
    with pytest.raises(ValueError, match="valid"):
        _resolve_cron_schedule(cron_schedule=cron_expression)


@pytest.mark.ai_generated
def test_provision_automation_expands_cron_shorthand(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "historia.setup._automation._validate_historia_spec",
        lambda **kwargs: (kwargs["historia_spec"], None, []),
    )
    monkeypatch.setattr(
        "historia.setup._automation._get_authenticated_username",
        lambda *, token: "octocat",  # noqa: ARG005
    )
    monkeypatch.setattr(
        "historia.setup._automation._create_data_repository",
        lambda **_kwargs: {**_REPOSITORY_PAYLOAD, "created": "true"},
    )
    monkeypatch.setattr(
        "historia.setup._automation.create_project_page",
        lambda **_kwargs: {"url": "https://github.com/users/octocat/projects/1", "id": "PVT_1"},
    )
    upserted_workflow: dict[str, object] = {}
    monkeypatch.setattr(
        "historia.setup._automation._upsert_workflow_file",
        lambda **kwargs: upserted_workflow.update(kwargs),
    )
    monkeypatch.setattr("historia.setup._automation._upsert_repository_secret", lambda **_kwargs: None)

    provision_automation(
        token="fake-token",
        username="octocat",
        owner="octocat",
        repository_name="work-history-data",
        private=False,
        secret_name="GH_PAT",
        recency_days=2,
        python_version="3.13",
        historia_spec="historia==1.2.3",
        cron_schedule="daily",
        project_title="Work History",
    )

    workflow_content = upserted_workflow["content"]
    assert isinstance(workflow_content, str)
    assert 'cron: "0 0 * * *"' in workflow_content


# ---------------------------------------------------------------------------
# _get_authenticated_username
# ---------------------------------------------------------------------------


@pytest.mark.ai_generated
def test_get_authenticated_username_success() -> None:
    response = _mock_response(200, {"login": "octocat"})

    with unittest.mock.patch("requests.get", return_value=response) as mock_get:
        username = _get_authenticated_username(token="fake-token")

    assert username == "octocat"
    _, kwargs = mock_get.call_args
    assert kwargs["headers"]["Authorization"] == "token fake-token"


@pytest.mark.ai_generated
def test_get_authenticated_username_raises_on_bad_token() -> None:
    response = _mock_response(401, {"message": "Bad credentials"})

    with unittest.mock.patch("requests.get", return_value=response), pytest.raises(RuntimeError, match="authenticate"):
        _get_authenticated_username(token="bad-token")


# ---------------------------------------------------------------------------
# _create_data_repository
# ---------------------------------------------------------------------------


@pytest.mark.ai_generated
def test_create_data_repository_reuses_existing_repository() -> None:
    existing = _mock_response(200, _REPOSITORY_PAYLOAD)

    with (
        unittest.mock.patch("requests.get", return_value=existing) as mock_get,
        unittest.mock.patch("requests.post") as mock_post,
    ):
        repository = _create_data_repository(
            owner="octocat",
            repository_name="work-history-data",
            token="fake-token",
            private=False,
            authenticated_username="octocat",
        )

    assert repository["created"] == "false"
    assert repository["full_name"] == "octocat/work-history-data"
    assert repository["default_branch"] == "main"
    mock_get.assert_called_once()
    mock_post.assert_not_called()


@pytest.mark.ai_generated
def test_create_data_repository_creates_fresh_when_name_was_redirected() -> None:
    """
    Regression test for a renamed-repo redirect being mistaken for a name match.

    GitHub redirects lookups of a renamed repo's old name to its current one (still HTTP 200), so a
    naive "200 means it exists" check would silently reuse the wrong (renamed) repository -- as happened
    when `work-history-data` had been renamed to `work-history-data-prev` and a lookup for
    `work-history-data` came back 200 with the `-prev` repo's info instead of 404.
    """
    redirected = _mock_response(
        200,
        {
            "name": "work-history-data-prev",
            "full_name": "octocat/work-history-data-prev",
            "html_url": "https://github.com/octocat/work-history-data-prev",
            "default_branch": "main",
        },
    )
    created = _mock_response(201, _REPOSITORY_PAYLOAD)

    with (
        unittest.mock.patch("requests.get", return_value=redirected),
        unittest.mock.patch("requests.post", return_value=created) as mock_post,
    ):
        repository = _create_data_repository(
            owner="octocat",
            repository_name="work-history-data",
            token="fake-token",
            private=False,
            authenticated_username="octocat",
        )

    assert repository["created"] == "true"
    assert repository["full_name"] == "octocat/work-history-data"
    mock_post.assert_called_once()


@pytest.mark.ai_generated
def test_create_data_repository_creates_under_user_endpoint() -> None:
    missing = _mock_response(404, {"message": "Not Found"})
    created = _mock_response(201, _REPOSITORY_PAYLOAD)

    with (
        unittest.mock.patch("requests.get", return_value=missing),
        unittest.mock.patch("requests.post", return_value=created) as mock_post,
    ):
        repository = _create_data_repository(
            owner="octocat",
            repository_name="work-history-data",
            token="fake-token",
            private=True,
            authenticated_username="octocat",
        )

    assert repository["created"] == "true"
    _, kwargs = mock_post.call_args
    assert kwargs["url"] == "https://api.github.com/user/repos"
    assert kwargs["json"]["private"] is True


@pytest.mark.ai_generated
def test_create_data_repository_creates_under_org_endpoint() -> None:
    missing = _mock_response(404, {"message": "Not Found"})
    created = _mock_response(
        201,
        {
            "full_name": "my-org/work-history-data",
            "html_url": "https://github.com/my-org/work-history-data",
            "default_branch": "main",
        },
    )

    with (
        unittest.mock.patch("requests.get", return_value=missing),
        unittest.mock.patch("requests.post", return_value=created) as mock_post,
    ):
        _create_data_repository(
            owner="my-org",
            repository_name="work-history-data",
            token="fake-token",
            private=False,
            authenticated_username="octocat",
        )

    _, kwargs = mock_post.call_args
    assert kwargs["url"] == "https://api.github.com/orgs/my-org/repos"


@pytest.mark.ai_generated
def test_create_data_repository_raises_on_failure() -> None:
    missing = _mock_response(404, {"message": "Not Found"})
    failure = _mock_response(422, {"message": "Repository creation failed."})

    with (
        unittest.mock.patch("requests.get", return_value=missing),
        unittest.mock.patch("requests.post", return_value=failure),
        pytest.raises(RuntimeError, match="Failed to create repository"),
    ):
        _create_data_repository(
            owner="octocat",
            repository_name="work-history-data",
            token="fake-token",
            private=False,
            authenticated_username="octocat",
        )


# ---------------------------------------------------------------------------
# _upsert_workflow_file
# ---------------------------------------------------------------------------


@pytest.mark.ai_generated
def test_upsert_workflow_file_creates_when_absent() -> None:
    missing = _mock_response(404, {"message": "Not Found"})
    created = _mock_response(201, {})

    with (
        unittest.mock.patch("requests.get", return_value=missing),
        unittest.mock.patch("requests.put", return_value=created) as mock_put,
    ):
        _upsert_workflow_file(
            owner="octocat",
            repository_name="work-history-data",
            branch="main",
            token="fake-token",
            content="name: test\n",
        )

    _, kwargs = mock_put.call_args
    assert "sha" not in kwargs["json"]
    assert kwargs["json"]["branch"] == "main"
    assert kwargs["json"]["author"]["name"] == "historia bot"
    assert kwargs["json"]["committer"]["name"] == "historia bot"


@pytest.mark.ai_generated
def test_upsert_workflow_file_includes_sha_when_present() -> None:
    existing = _mock_response(200, {"sha": "abc123"})
    updated = _mock_response(200, {})

    with (
        unittest.mock.patch("requests.get", return_value=existing),
        unittest.mock.patch("requests.put", return_value=updated) as mock_put,
    ):
        _upsert_workflow_file(
            owner="octocat",
            repository_name="work-history-data",
            branch="main",
            token="fake-token",
            content="name: test\n",
        )

    _, kwargs = mock_put.call_args
    assert kwargs["json"]["sha"] == "abc123"


@pytest.mark.ai_generated
def test_upsert_workflow_file_raises_on_failure() -> None:
    missing = _mock_response(404, {"message": "Not Found"})
    failure = _mock_response(403, {"message": "Forbidden"})

    with (
        unittest.mock.patch("requests.get", return_value=missing),
        unittest.mock.patch("requests.put", return_value=failure),
        pytest.raises(RuntimeError, match="Failed to write the workflow file"),
    ):
        _upsert_workflow_file(
            owner="octocat",
            repository_name="work-history-data",
            branch="main",
            token="fake-token",
            content="name: test\n",
        )


# ---------------------------------------------------------------------------
# _upsert_repository_secret
# ---------------------------------------------------------------------------


@pytest.mark.ai_generated
def test_upsert_repository_secret_encrypts_with_repository_public_key() -> None:
    private_key, encoded_public_key = _fake_public_key()
    key_response = _mock_response(200, {"key": encoded_public_key, "key_id": "key-id-1"})
    put_response = _mock_response(204, {})

    with (
        unittest.mock.patch("requests.get", return_value=key_response),
        unittest.mock.patch("requests.put", return_value=put_response) as mock_put,
    ):
        _upsert_repository_secret(
            owner="octocat",
            repository_name="work-history-data",
            secret_name="GH_PAT",
            secret_value="ghp_supersecret",
            token="fake-token",
        )

    _, kwargs = mock_put.call_args
    assert kwargs["json"]["key_id"] == "key-id-1"

    sealed = base64.b64decode(kwargs["json"]["encrypted_value"])
    decrypted = nacl.public.SealedBox(private_key).decrypt(sealed)
    assert decrypted == b"ghp_supersecret"


@pytest.mark.ai_generated
def test_upsert_repository_secret_raises_when_public_key_fetch_fails() -> None:
    failure = _mock_response(404, {"message": "Not Found"})

    with unittest.mock.patch("requests.get", return_value=failure), pytest.raises(RuntimeError, match="public key"):
        _upsert_repository_secret(
            owner="octocat",
            repository_name="work-history-data",
            secret_name="GH_PAT",
            secret_value="ghp_supersecret",
            token="fake-token",
        )


@pytest.mark.ai_generated
def test_upsert_repository_secret_raises_when_put_fails() -> None:
    _, encoded_public_key = _fake_public_key()
    key_response = _mock_response(200, {"key": encoded_public_key, "key_id": "key-id-1"})
    failure = _mock_response(403, {"message": "Forbidden"})

    with (
        unittest.mock.patch("requests.get", return_value=key_response),
        unittest.mock.patch("requests.put", return_value=failure),
        pytest.raises(RuntimeError, match="Failed to set secret"),
    ):
        _upsert_repository_secret(
            owner="octocat",
            repository_name="work-history-data",
            secret_name="GH_PAT",
            secret_value="ghp_supersecret",
            token="fake-token",
        )
