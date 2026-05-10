# Changelog

## Upcoming

### 🏠 Internal

- Documented or released most of the per-rule entries in the ruff `ignore` list: rules with no remaining violations were dropped, tests-only and docs-only suppressions were moved into `[tool.ruff.lint.per-file-ignores]`, and every remaining global ignore now has an inline comment explaining why it is suppressed. ([#58](https://github.com/CodyCBakerPhD/historia/pull/58))
- Updated the PyPI release workflow to also trigger on `v*` tag pushes so PyPI uploads occur when a tag is cut, in addition to GitHub release publication. ([#57](https://github.com/CodyCBakerPhD/historia/pull/57))

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
