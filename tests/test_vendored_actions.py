import pathlib

import click.testing
import pytest
import yaml

import historia

_REPOSITORY_ROOT = pathlib.Path(__file__).parent.parent
_ACTION_DIRECTORY = _REPOSITORY_ROOT / "action"
_COMPOSITE_ACTION_PATH = _ACTION_DIRECTORY / "action.yml"
_ACTION_PATHS = sorted(_ACTION_DIRECTORY.glob("*/action.yml"))

# These assert on repository files rather than on anything the installed package carries, so they
# cannot run against a distribution that ships only `src/` and `tests/` (conda-forge, for one).
pytestmark = pytest.mark.skipif(
    not _ACTION_DIRECTORY.is_dir(),
    reason="`action/` is not present, so this is not a repository checkout",
)


def _composite_action() -> dict:
    return yaml.safe_load(_COMPOSITE_ACTION_PATH.read_text(encoding="utf-8"))


@pytest.mark.ai_generated
def test_vendored_actions_are_discovered() -> None:
    action_names = [path.parent.name for path in _ACTION_PATHS]

    assert action_names == ["project-populate", "project-update-dates", "update-github"]


@pytest.mark.ai_generated
@pytest.mark.parametrize("action_path", _ACTION_PATHS, ids=lambda path: path.parent.name)
def test_vendored_action_runs_the_newest_published_image(action_path: pathlib.Path) -> None:
    """
    The actions run whichever **Historia** a release last published, not the version they shipped beside.

    `runs.image` expands no expression, so a version here would have to be rewritten every release and
    would send readers to an image that does not exist until that release completes. `latest` is pushed
    by every release, so it is always resolvable.
    """
    action = yaml.safe_load(action_path.read_text(encoding="utf-8"))

    assert action["runs"]["image"] == "docker://ghcr.io/codycbakerphd/historia:latest"


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
def test_composite_action_reaches_its_siblings_by_major_tag() -> None:
    """
    The composite reaches its siblings by full reference, since `uses:` accepts no expressions.

    They move together, so the moving major tag is the reference that never needs rewriting. An exact
    version here would have to be bumped every release and would name a tag that does not exist yet.
    """
    steps = _composite_action()["runs"]["steps"]
    historia_refs = [step["uses"] for step in steps if step.get("uses", "").startswith("CodyCBakerPhD/")]

    expected = [
        f"CodyCBakerPhD/historia/action/{name}@v0"
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


@pytest.mark.ai_generated
def test_composite_action_pushes_with_the_workflow_token_only() -> None:
    """
    The personal token never pushes.

    The checkout persists its credential for every later `git push`, so handing it the workflow's own
    token is what keeps the personal token unable to write to any repository. The Historia steps are
    the only ones that receive the personal token.
    """
    action = _composite_action()
    steps = {step["name"]: step for step in action["runs"]["steps"]}

    assert [name for name in action["inputs"] if "token" in name] == ["token"]
    assert steps["Check out the data repository"]["with"]["token"] == "${{ github.token }}"  # noqa: S105
    for step in action["runs"]["steps"]:
        if step.get("uses", "").startswith("CodyCBakerPhD/"):
            assert step["with"]["token"] == "${{ inputs.token }}", step["name"]  # noqa: S105


@pytest.mark.ai_generated
@pytest.mark.parametrize("action_path", _ACTION_PATHS, ids=lambda path: path.parent.name)
def test_vendored_action_arguments_are_accepted_by_the_cli(action_path: pathlib.Path) -> None:
    """
    The actions run the newest image, so the CLI they call is a compatibility surface.

    An action tag stays usable forever while the image beneath it moves, which means renaming or
    dropping one of these options breaks published workflows. This fails before such a release, rather
    than after it.
    """
    arguments = yaml.safe_load(action_path.read_text(encoding="utf-8"))["runs"]["args"]
    command = [argument for argument in arguments if not argument.startswith(("-", "${{"))]
    command = command[: next((index for index, value in enumerate(arguments) if value.startswith("-")), len(command))]
    options = [argument for argument in arguments if argument.startswith("--")]

    result = click.testing.CliRunner().invoke(historia.historia_cli, [*command, "--help"])

    assert result.exit_code == 0, result.output
    for option in options:
        assert option in result.output, option
