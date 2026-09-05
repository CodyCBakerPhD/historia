---
orphan: true
---

# Manual setup: CRON-based GitHub Action

This page is the manual version of [Step 6 of the tutorial](index.md): configuring a scheduled GitHub Actions workflow that keeps a data repository and its associated project board up to date.

:::{tip}
Most people should just run `historia setup automation` instead. It creates the repository, the project board, the encrypted secret, and this exact workflow file for you. Use this page only if you want to do each part by hand, or want to understand what the wizard is doing under the hood.
:::

The example below assumes:

- A dedicated repository (e.g., `work-history-data`) hosts the collected JSON files on its `main` branch.
- A repository secret named `GH_PAT` holds a [GitHub personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens) with `repo`, `project`,  and `read:project` scopes.
  - These permissions are required to fetch activity, push commits, and update the project board.
- A GitHub Project board has already been created via Step 2; its URL is referenced as `[project url]` below.
- The runner is Linux. The workflow calls **Historia** through container actions, which GitHub only runs on Linux runners.

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
  PROJECT_URL: [project url]
  # Let these set themselves
  GITHUB_TOKEN: ${{ secrets.GH_PAT }}
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
          git fetch origin main
          git checkout -f main
          git reset --hard origin/main
          git clean -fd

      - name: Prepare repository from remote
        if: steps.repo-cache.outputs.cache-hit != 'true'
        run: git clone -b main "https://github.com/$REPO_FULL_NAME.git" "$REPO_DIR"

      - name: Configure git identity
        run: |
          git config --global user.name "github-actions[bot]"
          git config --global user.email "github-actions[bot]@users.noreply.github.com"

      - name: Run update
        uses: CodyCBakerPhD/historia/action/update-github@vx.y.z
        with:
          directory: ${{ env.REPO_DIR }}/history
          username: ${{ env.USERNAME }}
          recency: "2"
          token: ${{ env.GITHUB_TOKEN }}

      # Container actions run as root, so anything they write into the workspace is root-owned.
      # The git steps below run as the unprivileged runner user and need to modify those files.
      - name: Restore workspace ownership
        run: sudo chown -R "$(id -u):$(id -g)" "$REPO_DIR"

      - name: Upload new content
        working-directory: ${{ env.REPO_DIR }}
        run: |
          git add .
          git commit --message "update" || true  # || true in case of no changes
          git push https://x-access-token:${{ env.GITHUB_TOKEN }}@github.com/$REPO_FULL_NAME.git HEAD:main

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
        uses: CodyCBakerPhD/historia/action/project-populate@vx.y.z
        with:
          directory: ${{ env.REPO_DIR }}/history
          url: ${{ env.PROJECT_URL }}
          token: ${{ env.GITHUB_TOKEN }}

      - name: Update GitHub project dates
        uses: CodyCBakerPhD/historia/action/project-update-dates@vx.y.z
        with:
          url: ${{ env.PROJECT_URL }}
          token: ${{ env.GITHUB_TOKEN }}
```

Tips:

- Replace `x.y.z` in the three `uses:` lines with the **Historia** version you want to run. Each action tag pins the matching container image, so all three should name the same version.
- The `recency: "2"` input tells **Historia** to refresh just the last two days on each run.
- The compressed `content.tar.gz` archive can be distributed as a portable payload living on an ephemeral branch.
- Add additional `project-populate` steps with another `url:` after the final step to post the same data to multiple project boards.
- **Historia** runs from a pinned container image rather than a `pip install`, so the workflow never depends on the runner's Python. There is no interpreter to set up and no install cache to invalidate.
- Container actions run as root, which is why the `Restore workspace ownership` step exists. Without it the later `git` steps cannot modify files the update wrote.

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
