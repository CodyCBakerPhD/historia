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
historia update github --directory ./history --username $PROJECT_OWNER --recency 3 --start 2026-02-09
```

```{code-block} python
:class: hidden
import pathlib

tutorial_text = pathlib.Path("docs/tutorial/index.md").read_text(encoding="utf-8")
target_cli_start_flag = "--start " + "2026-02-09"
assert tutorial_text.count(target_cli_start_flag) == 1
```

- `--directory` is the root directory where data files are stored.
- `--username` is the GitHub username whose activity to fetch.
- `--recency` is number of past days to fetch.
  - The two most recent days are always refreshed to account for late-arriving data.
- `--start` is an optional anchor date.
  - Use the `YYYY-MM-DD` string format, for example `2026-02-09`.
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
    start_date="2026-02-09",
)
```

```{code-block} python
:class: hidden
import pathlib

tutorial_text = pathlib.Path("docs/tutorial/index.md").read_text(encoding="utf-8")
target_python_start_date = 'start_date="' + "2026-02-09" + '"'
assert tutorial_text.count(target_python_start_date) == 1
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

- `--public` makes the project publicly visible. Projects are created private by default, since GitHub's project-creation API does not support setting visibility at creation time; passing this flag applies a follow-up mutation immediately after creation.
:::
:::{tab} Python API
```python
import historia

project = historia.project.create_project_page(
    owner=project_owner,
    title="Work History",
    public=False,
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
historia project populate --directory ./history --url $PROJECT_URL --yes
```

Optional flags:

- `--status [value]` will pin every item to a specific status instead of deriving it automatically.
- `--placeholder [days]` is a placeholder end date offset (in days from creation) for open items.
  - Defaults to `180` days.
- `--members` writes each item's custom `Members` text field using usernames from `username-*` folders.
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
historia project transition --url $PROJECT_URL --status Done --new History --yes
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

## Step 6: Automate with a CRON-based GitHub Action

The steps above can be wired together into a data repository with a scheduled [GitHub Actions](https://docs.github.com/en/actions) workflow that runs regularly, keeping content on its associated project board up to date without manual effort.

Steps 1, 3, and 4 all run from one action: it collects the activity data, populates the project board, and refreshes the board's date fields. Save this as `.github/workflows/update.yml` in the data repository:

```yaml
name: Update work history data

on:
  workflow_dispatch:
  schedule:
    - cron: "0 0 * * *"

jobs:
  Update:
    runs-on: ubuntu-latest

    steps:
      - uses: CodyCBakerPhD/historia/action@v0.10.14
        with:
          username: [user]
          project-url: [project url]
          recency: "2"
          token: ${{ secrets.GH_PAT }}
```

That needs three things in place beforehand:

- A dedicated repository (e.g., `work-history-data`) to host the collected JSON files.
- The project board from Step 2, whose URL becomes `project-url`. The action updates an existing board, it does not create one.
- A repository secret named `GH_PAT` holding a [GitHub personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) with `repo`, `project`, and `read:project` scopes. The action uses it to fetch activity, push commits, and update the project board.

The action checks out the data repository, fetches recent activity, commits and pushes the new content, updates the project board, and force-pushes a compressed archive to a `dist` branch. Pin the version to a published release, and see the [action reference](https://github.com/CodyCBakerPhD/historia/tree/main/action) for the optional inputs.

Step 5 is deliberately not included. Transitioning statuses is an occasional editorial decision rather than something to run on a schedule, so keep using `historia project transition` by hand when you want it.

The final output should appear similar to [`work-history-data`](https://github.com/CodyCBakerPhD/work-history-data).

:::{tip}
Want to see each underlying step spelled out, or run only part of the process? See the [manual setup instructions](manual-automation-setup.md).
:::
