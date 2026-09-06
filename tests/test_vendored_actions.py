import pathlib

import pytest
import tomllib
import yaml

_REPOSITORY_ROOT = pathlib.Path(__file__).parent.parent
_COMPOSITE_ACTION_PATH = _REPOSITORY_ROOT / "action" / "action.yml"
_ACTION_PATHS = sorted((_REPOSITORY_ROOT / "action").glob("*/action.yml"))


def _package_version() -> str:
    pyproject = tomllib.loads((_REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return pyproject["project"]["version"]


def _composite_action() -> dict:
    return yaml.safe_load(_COMPOSITE_ACTION_PATH.read_text(encoding="utf-8"))


@pytest.mark.ai_generated
def test_vendored_actions_are_discovered() -> None:
    action_names = [path.parent.name for path in _ACTION_PATHS]

    assert action_names == ["project-populate", "project-update-dates", "update-github"]


@pytest.mark.ai_generated
@pytest.mark.parametrize("action_path", _ACTION_PATHS, ids=lambda path: path.parent.name)
def test_vendored_action_pins_the_current_package_version(action_path: pathlib.Path) -> None:
    """
    The image tag must track the release that carries the action.

    Consumers reference `.../action/<name>@vX.Y.Z`, so the action file at tag `vX.Y.Z` has to pin the
    `X.Y.Z` image. Letting the two drift would silently run a different version than the one requested.
    """
    action = yaml.safe_load(action_path.read_text(encoding="utf-8"))

    assert action["runs"]["image"] == f"docker://ghcr.io/codycbakerphd/historia:{_package_version()}"


@pytest.mark.ai_generated
@pytest.mark.parametrize("action_path", _ACTION_PATHS, ids=lambda path: path.parent.name)
def test_vendored_action_passes_the_token_and_no_empty_arguments(action_path: pathlib.Path) -> None:
    action = yaml.safe_load(action_path.read_text(encoding="utf-8"))

    assert action["runs"]["using"] == "docker"
    # S105: an unevaluated Actions expression that forwards the input, not a credential.
    assert action["runs"]["env"]["GITHUB_TOKEN"] == "${{ inputs.token }}"  # noqa: S105
    # Docker actions pass every entry of `args` through as its own argv element, including empty
    # strings, which the CLI would reject. Every optional input therefore needs a default.
    for argument in action["runs"]["args"]:
        assert argument != ""
    for name, specification in action["inputs"].items():
        assert specification["required"] is True or "default" in specification, name


# ---------------------------------------------------------------------------
# The composite action a data repository actually calls
# ---------------------------------------------------------------------------


@pytest.mark.ai_generated
def test_composite_action_pins_the_current_package_version() -> None:
    """
    The composite reaches its siblings by full reference, since `uses:` accepts no expressions.

    A stale tag here would run last release's commands from inside this release's action, so the
    references have to move with the version exactly like the image tags do.
    """
    steps = _composite_action()["runs"]["steps"]
    historia_refs = [step["uses"] for step in steps if step.get("uses", "").startswith("CodyCBakerPhD/")]

    expected = [
        f"CodyCBakerPhD/historia/action/{name}@v{_package_version()}"
        for name in ("update-github", "project-populate", "project-update-dates")
    ]
    assert historia_refs == expected


@pytest.mark.ai_generated
def test_composite_action_needs_only_a_token_and_two_identifiers() -> None:
    """A data repository should be able to adopt this with three inputs and no other setup."""
    action = _composite_action()

    required = {name for name, spec in action["inputs"].items() if spec.get("required") is True}
    optional = {name for name, spec in action["inputs"].items() if spec.get("required") is not True}

    assert required == {"username", "project-url", "token"}
    for name in optional:
        assert "default" in action["inputs"][name], name


@pytest.mark.ai_generated
def test_composite_action_commits_only_after_reclaiming_root_owned_files() -> None:
    steps = _composite_action()["runs"]["steps"]
    step_names = [step["name"] for step in steps]

    assert step_names.index("Restore workspace ownership") == step_names.index("Update work history data") + 1
    assert step_names.index("Restore workspace ownership") < step_names.index("Commit and push new content")


@pytest.mark.ai_generated
def test_composite_action_pushes_the_archive_last() -> None:
    """The archive step leaves the checkout on an orphan branch, so nothing may run after it."""
    steps = _composite_action()["runs"]["steps"]

    assert steps[-1]["name"] == "Push the compressed archive"
    assert steps[-1]["if"] == "inputs.archive-branch != ''"


@pytest.mark.ai_generated
def test_composite_action_keeps_the_token_out_of_command_lines() -> None:
    """Interpolating the token into a `run:` body would place it in the command GitHub echoes."""
    for step in _composite_action()["runs"]["steps"]:
        assert "inputs.token" not in step.get("run", "")
