# Tutorial

This tutorial walks you through a complete **Historia** workflow, from collecting raw GitHub activity data all the way to maintaining a live GitHub Project board.

## Prerequisites

To start, you will need a [GitHub personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) with `read:project` and `repo` scopes exported as the `GITHUB_TOKEN` environment variable:

```bash
export GITHUB_TOKEN="ghp_..."
```

---

## Step 1: Collect GitHub activity data

**Historia** fetches GitHub activity (such as pull requests and issues opened or assigned to a user) for a rolling window of days and saves the results as structured JSON files.

::::{tabs}
:::{tab} CLI
```bash
historia update github --directory ./history --username $PROJECT_OWNER --recency 3 --start 2026-05-10
```

- `--directory` is the root directory where data files are stored.
- `--username` is the GitHub username whose activity to fetch.
- `--recency` is number of past days to fetch.
  - The two most recent days are always refreshed to account for late-arriving data.
- `--start` is an optional anchor date.
  - It is included here to keep the tutorial on a fixed historical range. Omit it for a moving window anchored on today.
:::
:::{tab} Python API
```python
import pathlib
import historia

historia.github.update(
    directory=pathlib.Path("./history"),
    username=project_owner,
    past_number_of_days=3,
    start_date="2026-05-10",
)
```
:::
::::

After this step, `./history` will contain a versioned folder tree such as:

```
history/
└── version-0+5/
    └── username-[user]/
        └── year-2026/
            └── month-05/
                └── day-10/
                    ├── info-prs+opened_date-2026+05+10.json
                    ├── info-prs+assigned_date-2026+05+10.json
                    ├── info-issues+opened_date-2026+05+10.json
                    └── info-issues+assigned_date-2026+05+10.json
```

---

## Step 2: Create a GitHub Project board

**Historia** can create and manage a [GitHub Projects v2](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects) board that visualizes your collected activity.

::::{tabs}
:::{tab} CLI
```bash
historia project create --owner $PROJECT_OWNER --title "Work History"
```

The command prints the new project's numeric ID and URL on success:

```
Project created successfully!
ID: PVT_...
URL: https://github.com/users/[user]/projects/[project number]
```

Keep the URL as you will need it in the following steps.
:::
:::{tab} Python API
```python
import historia

project = historia.project.create_project_page(
    owner=project_owner,
    title="Work History",
)
print(project["url"])
```
:::
::::

---

## Step 3: Populate the project from collected data

Once data has been collected, populate the project board with the activity items.

::::{tabs}
:::{tab} CLI
```bash
historia project populate --directory ./history --url $PROJECT_URL
```

Optional flags:

- `--status [value]` will pin every item to a specific status instead of deriving it automatically.
- `--placeholder [days]` is a placeholder end date offset (in days from creation) for open items.
  - Defaults to `180` days.
:::
:::{tab} Python API
```python
import pathlib
import historia

historia.project.add_to_project(
    directory=pathlib.Path("./history"),
    project_url=project_url,
)
```
:::
::::

---

## Step 4: Keep date fields up to date

As items progress and are eventually closed, their recorded end dates should be refreshed to reflect the actual close dates.

::::{tabs}
:::{tab} CLI
```bash
historia project update dates --url $PROJECT_URL
```

Use `--placeholder [days]` to change the placeholder window for still-open items.
:::
:::{tab} Python API
```python
import historia

historia.project.update_project_item_dates(
    project_url=project_url,
)
```
:::
::::

---

## Step 5: Transition item statuses

Move groups of items from one project status to another.
For example, archive completed work by transitioning items from `Done` to `History`.

::::{tabs}
:::{tab} CLI
```bash
historia project transition --url $PROJECT_URL --status Done --new History
```

- `--status` — the current status of items to match.
- `--new` — the status to assign to those items.
:::
:::{tab} Python API
```python
import historia

historia.project.transition_status(
    project_url=project_url,
    current_status="Done",
    new_status="History",
)
```
:::
::::

---

## Step 6  (Optional): Automate with a CRON-based GitHub Action

