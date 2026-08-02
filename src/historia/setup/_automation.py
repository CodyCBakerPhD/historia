import base64
import os
import typing

import beartype
import nacl.encoding
import nacl.public
import requests

from ..project import create_project_page
from ..project._add_to_project import _parse_project_url

_GITHUB_API_URL = "https://api.github.com"

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
          key: repo-${{ runner.os }}-${{ github.repository }}-${{ hashFiles('.github/workflows/update.yml') }}
          restore-keys: repo-${{ runner.os }}-${{ github.repository }}-

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
        uses: actions/setup-python@v6
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Restore pip cache
        id: pip-cache
        uses: actions/cache@v5
        with:
          path: |
            ~/.cache/pip
            ~/.local
          key: pip-${{ runner.os }}-py${{ env.PYTHON_VERSION }}-${{ hashFiles('.github/workflows/update.yml') }}
          restore-keys: pip-${{ runner.os }}-py${{ env.PYTHON_VERSION }}-

      - name: Install historia
        if: steps.pip-cache.outputs.cache-hit != 'true'
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

    Returns
    -------
    dict[str, str]
        A dictionary with the `repository_url`, `repository_created` ("true"/"false"), `project_url`,
        and `workflow_url`.

    """
    if (project_title is None) == (project_url is None):
        message = "Exactly one of `project_title` or `project_url` must be provided."
        raise ValueError(message)

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
        project = create_project_page(owner=owner, title=project_title)
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
