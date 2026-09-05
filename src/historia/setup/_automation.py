import base64
import os
import re
import typing

import beartype
import nacl.encoding
import nacl.public
import packaging.specifiers
import packaging.version
import requests

from ..project import create_project_page
from ..project._add_to_project import _parse_project_url

_GITHUB_API_URL = "https://api.github.com"
_PYPI_PROJECT_URL = "https://pypi.org/pypi/{package_name}/json"
_PYPI_RELEASE_URL = "https://pypi.org/pypi/{package_name}/{version}/json"

# Commits made via the Contents API are attributed to the token owner by default; pin them to a
# bot identity instead so the wizard doesn't leave commits authored as the person who ran it.
_BOT_COMMITTER = {"name": "historia bot", "email": "historia-bot@users.noreply.github.com"}

_WORKFLOW_TEMPLATE = """\
name: Update work history data

on:
  workflow_dispatch:
  schedule:
    - cron: "{{CRON_SCHEDULE}}"

env:
  # Set these
  USERNAME: {{USERNAME}}
  PROJECT_NUMBER: {{PROJECT_NUMBER}}
  PYTHON_VERSION: "{{PYTHON_VERSION}}"
  HISTORIA_SPEC: {{HISTORIA_SPEC}}
  # Let these set themselves
  GITHUB_TOKEN: ${{ secrets.{{SECRET_NAME}} }}
  REPO_OWNER: ${{ github.repository_owner }}
  REPO_OWNER_TYPE: ${{ fromJSON('{"Organization":"orgs","User":"users"}')[github.event.repository.owner.type] }}
  REPO_DIR: ${{ github.event.repository.name }}
  REPO_FULL_NAME: ${{ github.repository }}

jobs:
  Update:
    runs-on: ubuntu-latest

    steps:
      - name: Restore repository cache
        id: repo-cache
        uses: actions/cache@v5
        with:
          path: ${{ env.REPO_DIR }}
          key: repo-${{ runner.os }}-${{ github.repository }}

      - name: Prepare repository from cache
        if: steps.repo-cache.outputs.cache-hit == 'true'
        working-directory: ${{ env.REPO_DIR }}
        run: |
          git fetch origin {{DEFAULT_BRANCH}}
          git checkout -f {{DEFAULT_BRANCH}}
          git reset --hard origin/{{DEFAULT_BRANCH}}
          git clean -fd

      - name: Prepare repository from remote
        if: steps.repo-cache.outputs.cache-hit != 'true'
        run: git clone -b {{DEFAULT_BRANCH}} "https://github.com/$REPO_FULL_NAME.git" "$REPO_DIR"

      - name: Configure git identity
        run: |
          git config --global user.name "github-actions[bot]"
          git config --global user.email "github-actions[bot]@users.noreply.github.com"

      - name: Setup Python
        id: setup-python
        uses: actions/setup-python@v6
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      # Only the wheel cache is persisted, never the installed tree (`~/.local`).
      # Console script shebangs embed the exact interpreter path, which the runner image
      # invalidates whenever it bumps the Python patch release.
      - name: Restore pip cache
        uses: actions/cache@v5
        with:
          path: ~/.cache/pip
          key: pip-${{ runner.os }}-py${{ steps.setup-python.outputs.python-version }}-${{ env.HISTORIA_SPEC }}
          restore-keys: pip-${{ runner.os }}-py${{ steps.setup-python.outputs.python-version }}-

      - name: Install historia
        run: |
          python -m pip install --upgrade pip
          python -m pip install --user "$HISTORIA_SPEC"

      - name: Add user-local bin to PATH
        run: echo "$HOME/.local/bin" >> "$GITHUB_PATH"

      - name: Run update
        working-directory: ${{ env.REPO_DIR }}
        run: historia update github --directory ./history --username "$USERNAME" --recency {{RECENCY_DAYS}}

      - name: Upload new content
        working-directory: ${{ env.REPO_DIR }}
        run: |
          git add .
          git commit --message "update" || true  # || true in case of no changes
          git push https://x-access-token:${{ env.GITHUB_TOKEN }}@github.com/$REPO_FULL_NAME.git HEAD:{{DEFAULT_BRANCH}}

      - name: Create compressed content
        working-directory: ${{ env.REPO_DIR }}
        run: tar -czf content.tar.gz ./history/

      - name: Push archive to dist branch
        working-directory: ${{ env.REPO_DIR }}
        run: |
          git branch -D dist || true
          git checkout --orphan dist
          git rm -rf --cached .
          git add content.tar.gz
          git commit -m "update dist archive [skip ci]"
          git push --force https://x-access-token:${{ env.GITHUB_TOKEN }}@github.com/$REPO_FULL_NAME.git HEAD:dist

      - name: Push to GitHub project
        working-directory: ${{ env.REPO_DIR }}
        run: |
          OWNER_PROJECT_URL="https://github.com/$REPO_OWNER_TYPE/$REPO_OWNER/projects/$PROJECT_NUMBER"
          historia project populate --directory ./history --url "$OWNER_PROJECT_URL" --yes
          historia project update dates --url "$OWNER_PROJECT_URL"
"""


