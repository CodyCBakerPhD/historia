# Changelog

## Upcoming

#### 🚀 Enhancement

- Added the Historia logo to the README and documentation landing page, and configured docs rendering so the landing-page logo remains non-clickable without the dark-mode background wrapper. ([#39](https://github.com/CodyCBakerPhD/historia/pull/39))
- Added data-update routing at `historia data update github ...`, with GitHub-specific data APIs nested under `historia.data.github` (including `historia.data.github.update(...)`), and exposed `historia._cli.historia_data_update_cli` for plugin-oriented extension. ([#38](https://github.com/CodyCBakerPhD/historia/pull/38))
- Added a centered README badge block for PyPI version, supported Python versions, CI workflows, coverage, and license status. ([#37](https://github.com/CodyCBakerPhD/historia/pull/37))
- Removed REST request modes and related logic so data collection now consistently uses GitHub GraphQL APIs. ([#6](https://github.com/CodyCBakerPhD/historia/pull/6))
- Reorganized the CLI into nested `data` and `project` command groups, including `historia project update dates`, so operations were grouped by type and better mirrored API structure. ([#12](https://github.com/CodyCBakerPhD/historia/pull/12))
- Added mirrored API submodule groupings at `historia.data` and `historia.project` (including `historia.project.update`) to align import paths with the CLI domain structure. ([#12](https://github.com/CodyCBakerPhD/historia/pull/12))
- Limited top-level `historia` exports to submodules (`historia.data`, `historia.project`) so package imports consistently follow domain-grouped API paths. ([#12](https://github.com/CodyCBakerPhD/historia/pull/12))
- Renamed the root CLI function to `historia_cli` and exposed it for plugin integrations as both `historia._cli.historia_cli` and `historia.historia_cli`, while preserving private aliases. ([#12](https://github.com/CodyCBakerPhD/historia/pull/12))
- Added Sphinx documentation scaffolding with the PyData theme, API autodocs, and Read the Docs configuration for hosted docs builds. ([#19](https://github.com/CodyCBakerPhD/historia/pull/19))
- Unpacked project date updates to `historia.project.update_project_item_dates` and removed the `historia.project.update` submodule layer entirely. ([#34](https://github.com/CodyCBakerPhD/historia/pull/34))
- Added a GitHub icon link to the docs navbar for quick navigation back to the repository, and removed the "Show Source" page links that exposed raw HTML output. ([#42](https://github.com/CodyCBakerPhD/historia/pull/42))

#### 🐛 Bug Fix

- Fixed GraphQL rate-limit handling to return an empty result set without raising key errors, and updated tests to be deterministic/offline-compatible. ([#6](https://github.com/CodyCBakerPhD/historia/pull/6))
- Fixed Sphinx API reference pages to render autodoc content for documented module members instead of appearing empty under the toctree. ([#19](https://github.com/CodyCBakerPhD/historia/pull/19))

#### 🏠 Internal

- Added GHCR Dockerfiles and GitHub Actions workflows to publish `dev` and release-tagged `latest` container images. ([#36](https://github.com/CodyCBakerPhD/historia/pull/36))
- Added a GitHub Actions release workflow to automatically build and publish packages to PyPI when a release is published. ([#32](https://github.com/CodyCBakerPhD/historia/pull/32))
- Enhanced CLI tests to cover all commands (`data minify`, `project populate`, `project transition`), failure/error paths, and subgroup help output, using parametrize for exception-type variants. ([#33](https://github.com/CodyCBakerPhD/historia/pull/33))
- Rewrote repetitive API export tests to use pytest parametrization and reduce duplication. ([#17](https://github.com/CodyCBakerPhD/historia/pull/17))
- Added Codecov integration to track test coverage on every pull request. ([#18](https://github.com/CodyCBakerPhD/historia/pull/18))
- Set Sphinx Python signature rendering options to use Black-style wrapping behavior in API docs output. ([#19](https://github.com/CodyCBakerPhD/historia/pull/19))
- Added a scheduled daily testing workflow that reuses the shared testing workflow via `workflow_call` to avoid duplicate CI configuration. ([#29](https://github.com/CodyCBakerPhD/historia/pull/29))
- Added email notification to the daily tests workflow to alert on failures via `dawidd6/action-send-mail`. ([#40](https://github.com/CodyCBakerPhD/historia/pull/40))
