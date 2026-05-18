# Changelog

## Upcoming

### 🐛 Bug Fix

- Fixed `containers/Dockerfile.latest` which was installing `nwb2bids` instead of `historia`, causing the Docker release to fail with "executable file not found in $PATH". ([#136](https://github.com/CodyCBakerPhD/historia/pull/136))



## v0.10.5

### 🚀 Enhancement

- Added optional member-assignment mode to project population via `--members` and `historia.project.add_to_project(..., assign_members=True)`. In this mode, new items get a `Members` field value inferred from `username-*` folders and existing project items merge in additional usernames as a deduplicated comma-separated list. ([#117](https://github.com/CodyCBakerPhD/historia/pull/117))
- Added `historia project update members` and `historia.project.update_project_item_members(project_url=...)` to backfill each project's `Members` field from issue assignees and pull-request assignees/reviewers. ([#118](https://github.com/CodyCBakerPhD/historia/pull/118))

### 🐛 Bug Fix

- Prevented the PyPI release workflow from publishing twice when a GitHub Release is created. Publishing a release pushes its tag, which was firing both the `push: tags` and `release: published` triggers simultaneously. Added an `if: github.event_name == 'release'` guard on the publish job so it only runs on the release event, while keeping both triggers for future compatibility. ([#116](https://github.com/CodyCBakerPhD/historia/pull/116))
- Updated `historia project populate` / `historia.project.add_to_project` to detect incompatible mixed `version-*` data directories, warn, and use only the latest version directory during population. ([#134](https://github.com/CodyCBakerPhD/historia/pull/134))

### 🏠 Internal

- Added a regression test that verifies `dump_specific_info` writes to only the active `version-*` cache layout and does not clobber same-day files in other cache layout versions. ([#134](https://github.com/CodyCBakerPhD/historia/pull/134))



## v0.10.2

### 🚀 Enhancement

- Added runtime input type checking to all public API functions via the `beartype` decorator. The covered functions are `historia.github.fetch_info_for_date`, `dump_specific_info`, `dump_info_for_date`, `update`, and `historia.project.add_to_project`, `transition_status`, `update_project_item_dates`, `create_project_page`. Passing arguments of the wrong type now raises a clear `BeartypeCallHintParamViolation` instead of failing later with a confusing error. For example, passing a `str` for a `pathlib.Path` parameter, or a `str` for an `int` parameter, is now caught at the call site. `beartype` is now a runtime dependency. ([#97](https://github.com/CodyCBakerPhD/historia/pull/97))

### 📝 Documentation

- Added Zenodo DOI badge to README.md. ([#111](https://github.com/CodyCBakerPhD/historia/pull/111))
- Pinned the tutorial's live `historia update github` examples to a fixed historical window with `--start` / `start_date` so the remote documentation tests no longer depend on whatever activity happened "today". ([#105](https://github.com/CodyCBakerPhD/historia/pull/105))
- Replaced the README PyPI version badge image source with a stable `img.shields.io` endpoint so the badge renders correctly instead of showing "not found". ([#102](https://github.com/CodyCBakerPhD/historia/pull/102))
- Added a Step 6 to the tutorial showing an example scheduled GitHub Actions workflow that runs the full Historia maintenance loop (data fetch, commit, minified `min` branch refresh, and project board update) on a CRON schedule, and moved the optional minify step out of the numbered flow into a `note` admonition at the bottom of the page. ([#75](https://github.com/CodyCBakerPhD/historia/pull/75))
- Bolded proper-name references to Historia in docs prose for consistency across the tutorial, installation page, docs landing page, and developer guide. ([#81](https://github.com/CodyCBakerPhD/historia/pull/81))

### 🐛 Bug Fix

- Fixed trusted publishing in the PyPI release workflow by granting `id-token: write` so OIDC token exchange succeeds for `pypa/gh-action-pypi-publish`. ([#114](https://github.com/CodyCBakerPhD/historia/pull/114))
- Prevented `historia.project.update_project_item_dates` from failing when a project item is deleted mid-run by skipping only `NOT_FOUND` item-date mutations and continuing with the remaining items. ([#105](https://github.com/CodyCBakerPhD/historia/pull/105))
- Fixed an `IndexError` when a short-form GitHub Project URL (e.g. `https://github.com/{login}/projects/{number}`) was passed to any project command; a new `_parse_project_url` helper now handles both the short user format and the long `users`/`orgs` formats. ([#77](https://github.com/CodyCBakerPhD/historia/pull/77))

### 🚀 Enhancement

- Simplified the cache path version segment to a dedicated single-digit layout version that starts at `1`. Cache layout bumps are now decoupled from the package release version. ([#85](https://github.com/CodyCBakerPhD/historia/pull/85))
- Retired the `historia data minify` CLI/API. Updated the tutorial CRON automation to build a compressed archive with `tar -czf content.tar.gz content/` and to use standard-library tarball retrieval instructions. ([#86](https://github.com/CodyCBakerPhD/historia/pull/86))
- Removed the now-unused `request-graphql/` directory level from the dump layout (between `username-<login>/` and `year-<yyyy>/`). All Historia data is fetched via GraphQL, so the REST/GraphQL distinction is no longer needed and the path tree is now one segment shallower. The `historia data minify` and `historia project populate` CLIs (and their Python equivalents) now expect the `username-<login>` directory directly. ([#73](https://github.com/CodyCBakerPhD/historia/pull/73))
- Unpacked GitHub data update paths by promoting the CLI group to `historia update github` and exposing the API at `historia.github.update(...)`, and updated API docs autosummary entries so subgroup pages appear in the generated toctree. ([#89](https://github.com/CodyCBakerPhD/historia/pull/89))

### 🏠 Internal

- Split the CI test suite into two separate workflows. `testing.yml` now runs only non-remote tests and `testing_remote.yml` runs only remote-marked tests. Both are triggered on pull requests so remote connectivity failures no longer block merging. The daily schedule runs both workflows and sends separate failure notification emails per suite. ([#112](https://github.com/CodyCBakerPhD/historia/pull/112))
- Expanded daily link-checker excludes for known placeholder and authentication-required API URLs in source and tests so line-level false positives no longer fail the workflow. ([#103](https://github.com/CodyCBakerPhD/historia/pull/103))
- Updated the daily link-checker workflow to ignore GitHub blob source-line URLs under `src/` so line-annotated self-links do not trigger false-positive failures. ([#100](https://github.com/CodyCBakerPhD/historia/pull/100))
- Tagged live-service tests with the `remote` marker and applied it to the integration and tutorial Sybil suites so remote-dependent coverage is easier to find and select. ([#98](https://github.com/CodyCBakerPhD/historia/pull/98))
- Added Sybil integration to test all Python and CLI code blocks in the tutorial documentation. All placeholder values (`[user]`, `[project url]`, `[org or user]`) are replaced with live test values; outbound API calls are mocked via `unittest.mock.patch`; and the network-dependent Python snippet is skipped with a Sybil `skip` directive. ([#91](https://github.com/CodyCBakerPhD/historia/pull/91))
- Required positional-only (`/`) usage for atomic single-input functions, including `_parse_project_url`, `_collect_unique_urls`, and `move_done_to_history`, and documented the signature rule in `AGENTS.md`. ([#90](https://github.com/CodyCBakerPhD/historia/pull/90))
- Removed `move_done_to_history` entirely; the identical behavior is now available via `historia.project.transition_status(project_url=..., current_status="DONE", new_status="History")`. ([#92](https://github.com/CodyCBakerPhD/historia/pull/92))
- Fixed the `Build and upload latest release Docker image to GHCR` workflow, which is triggered via `workflow_run` after `Release to PyPI`: the release tag is now resolved from the latest published GitHub release (rather than the empty `github.event.release.tag_name`), so the checkout uses the released tag and the versioned image tag is no longer constructed as `ghcr.io/<repo>:` (which `docker tag` rejected as an invalid reference). Also gated the job on the upstream workflow's success. ([#70](https://github.com/CodyCBakerPhD/historia/pull/70))



## v0.6.0

### 🚀 Enhancement

- All public and private functions accepting more than one argument now require keyword usage via the `(*, ...)` syntax, eliminating positional argument call sites and clarifying every call. ([#67](https://github.com/CodyCBakerPhD/historia/pull/67))
- Added a `start_date` keyword argument to `historia.data.github.update`, exposed as `--start` on `historia data update github`, that overrides the "today" anchor used to count backwards, primarily so the iteration order can be exercised deterministically. ([#68](https://github.com/CodyCBakerPhD/historia/pull/68))
- Added a `--version` flag to the `historia` CLI that prints the installed package version. ([#66](https://github.com/CodyCBakerPhD/historia/pull/66))

### 🏠 Internal

- Removed the `FBT001` / `FBT002` ruff suppressions from the global `ignore` list now that boolean parameters (e.g. `overwrite` on `historia.data.github.dump_specific_info` / `dump_info_for_date`) are keyword-only; `FBT001` is suppressed only for `tests/**/*.py` because `pytest.mark.parametrize` requires positional parameters. ([#67](https://github.com/CodyCBakerPhD/historia/pull/67))
- Resolved the test TODO list in `tests/test_api_fetch.py` by adding direct tests for empty-day folder skipping, `overwrite=True` replacing existing files, `overwrite=False` preserving existing files, and a deterministic `historia.data.github.update` flow using the new `start_date` kwarg; relaxed the now-unused `FIX002` / `TD002` / `TD003` ruff suppressions on `tests/**/*.py`. ([#68](https://github.com/CodyCBakerPhD/historia/pull/68))

- Moved developer-only dependencies (`pytest`, `pre-commit`, `ipython`) out of the runtime `dependencies` list and into a new `dev` dependency group, so end users no longer pull them in on `pip install historia`. Install them for development with `pip install -e . --group dev`. ([#65](https://github.com/CodyCBakerPhD/historia/pull/65))

- Documented or released most of the per-rule entries in the ruff `ignore` list: rules with no remaining violations were dropped, tests-only and docs-only suppressions were moved into `[tool.ruff.lint.per-file-ignores]`, and every remaining global ignore now has an inline comment explaining why it is suppressed. ([#58](https://github.com/CodyCBakerPhD/historia/pull/58))
- Released the `DTZ005` / `DTZ011` ruff suppressions by attaching the system timezone to the two `datetime.now()` / `date.today()` call sites (`docs/conf.py` copyright year and the GitHub data-update CLI's "today" anchor). ([#58](https://github.com/CodyCBakerPhD/historia/pull/58))
- Released the `EM101` ruff suppression by assigning string-literal exception messages to a local variable before `raise`. ([#58](https://github.com/CodyCBakerPhD/historia/pull/58))
- Released the `PT030` ruff suppression by adding a `match=` parameter to every `pytest.warns(UserWarning)` call site. ([#58](https://github.com/CodyCBakerPhD/historia/pull/58))
- Updated the PyPI release workflow to also trigger on `v*` tag pushes so PyPI uploads occur when a tag is cut, in addition to GitHub release publication. ([#57](https://github.com/CodyCBakerPhD/historia/pull/57))
- Added a Version Check GitHub Actions workflow that fails pull requests touching `src/**` or `pyproject.toml` if the project version in `pyproject.toml` is not bumped relative to the base branch. ([#58](https://github.com/CodyCBakerPhD/historia/pull/58))



## v0.5.8

### 📝 Documentation

- Added tutorial to the docs showing step-by-step usage of the CLI and Python API for data collection, minification, project creation, population, date updates, and status transitions. ([#50](https://github.com/CodyCBakerPhD/historia/pull/50))
- Added AI usage addendum to the developer guide covering commit co-authorship requirements when AI tools contribute to commits, and updated `AGENTS.md` with the co-authorship rule. ([#48](https://github.com/CodyCBakerPhD/historia/pull/48))
- Added the Historia logo to the README and documentation landing page, and configured docs rendering so the landing-page logo remains non-clickable without the dark-mode background wrapper. ([#39](https://github.com/CodyCBakerPhD/historia/pull/39))
- Added a centered README badge block for PyPI version, supported Python versions, CI workflows, coverage, and license status. ([#37](https://github.com/CodyCBakerPhD/historia/pull/37))
- Added basic developer documentation page that embeds `AGENTS.md` content via MyST include directive. ([#44](https://github.com/CodyCBakerPhD/historia/pull/44))
- Added Sphinx documentation scaffolding with the PyData theme, API autodocs, and Read the Docs configuration for hosted docs builds. ([#19](https://github.com/CodyCBakerPhD/historia/pull/19))
- Added a GitHub icon link to the docs navbar for quick navigation back to the repository, and removed the "Show Source" page links that exposed raw HTML output. ([#42](https://github.com/CodyCBakerPhD/historia/pull/42))
- Set Sphinx Python signature rendering options to use Black-style wrapping behavior in API docs output. ([#19](https://github.com/CodyCBakerPhD/historia/pull/19))

### 🚀 Enhancement

- Generalized project status transitions so `historia project transition` can move items from any source status to any destination status via `--status` and `--new`. ([#47](https://github.com/CodyCBakerPhD/historia/pull/47))
- Simplified CLI option names to dash-free forms (for example `--url` and `--placeholder`) while preserving snake_case keyword routing in command handlers. ([#46](https://github.com/CodyCBakerPhD/historia/pull/46))
- Added data-update routing at `historia data update github ...`, with GitHub-specific data APIs nested under `historia.data.github` (including `historia.data.github.update(...)`), and exposed `historia._cli.historia_data_update_cli` for plugin-oriented extension. ([#38](https://github.com/CodyCBakerPhD/historia/pull/38))
- Removed REST request modes and related logic so data collection now consistently uses GitHub GraphQL APIs. ([#6](https://github.com/CodyCBakerPhD/historia/pull/6))
- Reorganized the CLI into nested `data` and `project` command groups, including `historia project update dates`, so operations were grouped by type and better mirrored API structure. ([#12](https://github.com/CodyCBakerPhD/historia/pull/12))
- Added mirrored API submodule groupings at `historia.data` and `historia.project` (including `historia.project.update`) to align import paths with the CLI domain structure. ([#12](https://github.com/CodyCBakerPhD/historia/pull/12))
- Limited top-level `historia` exports to submodules (`historia.data`, `historia.project`) so package imports consistently follow domain-grouped API paths. ([#12](https://github.com/CodyCBakerPhD/historia/pull/12))
- Renamed the root CLI function to `historia_cli` and exposed it for plugin integrations as both `historia._cli.historia_cli` and `historia.historia_cli`, while preserving private aliases. ([#12](https://github.com/CodyCBakerPhD/historia/pull/12))
- Unpacked project date updates to `historia.project.update_project_item_dates` and removed the `historia.project.update` submodule layer entirely. ([#34](https://github.com/CodyCBakerPhD/historia/pull/34))

### 🐛 Bug Fix

- Fixed GraphQL rate-limit handling to return an empty result set without raising key errors, and updated tests to be deterministic/offline-compatible. ([#6](https://github.com/CodyCBakerPhD/historia/pull/6))
- Fixed Sphinx API reference pages to render autodoc content for documented module members instead of appearing empty under the toctree. ([#19](https://github.com/CodyCBakerPhD/historia/pull/19))

### 🏠 Internal

- Expanded ruff lint rules to `select = ["ALL"]` and resolved all newly enabled violations, including adding request timeouts, fixing exception chaining, converting to absolute imports, and collapsing implicit string concatenations. ([#48](https://github.com/CodyCBakerPhD/historia/pull/48))
- Added mypy via pre-commit mirror for static type checking, with all pre-existing type errors resolved. ([#45](https://github.com/CodyCBakerPhD/historia/pull/45))
- Added a scheduled daily link checker workflow using `lycheeverse/lychee-action` that scans all Markdown, RST, and Python files for broken links, with a separate email notification track to distinguish failures from daily test failures. ([#51](https://github.com/CodyCBakerPhD/historia/pull/51))
- Added GHCR Dockerfiles and GitHub Actions workflows to publish `dev` and release-tagged `latest` container images. ([#36](https://github.com/CodyCBakerPhD/historia/pull/36))
- Added a GitHub Actions release workflow to automatically build and publish packages to PyPI when a release is published. ([#32](https://github.com/CodyCBakerPhD/historia/pull/32))
- Enhanced CLI tests to cover all commands (`data minify`, `project populate`, `project transition`), failure/error paths, and subgroup help output, using parametrize for exception-type variants. ([#33](https://github.com/CodyCBakerPhD/historia/pull/33))
- Rewrote repetitive API export tests to use pytest parametrization and reduce duplication. ([#17](https://github.com/CodyCBakerPhD/historia/pull/17))
- Added Codecov integration to track test coverage on every pull request. ([#18](https://github.com/CodyCBakerPhD/historia/pull/18))
- Added a scheduled daily testing workflow that reuses the shared testing workflow via `workflow_call` to avoid duplicate CI configuration. ([#29](https://github.com/CodyCBakerPhD/historia/pull/29))
- Added email notification to the daily tests workflow to alert on failures via `dawidd6/action-send-mail`. ([#40](https://github.com/CodyCBakerPhD/historia/pull/40))
