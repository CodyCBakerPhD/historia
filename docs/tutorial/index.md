# Tutorial

This tutorial walks you through a complete Historia workflow, from collecting raw GitHub activity data all the way to maintaining a live GitHub Project board.

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
historia data update github --directory ./history --username [user] --recency 3
```

- `--directory` — the root directory where data files are stored.
- `--username` — the GitHub username whose activity to fetch.
- `--recency` — number of past days to fetch (the two most recent days are always refreshed to account for late-arriving data).
:::
:::{tab} Python API
```python
import pathlib
import historia

historia.data.github.update(
    directory=pathlib.Path("./history"),
    username="[user]",
    past_number_of_days=90,
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

Historia can create and manage a [GitHub Projects v2](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects) board that visualises your collected activity.

::::{tabs}
:::{tab} CLI
```bash
historia project create --owner [org or user] --title "Work History"
```

The command prints the new project's numeric ID and URL on success:

```
Project created successfully!
ID: PVT_...
URL: https://github.com/users/[user]/projects/[project number]
```

Keep the URL — you will need it in the following steps.
:::
:::{tab} Python API
```python
import historia

project = historia.project.create_project_page(
    owner="[GitHub organization or username]",
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
historia project populate --directory ./history --url [project url]
```

Optional flags:

- `--status [value]` — pin every item to a specific status instead of deriving it automatically.
- `--placeholder [days]` — number of days after an item's creation date to use as a placeholder end date for open items (default: `180`).
:::
:::{tab} Python API
```python
import pathlib
import historia

historia.project.add_to_project(
    directory=pathlib.Path(
        "./history"
    ),
    project_url="[project url]",
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
historia project update dates --url [project url]
```

Use `--placeholder [days]` to change the placeholder window for still-open items.
:::
:::{tab} Python API
```python
import historia

historia.project.update_project_item_dates(
    project_url="[project url]",
)
```
:::
::::

---

## Step 5: Transition item statuses

Move groups of items from one project status to another — for example, archive completed work by transitioning items from `Done` to `History`.

::::{tabs}
:::{tab} CLI
```bash
historia project transition --url [project url] --status Done --new History
```

- `--status` — the current status of items to match.
- `--new` — the status to assign to those items.
:::
:::{tab} Python API
```python
import historia

historia.project.transition_status(
    project_url="[project url]",
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
- A repository secret named `GH_PAT` holds a [GitHub personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) with `read:project`, `project`, and `repo` scopes — enough to fetch activity, push commits, and update the project board.
- A GitHub Project board has already been created via Step 2; its URL is referenced as `[project url]` below.

Save the file as `.github/workflows/update.yml` in the data repository:

```yaml
name: Update work history data

on:
  schedule:
    - cron: "0 0 * * *"
  workflow_dispatch:

env:
  GITHUB_TOKEN: ${{ secrets.GH_PAT }}
  REPO_DIR: ${{ github.event.repository.name }}
  HISTORIA_SPEC: historia==0.7.1

jobs:
  Update:
    runs-on: ubuntu-latest

    steps:
      - name: Clone
        run: git clone -b main https://x-access-token:${{ secrets.GH_PAT }}@github.com/${{ github.repository_owner }}/$REPO_DIR.git

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: 3.13
          cache: pip
          cache-dependency-path: .github/workflows/update.yml

      - name: Configure git
        run: |
          git config --global user.name "github-actions[bot]"
          git config --global user.email "github-actions[bot]@users.noreply.github.com"

      - name: Install historia
        run: python -m pip install "$HISTORIA_SPEC"

      - name: Fetch new activity
        run: |
          cd $REPO_DIR
          historia data update github --directory ./history --username [user] --recency 2

      - name: Commit and push raw data
        run: |
          git -C $REPO_DIR add .
          git -C $REPO_DIR commit --message "update" || true  # || true in case of no changes
          git -C $REPO_DIR push

      - name: Push minified copy to the `min` branch
        run: |
          cd $REPO_DIR
          historia data minify --directory ./history/version-0+5/

          git push origin --delete min || true  # || true in case the branch doesn't exist yet
          git checkout -b min
          git add .
          git commit --message "update min" || true  # || true in case of no changes
          git push --set-upstream origin min

      - name: Update the project board
        run: |
          cd $REPO_DIR
          historia project populate --directory ./history --url [project url]
          historia project update dates --url [project url]
```

Tips:

- The `--recency 2` flag tells Historia to refresh just the last two days on each run.
- The minified copy is pushed to a separate `min` branch as an ephemeral snapshot for the smallest portable payload.
- Add additional `historia project populate ... --url [other project url]` lines after the final step to post the same data to multiple project boards.

:::::{note}
**Optional: data minification**

Raw JSON responses can be large.
The `historia data minify` step strips whitespace to reduce storage footprint without losing any information, and is what the workflow above uses to build the `min` branch.
It can also be run on its own:

::::{tabs}
:::{tab} CLI
Pass the username directory:

```bash
historia data minify --directory ./history
```
:::
:::{tab} Python API
```python
import pathlib
import historia

historia.data.minify(
    directory=pathlib.Path("./history/version-0+5/")
)
```
:::
::::

Once published to a `min` branch (as in the workflow above), the minified files can be downloaded directly from `raw.githubusercontent.com` using only the Python standard library:

```python
import gzip
import json
import urllib.request

url = "https://raw.githubusercontent.com/[user]/[repo]/refs/heads/min/data.min.json.gz"
with urllib.request.urlopen(url=url) as response:
    data = json.loads(gzip.decompress(response.read()))
```
:::::
