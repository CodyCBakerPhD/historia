import pathlib

import click.testing
import pytest

import historia._cli


@pytest.mark.ai_generated
def test_root_cli_help_shows_nested_groups() -> None:
    runner = click.testing.CliRunner()

    result = runner.invoke(historia._cli._historia_cli, ["--help"])

    assert result.exit_code == 0
    assert "request" in result.output
    assert "project" in result.output


@pytest.mark.ai_generated
def test_request_update_command_invokes_update(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    called_args: dict[str, pathlib.Path | str | int] = {}

    def _fake_update(directory: pathlib.Path, username: str, past_number_of_days: int) -> None:
        called_args["directory"] = directory
        called_args["username"] = username
        called_args["past_number_of_days"] = past_number_of_days

    monkeypatch.setattr(historia._cli, "update", _fake_update)
    runner = click.testing.CliRunner()

    result = runner.invoke(
        historia._cli._historia_cli,
        ["request", "update", "--directory", str(tmp_path), "--username", "octocat", "--recency", "3"],
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
        historia._cli._historia_cli,
        ["project", "create", "--owner", "octocat", "--title", "Work Board"],
    )

    assert result.exit_code == 0
    assert called_args["owner"] == "octocat"
    assert called_args["title"] == "Work Board"
    assert "Project created successfully!" in result.output
