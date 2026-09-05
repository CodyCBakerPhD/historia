# Vendored GitHub Actions

Container actions that run **Historia** from a pinned image, so a workflow never has to install the package itself.

These exist for the scheduled workflow described in [Step 6 of the tutorial](https://historia.readthedocs.io/en/latest/tutorial/index.html), which `historia setup automation` generates. They are usable directly in any Linux workflow.

| Action | Command it runs |
| --- | --- |
| `action/update-github` | `historia update github` |
| `action/project-populate` | `historia project populate` |
| `action/project-update-dates` | `historia project update dates` |

## Usage

```yaml
- uses: CodyCBakerPhD/historia/action/update-github@v0.10.14
  with:
    directory: ./work-history-data/history
    username: octocat
    recency: "2"
    token: ${{ secrets.GH_PAT }}
```

Paths are relative to the workspace root, since GitHub mounts the workspace as the container's working directory. A step-level `working-directory:` has no effect on `uses:` steps.

## Versioning

Each action is tagged alongside the package and pins the container image built for that same release, so `@v0.10.14` runs `ghcr.io/codycbakerphd/historia:0.10.14`. Always reference a released tag. `@main` points at an image that has not been published yet.

The `action/` directory was introduced in `v0.10.14`; earlier tags do not contain it.

## Notes

- Linux runners only. This is a GitHub limitation on container actions.
- Container actions run as root, so files written into the workspace are root-owned. If later steps in the same job need to modify them, restore ownership first:

  ```yaml
  - run: sudo chown -R "$(id -u):$(id -g)" ./work-history-data
  ```

- Each action exposes the options the scheduled workflow uses. For anything else, run the image directly with `docker run --rm -v "$PWD:/github/workspace" -w /github/workspace ghcr.io/codycbakerphd/historia:0.10.14 ...`.
