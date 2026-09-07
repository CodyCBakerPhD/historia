import pathlib
import re
import shutil
import subprocess
import sys

import pytest

_REPOSITORY_ROOT = pathlib.Path(__file__).parent.parent
_SCRIPT_PATH = _REPOSITORY_ROOT / "scripts" / "sync_version_pins.py"
_ACTION_RELATIVE_PATHS = (
    pathlib.Path("action/action.yml"),
    pathlib.Path("action/project-populate/action.yml"),
    pathlib.Path("action/project-update-dates/action.yml"),
    pathlib.Path("action/update-github/action.yml"),
)
_DOCUMENTATION_RELATIVE_PATHS = (
    pathlib.Path("action/README.md"),
    pathlib.Path("docs/tutorial/index.md"),
)
_COPIED_RELATIVE_PATHS = (
    pathlib.Path("pyproject.toml"),
    pathlib.Path("scripts/sync_version_pins.py"),
    *_ACTION_RELATIVE_PATHS,
    *_DOCUMENTATION_RELATIVE_PATHS,
)
_PIN_PATTERN = re.compile(r"(?:@v|historia:)(\d+\.\d+\.\d+)")

# These assert on repository files rather than on anything the installed package carries, so they
# cannot run against a distribution that ships only `src/` and `tests/` (conda-forge, for one).
pytestmark = pytest.mark.skipif(
    not _SCRIPT_PATH.is_file(),
    reason="`scripts/` is not present, so this is not a repository checkout",
)


def _run_script(*, root: pathlib.Path, arguments: list[str]) -> subprocess.CompletedProcess:
    command = [sys.executable, str(root / "scripts" / "sync_version_pins.py"), *arguments]
    # S603: the arguments are this interpreter and a path built from the repository layout.
    return subprocess.run(command, capture_output=True, text=True, check=False)  # noqa: S603


def _copy_repository_files(destination: pathlib.Path, /) -> None:
    for relative_path in _COPIED_RELATIVE_PATHS:
        copied_path = destination / relative_path
        copied_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(_REPOSITORY_ROOT / relative_path, copied_path)


@pytest.mark.ai_generated
def test_repository_action_pins_match_the_package_version() -> None:
    """The action pins committed to the repository must already agree with `pyproject.toml`."""
    result = _run_script(root=_REPOSITORY_ROOT, arguments=["--check"])

    assert result.returncode == 0, result.stdout


@pytest.mark.ai_generated
@pytest.mark.parametrize("relative_path", _DOCUMENTATION_RELATIVE_PATHS, ids=str)
def test_documentation_never_advertises_an_unreleased_version(relative_path: pathlib.Path) -> None:
    """
    Readers follow the documentation off the default branch, long before the next release exists.

    The tutorial pinned the in-development version once, sending readers to a tag and a container image
    that had not been published, so the documentation may never run ahead of the newest release tag.
    """
    released_versions = {
        tag.removeprefix("v")
        for tag in subprocess.run(
            ["git", "tag", "--list", "v*"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
            cwd=_REPOSITORY_ROOT,
        ).stdout.split()
    }
    if not released_versions:
        pytest.skip("no release tags are available in this checkout")
    documented_versions = set(_PIN_PATTERN.findall((_REPOSITORY_ROOT / relative_path).read_text(encoding="utf-8")))

    assert documented_versions <= released_versions, sorted(documented_versions - released_versions)


@pytest.mark.ai_generated
def test_script_rewrites_every_action_pin_after_a_version_bump(tmp_path: pathlib.Path) -> None:
    _copy_repository_files(tmp_path)
    pyproject_path = tmp_path / "pyproject.toml"
    bumped_pyproject = re.sub(
        r'(?m)^version = "\d+\.\d+\.\d+"$',
        'version = "99.99.99"',
        pyproject_path.read_text(encoding="utf-8"),
    )
    pyproject_path.write_text(bumped_pyproject, encoding="utf-8")

    bump_result = _run_script(root=tmp_path, arguments=[])
    recheck_result = _run_script(root=tmp_path, arguments=["--check"])

    assert bump_result.returncode == 1, bump_result.stdout
    assert recheck_result.returncode == 0, recheck_result.stdout
    for relative_path in _ACTION_RELATIVE_PATHS:
        assert "99.99.99" in (tmp_path / relative_path).read_text(encoding="utf-8"), relative_path


@pytest.mark.ai_generated
def test_bumping_the_package_version_leaves_the_documentation_alone(tmp_path: pathlib.Path) -> None:
    """A version bump must not re-point readers at a release that has not happened yet."""
    _copy_repository_files(tmp_path)
    pyproject_path = tmp_path / "pyproject.toml"
    original_documentation = {
        relative_path: (tmp_path / relative_path).read_text(encoding="utf-8")
        for relative_path in _DOCUMENTATION_RELATIVE_PATHS
    }
    pyproject_path.write_text(
        re.sub(r'(?m)^version = "\d+\.\d+\.\d+"$', 'version = "99.99.99"', pyproject_path.read_text(encoding="utf-8")),
        encoding="utf-8",
    )

    _run_script(root=tmp_path, arguments=[])

    for relative_path, content in original_documentation.items():
        assert (tmp_path / relative_path).read_text(encoding="utf-8") == content, relative_path


@pytest.mark.ai_generated
def test_release_mode_rewrites_only_the_documentation(tmp_path: pathlib.Path) -> None:
    _copy_repository_files(tmp_path)
    original_actions = {
        relative_path: (tmp_path / relative_path).read_text(encoding="utf-8")
        for relative_path in _ACTION_RELATIVE_PATHS
    }

    result = _run_script(root=tmp_path, arguments=["--release", "1.2.3"])

    assert result.returncode == 0, result.stdout
    for relative_path in _DOCUMENTATION_RELATIVE_PATHS:
        assert "1.2.3" in (tmp_path / relative_path).read_text(encoding="utf-8"), relative_path
    for relative_path, content in original_actions.items():
        assert (tmp_path / relative_path).read_text(encoding="utf-8") == content, relative_path


@pytest.mark.ai_generated
def test_release_mode_rejects_a_malformed_version(tmp_path: pathlib.Path) -> None:
    _copy_repository_files(tmp_path)

    result = _run_script(root=tmp_path, arguments=["--release", "v1.2"])

    assert result.returncode == 2, result.stdout
