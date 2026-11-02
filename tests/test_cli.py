import collections.abc
import importlib.metadata
import pathlib

import click.testing
import pytest
import requests

import historia
import historia._cli


@pytest.fixture(autouse=True)
def _outside_github_actions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the tests from writing to the step outputs of the CI run that executes them."""
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)


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
@pytest.mark.parametrize(
    ("extra_args", "expected_past_number_of_days", "expected_start_date"),
    [
        (["--recency", "3"], 3, None),
        (["--recency", "2", "--start", "2026-01-05"], 2, "2026-01-05"),
    ],
    ids=["recency", "start"],
)
def test_data_update_command_invokes_update(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    extra_args: list[str],
    expected_past_number_of_days: int,
    expected_start_date: str | None,
) -> None:
    called_args: dict[str, pathlib.Path | str | int | None] = {}

    def _fake_update(
        *,
        directory: pathlib.Path,
        username: str,
        past_number_of_days: int,
        start_date: str | None,
    ) -> bool:
        called_args["directory"] = directory
        called_args["username"] = username
        called_args["past_number_of_days"] = past_number_of_days
        called_args["start_date"] = start_date
        return False

    monkeypatch.setattr(historia._cli.data.github, "update", _fake_update)
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia.historia_cli,
        ["update", "github", "--directory", str(tmp_path), "--username", "octocat", *extra_args],
    )

    assert result.exit_code == 0
    assert called_args["directory"] == tmp_path
    assert called_args["username"] == "octocat"
    assert called_args["past_number_of_days"] == expected_past_number_of_days
    assert called_args["start_date"] == expected_start_date


@pytest.mark.ai_generated
@pytest.mark.parametrize(("command", "expected_present"), [("github", True), ("minify", False)])
def test_data_update_help_commands(command: str, expected_present: bool) -> None:
    runner = click.testing.CliRunner()

    result = runner.invoke(historia.historia_cli, ["update", "--help"])

    assert result.exit_code == 0
    assert (command in result.output) is expected_present


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("extra_args", "expected_public"),
    [([], False), (["--public"], True)],
    ids=["private", "public"],
)
def test_project_create_command_invokes_create(
    monkeypatch: pytest.MonkeyPatch,
    extra_args: list[str],
    expected_public: bool,
) -> None:
    called_args: dict[str, str | bool] = {}

    def _fake_create(*, owner: str, title: str, public: bool) -> dict[str, str]:
        called_args["owner"] = owner
        called_args["title"] = title
        called_args["public"] = public
        return {"id": "PVT_123", "url": "https://github.com/users/octocat/projects/1"}

    monkeypatch.setattr(historia._cli, "create_project_page", _fake_create)
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia.historia_cli,
        ["project", "create", "--owner", "octocat", "--title", "Work Board", *extra_args],
    )

    assert result.exit_code == 0
    assert called_args["owner"] == "octocat"
    assert called_args["title"] == "Work Board"
    assert called_args["public"] is expected_public
    assert "Project created successfully!" in result.output


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("hit_rate_limit", "expected_note"),
    [pytest.param(True, True, id="rate-limited"), pytest.param(False, False, id="not-rate-limited")],
)
def test_data_update_command_notes_a_rate_limit_and_still_succeeds(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    hit_rate_limit: bool,
    expected_note: bool,
) -> None:
    monkeypatch.setattr(historia._cli.data.github, "update", lambda **_kwargs: hit_rate_limit)
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia.historia_cli,
        ["update", "github", "--directory", str(tmp_path), "--username", "octocat", "--recency", "2"],
    )

    assert result.exit_code == 0
    assert ("rate limit was hit" in result.output) is expected_note


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("hit_rate_limit", "expected_output", "expected_annotation"),
    [
        pytest.param(True, "rate-limited=true\n", True, id="rate-limited"),
        pytest.param(False, "rate-limited=false\n", False, id="not-rate-limited"),
    ],
)
def test_data_update_command_reports_a_rate_limit_to_github_actions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    hit_rate_limit: bool,
    expected_output: str,
    expected_annotation: bool,
) -> None:
    """Inside GitHub Actions, the command sets a `rate-limited` step output and annotates a rate limit."""
    output_path = tmp_path / "github_output"
    output_path.write_text("earlier=value\n")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_path))
    monkeypatch.setattr(historia._cli.data.github, "update", lambda **_kwargs: hit_rate_limit)
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia.historia_cli,
        ["update", "github", "--directory", str(tmp_path), "--username", "octocat", "--recency", "2"],
    )

    assert result.exit_code == 0
    assert output_path.read_text() == "earlier=value\n" + expected_output
    assert ("::warning title=GitHub API rate limit::" in result.output) is expected_annotation


@pytest.mark.ai_generated
def test_data_update_command_sets_no_output_outside_github_actions(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    monkeypatch.setattr(historia._cli.data.github, "update", lambda **_kwargs: True)
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia.historia_cli,
        ["update", "github", "--directory", str(tmp_path), "--username", "octocat", "--recency", "2"],
    )

    assert result.exit_code == 0
    assert "rate limit was hit" in result.output
    assert "::warning" not in result.output
    assert list(tmp_path.iterdir()) == []


@pytest.mark.ai_generated
def test_data_update_command_reports_a_malformed_start_date(tmp_path: pathlib.Path) -> None:
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
            "1",
            "--start",
            "05/01/2026",
        ],
    )

    assert result.exit_code == 1
    assert "Invalid isoformat string: '05/01/2026'" in result.output
    assert not isinstance(result.exception, ValueError)


@pytest.mark.ai_generated
def test_project_populate_command_invokes_add_to_project(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    called_args: dict[str, pathlib.Path | str | int | bool | None] = {}

    def _fake_add_to_project(
        *,
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


def _populate_with_done_status_args(tmp_path: pathlib.Path, /) -> list[str]:
    return [
        "project",
        "populate",
        "--directory",
        str(tmp_path),
        "--url",
        "https://github.com/users/octocat/projects/1",
        "--status",
        "Done",
    ]


def _transition_to_done_args(_tmp_path: pathlib.Path, /) -> list[str]:
    return [
        "project",
        "transition",
        "--url",
        "https://github.com/users/octocat/projects/1",
        "--status",
        "In Progress",
        "--new",
        "Done",
    ]


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("attr_name", "make_cli_args", "expected_texts"),
    [
        (
            "add_to_project",
            _populate_with_done_status_args,
            ["Auto-close issue", "Warning", "specified status 'Done'"],
        ),
        ("transition_status", _transition_to_done_args, ["Auto-close issue", "Warning"]),
    ],
    ids=["populate", "transition"],
)
def test_project_command_warns_and_prompts_when_closing_workflows_exist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    attr_name: str,
    make_cli_args: collections.abc.Callable[[pathlib.Path], list[str]],
    expected_texts: list[str],
) -> None:
    called: list[bool] = []

    def _fake(**_kwargs: object) -> None:
        called.append(True)

    monkeypatch.setattr(historia._cli, attr_name, _fake)
    monkeypatch.setattr(
        historia._cli,
        "get_project_closing_workflows",
        lambda _url: ["Auto-close issue"],
    )
    runner = click.testing.CliRunner()

    result = runner.invoke(historia.historia_cli, make_cli_args(tmp_path), input="y\n")

    assert result.exit_code == 0
    assert called == [True]
    for expected_text in expected_texts:
        assert expected_text in result.output


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("attr_name", "make_cli_args"),
    [
        ("add_to_project", _populate_with_done_status_args),
        ("transition_status", _transition_to_done_args),
    ],
    ids=["populate", "transition"],
)
def test_project_command_aborts_when_closing_workflows_exist_and_user_declines(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    attr_name: str,
    make_cli_args: collections.abc.Callable[[pathlib.Path], list[str]],
) -> None:
    called: list[bool] = []

    def _fake(**_kwargs: object) -> None:
        called.append(True)

    monkeypatch.setattr(historia._cli, attr_name, _fake)
    monkeypatch.setattr(
        historia._cli,
        "get_project_closing_workflows",
        lambda _url: ["Auto-close issue"],
    )
    runner = click.testing.CliRunner()

    result = runner.invoke(historia.historia_cli, make_cli_args(tmp_path), input="n\n")

    assert result.exit_code == 0
    assert called == []


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("attr_name", "make_cli_args", "prompt_text"),
    [
        ("add_to_project", _populate_with_done_status_args, "Do you want to proceed with populating this project?"),
        ("transition_status", _transition_to_done_args, "Do you want to proceed"),
    ],
    ids=["populate", "transition"],
)
def test_project_command_auto_accepts_when_yes_flag_and_closing_workflows_exist(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    attr_name: str,
    make_cli_args: collections.abc.Callable[[pathlib.Path], list[str]],
    prompt_text: str,
) -> None:
    called: list[bool] = []

    def _fake(**_kwargs: object) -> None:
        called.append(True)

    monkeypatch.setattr(historia._cli, attr_name, _fake)
    monkeypatch.setattr(
        historia._cli,
        "get_project_closing_workflows",
        lambda _url: ["Auto-close issue"],
    )
    runner = click.testing.CliRunner()

    result = runner.invoke(historia.historia_cli, [*make_cli_args(tmp_path), "--yes"])

    assert result.exit_code == 0
    assert called == [True]
    assert "Warning" in result.output
    assert "Auto-close issue" in result.output
    assert prompt_text not in result.output


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("extra_args", "expected_end_date_placeholder_days", "expected_past_number_of_days"),
    [
        (["--placeholder", "200"], 200, None),
        (["--recency", "2"], 180, 2),
    ],
    ids=["placeholder", "recency"],
)
def test_project_update_dates_command_invokes_update_item_dates(
    monkeypatch: pytest.MonkeyPatch,
    extra_args: list[str],
    expected_end_date_placeholder_days: int,
    expected_past_number_of_days: int | None,
) -> None:
    called_args: dict[str, str | int | None] = {}

    def _fake_update_project_item_dates(
        *,
        project_url: str,
        end_date_placeholder_days: int,
        past_number_of_days: int | None,
    ) -> None:
        called_args["project_url"] = project_url
        called_args["end_date_placeholder_days"] = end_date_placeholder_days
        called_args["past_number_of_days"] = past_number_of_days

    monkeypatch.setattr(historia._cli, "update_project_item_dates", _fake_update_project_item_dates)
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia.historia_cli,
        ["project", "update", "dates", "--url", "https://github.com/users/octocat/projects/1", *extra_args],
    )

    assert result.exit_code == 0
    assert called_args["project_url"] == "https://github.com/users/octocat/projects/1"
    assert called_args["end_date_placeholder_days"] == expected_end_date_placeholder_days
    assert called_args["past_number_of_days"] == expected_past_number_of_days


@pytest.mark.ai_generated
def test_project_update_members_command_invokes_update_item_members(monkeypatch: pytest.MonkeyPatch) -> None:
    called_args: dict[str, str] = {}

    def _fake_update_project_item_members(*, project_url: str) -> None:
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

    def _fake_transition_status(*, project_url: str, current_status: str, new_status: str) -> None:
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
@pytest.mark.parametrize("exception_type", [ValueError, RuntimeError, requests.exceptions.ConnectionError])
@pytest.mark.parametrize(
    ("attr_name", "make_cli_args"),
    [
        (
            "data.github.update",
            lambda tmp_path: [
                "update",
                "github",
                "--directory",
                str(tmp_path),
                "--username",
                "octocat",
                "--recency",
                "1",
            ],
        ),
        (
            "create_project_page",
            lambda _: ["project", "create", "--owner", "octocat", "--title", "Work Board"],
        ),
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
def test_command_shows_error_on_exception(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    exception_type: type[Exception],
    attr_name: str,
    make_cli_args: collections.abc.Callable[[pathlib.Path], list[str]],
) -> None:
    def _fake(*_args: object, **_kwargs: object) -> None:
        error_message = "something went wrong"
        raise exception_type(error_message)

    monkeypatch.setattr(f"historia._cli.{attr_name}", _fake)
    if attr_name in {"add_to_project", "transition_status"}:
        monkeypatch.setattr(historia._cli, "get_project_closing_workflows", lambda _url: [])
    runner = click.testing.CliRunner()

    result = runner.invoke(historia.historia_cli, make_cli_args(tmp_path))

    assert result.exit_code == 1
    assert "something went wrong" in result.output
    assert isinstance(result.exception, SystemExit)


@pytest.mark.ai_generated
def test_removed_setup_automation_command_is_unknown() -> None:
    runner = click.testing.CliRunner()

    result = runner.invoke(historia.historia_cli, ["setup", "automation"])

    assert result.exit_code == 2
    assert "No such command 'setup'" in result.output


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


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "command",
    [
        ["update", "github"],
        ["project", "create"],
        ["project", "populate"],
        ["project", "update", "dates"],
        ["project", "update", "members"],
        ["project", "transition"],
    ],
)
def test_command_without_arguments_shows_help(command: list[str]) -> None:
    runner = click.testing.CliRunner()

    no_arguments_result = runner.invoke(historia.historia_cli, command)
    help_result = runner.invoke(historia.historia_cli, [*command, "--help"])

    assert "Missing option" not in no_arguments_result.output
    assert no_arguments_result.output == help_result.output
