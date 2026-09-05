import pathlib

import pytest
import tomllib
import yaml

_REPOSITORY_ROOT = pathlib.Path(__file__).parent.parent
_ACTION_PATHS = sorted((_REPOSITORY_ROOT / "action").glob("*/action.yml"))


def _package_version() -> str:
    pyproject = tomllib.loads((_REPOSITORY_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    return pyproject["project"]["version"]


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