@beartype.beartype
def provision_automation(  # noqa: PLR0913
    *,
    token: str,
    username: str,
    owner: str,
    repository_name: str,
    private: bool,
    secret_name: str,
    recency_days: int,
    python_version: str,
    historia_spec: str,
    cron_schedule: str,
    project_title: str | None = None,
    project_url: str | None = None,
    project_public: bool = False,
) -> dict[str, str]:
    """
    Provision the CRON-based GitHub Action described in Step 6 of the tutorial end to end.

    Creates (or reuses) the data repository, creates or reuses the GitHub Project board, commits
    the rendered `.github/workflows/update.yml`, and stores `token` as an encrypted repository secret.

    Parameters
    ----------
    token : str
        A GitHub personal access token with `repo`, `project`, `read:project`, and `workflow` scopes.
    username : str
        The GitHub username whose activity should be tracked.
    owner : str
        The GitHub user or organization login that will host the data repository and project board.
    repository_name : str
        The name of the data repository to create or reuse.
    private : bool
        Whether the data repository should be created as private (ignored if it already exists).
    secret_name : str
        Name of the repository secret that will hold `token`.
    recency_days : int
        Number of most recent days the scheduled workflow refreshes on each run.
    python_version : str
        Python version to use in the workflow.
    historia_spec : str
        Version specifier for the `historia` package to install in the workflow.
    cron_schedule : str
        CRON schedule for the scheduled run.
    project_title : str, optional
        Title for a new GitHub Project board. Exactly one of `project_title` or `project_url` must be given.
    project_url : str, optional
        URL of an existing GitHub Project board to reuse. Exactly one of `project_title` or `project_url`
        must be given.
    project_public : bool, default: False
        Whether a newly created project board (via `project_title`) should be publicly visible.
        Ignored when reusing an existing project via `project_url`.

    Returns
    -------
    dict[str, str]
        A dictionary with the `repository_url`, `repository_created` ("true"/"false"), `project_url`,
        and `workflow_url`.

    """
    if (project_title is None) == (project_url is None):
        message = "Exactly one of `project_title` or `project_url` must be provided."
        raise ValueError(message)

    historia_spec, requires_python, _ = _validate_historia_spec(historia_spec=historia_spec)
    _validate_python_version(python_version=python_version, requires_python=requires_python)
    cron_schedule = _resolve_cron_schedule(cron_schedule=cron_schedule)

    authenticated_username = _get_authenticated_username(token=token)
    os.environ["GITHUB_TOKEN"] = token

    repository = _create_data_repository(
        owner=owner,
        repository_name=repository_name,
        token=token,
        private=private,
        authenticated_username=authenticated_username,
    )

    if project_title is not None:
        project = create_project_page(owner=owner, title=project_title, public=project_public)
        if not project:
            message = "Project creation failed due to rate limiting. Please try again later."
            raise RuntimeError(message)
        resolved_project_url = project["url"]
    else:
        resolved_project_url = typing.cast("str", project_url)

    _, _, project_number = _parse_project_url(resolved_project_url)

    workflow_yaml = _render_workflow_yaml(
        username=username,
        project_number=project_number,
        python_version=python_version,
        historia_spec=historia_spec,
        secret_name=secret_name,
        cron_schedule=cron_schedule,
        recency_days=recency_days,
        default_branch=repository["default_branch"],
    )
    _upsert_workflow_file(
        owner=owner,
        repository_name=repository_name,
        branch=repository["default_branch"],
        token=token,
        content=workflow_yaml,
    )
    _upsert_repository_secret(
        owner=owner,
        repository_name=repository_name,
        secret_name=secret_name,
        secret_value=token,
        token=token,
    )

    return {
        "repository_url": repository["html_url"],
        "repository_created": repository["created"],
        "project_url": resolved_project_url,
        "workflow_url": f"{repository['html_url']}/actions/workflows/update.yml",
    }


