# ruff: noqa: S105 -- assertions compare against literal placeholder secrets, not real credentials
import importlib.metadata
import pathlib
from collections.abc import Callable

import click.testing
import pytest

import historia
import historia._cli


@pytest.mark.ai_generated
def test_root_cli_version_flag() -> None:
    runner = click.testing.CliRunner()

    result = runner.invoke(historia.historia_cli, ["--version"])

    assert result.exit_code == 0
    assert importlib.metadata.distribution("historia").version in result.output
    assert "historia" in result.output
    assert "version" in result.output.lower()


@pytest.mark.ai_generated
def test_root_cli_help_shows_nested_groups() -> None:
    runner = click.testing.CliRunner()

    result = runner.invoke(historia.historia_cli, ["--help"])

    assert result.exit_code == 0
    assert "update" in result.output
    assert "project" in result.output


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("group", "expected_commands"),
    [
        ("update", ["github"]),
        ("project", ["create", "populate", "update", "transition"]),
    ],
)
def test_subgroup_help_shows_commands(group: str, expected_commands: list[str]) -> None:
    runner = click.testing.CliRunner()

    result = runner.invoke(historia.historia_cli, [group, "--help"])

    assert result.exit_code == 0
    for cmd in expected_commands:
        assert cmd in result.output


@pytest.mark.ai_generated
def test_data_update_command_invokes_update(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    called_args: dict[str, pathlib.Path | str | int | None] = {}

    def _fake_update(
        directory: pathlib.Path,
        username: str,
        past_number_of_days: int,
        start_date: str | None,
    ) -> None:
        called_args["directory"] = directory
        called_args["username"] = username
        called_args["past_number_of_days"] = past_number_of_days
        called_args["start_date"] = start_date

    monkeypatch.setattr(historia._cli.data.github, "update", _fake_update)
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia.historia_cli,
        ["update", "github", "--directory", str(tmp_path), "--username", "octocat", "--recency", "3"],
    )

    assert result.exit_code == 0
    assert called_args["directory"] == tmp_path
    assert called_args["username"] == "octocat"
    assert called_args["past_number_of_days"] == 3
    assert called_args["start_date"] is None


@pytest.mark.ai_generated
def test_data_update_command_passes_start_date(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    called_args: dict[str, pathlib.Path | str | int | None] = {}

    def _fake_update(
        directory: pathlib.Path,
        username: str,
        past_number_of_days: int,
        start_date: str | None,
    ) -> None:
        called_args["directory"] = directory
        called_args["username"] = username
        called_args["past_number_of_days"] = past_number_of_days
        called_args["start_date"] = start_date

    monkeypatch.setattr(historia._cli.data.github, "update", _fake_update)
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia.historia_cli,
        [
            "update",
            "github",
            "--directory",
            str(tmp_path),
            "--username",
            "octocat",
            "--recency",
            "2",
            "--start",
            "2026-01-05",
        ],
    )

    assert result.exit_code == 0
    assert called_args["start_date"] == "2026-01-05"


@pytest.mark.ai_generated
@pytest.mark.parametrize(("command", "expected_present"), [("github", True), ("minify", False)])
def test_data_update_help_commands(command: str, expected_present: bool) -> None:
    runner = click.testing.CliRunner()

    result = runner.invoke(historia.historia_cli, ["update", "--help"])

    assert result.exit_code == 0
    assert (command in result.output) is expected_present


@pytest.mark.ai_generated
def test_project_create_command_invokes_create(monkeypatch: pytest.MonkeyPatch) -> None:
    called_args: dict[str, str | bool] = {}

    def _fake_create(owner: str, title: str, public: bool) -> dict[str, str]:
        called_args["owner"] = owner
        called_args["title"] = title
        called_args["public"] = public
        return {"id": "PVT_123", "url": "https://github.com/users/octocat/projects/1"}

    monkeypatch.setattr(historia._cli, "create_project_page", _fake_create)
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia.historia_cli,
        ["project", "create", "--owner", "octocat", "--title", "Work Board"],
    )

    assert result.exit_code == 0
    assert called_args["owner"] == "octocat"
    assert called_args["title"] == "Work Board"
    assert called_args["public"] is False
    assert "Project created successfully!" in result.output