The steps above can be wired together into a scheduled [GitHub Actions](https://docs.github.com/en/actions) workflow that runs on a CRON schedule (and on demand via `workflow_dispatch`), keeping a data repository and its associated project board up to date without manual intervention.

The example below assumes:

- A dedicated repository (e.g. `work-history-data`) hosts the collected JSON files on its `main` branch.
- A repository secret named `GH_PAT` holds a [GitHub personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) with `repo`, `project`,  and `read:project` scopes.
  - These permissions are required to fetch activity, push commits, and update the project board.
- A GitHub Project board has already been created via Step 2; its URL is referenced as `[project url]` below.

Save the file as `.github/workflows/update.yml` in the data repository:

```yaml
name: Update work history data

on:
  workflow_dispatch:
  schedule:
    - cron: "0 0 * * *"

env:
  # Set these
  USERNAME: [user]
  PROJECT_NUMBER: [project number]
  PYTHON_VERSION: "3.13"
  HISTORIA_SPEC: historia==x.y.z
  # Let these set themselves
  GITHUB_TOKEN: ${{ secrets.GH_PAT }}
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
        uses: actions/cache@v4
        with:
          path: ${{ env.REPO_DIR }}
          key: repo-${{ runner.os }}-${{ github.repository }}-${{ hashFiles('.github/workflows/update.yml') }}
          restore-keys: repo-${{ runner.os }}-${{ github.repository }}-

      - name: Prepare repository from cache
        if: steps.repo-cache.outputs.cache-hit == 'true'
        working-directory: ${{ env.REPO_DIR }}
        run: |
          git fetch origin main
          git checkout main
          git reset --hard origin/main
          git clean -fd

      - name: Prepare repository from remote
        if: steps.repo-cache.outputs.cache-hit != 'true'
        run: git clone -b main "https://github.com/$REPO_FULL_NAME.git" "$REPO_DIR"

      - name: Configure git identity
        run: |
          git config --global user.name "github-actions[bot]"
          git config --global user.email "github-actions[bot]@users.noreply.github.com"

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Restore pip cache
        id: pip-cache
        uses: actions/cache@v4
        with:
          path: |
            ~/.cache/pip
            ~/.local
          key: pip-${{ runner.os }}-py${{ env.PYTHON_VERSION }}-${{ hashFiles('.github/workflows/update.yml') }}
          restore-keys: pip-${{ runner.os }}-py${{ env.PYTHON_VERSION }}-

      - name: Install historia
        if: steps.pip-cache.outputs.cache-hit != 'true'
        run: python -m pip install --user "$HISTORIA_SPEC"

      - name: Add user-local bin to PATH
        run: echo "$HOME/.local/bin" >> "$GITHUB_PATH"

      - name: Run update
        run: historia data github update --directory ./work-history-data/history --username "$USERNAME" --recency 2

      - name: Upload new content
        working-directory: ${{ env.REPO_DIR }}
        run: |
          git add .
          git commit --message "update" || true  # || true in case of no changes
          git push https://x-access-token:${{ secrets.GH_PAT }}@github.com/$REPO_FULL_NAME.git HEAD:main

      - name: Create compressed content
        working-directory: ${{ env.REPO_DIR }}
        run: tar -czf content.tar.gz content/

      - name: Push archive to dist branch
        working-directory: ${{ env.REPO_DIR }}
        run: |
          git checkout --orphan dist
          git rm -rf --cached .
          git add content.tar.gz
          git commit -m "update dist archive [skip ci]"
          git push https://x-access-token:${{ secrets.GH_PAT }}@github.com/$REPO_FULL_NAME.git HEAD:dist

      - name: Push to GitHub project
        run: |
          OWNER_PROJECT_URL="https://github.com/$REPO_OWNER_TYPE/$REPO_OWNER/projects/$PROJECT_NUMBER"
          historia populate --directory ./work-history-data/history --project-url "$OWNER_PROJECT_URL"
          historia project update dates --url [project url]
```

Tips:

- The `--recency 2` flag tells **Historia** to refresh just the last two days on each run.
- The compressed `content.tar.gz` archive can be distributed as a portable payload living on an ephemeral branch.
- Add additional `historia project populate ... --url [other project url]` lines after the final step to post the same data to multiple project boards.
- The workflow leverages efficient caching at every layer, guaranteeing as few wasted action minutes as possible on each CRON cycle.

:::::{note}
**Compressed content download**

Direct downloads of compressed content can be efficiently distributed over the GitHub CDN using `curl`:

```bash
curl -fsSL https://raw.githubusercontent.com/[org or user name]/[repo name]/dist/content.tar.gz | tar -xz
```

Or via the Python standard library:

<!-- skip: next -->
```python
import io
import tarfile
import urllib.request

url = "https://raw.githubusercontent.com/[org or user name]/[repo name]/dist/content.tar.gz"
with urllib.request.urlopen(url=url) as response:
    with tarfile.open(fileobj=io.BytesIO(response.read()), mode="r:gz") as tar:
        tar.extractall(filter="data")
```
:::::