@beartype.beartype
def _get_latest_pypi_version(*, package_name: str = "historia") -> str:
    """Return the latest version of `package_name` published on PyPI."""
    return _fetch_pypi_project_info(package_name=package_name)["info"]["version"]


def _fetch_pypi_project_info(*, package_name: str) -> dict:
    response = requests.get(url=_PYPI_PROJECT_URL.format(package_name=package_name), timeout=30)
    if response.status_code != 200:
        message = (
            f"\nCould not look up `{package_name}` on PyPI.\nStatus code {response.status_code}: {response.text}\n\n"
        )
        raise RuntimeError(message)
    return response.json()


def _fetch_pypi_release_info(*, package_name: str, version: str) -> dict:
    response = requests.get(url=_PYPI_RELEASE_URL.format(package_name=package_name, version=version), timeout=30)
    if response.status_code != 200:
        message = (
            f"\nCould not look up `{package_name}=={version}` on PyPI.\n"
            f"Status code {response.status_code}: {response.text}\n\n"
        )
        raise RuntimeError(message)
    return response.json()


_PYTHON_CLASSIFIER_PATTERN = re.compile(r"Programming Language :: Python :: (\d+\.\d+)$")


def _extract_supported_python_versions(*, classifiers: list[str]) -> list[str]:
    """Extract and sort the `X.Y` versions out of a release's `Programming Language :: Python :: X.Y` classifiers."""
    matches = (_PYTHON_CLASSIFIER_PATTERN.fullmatch(classifier) for classifier in classifiers)
    versions = {match.group(1) for match in matches if match is not None}
    return sorted(versions, key=lambda version: tuple(int(part) for part in version.split(".")))


def _validate_historia_spec(*, historia_spec: str) -> tuple[str, str | None, list[str]]:
    """
    Validate a `historia` version specifier against PyPI's published releases.

    Accepts either the full `historia==X.Y.Z` form or a bare `X.Y.Z` version (a common slip,
    since the prompt asks for "the version"), normalizing the latter to the full form. Specifiers
    that match neither shape (a range, extras, no pin, a different package name, ...) are left
    alone; validating those in general would require a real dependency resolver, which is out of
    scope here.

    Returns
    -------
    tuple[str, str | None, list[str]]
        The (possibly normalized) specifier, the resolved release's `Requires-Python` constraint
        (or `None` if the specifier couldn't be resolved to a single published version), and the
        list of Python versions the resolved release declares support for via its classifiers
        (empty if unresolved).

    """
    match = re.fullmatch(r"(?:historia==)?(\d[\w.\-+]*)", historia_spec.strip())
    if match is None:
        return historia_spec, None, []
    pinned_version = match.group(1)

    project_info = _fetch_pypi_project_info(package_name="historia")
    if pinned_version not in project_info["releases"]:
        message = (
            f"\n`{historia_spec}` is not a published release of `historia` on PyPI.\n"
            "This often happens when defaulting to a local development install that hasn't been "
            f"released yet. The latest published version is `{project_info['info']['version']}`.\n\n"
        )
        raise ValueError(message)

    if pinned_version == project_info["info"]["version"]:
        release_info = project_info
    else:
        release_info = _fetch_pypi_release_info(package_name="historia", version=pinned_version)

    supported_python_versions = _extract_supported_python_versions(
        classifiers=release_info["info"].get("classifiers") or [],
    )
    return f"historia=={pinned_version}", release_info["info"].get("requires_python"), supported_python_versions


def _validate_python_version(*, python_version: str, requires_python: str | None) -> None:
    """Validate `python_version` and, if known, check it against a `Requires-Python` constraint."""
    try:
        version = packaging.version.Version(python_version)
    except packaging.version.InvalidVersion as exception:
        message = f"\n`{python_version}` is not a valid Python version (expected e.g. `3.13`).\n\n"
        raise ValueError(message) from exception

    if requires_python is None:
        return

    if not packaging.specifiers.SpecifierSet(requires_python).contains(version):
        message = (
            f"\nPython {python_version} does not satisfy the pinned `historia` release's required "
            f"Python version (`{requires_python}`). Choose a Python version that satisfies this constraint.\n\n"
        )
        raise ValueError(message)


_CRON_SHORTHANDS = {
    "daily": "0 0 * * *",
    "weekly": "0 0 * * 0",
    "monthly": "0 0 1 * *",
}
_CRON_FIELD_BOUNDS = ((0, 59), (0, 23), (1, 31), (1, 12), (0, 6))
_CRON_FIELD_NAMES = ("minute", "hour", "day-of-month", "month", "day-of-week")


