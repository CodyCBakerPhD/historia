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
      - uses: CodyCBakerPhD/historia/action@v0.10.15
        with:
          username: octocat
          project-url: https://github.com/users/octocat/projects/1
          token: ${{ secrets.GH_READ_TOKEN }}
          project-token: ${{ secrets.GH_PROJECT_TOKEN }}
          repository-token: ${{ github.token }}
```

It checks out the data repository, fetches recent activity, commits and pushes the new content, populates the project board, refreshes the board's dates, and force-pushes a compressed archive to a `dist` branch.

| Input | Required | Default | Description |
| --- | --- | --- | --- |
| `username` | yes | | GitHub username whose activity is tracked. |
| `project-url` | yes | | URL of the GitHub Project v2 to keep up to date. |
| `token` | yes | | Token that fetches the activity. Read-only is enough. See [Tokens](#tokens). |
| `project-token` | no | `token` | Token that updates the project board. |
| `repository-token` | no | `token` | Token that checks out and pushes to the data repository. |
| `recency` | no | `2` | Number of most recent days to fetch. |
| `directory` | no | `history` | Directory in the repository holding the JSON files. |
| `placeholder` | no | `180` | Days after creation to use as a placeholder end date for open items. |
| `archive-branch` | no | `dist` | Orphan branch for the `content.tar.gz` archive. Empty string skips it. |
| `commit-message` | no | `update` | Message for each run's commit. |

## Tokens

The process does three distinct things with GitHub, and each one gets its own token so that none of them holds more access than its step needs.

| Input | Step | Access it needs |
| --- | --- | --- |
| `token` | Fetch activity | Read issues and pull requests in the repositories to track. |
| `project-token` | Populate the board and refresh its dates | Write the project board. Read issues and pull requests, since adding an item resolves its URL and the dates step reads each item's creation and closing dates. |
| `repository-token` | Check out, commit, push | Write the contents of the data repository. Nothing else. |

The activity fetch is the step that handles the most untrusted input of the run, since it processes search results from every repository its token can see. With the split above, that step holds a token that cannot write anywhere, and no personal token can push to any repository at all.

**Fine-grained tokens.** Create two [fine-grained personal access tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/managing-your-personal-access-tokens#creating-a-fine-grained-personal-access-token) and store them as repository secrets on the data repository:

- `GH_READ_TOKEN`, for `token`. Repository access: the repositories to track. Repository permissions: `Issues` read-only, `Pull requests` read-only. Leave every account permission off.
- `GH_PROJECT_TOKEN`, for `project-token`. Account permissions: `Projects` read and write (for an organization board, the organization's `Projects` permission instead). Repository access and permissions: the same read-only `Issues` and `Pull requests` as above, so the board can resolve the items it holds.

Then pass `repository-token: ${{ github.token }}` and grant the job `permissions: contents: write`, as in the example above. The workflow's own token is scoped to the data repository, expires when the run ends, and cannot be used to push anywhere else. Pushes made with it also do not trigger other workflows, which is what a scheduled update wants.

Two things to know about fine-grained tokens:

- A fine-grained token belongs to one resource owner, either your account or a single organization. Private repositories under other owners are invisible to it, and their activity silently does not appear in the results. Public repositories are always readable. Track private activity across several organizations by running the `update-github` step once per token, or by falling back to a classic token for `token` only.
- Organizations have to allow fine-grained tokens before one can reach their private repositories. Check the organization's third-party access settings if a repository you expect is missing.

**One classic token.** `project-token` and `repository-token` both fall back to `token` when left empty, so a workflow that passes a single classic token with `repo` and `project` scopes keeps working exactly as before. That token can write to every repository it can see, though, which is what the split is for.

The `workflow` scope is not needed by the action. Only the deprecated `historia setup automation` wizard requires it, because it commits `.github/workflows/update.yml` through the Contents API, which GitHub gates behind that scope.

## The individual steps

The composite is built from three narrower actions, each wrapping one command. Use them directly to run only part of the process, or to insert steps of your own in between. The [expanded workflow](https://historia.readthedocs.io/en/latest/tutorial/manual-automation-setup.html) shows them wired together.

| Action | Command it runs |
| --- | --- |
| `action/update-github` | `historia update github` |
| `action/project-populate` | `historia project populate` |
| `action/project-update-dates` | `historia project update dates` |

```yaml
- uses: CodyCBakerPhD/historia/action/update-github@v0.10.15
  with:
    directory: history
    username: octocat
    recency: "2"
    token: ${{ secrets.GH_READ_TOKEN }}
```

Each of the three takes exactly one `token`, which is what makes the split in [Tokens](#tokens) possible: hand every step only the token for its job.

Paths are relative to the workspace root, since GitHub mounts the workspace as the container's working directory. A step-level `working-directory:` has no effect on `uses:` steps.

## Versioning

Every action is tagged alongside the package and pins the container image built for that same release, so `@v0.10.15` runs `ghcr.io/codycbakerphd/historia:0.10.15`. Always reference a released tag. `@main` points at an image that has not been published yet.

The `action/` directory was introduced in `v0.10.14`; earlier tags do not contain it.

## Notes

- Linux runners only. This is a GitHub limitation on container actions.
- Container actions run as root, so files written into the workspace are root-owned. The composite reclaims them before committing. If you use the individual actions, restore ownership yourself before any step that needs to modify those files:

  ```yaml
  - run: sudo chown -R "$(id -u):$(id -g)" .
  ```

- Each action exposes the options the scheduled workflow uses. For anything else, run the image directly with `docker run --rm -v "$PWD:/github/workspace" -w /github/workspace ghcr.io/codycbakerphd/historia:0.10.15 ...`.
