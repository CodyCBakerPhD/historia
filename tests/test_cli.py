import pathlib
from collections.abc import Callable

import click.testing
import pytest

import historia
import historia._cli


@pytest.mark.ai_generated
def test_root_cli_help_shows_nested_groups() -> None:
    runner = click.testing.CliRunner()

    result = runner.invoke(historia.historia_cli, ["--help"])

    assert result.exit_code == 0
    assert "data" in result.output
    assert "project" in result.output


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("group", "expected_commands"),
    [
        ("data", ["minify", "update"]),
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
def test_public_root_cli_aliases_compat_root() -> None:
    public_cli = historia._cli.historia_cli
    compat_alias = historia._cli._mywork_cli
    assert public_cli is compat_alias


@pytest.mark.ai_generated
def test_data_update_command_invokes_update(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    called_args: dict[str, pathlib.Path | str | int] = {}

    def _fake_update(directory: pathlib.Path, username: str, past_number_of_days: int) -> None:
        called_args["directory"] = directory
        called_args["username"] = username
        called_args["past_number_of_days"] = past_number_of_days

    monkeypatch.setattr(historia._cli.data.github, "update", _fake_update)
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia.historia_cli,
        ["data", "update", "github", "--directory", str(tmp_path), "--username", "octocat", "--recency", "3"],
    )

    assert result.exit_code == 0
    assert called_args["directory"] == tmp_path
    assert called_args["username"] == "octocat"
    assert called_args["past_number_of_days"] == 3


@pytest.mark.ai_generated
def test_data_minify_command_invokes_minify(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    called_args: dict[str, pathlib.Path] = {}

    def _fake_minify(directory: pathlib.Path) -> None:
        called_args["directory"] = directory

    monkeypatch.setattr(historia._cli, "_minify", _fake_minify)
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia.historia_cli,
        ["data", "minify", "--directory", str(tmp_path)],
    )

    assert result.exit_code == 0
    assert called_args["directory"] == tmp_path


@pytest.mark.ai_generated
@pytest.mark.parametrize(("command", "expected_present"), [("github", True), ("minify", False)])
def test_data_update_help_commands(command: str, expected_present: bool) -> None:
    runner = click.testing.CliRunner()

    result = runner.invoke(historia.historia_cli, ["data", "update", "--help"])

    assert result.exit_code == 0
    assert (command in result.output) is expected_present


@pytest.mark.ai_generated
def test_project_create_command_invokes_create(monkeypatch: pytest.MonkeyPatch) -> None:
    called_args: dict[str, str] = {}

    def _fake_create(owner: str, title: str) -> dict[str, str]:
        called_args["owner"] = owner
        called_args["title"] = title
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
    assert "Project created successfully!" in result.output


@pytest.mark.ai_generated
def test_project_create_command_shows_failure_message_when_none_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_create(owner: str, title: str) -> None:
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
    monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path
) -> None:
    called_args: dict[str, pathlib.Path | str | int | None] = {}

    def _fake_add_to_project(
        directory: pathlib.Path, project_url: str, status: str | None, end_date_placeholder_days: int
    ) -> None:
        called_args["directory"] = directory
        called_args["project_url"] = project_url
        called_args["status"] = status
        called_args["end_date_placeholder_days"] = end_date_placeholder_days

    monkeypatch.setattr(historia._cli, "add_to_project", _fake_add_to_project)
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
        ],
    )

    assert result.exit_code == 0
    assert called_args["directory"] == tmp_path
    assert called_args["project_url"] == "https://github.com/users/octocat/projects/1"
    assert called_args["status"] == "In Progress"
    assert called_args["end_date_placeholder_days"] == 90


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
def test_project_transition_command_invokes_transition_status(monkeypatch: pytest.MonkeyPatch) -> None:
    called_args: dict[str, str] = {}

    def _fake_transition_status(project_url: str, current_status: str, new_status: str) -> None:
        called_args["project_url"] = project_url
        called_args["current_status"] = current_status
        called_args["new_status"] = new_status

    monkeypatch.setattr(historia._cli, "transition_status", _fake_transition_status)
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
    ],
)
def test_project_command_shows_error_on_exception(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    exception_type: type[Exception],
    attr_name: str,
    make_cli_args: Callable[[pathlib.Path], list[str]],
) -> None:
    def _fake(*args: object, **kwargs: object) -> None:
        raise exception_type("something went wrong")

    monkeypatch.setattr(historia._cli, attr_name, _fake)
    runner = click.testing.CliRunner()

    result = runner.invoke(historia.historia_cli, make_cli_args(tmp_path))

    assert result.exit_code == 1
    assert "something went wrong" in result.output


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("command", "expected_flags", "removed_flags"),
    [
        (
            "populate",
            ["--url", "--placeholder"],
            ["--project-url", "--projecturl", "--end-date-placeholder-days", "--enddateplaceholderdays"],
        ),
        (
            "update dates",
            ["--url", "--placeholder"],
            ["--project-url", "--projecturl", "--end-date-placeholder-days", "--enddateplaceholderdays"],
        ),
        ("transition", ["--url", "--status", "--new"], ["--project-url", "--projecturl"]),
    ],
)
def test_project_command_flags_use_no_dash_format(
    command: str, expected_flags: list[str], removed_flags: list[str]
) -> None:
    runner = click.testing.CliRunner()

    result = runner.invoke(historia.historia_cli, ["project", *command.split(), "--help"])

    assert result.exit_code == 0
    for expected_flag in expected_flags:
        assert expected_flag in result.output
    for removed_flag in removed_flags:
        assert removed_flag not in result.output
