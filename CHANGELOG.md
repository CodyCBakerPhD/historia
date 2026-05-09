# Changelog

## Upcoming

#### 🚀 Enhancement

- Removed REST request modes and related logic so data collection now consistently uses GitHub GraphQL APIs. ([#6](https://github.com/CodyCBakerPhD/historia/pull/6))
- Reorganized the CLI into nested `data` and `project` command groups, including `historia project update dates`, so operations were grouped by type and better mirrored API structure. ([#12](https://github.com/CodyCBakerPhD/historia/pull/12))
- Added mirrored API submodule groupings at `historia.data` and `historia.project` (including `historia.project.update`) to align import paths with the CLI domain structure. ([#12](https://github.com/CodyCBakerPhD/historia/pull/12))
- Limited top-level `historia` exports to submodules (`historia.data`, `historia.project`) so package imports consistently follow domain-grouped API paths. ([#12](https://github.com/CodyCBakerPhD/historia/pull/12))
- Renamed the root CLI function to `historia_cli` and exposed it for plugin integrations as both `historia._cli.historia_cli` and `historia.historia_cli`, while preserving private aliases. ([#12](https://github.com/CodyCBakerPhD/historia/pull/12))
- Added Sphinx documentation scaffolding with the PyData theme, API autodocs, and Read the Docs configuration for hosted docs builds. ([#19](https://github.com/CodyCBakerPhD/historia/pull/19))

#### 🐛 Bug Fix

- Fixed GraphQL rate-limit handling to return an empty result set without raising key errors, and updated tests to be deterministic/offline-compatible. ([#6](https://github.com/CodyCBakerPhD/historia/pull/6))
- Fixed Sphinx API reference pages to render autodoc content for documented module members instead of appearing empty under the toctree. ([#19](https://github.com/CodyCBakerPhD/historia/pull/19))

#### 🏠 Internal

- Rewrote repetitive API export tests to use pytest parametrization and reduce duplication. ([#17](https://github.com/CodyCBakerPhD/historia/pull/17))
- Added Codecov integration to track test coverage on every pull request. ([#18](https://github.com/CodyCBakerPhD/historia/pull/18))
- Set Sphinx Python signature rendering options to use Black-style wrapping behavior in API docs output. ([#19](https://github.com/CodyCBakerPhD/historia/pull/19))
- Added a scheduled daily testing workflow that reuses the shared testing workflow via `workflow_call` to avoid duplicate CI configuration. ([#29](https://github.com/CodyCBakerPhD/historia/pull/29))
