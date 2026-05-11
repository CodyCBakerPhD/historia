# Developer Guide

## Installation From Source (Development)

Clone the repository and install in editable mode with the `dev` dependency group (which provides `pytest`, `pre-commit`, and `ipython`):

```bash
pip install -e . --group dev
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

```bash
python -m pytest
```

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

Use `pytest.mark.parametrize` wherever appropriate to reduce test duplication.

## Code Quality (Pre-commit Hooks)

This project uses [pre-commit](https://pre-commit.com/) to enforce code quality automatically before each commit.

The configured hooks are:

- **black** — code formatting
- **ruff** — linting and import sorting (with auto-fix)
- **codespell** — spell checking
- **mypy** — static type checking

Install the hooks once after cloning:

```bash
pre-commit install
```

Run all hooks manually against all files (recommended before opening a PR):

```bash
pre-commit run --all-files
```

Pre-commit will auto-fix most formatting and lint issues.
Re-run the command afterward to confirm everything passes.

## CLI

The **Historia** package exposes a single entry point:

- `historia` — primary entrypoint

Commands are organized into sub-groups:

- `historia data` — data management
  - `historia data update github` — fetch raw GitHub activity data for a user
  - `historia data minify` — compact raw data files
- `historia project` — GitHub Project management
  - `historia project create` — create a new GitHub Project page
  - `historia project populate` — populate a project from fetched data
  - `historia project update dates` — update item date fields in a project
  - `historia project transition` — transition project items between statuses

Since every command requires at least one option, running any command or sub-group without arguments automatically prints its help text:

```bash
historia
historia data
historia data update
historia project
```

## Changelog

Add a short description of any user-facing change to the `## Upcoming` section of `CHANGELOG.md` under the appropriate subsection:

- `### 🚀 Enhancement` — new features
- `### 🐛 Bug Fix` — bug fixes
- `### 📝 Documentation` — documentation-only changes
- `### 🏠 Internal` — refactors, tooling, CI, and test infrastructure
- `### 🔩 Dependency Updates` — dependency-only changes

Include the GitHub PR link at the end of each entry:

```markdown
- Brief description of the change. ([#N](https://github.com/CodyCBakerPhD/historia/pull/N))
```

## Building Documentation

```{include} ../README.md
:start-line: 2
```

## AI Usage Addendum

Materials across repositories in this organization have been prepared with the assistance of agentic AI coding tools and large language models (LLMs), alongside direct human authoring and supervision.

Our working practice is:
👤 Human review and accountability. We strive to have final versions of all work — prose, code, figures, and specifications — to be reviewed and/or edited by human authors, who remain accountable for the content.
🪪 Transparent annotation. Where AI tools materially contributed to a commit, we strive to annotate that commit adequately and trustworthily (for example, via a Co-Authored-By trailer identifying the tool and model version), so that the provenance of individual changes can be inspected in the git history.
🔍 Inspectable provenance. Because all work is developed in public git repositories with pull-request review, readers can trace portions of the materials which involved AI assistance.

AI tools are used as assistive instruments; they do not substitute for the scientific judgment, domain expertise, or editorial responsibility of the human authors.

### Commit Co-Authorship

When an AI tool (agent, coding assistant, IDE integration) materially contributes to a commit, the commit MUST include a `Co-Authored-By` trailer identifying both the **tool and its version** and the **model and its version**. This makes the git history the inspectable provenance record so anyone reading the repo can tell which tool produced which change.

Format (replace all `<…>` placeholders with actual values):

```
Co-Authored-By: <Tool> <tool-version> / <Model> <model-version> <noreply@<vendor-domain>>
```

Discover the tool version from the tool itself (commonly `--version`) and use the model identifier the tool reports. Don't guess.

#### Example: Claude Code

```
Co-Authored-By: Claude Code 2.1.63 / Claude Opus 4.6 <noreply@anthropic.com>
```

`claude --version` reports the Claude Code CLI version; the active model is reported by the CLI in its status / via `/model`.

## Agent / AI Contributor Instructions

```{include} ../../AGENTS.md
```
