# GitHub Actions

Container actions that run **Historia** from a pinned image, so a workflow never has to install the package itself.

## The whole process in one step

`CodyCBakerPhD/historia/action` is a composite action that runs the entire scheduled update for a work history data repository:

```yaml
name: Update work history data

on:
  workflow_dispatch:
  schedule:
    - cron: "0 0 * * *"

jobs:
  Update:
    runs-on: ubuntu-latest
    permissions:
      contents: write

    steps:
      - uses: CodyCBakerPhD/historia/action@v0.10.16
        with:
          username: octocat
          project-url: https://github.com/users/octocat/projects/1
          token: ${{ secrets.GH_PAT }}
```

It checks out the data repository, fetches recent activity, commits and pushes the new content, populates the project board, refreshes the board's dates, and force-pushes a compressed archive to a `dist` branch.

| Input | Required | Default | Description |
| --- | --- | --- | --- |
| `username` | yes | | GitHub username whose activity is tracked. |
| `project-url` | yes | | URL of the GitHub Project v2 to keep up to date. |
| `token` | yes | | Classic personal access token with the `project` scope. See [Setup](#setup). |
| `recency` | no | `2` | Number of most recent days to fetch. |
| `directory` | no | `history` | Directory in the repository holding the JSON files. |
| `placeholder` | no | `180` | Days after creation to use as a placeholder end date for open items. |
| `archive-branch` | no | `dist` | Orphan branch for the `content.tar.gz` archive. Empty string skips it. |
| `commit-message` | no | `update` | Message for each run's commit. |

## Setup

The action needs one personal access token, plus the workflow's own `GITHUB_TOKEN` for the pushes.

1. Create a [classic personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-personal-access-token-classic) with the `project` scope. Add the `repo` scope only if any repository you track is private. It must be a classic token because GitHub offers no fine-grained permission for Projects, and `repo` is the only classic scope that reads private repositories.
2. In the data repository, open Settings, then Secrets and variables, then Actions, and add a repository secret named `GH_PAT` holding that token.
3. Give the job `permissions: contents: write`, as in the example above. The checkout and every push use the workflow's own `GITHUB_TOKEN`, which is limited to the data repository. The personal token never pushes anywhere.

Unless you track private repositories, the personal token cannot write to any repository. The `workflow` scope is only needed by the deprecated `historia setup automation` wizard.

## The individual steps

The composite is built from three narrower actions, each wrapping one command. Use them directly to run only part of the process, or to insert steps of your own in between. The [expanded workflow](https://historia.readthedocs.io/en/latest/tutorial/manual-automation-setup.html) shows them wired together.

| Action | Command it runs |
| --- | --- |
| `action/update-github` | `historia update github` |
| `action/project-populate` | `historia project populate` |
| `action/project-update-dates` | `historia project update dates` |

```yaml
- uses: CodyCBakerPhD/historia/action/update-github@v0.10.16
  with:
    directory: history
    username: octocat
    recency: "2"
    token: ${{ secrets.GH_PAT }}
```

Paths are relative to the workspace root, since GitHub mounts the workspace as the container's working directory. A step-level `working-directory:` has no effect on `uses:` steps.

## Versioning

Every action is tagged alongside the package and pins the container image built for that same release, so `@v0.10.16` runs `ghcr.io/codycbakerphd/historia:0.10.16`. Always reference a released tag. `@main` points at an image that has not been published yet.

The `action/` directory was introduced in `v0.10.14`; earlier tags do not contain it.

## Notes

- Linux runners only. This is a GitHub limitation on container actions.
- Container actions run as root, so files written into the workspace are root-owned. The composite reclaims them before committing. If you use the individual actions, restore ownership yourself before any step that needs to modify those files:

  ```yaml
  - run: sudo chown -R "$(id -u):$(id -g)" .
  ```

- Each action exposes the options the scheduled workflow uses. For anything else, run the image directly with `docker run --rm -v "$PWD:/github/workspace" -w /github/workspace ghcr.io/codycbakerphd/historia:0.10.16 ...`.
