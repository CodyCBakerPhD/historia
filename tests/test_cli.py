import pathlib

import click.testing
import pytest

import historia


@pytest.mark.ai_generated
def test_root_cli_help_shows_nested_groups() -> None:
    runner = click.testing.CliRunner()

    result = runner.invoke(historia.historia_cli, ["--help"])

    assert result.exit_code == 0
    assert "data" in result.output
    assert "project" in result.output


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

    monkeypatch.setattr(historia._cli, "update", _fake_update)
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia._cli.historia_cli,
        ["data", "update", "--directory", str(tmp_path), "--username", "octocat", "--recency", "3"],
    )

    assert result.exit_code == 0
    assert called_args["directory"] == tmp_path
    assert called_args["username"] == "octocat"
    assert called_args["past_number_of_days"] == 3


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
        historia._cli.historia_cli,
        ["project", "create", "--owner", "octocat", "--title", "Work Board"],
    )

    assert result.exit_code == 0
    assert called_args["owner"] == "octocat"
    assert called_args["title"] == "Work Board"
    assert "Project created successfully!" in result.output


@pytest.mark.ai_generated
def test_project_update_dates_command_invokes_update_item_dates(monkeypatch: pytest.MonkeyPatch) -> None:
    called_args: dict[str, str | int] = {}

    def _fake_update_project_item_dates(project_url: str, end_date_placeholder_days: int) -> None:
        called_args["project_url"] = project_url
        called_args["end_date_placeholder_days"] = end_date_placeholder_days

    monkeypatch.setattr(historia._cli, "update_project_item_dates", _fake_update_project_item_dates)
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia._cli.historia_cli,
        [
            "project",
            "update",
            "dates",
            "--project-url",
            "https://github.com/users/octocat/projects/1",
            "--end-date-placeholder-days",
            "200",
        ],
    )

    assert result.exit_code == 0
    assert called_args["project_url"] == "https://github.com/users/octocat/projects/1"
    assert called_args["end_date_placeholder_days"] == 200
