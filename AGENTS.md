# Agent instructions

-   Always run `pre-commit` before committing and pushing changes
-   To the best of your ability, ensure tests are passing
-   Follow assertion style (actual on left, expected on right)
-   Always mark AI-generated tests with `ai_generated` Pytest marker
-   Attempt to utilize `pytest.mark.parametrize` wherever appropriate to reduce duplication in test cases
-   Avoid importing private-marked API functions (those with leading underscores) and always favor importing what is publicly exposed through `__init__.py` files
-   Always bump the version in `pyproject.toml` appropriately when any file under `src/` (except `tests/` or `docs/`), only once per pull request; do NOT bump the version for changes that are purely CI/workflow, documentation, or configuration (e.g. adding a GitHub Actions workflow, updating `AGENTS.md`, or editing `README.md` badges)
-   Leave a short description of the change or addition in the top `## Upcoming` section of the `CHANGELOG.md` under the appropriate subsection (`#### 🚀 Enhancement`, `#### 🐛 Bug Fix`, or `#### 🏠 Internal`); create the subsection if it does not yet exist; include the GitHub PR link at the end of each entry in the format `([#N](https://github.com/stamped-principles/stamped-checklist/pull/N))`
-   PR titles should be human-readable and in the past tense; they should NOT use conventional commit style
-   Always add new imports to the top of the file rather than locally scoped inside a function; the only exception is if it is needed to avoid a circular dependency
-   Never include code other than imports, `__all__`, simple import errors, or magic `__dir__` overrides in any `__init__.py` file
-   For external dependencies, always avoid specific import style (e.g., using `import abc from xyz` keyword) in favor of the generic full import (e.g., `import xyz; xyz.abc`)
-   For internal imports, always use the relative import style (e.g., `from .foo import bar`); when monkeypatching such imports in tests, target the importing module's binding (e.g., `historia.data.github.fetch_info_for_date`, instead of `historia.data.github._dump.fetch_info_for_date`), not the original definition module
-   Every commit you author MUST include a `Co-Authored-By` trailer identifying both your tool name + version and your underlying model + version. Format (replace all `<…>` placeholders with actual values): `Co-Authored-By: <Tool> <tool-version> / <Model> <model-version> <noreply@<vendor-domain>>
