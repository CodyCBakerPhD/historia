---
orphan: true
---

# Manual setup: the expanded workflow

[Step 6 of the tutorial](index.md) keeps a data repository up to date with a single `uses:` step by harnessing a vendored action.

This page expands that one step into the individual actions it runs, for anyone who wants to see exactly what happens, run only part of the process, or slot extra steps in between.

The example below assumes:

- A dedicated data repository (e.g., `work-history-data`) has been created to host the collected JSON files.
- A secret named `GH_PAT` has been set on that repository as described under [Setup](https://github.com/CodyCBakerPhD/historia/tree/main/action#setup) in the action reference. The pushes use the workflow's own `GITHUB_TOKEN`, granted `contents: write` below.
- A GitHub Project board has already been created via Step 2; its URL is referenced as `[project url]` below.

Save the file as `.github/workflows/update.yml` in the data repository:

```yaml
name: Update work history data

on:
  workflow_dispatch:
  schedule:
    - cron: "0 0 * * *"

env:
  USERNAME: [user]
  PROJECT_URL: [project url]

jobs:
  Update:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      # Without an explicit token, the checkout uses the workflow's own `GITHUB_TOKEN`.
      - name: Check out the data repository
        uses: actions/checkout@v7

      - name: Configure git identity
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"

      - name: Update work history data
        uses: CodyCBakerPhD/historia/action/update-github@vx.y.z
        with:
          directory: history
          username: ${{ env.USERNAME }}
          recency: "2"
          token: ${{ secrets.GH_PAT }}

      # Container actions run as root, so the files the update wrote are root-owned.
      # The git steps below run as the unprivileged runner user and need to modify them.
      - name: Restore workspace ownership
        run: sudo chown -R "$(id -u):$(id -g)" .

      - name: Commit and push new content
        run: |
          git add .
          git diff --quiet --cached || git commit --message "update"
          git push

      - name: Populate the GitHub project
        uses: CodyCBakerPhD/historia/action/project-populate@vx.y.z
        with:
          directory: history
          url: ${{ env.PROJECT_URL }}
          token: ${{ secrets.GH_PAT }}

      - name: Update GitHub project dates
        uses: CodyCBakerPhD/historia/action/project-update-dates@vx.y.z
        with:
          url: ${{ env.PROJECT_URL }}
          token: ${{ secrets.GH_PAT }}

      # Last, because it leaves the checkout on the orphan archive branch.
      - name: Push the compressed archive
        run: |
          tar -czf content.tar.gz history
          git branch -D dist || true
          git checkout --orphan dist
          git rm -rf --cached .
          git add content.tar.gz
          git commit --message "update dist archive [skip ci]"
          git push --force origin HEAD:dist
```

Tips:

- Replace `x.y.z` in the three `uses:` lines with the **Historia** version you want to run. Each action tag pins the matching container image, so all three should name the same version.
- The `recency: "2"` input tells **Historia** to refresh just the last two days on each run.
- The compressed `content.tar.gz` archive can be distributed as a portable payload living on an ephemeral branch.
- Add additional `project-populate` steps with another `url:` to post the same data to multiple project boards.
- **Historia** runs from a pinned container image rather than a `pip install`, so the workflow never depends on the runner's Python. There is no interpreter to set up and no install cache to invalidate.
- Drop any step you do not want. Collecting data without touching a project board, for instance, means keeping only the checkout, the update, the ownership fix, and the commit.

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

:::{tip}
**Get notified on failure**

This workflow runs unattended, so a broken run can silently stop refreshing your data for weeks before anyone notices. Add a job that only runs when `Update` fails and sends you a notification, for example via [dawidd6/action-send-mail](https://github.com/dawidd6/action-send-mail):

```yaml
  NotifyOnFailure:
    runs-on: ubuntu-latest
    needs: [ Update ]
    if: ${{ always() && failure() }}
    steps:
      - uses: dawidd6/action-send-mail@v18
        with:
          server_address: smtp.gmail.com
          server_port: 465
          username: ${{ secrets.MAIL_USERNAME }}
          password: ${{ secrets.MAIL_PASSWORD }}
          subject: "Work history data update failed"
          to: [your email]
          from: [repo name] <${{ secrets.MAIL_USERNAME }}>
          body: "Please check the latest run: https://github.com/[org or user name]/[repo name]/actions/workflows/update.yml"
```

This requires `MAIL_USERNAME` and `MAIL_PASSWORD` repository secrets (for Gmail, an [app password](https://support.google.com/accounts/answer/185833) works well) — swap in whatever SMTP provider or notification action you prefer.

If a failure looks like a bug in **Historia** itself rather than a one-off network hiccup, please [open an issue](https://github.com/CodyCBakerPhD/historia/issues) with the failed run's log output attached; that's usually enough to reproduce and fix it.
:::