def _is_valid_cron_field(*, field: str, minimum: int, maximum: int) -> bool:
    for part in field.split(","):
        base, sep, step = part.partition("/")
        if sep and not (step.isdigit() and int(step) >= 1):
            return False
        if base == "*":
            continue
        start_str, has_range, end_str = base.partition("-")
        if not start_str.isdigit() or (has_range and not end_str.isdigit()):
            return False
        start = int(start_str)
        end = int(end_str) if has_range else start
        if not (minimum <= start <= end <= maximum):
            return False
    return True


def _validate_cron_expression(*, cron_expression: str) -> None:
    """Validate a 5-field CRON expression (minute hour day-of-month month day-of-week)."""
    fields = cron_expression.split()
    if len(fields) != len(_CRON_FIELD_BOUNDS):
        message = (
            f"\n`{cron_expression}` is not a valid CRON expression: expected 5 space-separated fields "
            f"(minute hour day-of-month month day-of-week), got {len(fields)}.\n\n"
        )
        raise ValueError(message)

    for field, (minimum, maximum), name in zip(fields, _CRON_FIELD_BOUNDS, _CRON_FIELD_NAMES, strict=True):
        if not _is_valid_cron_field(field=field, minimum=minimum, maximum=maximum):
            message = (
                f"\n`{field}` is not a valid {name} field in `{cron_expression}` "
                f"(expected `*`, a number, a range, a step, or a comma-separated list within {minimum}-{maximum}).\n\n"
            )
            raise ValueError(message)


def _resolve_cron_schedule(*, cron_schedule: str) -> str:
    """
    Resolve `cron_schedule` to a validated 5-field CRON expression.

    Accepts the shorthands `daily`, `weekly`, and `monthly` (case-insensitive), or a raw CRON
    expression, which is validated for well-formedness (not for how often GitHub will actually run it).
    """
    stripped = cron_schedule.strip()
    shorthand = _CRON_SHORTHANDS.get(stripped.lower())
    if shorthand is not None:
        return shorthand

    _validate_cron_expression(cron_expression=stripped)
    return stripped


@beartype.beartype
def _render_workflow_yaml(  # noqa: PLR0913
    *,
    username: str,
    project_number: int,
    python_version: str,
    historia_spec: str,
    secret_name: str,
    cron_schedule: str,
    recency_days: int,
    default_branch: str,
) -> str:
    """Render the `.github/workflows/update.yml` contents for the CRON-based automation described in Step 6."""
    replacements = {
        "{{USERNAME}}": username,
        "{{PROJECT_NUMBER}}": str(project_number),
        "{{PYTHON_VERSION}}": python_version,
        "{{HISTORIA_SPEC}}": historia_spec,
        "{{SECRET_NAME}}": secret_name,
        "{{CRON_SCHEDULE}}": cron_schedule,
        "{{RECENCY_DAYS}}": str(recency_days),
        "{{DEFAULT_BRANCH}}": default_branch,
    }
    rendered = _WORKFLOW_TEMPLATE
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)
    return rendered


@beartype.beartype
def _get_authenticated_username(*, token: str) -> str:
    """Resolve the login of the user that owns the provided GitHub personal access token."""
    response = requests.get(url=f"{_GITHUB_API_URL}/user", headers=_auth_headers(token=token), timeout=30)
    if response.status_code != 200:
        message = (
            f"\nCould not authenticate with the provided GitHub token.\n"
            f"Status code {response.status_code}: {response.json()}\n\n"
        )
        raise RuntimeError(message)
    return response.json()["login"]