@pytest.mark.ai_generated
def test_project_create_command_passes_public_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    called_args: dict[str, object] = {}

    def _fake_create(owner: str, title: str, public: bool) -> dict[str, str]:  # noqa: ARG001
        called_args["public"] = public
        return {"id": "PVT_123", "url": "https://github.com/users/octocat/projects/1"}

    monkeypatch.setattr(historia._cli, "create_project_page", _fake_create)
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia.historia_cli,
        ["project", "create", "--owner", "octocat", "--title", "Work Board", "--public"],
    )

    assert result.exit_code == 0
    assert called_args["public"] is True


@pytest.mark.ai_generated
def test_project_create_command_shows_failure_message_when_none_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_create(owner: str, title: str, public: bool) -> None:
        pass

    monkeypatch.setattr(historia._cli, "create_project_page", _fake_create)
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia.historia_cli,
        ["project", "create", "--owner", "octocat", "--title", "Work Board"],
    )

    assert result.exit_code == 0
    assert "Project creation failed" in result.output


@pytest.mark.ai_generated
def test_project_populate_command_invokes_add_to_project(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    called_args: dict[str, pathlib.Path | str | int | bool | None] = {}

    def _fake_add_to_project(
        directory: pathlib.Path,
        project_url: str,
        status: str | None,
        end_date_placeholder_days: int,
        assign_members: bool,
    ) -> None:
        called_args["directory"] = directory
        called_args["project_url"] = project_url
        called_args["status"] = status
        called_args["end_date_placeholder_days"] = end_date_placeholder_days
        called_args["assign_members"] = assign_members

    monkeypatch.setattr(historia._cli, "add_to_project", _fake_add_to_project)
    monkeypatch.setattr(historia._cli, "get_project_closing_workflows", lambda _url: [])
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia.historia_cli,
        [
            "project",
            "populate",
            "--directory",
            str(tmp_path),
            "--url",
            "https://github.com/users/octocat/projects/1",
            "--status",
            "In Progress",
            "--placeholder",
            "90",
            "--members",
        ],
    )

    assert result.exit_code == 0
    assert called_args["directory"] == tmp_path
    assert called_args["project_url"] == "https://github.com/users/octocat/projects/1"
    assert called_args["status"] == "In Progress"
    assert called_args["end_date_placeholder_days"] == 90
    assert called_args["assign_members"] is True


@pytest.mark.ai_generated
def test_project_populate_warns_and_prompts_when_closing_workflows_exist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    called: list[bool] = []

    def _fake_add_to_project(**_kwargs: object) -> None:
        called.append(True)

    monkeypatch.setattr(historia._cli, "add_to_project", _fake_add_to_project)
    monkeypatch.setattr(
        historia._cli,
        "get_project_closing_workflows",
        lambda _url: ["Auto-close issue"],
    )
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia.historia_cli,
        [
            "project",
            "populate",
            "--directory",
            str(tmp_path),
            "--url",
            "https://github.com/users/octocat/projects/1",
            "--status",
            "Done",
        ],
        input="y\n",
    )

    assert result.exit_code == 0
    assert called == [True]
    assert "Auto-close issue" in result.output
    assert "Warning" in result.output
    assert "specified status 'Done'" in result.output


@pytest.mark.ai_generated
def test_project_populate_aborts_when_closing_workflows_exist_and_user_declines(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    called: list[bool] = []

    def _fake_add_to_project(**_kwargs: object) -> None:
        called.append(True)

    monkeypatch.setattr(historia._cli, "add_to_project", _fake_add_to_project)
    monkeypatch.setattr(
        historia._cli,
        "get_project_closing_workflows",
        lambda _url: ["Auto-close issue"],
    )
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia.historia_cli,
        [
            "project",
            "populate",
            "--directory",
            str(tmp_path),
            "--url",
            "https://github.com/users/octocat/projects/1",
            "--status",
            "Done",
        ],
        input="n\n",
    )

    assert result.exit_code == 0
    assert called == []


