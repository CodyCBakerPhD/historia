# Code quality review — historia — 2026-10-17 (skill evaluation)

Should stylize the report in a more condensed / readable way; there could be more tables, checklists, and overall just less text blocks. Could define a jinja template or something for the skill to inject various text into (including main title). Also a table of contents for easier navigation.

NV tests should come along with minimal code snippets to make it easy to tell or not from a users level of permission / knowledge

Nest the details for each section under a `<details>` dropdown; leave a single line summary for each section above that.
 - do this in a doubly nested manner for structured report elements (a single suggestion) to hide away the lower level details

For "DC-6 — Three settings restate their tool's default" this should be a configurable option to allow; make the skill ask user at the start of it if they prefer to check for that (for example, I love setting explicit defaults, which is both PEP8 (more explicit and readable) and future-proofs against silent changes of defaults whenever I do care about the current values not changing

Does the skill suggest condensing test cases into params whenever possible? Instead of repeating the same test with slightly different conditions

CL-17 suggested a global `.dockerignore` file when a specifically named one (`Dockerfile.dev.dockerignore`) would have been more appropriate

Having a machine-readable JSON dump of the "Not changed (deliberately)" (or other structured records) would also be nice; whereby the 'md file' could be seen as the viewer of

The "Method & limits" section could have been called 'provenance' and should be minimized from most readers who do not care to know those low level records of how the scan ran

The skill should check that docstrings are actually linted, both for presence and against the code they describe. Here `select = ["ALL"]` turned on the pydocstyle rules, but every source module's name starts with an underscore, so ruff treated the whole package as private and D100 to D107 never fired. Deleting the docstring of the public `add_to_project` still passed. Nothing checked that a docstring's sections match the code either, which is how CL-1 (a documented `bool` return that never existed) got in. The report found CL-1 by running ruff's preview DOC202 by hand, yet never proposed turning that check on, and it dismissed the missing `Raises` sections on public functions as a style choice. The missing lint configuration should be its own finding, with a count of what turning it on would flag.
 - ruff's DOC rules and numpydoc's `numpydoc-validation` hook complement each other, so suggest both. DOC202 and DOC501 catch a stray `Returns` and a missing `Raises`, which numpydoc does not check. numpydoc's GL08 and PR01 catch a public name with no docstring and an undocumented parameter with no `Parameters` section, which ruff misses
 - do not suggest `[tool.ruff.lint.pydocstyle] convention = "numpy"` on its own. It switches off D417, which is the ruff rule that catches a parameter missing from a numpy `Parameters` section
 - measured on this repo after round 4: the DOC rules (DOC502 aside) with one-line docstrings exempt flagged 20 gaps, 6 of them on public functions, and numpydoc (with private names, EX01, SA01, ES01, GL02 and GL03 excluded) flagged 2 click groups and 7 modules with no docstring. [#214](https://github.com/CodyCBakerPhD/historia/pull/214) fixed all of them and turned both checks on