@beartype.beartype
def _create_data_repository(
    *,
    owner: str,
    repository_name: str,
    token: str,
    private: bool,
    authenticated_username: str,
) -> dict[str, str]:
    """
    Create the GitHub repository that will host the collected data, reusing it if it already exists.

    Parameters
    ----------
    owner : str
        The GitHub user or organization login that should own the repository.
    repository_name : str
        The name of the repository to create (e.g. ``"work-history-data"``).
    token : str
        A GitHub personal access token with permission to create repositories for ``owner``.
    private : bool
        Whether the repository should be created as private.
    authenticated_username : str
        The login of the user that owns ``token``, used to decide between the user and organization
        repository-creation endpoints.

    Returns
    -------
    dict[str, str]
        A dictionary with the ``"full_name"``, ``"html_url"``, and ``"default_branch"`` of the repository.

    """
    headers = _auth_headers(token=token)

    existing = requests.get(url=f"{_GITHUB_API_URL}/repos/{owner}/{repository_name}", headers=headers, timeout=30)
    if existing.status_code == 200:
        info = existing.json()
        # GitHub silently redirects lookups of a renamed repository's old name to its current
        # one, so a 200 here doesn't guarantee `repository_name` still exists; only treat this
        # as a match (and thus safe to reuse) if the returned repo's name is exactly what we asked for.
        if info["name"].lower() == repository_name.lower():
            return {
                "full_name": info["full_name"],
                "html_url": info["html_url"],
                "default_branch": info["default_branch"],
                "created": "false",
            }

    payload = {"name": repository_name, "private": private, "auto_init": True}
    creation_url = (
        f"{_GITHUB_API_URL}/user/repos" if owner == authenticated_username else f"{_GITHUB_API_URL}/orgs/{owner}/repos"
    )
    response = requests.post(url=creation_url, headers=headers, json=payload, timeout=30)
    if response.status_code != 201:
        message = (
            f"\nFailed to create repository `{owner}/{repository_name}`.\n"
            f"Status code {response.status_code}: {response.json()}\n\n"
        )
        raise RuntimeError(message)

    info = response.json()
    return {
        "full_name": info["full_name"],
        "html_url": info["html_url"],
        "default_branch": info["default_branch"],
        "created": "true",
    }


@beartype.beartype
def _upsert_workflow_file(
    *,
    owner: str,
    repository_name: str,
    branch: str,
    token: str,
    content: str,
) -> None:
    """Create or update `.github/workflows/update.yml` in the data repository via the GitHub Contents API."""
    headers = _auth_headers(token=token)
    path = ".github/workflows/update.yml"
    url = f"{_GITHUB_API_URL}/repos/{owner}/{repository_name}/contents/{path}"

    existing = requests.get(url=url, headers=headers, params={"ref": branch}, timeout=30)
    payload = {
        "message": "Add automated update workflow (via `historia setup automation`)",
        "content": base64.b64encode(content.encode("utf-8")).decode("utf-8"),
        "branch": branch,
        "author": _BOT_COMMITTER,
        "committer": _BOT_COMMITTER,
    }
    if existing.status_code == 200:
        payload["sha"] = existing.json()["sha"]

    response = requests.put(url=url, headers=headers, json=payload, timeout=30)
    if response.status_code not in (200, 201):
        message = (
            f"\nFailed to write the workflow file to `{owner}/{repository_name}`.\n"
            f"Status code {response.status_code}: {response.json()}\n\n"
        )
        raise RuntimeError(message)


@beartype.beartype
def _upsert_repository_secret(
    *,
    owner: str,
    repository_name: str,
    secret_name: str,
    secret_value: str,
    token: str,
) -> None:
    """Encrypt and set (or overwrite) an Actions repository secret using the repository's public key."""
    headers = _auth_headers(token=token)
    key_response = requests.get(
        url=f"{_GITHUB_API_URL}/repos/{owner}/{repository_name}/actions/secrets/public-key",
        headers=headers,
        timeout=30,
    )
    if key_response.status_code != 200:
        message = (
            f"\nFailed to fetch the Actions public key for `{owner}/{repository_name}`.\n"
            f"Status code {key_response.status_code}: {key_response.json()}\n\n"
        )
        raise RuntimeError(message)
    key_info = key_response.json()

    public_key = nacl.public.PublicKey(key_info["key"].encode("utf-8"), nacl.encoding.Base64Encoder)
    sealed_box = nacl.public.SealedBox(public_key)
    encrypted_value = base64.b64encode(sealed_box.encrypt(secret_value.encode("utf-8"))).decode("utf-8")

    payload = {"encrypted_value": encrypted_value, "key_id": key_info["key_id"]}
    response = requests.put(
        url=f"{_GITHUB_API_URL}/repos/{owner}/{repository_name}/actions/secrets/{secret_name}",
        headers=headers,
        json=payload,
        timeout=30,
    )
    if response.status_code not in (201, 204):
        message = (
            f"\nFailed to set secret `{secret_name}` on `{owner}/{repository_name}`.\n"
            f"Status code {response.status_code}: {response.json()}\n\n"
        )
        raise RuntimeError(message)


def _auth_headers(*, token: str) -> dict[str, str]:
    return {"Authorization": f"token {token}", "Accept": "application/vnd.github+json"}