@pytest.mark.ai_generated
def test_project_populate_auto_accepts_when_yes_flag_and_closing_workflows_exist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    called: list[bool] = []

    def _fake_add_to_project(**_kwargs: object) -> None:
        called.append(True)

    monkeypatch.setattr(historia._cli, "add_to_project", _fake_add_to_project)
    monkeypatch.setattr(
        historia._cli,
        "get_project_closing_workflows",
        lambda _url: ["Auto-close issue"],
    )
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia.historia_cli,
        [
            "project",
            "populate",
            "--directory",
            str(tmp_path),
            "--url",
            "https://github.com/users/octocat/projects/1",
            "--status",
            "Done",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    assert called == [True]
    assert "Warning" in result.output
    assert "Auto-close issue" in result.output
    assert "Do you want to proceed with populating this project?" not in result.output


@pytest.mark.ai_generated
def test_project_update_dates_command_invokes_update_item_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    called_args: dict[str, str | int] = {}

    def _fake_update_project_item_dates(project_url: str, end_date_placeholder_days: int) -> None:
        called_args["project_url"] = project_url
        called_args["end_date_placeholder_days"] = end_date_placeholder_days

    monkeypatch.setattr(historia._cli, "update_project_item_dates", _fake_update_project_item_dates)
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia.historia_cli,
        [
            "project",
            "update",
            "dates",
            "--url",
            "https://github.com/users/octocat/projects/1",
            "--placeholder",
            "200",
        ],
    )

    assert result.exit_code == 0
    assert called_args["project_url"] == "https://github.com/users/octocat/projects/1"
    assert called_args["end_date_placeholder_days"] == 200


@pytest.mark.ai_generated
def test_project_update_members_command_invokes_update_item_members(monkeypatch: pytest.MonkeyPatch) -> None:
    called_args: dict[str, str] = {}

    def _fake_update_project_item_members(project_url: str) -> None:
        called_args["project_url"] = project_url

    monkeypatch.setattr(historia._cli, "update_project_item_members", _fake_update_project_item_members)
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia.historia_cli,
        [
            "project",
            "update",
            "members",
            "--url",
            "https://github.com/users/octocat/projects/1",
        ],
    )

    assert result.exit_code == 0
    assert called_args["project_url"] == "https://github.com/users/octocat/projects/1"


@pytest.mark.ai_generated
def test_project_transition_command_invokes_transition_status(monkeypatch: pytest.MonkeyPatch) -> None:
    called_args: dict[str, str] = {}

    def _fake_transition_status(project_url: str, current_status: str, new_status: str) -> None:
        called_args["project_url"] = project_url
        called_args["current_status"] = current_status
        called_args["new_status"] = new_status

    monkeypatch.setattr(historia._cli, "transition_status", _fake_transition_status)
    monkeypatch.setattr(historia._cli, "get_project_closing_workflows", lambda _url: [])
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia.historia_cli,
        [
            "project",
            "transition",
            "--url",
            "https://github.com/users/octocat/projects/1",
            "--status",
            "DONE",
            "--new",
            "History",
        ],
    )

    assert result.exit_code == 0
    assert called_args["project_url"] == "https://github.com/users/octocat/projects/1"
    assert called_args["current_status"] == "DONE"
    assert called_args["new_status"] == "History"


@pytest.mark.ai_generated
def test_project_transition_warns_and_prompts_when_closing_workflows_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[bool] = []

    def _fake_transition_status(**_kwargs: object) -> None:
        called.append(True)

    monkeypatch.setattr(historia._cli, "transition_status", _fake_transition_status)
    monkeypatch.setattr(
        historia._cli,
        "get_project_closing_workflows",
        lambda _url: ["Auto-close issue"],
    )
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia.historia_cli,
        [
            "project",
            "transition",
            "--url",
            "https://github.com/users/octocat/projects/1",
            "--status",
            "In Progress",
            "--new",
            "Done",
        ],
        input="y\n",
    )

    assert result.exit_code == 0
    assert called == [True]
    assert "Auto-close issue" in result.output
    assert "Warning" in result.output


@pytest.mark.ai_generated
def test_project_transition_aborts_when_closing_workflows_exist_and_user_declines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[bool] = []

    def _fake_transition_status(**_kwargs: object) -> None:
        called.append(True)

    monkeypatch.setattr(historia._cli, "transition_status", _fake_transition_status)
    monkeypatch.setattr(
        historia._cli,
        "get_project_closing_workflows",
        lambda _url: ["Auto-close issue"],
    )
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia.historia_cli,
        [
            "project",
            "transition",
            "--url",
            "https://github.com/users/octocat/projects/1",
            "--status",
            "In Progress",
            "--new",
            "Done",
        ],
        input="n\n",
    )

    assert result.exit_code == 0
    assert called == []


