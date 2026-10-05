import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from sphinx.application import Sphinx

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

HISTORIA_ACTION_REPOSITORY = "https://github.com/CodyCBakerPhD/historia-action.git"
HISTORIA_ACTION_TAG_PLACEHOLDER = "|historia_action_tag|"


def _latest_historia_action_tag() -> str:
    # A draft release has no tag yet, so only published releases are listed. Asking git rather than
    # the REST API avoids its unauthenticated rate limit, which shared build machines can exhaust.
    # Any failure fails the build, and Read the Docs then keeps serving the last good one.
    override = os.environ.get("HISTORIA_ACTION_TAG")
    if override:
        return override

    result = subprocess.run(  # noqa: S603
        ["git", "ls-remote", "--tags", "--refs", HISTORIA_ACTION_REPOSITORY],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
        timeout=60,
    )
    majors = [int(match.group(1)) for match in re.finditer(r"refs/tags/v(\d+)$", result.stdout, flags=re.MULTILINE)]
    if not majors:
        message = f"No `vN` tags found on {HISTORIA_ACTION_REPOSITORY}."
        raise RuntimeError(message)
    return f"v{max(majors)}"


HISTORIA_ACTION_TAG = _latest_historia_action_tag()


def _substitute_historia_action_tag(app: Sphinx, docname: str, source: list[str]) -> None:  # noqa: ARG001
    # MyST substitutions skip code blocks, which is exactly where the workflow examples name the tag.
    source[0] = source[0].replace(HISTORIA_ACTION_TAG_PLACEHOLDER, HISTORIA_ACTION_TAG)


def setup(app: Sphinx) -> None:
    """Register the substitution of the latest `historia-action` tag into every page."""
    app.connect("source-read", _substitute_historia_action_tag)


project = "historia"
author = "Cody Baker"
copyright = f"{datetime.now(tz=timezone.utc).astimezone().year}, {author}"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "myst_parser",
    "sphinx_tabs.tabs",
    "sphinx_copybutton",
]

myst_enable_extensions = ["colon_fence"]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "README.md"]

autosummary_generate = True
autodoc_default_options = {
    "members": True,
    "undoc-members": True,
    "show-inheritance": True,
}
autosummary_imported_members = True
python_maximum_signature_line_length = 88
python_trailing_comma_in_multi_line_signatures = True

html_theme = "pydata_sphinx_theme"
html_scaled_image_link = False
html_show_sourcelink = False
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_sidebars: dict[str, list[str]] = {
    "installation/index": [],
    "tutorial/index": [],
    "development/index": [],
}
html_theme_options = {
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/CodyCBakerPhD/historia",
            "icon": "fa-brands fa-github",
            "type": "fontawesome",
        },
    ],
}
