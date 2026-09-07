"""
Synchronize the hard-coded version pins that cannot interpolate the version they need.

GitHub Actions expands no `${{ }}` expression in a container action's `runs.image` or in a composite
action's `uses:`, so each release has to carry the literal string. There are two kinds of pin, and they
do not track the same version.

The action files are only ever read at a release tag, so they pin `project.version` from `pyproject.toml`,
which is the version the next release will carry. Running with no arguments synchronizes them, and
`--check` reports drift without writing.

The documentation is read from the default branch as soon as a pull request merges, so it must name the
latest published release instead. Advertising the in-development version sends readers to a tag and a
container image that do not exist yet. `--release X.Y.Z` rewrites those pins, and the release workflow
runs it once the image for that version is on GHCR.
"""

import argparse
import pathlib
import re
import sys

import tomllib

_REPOSITORY_ROOT = pathlib.Path(__file__).parent.parent
_PYPROJECT_PATH = _REPOSITORY_ROOT / "pyproject.toml"

_ACTION_PATHS = (
    _REPOSITORY_ROOT / "action" / "action.yml",
    _REPOSITORY_ROOT / "action" / "project-populate" / "action.yml",
    _REPOSITORY_ROOT / "action" / "project-update-dates" / "action.yml",
    _REPOSITORY_ROOT / "action" / "update-github" / "action.yml",
)
_DOCUMENTATION_PATHS = (
    _REPOSITORY_ROOT / "action" / "README.md",
    _REPOSITORY_ROOT / "docs" / "tutorial" / "index.md",
)

_IMAGE_PIN_PATTERN = re.compile(r"(?<=ghcr\.io/codycbakerphd/historia:)\d+\.\d+\.\d+")
_ACTION_PIN_PATTERN = re.compile(r"(?<=CodyCBakerPhD/historia/action)((?:/[a-z-]+)?)@v\d+\.\d+\.\d+")
# Prose in the action README quotes the tag on its own, without the repository path in front of it.
_QUOTED_TAG_PATTERN = re.compile(r"(?<=`@v)\d+\.\d+\.\d+(?=`)")
_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+$")


def _read_package_version() -> str:
    pyproject = tomllib.loads(_PYPROJECT_PATH.read_text(encoding="utf-8"))
    return pyproject["project"]["version"]


def _pin_version(*, paths: tuple[pathlib.Path, ...], version: str, write: bool) -> list[pathlib.Path]:
    """Return the paths whose pins do not match `version`, rewriting them unless `write` is false."""
    outdated_paths = []
    for path in paths:
        content = path.read_text(encoding="utf-8")
        pinned_content = _IMAGE_PIN_PATTERN.sub(version, content)
        pinned_content = _ACTION_PIN_PATTERN.sub(rf"\g<1>@v{version}", pinned_content)
        pinned_content = _QUOTED_TAG_PATTERN.sub(version, pinned_content)
        if pinned_content == content:
            continue
        outdated_paths.append(path)
        if write:
            path.write_text(pinned_content, encoding="utf-8")
    return outdated_paths


def _main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Report outdated action pins without rewriting them.")
    parser.add_argument(
        "--release",
        metavar="X.Y.Z",
        default=None,
        help="Rewrite the documentation pins to this published release instead of syncing the action pins.",
    )
    arguments = parser.parse_args()

    if arguments.release is not None:
        if not _VERSION_PATTERN.match(arguments.release):
            print(f"`--release` expects a version of the form X.Y.Z, not {arguments.release!r}.")
            return 2
        updated_paths = _pin_version(paths=_DOCUMENTATION_PATHS, version=arguments.release, write=True)
        for path in updated_paths:
            print(f"Documented release {arguments.release} in {path.relative_to(_REPOSITORY_ROOT)}")
        return 0

    version = _read_package_version()
    outdated_paths = _pin_version(paths=_ACTION_PATHS, version=version, write=not arguments.check)
    if not outdated_paths:
        return 0

    action = "Outdated" if arguments.check else "Updated"
    for path in outdated_paths:
        print(f"{action} version pins in {path.relative_to(_REPOSITORY_ROOT)}")
    print(f"Action pins must match the `pyproject.toml` version {version}.")
    return 1


if __name__ == "__main__":
    sys.exit(_main())
