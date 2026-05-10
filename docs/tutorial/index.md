# Tutorial

This tutorial walks you through a complete Historia workflow — from collecting raw GitHub activity data all the way to maintaining a live GitHub Project board.

## Prerequisites

You will also need a [GitHub personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) with at minimum `read:project` and `repo` scopes exported as the `GITHUB_TOKEN` environment variable:

```bash
export GITHUB_TOKEN="ghp_..."
```

---

## Step 1: Collect GitHub activity data

Historia fetches GitHub activity (pull requests and issues opened or assigned to a user) for a rolling window of days and saves the results as structured JSON files.

::::{tabs}
:::{tab} CLI
```bash
historia data update github --directory ./historia-data --username your-github-username --recency 3
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
    directory=pathlib.Path("./historia-data"),
    username="your-github-username",
    past_number_of_days=90,
)
```
:::
::::

After this step, `./historia-data` will contain a versioned folder tree such as:

```
historia-data/
└── version-0+5/
    └── username-your-github-username/
        └── request-graphql/
            └── year-2026/
                └── month-05/
                    └── day-10/
                        ├── info-prs+opened_date-2026+05+10.json
                        ├── info-prs+assigned_date-2026+05+10.json
                        ├── info-issues+opened_date-2026+05+10.json
                        └── info-issues+assigned_date-2026+05+10.json
```

---

## Step 2: Minify the data (optional)

Raw JSON responses can be large. The minify step strips whitespace to reduce storage footprint without losing any information.

::::{tabs}
:::{tab} CLI
Pass the innermost `request-graphql` directory:

```bash
historia data minify --directory ./historia-data/version-0+5/username-your-github-username/request-graphql
```
:::
:::{tab} Python API
```python
import pathlib
import historia

historia.data.minify(
    directory=pathlib.Path(
        "./historia-data/version-0+5/username-your-github-username/request-graphql"
    )
)
```
:::
::::

---

## Step 3: Create a GitHub Project board

Historia can create and manage a [GitHub Projects v2](https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/about-projects) board that visualises your collected activity.

::::{tabs}
:::{tab} CLI
```bash
historia project create --owner your-github-username --title "Work History"
```

The command prints the new project's numeric ID and URL on success:

```
Project created successfully!
ID: PVT_...
URL: https://github.com/users/your-github-username/projects/your-id
```

Keep the URL — you will need it in the following steps.
:::
:::{tab} Python API
```python
import historia

project = historia.project.create_project_page(
    owner="your-github-username",
    title="Work History",
)
print(project["url"])  # https://github.com/users/your-github-username/projects/your-id
```
:::
::::

---

## Step 4: Populate the project from collected data

Once data has been collected, populate the project board with the activity items.

::::{tabs}
:::{tab} CLI
```bash
historia project populate --directory ./historia-data/version-0+5 --url https://github.com/users/your-github-username/projects/your-id
```

Optional flags:

- `--status <value>` — pin every item to a specific status instead of deriving it automatically.
- `--placeholder <days>` — number of days after an item's creation date to use as a placeholder end date for open items (default: `180`).
:::
:::{tab} Python API
```python
import pathlib
import historia

historia.project.add_to_project(
    directory=pathlib.Path(
        "./historia-data/version-0+5/username-your-github-username/request-graphql"
    ),
    project_url="https://github.com/users/your-github-username/projects/your-id",
)
```
:::
::::

---

## Step 5: Keep date fields up to date

As items progress and are eventually closed, their recorded end dates should be refreshed to reflect the actual close dates.

::::{tabs}
:::{tab} CLI
```bash
historia project update dates --url https://github.com/users/your-github-username/projects/your-id
```

Use `--placeholder <days>` to change the placeholder window for still-open items.
:::
:::{tab} Python API
```python
import historia

historia.project.update_project_item_dates(
    project_url="https://github.com/users/your-github-username/projects/your-id",
)
```
:::
::::

---

## Step 6: Transition item statuses

Move groups of items from one project status to another — for example, archive completed work by transitioning items from `Done` to `History`.

::::{tabs}
:::{tab} CLI
```bash
historia project transition --url https://github.com/users/your-github-username/projects/your-id --status Done --new History
```

- `--status` — the current status of items to match.
- `--new` — the status to assign to those items.
:::
:::{tab} Python API
```python
import historia

historia.project.transition_status(
    project_url="https://github.com/users/your-github-username/projects/your-id",
    current_status="Done",
    new_status="History",
)
```
:::
::::

---

## Putting it all together

A complete weekly maintenance script might look like this:

```python
import pathlib
import historia

DATA_DIR = pathlib.Path("./historia-data")
USERNAME = "your-github-username"
PROJECT_URL = "https://github.com/users/your-github-username/projects/your-id"
GRAPHQL_DIR = DATA_DIR / "version-0+5" / f"username-{USERNAME}" / "request-graphql"

# 1. Refresh the last 90 days of activity
historia.data.github.update(directory=DATA_DIR, username=USERNAME, past_number_of_days=90)

# 2. Compact the raw files
historia.data.minify(directory=GRAPHQL_DIR)

# 3. Sync the project board
historia.project.add_to_project(directory=GRAPHQL_DIR, project_url=PROJECT_URL)

# 4. Refresh item date fields
historia.project.update_project_item_dates(project_url=PROJECT_URL)

# 5. Archive completed items
historia.project.transition_status(
    project_url=PROJECT_URL, current_status="Done", new_status="History"
)
```