@pytest.mark.ai_generated
def test_project_transition_auto_accepts_when_yes_flag_and_closing_workflows_exist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[bool] = []

    def _fake_transition_status(**_kwargs: object) -> None:
        called.append(True)

    monkeypatch.setattr(historia._cli, "transition_status", _fake_transition_status)
    monkeypatch.setattr(
        historia._cli,
        "get_project_closing_workflows",
        lambda _url: ["Auto-close issue"],
    )
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia.historia_cli,
        [
            "project",
            "transition",
            "--url",
            "https://github.com/users/octocat/projects/1",
            "--status",
            "In Progress",
            "--new",
            "Done",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    assert called == [True]
    assert "Warning" in result.output
    assert "Auto-close issue" in result.output
    assert "Do you want to proceed" not in result.output


@pytest.mark.ai_generated
def test_project_transition_yes_flag_has_no_effect_when_no_closing_workflows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: list[bool] = []

    def _fake_transition_status(**_kwargs: object) -> None:
        called.append(True)

    monkeypatch.setattr(historia._cli, "transition_status", _fake_transition_status)
    monkeypatch.setattr(historia._cli, "get_project_closing_workflows", lambda _url: [])
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia.historia_cli,
        [
            "project",
            "transition",
            "--url",
            "https://github.com/users/octocat/projects/1",
            "--status",
            "In Progress",
            "--new",
            "Done",
            "--yes",
        ],
    )

    assert result.exit_code == 0
    assert called == [True]
    assert "Warning" not in result.output


@pytest.mark.ai_generated
@pytest.mark.parametrize("exception_type", [ValueError, RuntimeError])
@pytest.mark.parametrize(
    ("attr_name", "make_cli_args"),
    [
        (
            "add_to_project",
            lambda tmp_path: [
                "project",
                "populate",
                "--directory",
                str(tmp_path),
                "--url",
                "https://github.com/users/octocat/projects/1",
            ],
        ),
        (
            "update_project_item_dates",
            lambda _: [
                "project",
                "update",
                "dates",
                "--url",
                "https://github.com/users/octocat/projects/1",
            ],
        ),
        (
            "transition_status",
            lambda _: [
                "project",
                "transition",
                "--url",
                "https://github.com/users/octocat/projects/1",
                "--status",
                "DONE",
                "--new",
                "History",
            ],
        ),
        (
            "update_project_item_members",
            lambda _: [
                "project",
                "update",
                "members",
                "--url",
                "https://github.com/users/octocat/projects/1",
            ],
        ),
    ],
)
def test_project_command_shows_error_on_exception(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    exception_type: type[Exception],
    attr_name: str,
    make_cli_args: Callable[[pathlib.Path], list[str]],
) -> None:
    def _fake(*_args: object, **_kwargs: object) -> None:
        error_message = "something went wrong"
        raise exception_type(error_message)

    monkeypatch.setattr(historia._cli, attr_name, _fake)
    if attr_name in {"add_to_project", "transition_status"}:
        monkeypatch.setattr(historia._cli, "get_project_closing_workflows", lambda _url: [])
    runner = click.testing.CliRunner()

    result = runner.invoke(historia.historia_cli, make_cli_args(tmp_path))

    assert result.exit_code == 1
    assert "something went wrong" in result.output


@pytest.mark.ai_generated
def test_setup_automation_happy_path_creates_project_and_writes_workflow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: dict[str, object] = {}

    def _fake_get_authenticated_username(*, token: str) -> str:  # noqa: ARG001
        return "octocat"

    def _fake_provision_automation(**kwargs: object) -> dict[str, str]:
        calls.update(kwargs)
        return {
            "repository_url": "https://github.com/octocat/work-history-data",
            "repository_created": "true",
            "project_url": "https://github.com/users/octocat/projects/1",
            "workflow_url": "https://github.com/octocat/work-history-data/actions/workflows/update.yml",
        }

    monkeypatch.setattr(historia._cli, "_get_authenticated_username", _fake_get_authenticated_username)
    monkeypatch.setattr(historia._cli, "_get_latest_pypi_version", lambda *, package_name: "0.10.11")  # noqa: ARG005
    monkeypatch.setattr(
        historia._cli,
        "_validate_historia_spec",
        lambda *, historia_spec: (historia_spec, None, []),
    )
    monkeypatch.setattr(historia._cli, "_validate_python_version", lambda **_kwargs: None)
    monkeypatch.setattr(historia._cli, "provision_automation", _fake_provision_automation)

    runner = click.testing.CliRunner()
    result = runner.invoke(
        historia.historia_cli,
        ["setup", "automation"],
        input="fake-token\n\n\n\nn\ny\n\n\n\n\n\n\n\n",
    )

    assert result.exit_code == 0
    assert "https://github.com/octocat/work-history-data" in result.output
    assert "https://github.com/users/octocat/projects/1" in result.output
    assert calls["token"] == "fake-token"
    assert calls["username"] == "octocat"
    assert calls["owner"] == "octocat"
    assert calls["repository_name"] == "work-history-data"
    assert calls["private"] is False
    assert calls["project_title"] == "Work History"
    assert calls["project_url"] is None
    assert calls["project_public"] is False
    assert calls["secret_name"] == "GH_PAT"
    assert calls["recency_days"] == 2
    assert calls["historia_spec"] == "historia==0.10.11"


