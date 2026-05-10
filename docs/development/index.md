# Developer Guide

## Installation

Clone the repository and install in editable mode with the optional dependency groups you need:

```bash
# Core editable install
pip install -e .
```

## Project Layout

```
historia/
├── src/historia/         # Main package source
│   ├── _cli.py           # CLI entry points
│   └── data/
│       └── github/       # GitHub data fetch/dump/update APIs
├── tests/                # Pytest test suite
├── docs/                 # Sphinx documentation source
├── AGENTS.md             # Agent/AI contributor instructions
├── CHANGELOG.md          # Release changelog
└── pyproject.toml        # Project metadata and tool configuration
```

## Testing

This project uses [pytest](https://docs.pytest.org/) for its test suite.

### Assertion Style

Always place the **actual** (observed) value on the **left** and the **expected** value on the **right**:

```python
# Correct
assert actual_value == expected_value

# Incorrect
assert expected_value == actual_value
```

### AI-Generated Tests

Tests written or substantially assisted by AI must be marked with the `ai_generated` marker:

```python
import pytest

@pytest.mark.ai_generated
def test_something():
    ...
```

### Running Tests

```bash
python -m pytest
```

Use `pytest.mark.parametrize` wherever appropriate to reduce test duplication.

## Code Quality (Pre-commit Hooks)

This project uses [pre-commit](https://pre-commit.com/) to enforce code quality automatically before each commit.

The configured hooks are:

- **black** — code formatting
- **ruff** — linting and import sorting (with auto-fix)
- **codespell** — spell checking

Install the hooks once after cloning:

```bash
pre-commit install
```

Run all hooks manually against all files (recommended before opening a PR):

```bash
pre-commit run --all-files
```

Pre-commit will auto-fix most formatting and lint issues. Re-run the command afterward to confirm everything passes.

## CLI

The package exposes two entry points that both invoke the same CLI:

- `historia` — primary command
- `mywork` — convenience alias

Run `historia --help` to see available sub-commands.

## Changelog

Add a short description of any user-facing change to the `## Upcoming` section of `CHANGELOG.md` under the appropriate subsection:

- `#### 🚀 Enhancement` — new features
- `#### 🐛 Bug Fix` — bug fixes
- `#### 🏠 Internal` — refactors, tooling, docs

Include the GitHub PR link at the end of each entry:

```markdown
- Brief description of the change. ([#N](https://github.com/CodyCBakerPhD/historia/pull/N))
```

## Building Documentation

```{include} ../README.md
```

## Agent / AI Contributor Instructions

```{include} ../../AGENTS.md
```
