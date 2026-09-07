import pathlib
import re
import shutil
import subprocess
import sys

import pytest

_REPOSITORY_ROOT = pathlib.Path(__file__).parent.parent
_SCRIPT_PATH = _REPOSITORY_ROOT / "scripts" / "sync_version_pins.py"
_PINNED_RELATIVE_PATHS = (
    pathlib.Path("pyproject.toml"),
    pathlib.Path("action/README.md"),
    pathlib.Path("action/action.yml"),
    pathlib.Path("action/project-populate/action.yml"),
    pathlib.Path("action/project-update-dates/action.yml"),
    pathlib.Path("action/update-github/action.yml"),
    pathlib.Path("docs/tutorial/index.md"),
)

# These assert on repository files rather than on anything the installed package carries, so they
# cannot run against a distribution that ships only `src/` and `tests/` (conda-forge, for one).
pytestmark = pytest.mark.skipif(
    not _SCRIPT_PATH.is_file(),
    reason="`scripts/` is not present, so this is not a repository checkout",
)


def _run_script(*, root: pathlib.Path, check_only: bool) -> subprocess.CompletedProcess:
    arguments = [sys.executable, str(root / "scripts" / "sync_version_pins.py")]
    if check_only:
        arguments.append("--check")
    # S603: the arguments are this interpreter and a path built from the repository layout.
    return subprocess.run(arguments, capture_output=True, text=True, check=False)  # noqa: S603


@pytest.mark.ai_generated
def test_repository_pins_match_the_package_version() -> None:
    """The pins committed to the repository must already agree with `pyproject.toml`."""
    result = _run_script(root=_REPOSITORY_ROOT, check_only=True)

    assert result.returncode == 0, result.stdout


@pytest.mark.ai_generated
def test_script_rewrites_every_pin_after_a_version_bump(tmp_path: pathlib.Path) -> None:
    for relative_path in (*_PINNED_RELATIVE_PATHS, pathlib.Path("scripts/sync_version_pins.py")):
        destination = tmp_path / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(_REPOSITORY_ROOT / relative_path, destination)
    pyproject_path = tmp_path / "pyproject.toml"
    bumped_pyproject = re.sub(
        r'(?m)^version = "\d+\.\d+\.\d+"$',
        'version = "99.99.99"',
        pyproject_path.read_text(encoding="utf-8"),
    )
    pyproject_path.write_text(bumped_pyproject, encoding="utf-8")

    bump_result = _run_script(root=tmp_path, check_only=False)
    recheck_result = _run_script(root=tmp_path, check_only=True)

    assert bump_result.returncode == 1, bump_result.stdout
    assert recheck_result.returncode == 0, recheck_result.stdout
    for relative_path in _PINNED_RELATIVE_PATHS:
        assert "99.99.99" in (tmp_path / relative_path).read_text(encoding="utf-8"), relative_path
