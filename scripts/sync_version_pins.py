"""
Synchronize every hard-coded version pin in the repository with `project.version` in `pyproject.toml`.

The vendored actions cannot interpolate the version. GitHub Actions expands no `${{ }}` expression in a
container action's `runs.image` or in a composite action's `uses:`, so each release tag has to carry the
literal string. This keeps those literals, and the documentation quoting them, from drifting.

Run with no arguments to rewrite the pins in place. Run with `--check` to report drift without writing.
"""

import argparse
import pathlib
import re
import sys

import tomllib

_REPOSITORY_ROOT = pathlib.Path(__file__).parent.parent
_PYPROJECT_PATH = _REPOSITORY_ROOT / "pyproject.toml"

_PINNED_PATHS = (
    _REPOSITORY_ROOT / "action" / "README.md",
    _REPOSITORY_ROOT / "action" / "action.yml",
    _REPOSITORY_ROOT / "action" / "project-populate" / "action.yml",
    _REPOSITORY_ROOT / "action" / "project-update-dates" / "action.yml",
    _REPOSITORY_ROOT / "action" / "update-github" / "action.yml",
    _REPOSITORY_ROOT / "docs" / "tutorial" / "index.md",
)

_IMAGE_PIN_PATTERN = re.compile(r"(?<=ghcr\.io/codycbakerphd/historia:)\d+\.\d+\.\d+")
_ACTION_PIN_PATTERN = re.compile(r"(?<=CodyCBakerPhD/historia/action)((?:/[a-z-]+)?)@v\d+\.\d+\.\d+")
# Prose in the action README quotes the tag on its own, without the repository path in front of it.
_QUOTED_TAG_PATTERN = re.compile(r"(?<=`@v)\d+\.\d+\.\d+(?=`)")


def read_package_version() -> str:
    pyproject = tomllib.loads(_PYPROJECT_PATH.read_text(encoding="utf-8"))
    version = pyproject["project"]["version"]
    return version


def synchronize_pins(*, version: str, write: bool) -> list[pathlib.Path]:
    """Return the paths whose pins do not match `version`, rewriting them unless `write` is false."""
    outdated_paths = []
    for path in _PINNED_PATHS:
        content = path.read_text(encoding="utf-8")
        synchronized_content = _IMAGE_PIN_PATTERN.sub(version, content)
        synchronized_content = _ACTION_PIN_PATTERN.sub(rf"\g<1>@v{version}", synchronized_content)
        synchronized_content = _QUOTED_TAG_PATTERN.sub(version, synchronized_content)
        if synchronized_content == content:
            continue
        outdated_paths.append(path)
        if write:
            path.write_text(synchronized_content, encoding="utf-8")
    return outdated_paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Report outdated pins without rewriting them.")
    arguments = parser.parse_args()

    version = read_package_version()
    outdated_paths = synchronize_pins(version=version, write=not arguments.check)
    if not outdated_paths:
        return 0

    action = "Outdated" if arguments.check else "Updated"
    for path in outdated_paths:
        print(f"{action} version pins in {path.relative_to(_REPOSITORY_ROOT)}")
    print(f"Pins must match the `pyproject.toml` version {version}.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
