# Changelog

## Upcoming

#### 🚀 Enhancement

- Removed REST request modes and related logic so data collection now consistently uses GitHub GraphQL APIs. ([#6](https://github.com/CodyCBakerPhD/historia/pull/6))
- Reorganized the CLI into nested `data` and `project` command groups, including `historia project update dates`, so operations were grouped by type and better mirrored API structure. ([#12](https://github.com/CodyCBakerPhD/historia/pull/12))

#### 🐛 Bug Fix

- Fixed GraphQL rate-limit handling to return an empty result set without raising key errors, and updated tests to be deterministic/offline-compatible. ([#6](https://github.com/CodyCBakerPhD/historia/pull/6))
