"""Sybil configuration for testing all code and CLI examples in the tutorial."""

import shlex
import unittest.mock
from typing import Any

import click.testing
import sybil
import sybil.parsers.myst

import historia

_TUTORIAL_GITHUB_OWNER = "CodyCBakerPhD"
_TUTORIAL_PROJECT_URL = "https://github.com/users/CodyCBakerPhD/projects/1"
_TUTORIAL_PROJECT_MOCK_RETURN: dict[str, str] = {
    "id": "PVT_tutorial_test_id",
    "url": _TUTORIAL_PROJECT_URL,
}

_cli_runner = click.testing.CliRunner()


def _bash_evaluator(example: sybil.Example) -> str | None:
    """
    Evaluate a bash code block by running all ``historia`` commands via Click's test runner.

    Lines that are not ``historia`` commands (such as ``export``, ``curl``, ``git``,
    or comments) are silently skipped so that illustrative shell snippets do not
    cause the test to fail.
    """
    for raw_line in str(example.parsed).strip().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("historia "):
            args = shlex.split(line[len("historia ") :])
            result = _cli_runner.invoke(historia.historia_cli, args)
            if result.exit_code != 0:
                return f"CLI command failed (exit code {result.exit_code}):\n{result.output}"
    return None


def _tutorial_setup(namespace: dict[str, Any]) -> None:
    """Patch all outbound historia API calls so no real network traffic occurs."""
    namespace["project_owner"] = _TUTORIAL_GITHUB_OWNER
    namespace["project_url"] = _TUTORIAL_PROJECT_URL
    patches = [
        unittest.mock.patch("historia.data.github.update"),
        unittest.mock.patch(
            "historia.project.create_project_page",
            return_value=_TUTORIAL_PROJECT_MOCK_RETURN,
        ),
        unittest.mock.patch(
            "historia._cli.create_project_page",
            return_value=_TUTORIAL_PROJECT_MOCK_RETURN,
        ),
        unittest.mock.patch("historia.project.add_to_project"),
        unittest.mock.patch("historia._cli.add_to_project"),
        unittest.mock.patch("historia.project.update_project_item_dates"),
        unittest.mock.patch("historia._cli.update_project_item_dates"),
        unittest.mock.patch("historia.project.transition_status"),
        unittest.mock.patch("historia._cli.transition_status"),
    ]
    for patcher in patches:
        patcher.start()
    namespace["_patchers"] = patches


def _tutorial_teardown(namespace: dict[str, Any]) -> None:
    """Stop all patches started in :func:`_tutorial_setup`."""
    for patcher in namespace.get("_patchers", []):
        patcher.stop()


pytest_collect_file = sybil.Sybil(
    parsers=[
        sybil.parsers.myst.PythonCodeBlockParser(),
        sybil.parsers.myst.CodeBlockParser("bash", evaluator=_bash_evaluator),
        sybil.parsers.myst.SkipParser(),
    ],
    pattern="*.md",
    setup=_tutorial_setup,
    teardown=_tutorial_teardown,
).pytest()
