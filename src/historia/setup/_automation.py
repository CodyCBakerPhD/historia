import base64
import os
import re
import typing

import beartype
import nacl.encoding
import nacl.public
import packaging.version
import requests

from ..project import create_project_page
from ..project._add_to_project import _parse_project_url

_GITHUB_API_URL = "https://api.github.com"
_PYPI_PROJECT_URL = "https://pypi.org/pypi/{package_name}/json"

# The generated workflow calls Historia through the container actions under `action/`, which are
# tagged alongside the package and pin the image built for that same release.
_ACTION_REPOSITORY = "CodyCBakerPhD/historia"
_MINIMUM_ACTION_VERSION = "0.10.14"

# Commits made via the Contents API are attributed to the token owner by default; pin them to a
# bot identity instead so the wizard doesn't leave commits authored as the person who ran it.
_BOT_COMMITTER = {"name": "historia bot", "email": "historia-bot@users.noreply.github.com"}

_WORKFLOW_TEMPLATE = """\
name: Update work history data

on:
  workflow_dispatch:
  schedule:
    - cron: "{{CRON_SCHEDULE}}"

jobs:
  Update:
    runs-on: ubuntu-latest

    steps:
      - uses: {{ACTION_REPOSITORY}}/action@v{{HISTORIA_VERSION}}
        with:
          username: {{USERNAME}}
          project-url: {{PROJECT_URL}}
          recency: "{{RECENCY_DAYS}}"
          token: ${{ secrets.{{SECRET_NAME}} }}
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

    .. deprecated::
        The workflow this renders is now a single `uses:` step, short enough to add by hand, so
        Step 6 of the tutorial no longer documents this path. It will be removed in a future release.

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
    historia_spec : str
        Version specifier for the `historia` package the workflow's actions run.
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

    historia_spec = _validate_historia_spec(historia_spec=historia_spec)
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

    # Reject a malformed board URL here rather than letting the generated workflow fail on its first run.
    _parse_project_url(resolved_project_url)

    workflow_yaml = _render_workflow_yaml(
        username=username,
        project_url=resolved_project_url,
        historia_spec=historia_spec,
        secret_name=secret_name,
        cron_schedule=cron_schedule,
        recency_days=recency_days,
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


def _validate_historia_spec(*, historia_spec: str) -> str:
    """
    Validate a `historia` version specifier against PyPI's published releases.

    Accepts either the full `historia==X.Y.Z` form or a bare `X.Y.Z` version (a common slip,
    since the prompt asks for "the version"), normalizing the latter to the full form. Specifiers
    that match neither shape (a range, extras, no pin, a different package name, ...) are left
    alone; validating those in general would require a real dependency resolver, which is out of
    scope here.

    Returns
    -------
    str
        The (possibly normalized) specifier.

    """
    match = re.fullmatch(r"(?:historia==)?(\d[\w.\-+]*)", historia_spec.strip())
    if match is None:
        return historia_spec
    pinned_version = match.group(1)

    project_info = _fetch_pypi_project_info(package_name="historia")
    if pinned_version not in project_info["releases"]:
        message = (
            f"\n`{historia_spec}` is not a published release of `historia` on PyPI.\n"
            "This often happens when defaulting to a local development install that hasn't been "
            f"released yet. The latest published version is `{project_info['info']['version']}`.\n\n"
        )
        raise ValueError(message)

    return f"historia=={pinned_version}"


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
def _resolve_action_version(historia_spec: str, /) -> str:
    """
    Resolve the version tag of the vendored container actions the generated workflow should use.

    The actions live in this repository and are tagged alongside the package, so the workflow can only
    reference a version that both exists as a release tag and actually contains the `action/` directory.
    """
    match = re.fullmatch(r"historia==(\d[\w.\-+]*)", historia_spec.strip())
    if match is None:
        message = (
            f"\nThe generated workflow needs an exact version to pin its actions to, but `{historia_spec}` "
            "is not a pinned specifier.\nUse the `historia==X.Y.Z` form instead.\n\n"
        )
        raise ValueError(message)

    version = match.group(1)
    if packaging.version.Version(version) < packaging.version.Version(_MINIMUM_ACTION_VERSION):
        message = (
            f"\n`historia=={version}` predates the vendored workflow actions, which were introduced in "
            f"`historia=={_MINIMUM_ACTION_VERSION}`.\nPin `{_MINIMUM_ACTION_VERSION}` or newer.\n\n"
        )
        raise ValueError(message)
    return version


@beartype.beartype
def _render_workflow_yaml(  # noqa: PLR0913
    *,
    username: str,
    project_url: str,
    historia_spec: str,
    secret_name: str,
    cron_schedule: str,
    recency_days: int,
) -> str:
    """Render the `.github/workflows/update.yml` contents for the CRON-based automation described in Step 6."""
    replacements = {
        "{{USERNAME}}": username,
        "{{PROJECT_URL}}": project_url,
        "{{ACTION_REPOSITORY}}": _ACTION_REPOSITORY,
        "{{HISTORIA_VERSION}}": _resolve_action_version(historia_spec),
        "{{SECRET_NAME}}": secret_name,
        "{{CRON_SCHEDULE}}": cron_schedule,
        "{{RECENCY_DAYS}}": str(recency_days),
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