@pytest.mark.ai_generated
def test_setup_automation_new_project_can_be_made_public(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def _fake_get_authenticated_username(*, token: str) -> str:  # noqa: ARG001
        return "octocat"

    def _fake_provision_automation(**kwargs: object) -> dict[str, str]:
        calls.update(kwargs)
        return {
            "repository_url": "https://github.com/octocat/work-history-data",
            "repository_created": "true",
            "project_url": "https://github.com/users/octocat/projects/1",
            "workflow_url": "https://github.com/octocat/work-history-data/actions/workflows/update.yml",
        }

    monkeypatch.setattr(historia._cli, "_get_authenticated_username", _fake_get_authenticated_username)
    monkeypatch.setattr(historia._cli, "_get_latest_pypi_version", lambda *, package_name: "0.10.11")  # noqa: ARG005
    monkeypatch.setattr(
        historia._cli,
        "_validate_historia_spec",
        lambda *, historia_spec: (historia_spec, None, []),
    )
    monkeypatch.setattr(historia._cli, "_validate_python_version", lambda **_kwargs: None)
    monkeypatch.setattr(historia._cli, "provision_automation", _fake_provision_automation)

    runner = click.testing.CliRunner()
    result = runner.invoke(
        historia.historia_cli,
        ["setup", "automation"],
        input="fake-token\n\n\n\nn\ny\n\ny\n\n\n\n\n\n",
    )

    assert result.exit_code == 0
    assert calls["project_public"] is True


@pytest.mark.ai_generated
def test_setup_automation_reuses_existing_project(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def _fake_get_authenticated_username(*, token: str) -> str:  # noqa: ARG001
        return "octocat"

    def _fake_provision_automation(**kwargs: object) -> dict[str, str]:
        calls.update(kwargs)
        return {
            "repository_url": "https://github.com/octocat/work-history-data",
            "repository_created": "false",
            "project_url": "https://github.com/users/octocat/projects/5",
            "workflow_url": "https://github.com/octocat/work-history-data/actions/workflows/update.yml",
        }

    monkeypatch.setattr(historia._cli, "_get_authenticated_username", _fake_get_authenticated_username)
    monkeypatch.setattr(historia._cli, "_get_latest_pypi_version", lambda *, package_name: "0.10.11")  # noqa: ARG005
    monkeypatch.setattr(
        historia._cli,
        "_validate_historia_spec",
        lambda *, historia_spec: (historia_spec, None, []),
    )
    monkeypatch.setattr(historia._cli, "_validate_python_version", lambda **_kwargs: None)
    monkeypatch.setattr(historia._cli, "provision_automation", _fake_provision_automation)

    runner = click.testing.CliRunner()
    result = runner.invoke(
        historia.historia_cli,
        ["setup", "automation"],
        input="fake-token\n\n\n\nn\nn\nhttps://github.com/users/octocat/projects/5\n\n\n\n\n\n",
    )

    assert result.exit_code == 0
    assert "https://github.com/users/octocat/projects/5" in result.output
    assert calls["project_title"] is None
    assert calls["project_url"] == "https://github.com/users/octocat/projects/5"


@pytest.mark.ai_generated
def test_setup_automation_shows_error_and_exits_on_bad_token(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_runtime_error(*, token: str) -> str:  # noqa: ARG001
        error_message = "Could not authenticate with the provided GitHub token."
        raise RuntimeError(error_message)

    monkeypatch.setattr(historia._cli, "_get_authenticated_username", _raise_runtime_error)
    runner = click.testing.CliRunner()

    result = runner.invoke(historia.historia_cli, ["setup", "automation"], input="bad-token\n")

    assert result.exit_code == 1
    assert "Could not authenticate" in result.output


@pytest.mark.ai_generated
def test_setup_automation_shows_error_when_provision_automation_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_get_authenticated_username(*, token: str) -> str:  # noqa: ARG001
        return "octocat"

    def _raise_runtime_error(**_kwargs: object) -> dict[str, str]:
        error_message = "Failed to create repository."
        raise RuntimeError(error_message)

    monkeypatch.setattr(historia._cli, "_get_authenticated_username", _fake_get_authenticated_username)
    monkeypatch.setattr(historia._cli, "_get_latest_pypi_version", lambda *, package_name: "0.10.11")  # noqa: ARG005
    monkeypatch.setattr(
        historia._cli,
        "_validate_historia_spec",
        lambda *, historia_spec: (historia_spec, None, []),
    )
    monkeypatch.setattr(historia._cli, "_validate_python_version", lambda **_kwargs: None)
    monkeypatch.setattr(historia._cli, "provision_automation", _raise_runtime_error)

    runner = click.testing.CliRunner()
    result = runner.invoke(
        historia.historia_cli,
        ["setup", "automation"],
        input="fake-token\n\n\n\nn\ny\n\n\n\n\n\n\n\n",
    )

    assert result.exit_code == 1
    assert "Failed to create repository" in result.output


@pytest.mark.ai_generated
def test_setup_automation_falls_back_to_no_default_when_pypi_unreachable(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def _fake_get_authenticated_username(*, token: str) -> str:  # noqa: ARG001
        return "octocat"

    def _fake_provision_automation(**kwargs: object) -> dict[str, str]:
        calls.update(kwargs)
        return {
            "repository_url": "https://github.com/octocat/work-history-data",
            "repository_created": "true",
            "project_url": "https://github.com/users/octocat/projects/1",
            "workflow_url": "https://github.com/octocat/work-history-data/actions/workflows/update.yml",
        }

    def _raise_runtime_error(*, package_name: str) -> str:  # noqa: ARG001
        error_message = "Could not look up `historia` on PyPI."
        raise RuntimeError(error_message)

    monkeypatch.setattr(historia._cli, "_get_authenticated_username", _fake_get_authenticated_username)
    monkeypatch.setattr(historia._cli, "_get_latest_pypi_version", _raise_runtime_error)
    monkeypatch.setattr(
        historia._cli,
        "_validate_historia_spec",
        lambda *, historia_spec: (historia_spec, None, []),
    )
    monkeypatch.setattr(historia._cli, "_validate_python_version", lambda **_kwargs: None)
    monkeypatch.setattr(historia._cli, "provision_automation", _fake_provision_automation)

    runner = click.testing.CliRunner()
    result = runner.invoke(
        historia.historia_cli,
        ["setup", "automation"],
        # token, username, owner, repo name, private=n, new project=y, title, public, secret name,
        # recency, historia_spec (explicit, no default to accept), python version, cron
        input="fake-token\n\n\n\nn\ny\n\n\n\n\nhistoria==9.9.9\n\n\n",
    )

    assert result.exit_code == 0
    assert calls["historia_spec"] == "historia==9.9.9"


@pytest.mark.ai_generated
def test_setup_automation_reprompts_on_invalid_historia_spec(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}
    attempts: list[str] = []

    def _fake_get_authenticated_username(*, token: str) -> str:  # noqa: ARG001
        return "octocat"

    def _fake_provision_automation(**kwargs: object) -> dict[str, str]:
        calls.update(kwargs)
        return {
            "repository_url": "https://github.com/octocat/work-history-data",
            "repository_created": "true",
            "project_url": "https://github.com/users/octocat/projects/1",
            "workflow_url": "https://github.com/octocat/work-history-data/actions/workflows/update.yml",
        }

    def _fake_validate_historia_spec(*, historia_spec: str) -> tuple[str, str | None, list[str]]:
        attempts.append(historia_spec)
        if historia_spec == "1.0.0":
            error_message = "`1.0.0` is not a published release of `historia` on PyPI."
            raise ValueError(error_message)
        return historia_spec, None, []

    monkeypatch.setattr(historia._cli, "_get_authenticated_username", _fake_get_authenticated_username)
    monkeypatch.setattr(historia._cli, "_get_latest_pypi_version", lambda *, package_name: "0.10.11")  # noqa: ARG005
    monkeypatch.setattr(historia._cli, "_validate_historia_spec", _fake_validate_historia_spec)
    monkeypatch.setattr(historia._cli, "_validate_python_version", lambda **_kwargs: None)
    monkeypatch.setattr(historia._cli, "provision_automation", _fake_provision_automation)

    runner = click.testing.CliRunner()
    result = runner.invoke(
        historia.historia_cli,
        ["setup", "automation"],
        # token, username, owner, repo name, private=n, new project=y, title, public, secret name,
        # recency, historia_spec=1.0.0 (rejected, reprompted), historia_spec=historia==0.10.8 (accepted),
        # python version, cron
        input="fake-token\n\n\n\nn\ny\n\n\n\n\n1.0.0\nhistoria==0.10.8\n\n\n",
    )

    assert result.exit_code == 0, result.output
    assert attempts == ["1.0.0", "historia==0.10.8"]
    assert "not a published release" in result.output
    assert calls["historia_spec"] == "historia==0.10.8"


@pytest.mark.ai_generated
def test_setup_automation_reprompts_on_invalid_python_version(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}
    attempts: list[str] = []

    def _fake_get_authenticated_username(*, token: str) -> str:  # noqa: ARG001
        return "octocat"

    def _fake_provision_automation(**kwargs: object) -> dict[str, str]:
        calls.update(kwargs)
        return {
            "repository_url": "https://github.com/octocat/work-history-data",
            "repository_created": "true",
            "project_url": "https://github.com/users/octocat/projects/1",
            "workflow_url": "https://github.com/octocat/work-history-data/actions/workflows/update.yml",
        }

    def _fake_validate_python_version(*, python_version: str, requires_python: str | None) -> None:  # noqa: ARG001
        attempts.append(python_version)
        if python_version == "3.6":
            error_message = "Python 3.6 does not satisfy the pinned `historia` release's required Python version."
            raise ValueError(error_message)

    monkeypatch.setattr(historia._cli, "_get_authenticated_username", _fake_get_authenticated_username)
    monkeypatch.setattr(historia._cli, "_get_latest_pypi_version", lambda *, package_name: "0.10.11")  # noqa: ARG005
    monkeypatch.setattr(
        historia._cli,
        "_validate_historia_spec",
        lambda *, historia_spec: (historia_spec, ">=3.10", []),
    )
    monkeypatch.setattr(historia._cli, "_validate_python_version", _fake_validate_python_version)
    monkeypatch.setattr(historia._cli, "provision_automation", _fake_provision_automation)

    runner = click.testing.CliRunner()
    result = runner.invoke(
        historia.historia_cli,
        ["setup", "automation"],
        # token, username, owner, repo name, private=n, new project=y, title, public, secret name,
        # recency, historia_spec, python_version=3.6 (rejected, reprompted), python_version=3.13, cron
        input="fake-token\n\n\n\nn\ny\n\n\n\n\n\n3.6\n3.13\n\n",
    )

    assert result.exit_code == 0, result.output
    assert attempts == ["3.6", "3.13"]
    assert "does not satisfy" in result.output
    assert calls["python_version"] == "3.13"


@pytest.mark.ai_generated
def test_setup_automation_python_version_prompt_lists_supported_choices(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def _fake_get_authenticated_username(*, token: str) -> str:  # noqa: ARG001
        return "octocat"

    def _fake_provision_automation(**kwargs: object) -> dict[str, str]:
        calls.update(kwargs)
        return {
            "repository_url": "https://github.com/octocat/work-history-data",
            "repository_created": "true",
            "project_url": "https://github.com/users/octocat/projects/1",
            "workflow_url": "https://github.com/octocat/work-history-data/actions/workflows/update.yml",
        }

    monkeypatch.setattr(historia._cli, "_get_authenticated_username", _fake_get_authenticated_username)
    monkeypatch.setattr(historia._cli, "_get_latest_pypi_version", lambda *, package_name: "0.10.11")  # noqa: ARG005
    monkeypatch.setattr(
        historia._cli,
        "_validate_historia_spec",
        lambda *, historia_spec: (historia_spec, ">=3.10", ["3.10", "3.11", "3.12", "3.13", "3.14"]),
    )
    monkeypatch.setattr(historia._cli, "provision_automation", _fake_provision_automation)

    runner = click.testing.CliRunner()
    result = runner.invoke(
        historia.historia_cli,
        ["setup", "automation"],
        # token, username, owner, repo name, private=n, new project=y, title, public, secret name,
        # recency, historia_spec, python_version=3.6 (not a listed choice, reprompted), python_version=3.12, cron
        input="fake-token\n\n\n\nn\ny\n\n\n\n\n\n3.6\n3.12\n\n",
    )

    assert result.exit_code == 0, result.output
    assert "Python version to use in the workflow (3.10, 3.11, 3.12, 3.13, 3.14) [3.13]" in result.output
    assert "is not one of" in result.output
    assert calls["python_version"] == "3.12"


@pytest.mark.ai_generated
def test_setup_automation_cron_prompt_accepts_shorthand(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def _fake_get_authenticated_username(*, token: str) -> str:  # noqa: ARG001
        return "octocat"

    def _fake_provision_automation(**kwargs: object) -> dict[str, str]:
        calls.update(kwargs)
        return {
            "repository_url": "https://github.com/octocat/work-history-data",
            "repository_created": "true",
            "project_url": "https://github.com/users/octocat/projects/1",
            "workflow_url": "https://github.com/octocat/work-history-data/actions/workflows/update.yml",
        }

    monkeypatch.setattr(historia._cli, "_get_authenticated_username", _fake_get_authenticated_username)
    monkeypatch.setattr(historia._cli, "_get_latest_pypi_version", lambda *, package_name: "0.10.11")  # noqa: ARG005
    monkeypatch.setattr(
        historia._cli,
        "_validate_historia_spec",
        lambda *, historia_spec: (historia_spec, None, []),
    )
    monkeypatch.setattr(historia._cli, "_validate_python_version", lambda **_kwargs: None)
    monkeypatch.setattr(historia._cli, "provision_automation", _fake_provision_automation)

    runner = click.testing.CliRunner()
    result = runner.invoke(
        historia.historia_cli,
        ["setup", "automation"],
        # token, username, owner, repo name, private=n, new project=y, title, public, secret name,
        # recency, historia_spec, python version, cron=weekly
        input="fake-token\n\n\n\nn\ny\n\n\n\n\n\n\nweekly\n",
    )

    assert result.exit_code == 0, result.output
    assert calls["cron_schedule"] == "0 0 * * 0"


@pytest.mark.ai_generated
def test_setup_automation_reprompts_on_invalid_cron(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: dict[str, object] = {}

    def _fake_get_authenticated_username(*, token: str) -> str:  # noqa: ARG001
        return "octocat"

    def _fake_provision_automation(**kwargs: object) -> dict[str, str]:
        calls.update(kwargs)
        return {
            "repository_url": "https://github.com/octocat/work-history-data",
            "repository_created": "true",
            "project_url": "https://github.com/users/octocat/projects/1",
            "workflow_url": "https://github.com/octocat/work-history-data/actions/workflows/update.yml",
        }

    monkeypatch.setattr(historia._cli, "_get_authenticated_username", _fake_get_authenticated_username)
    monkeypatch.setattr(historia._cli, "_get_latest_pypi_version", lambda *, package_name: "0.10.11")  # noqa: ARG005
    monkeypatch.setattr(
        historia._cli,
        "_validate_historia_spec",
        lambda *, historia_spec: (historia_spec, None, []),
    )
    monkeypatch.setattr(historia._cli, "_validate_python_version", lambda **_kwargs: None)
    monkeypatch.setattr(historia._cli, "provision_automation", _fake_provision_automation)

    runner = click.testing.CliRunner()
    result = runner.invoke(
        historia.historia_cli,
        ["setup", "automation"],
        # token, username, owner, repo name, private=n, new project=y, title, public, secret name,
        # recency, historia_spec, python version, cron="99 * * * *" (invalid, reprompted), cron=daily
        input="fake-token\n\n\n\nn\ny\n\n\n\n\n\n\n99 * * * *\ndaily\n",
    )

    assert result.exit_code == 0, result.output
    assert "not a valid" in result.output
    assert calls["cron_schedule"] == "0 0 * * *"


@pytest.mark.ai_generated
def test_setup_automation_help_lists_command() -> None:
    runner = click.testing.CliRunner()

    result = runner.invoke(historia.historia_cli, ["setup", "--help"])

    assert result.exit_code == 0
    assert "automation" in result.output


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("command", "expected_flags", "removed_flags"),
    [
        (
            "populate",
            ["--url", "--placeholder", "--members", "--yes"],
            ["--project-url", "--projecturl", "--end-date-placeholder-days", "--enddateplaceholderdays"],
        ),
        (
            "update dates",
            ["--url", "--placeholder"],
            ["--project-url", "--projecturl", "--end-date-placeholder-days", "--enddateplaceholderdays"],
        ),
        ("update members", ["--url"], ["--project-url", "--projecturl"]),
        ("transition", ["--url", "--status", "--new", "--yes"], ["--project-url", "--projecturl"]),
    ],
)
def test_project_command_flags_use_no_dash_format(
    command: str,
    expected_flags: list[str],
    removed_flags: list[str],
) -> None:
    runner = click.testing.CliRunner()

    result = runner.invoke(historia.historia_cli, ["project", *command.split(), "--help"])

    assert result.exit_code == 0
    for expected_flag in expected_flags:
        assert expected_flag in result.output
    for removed_flag in removed_flags:
        assert removed_flag not in result.output
