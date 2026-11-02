import datetime
import os
import pathlib
import re
import subprocess
import sys
import typing

import sphinx.application

ROOT = pathlib.Path(__file__).resolve().parents[1]
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


def _substitute_historia_action_tag(
    app: sphinx.application.Sphinx,  # noqa: ARG001
    docname: str,  # noqa: ARG001
    source: list[str],
) -> None:
    # MyST substitutions skip code blocks, which is exactly where the workflow examples name the tag.
    source[0] = source[0].replace(HISTORIA_ACTION_TAG_PLACEHOLDER, HISTORIA_ACTION_TAG)


class _Probe(typing.NamedTuple):
    field: int


_NAMED_TUPLE_FIELD_TYPE = type(_Probe.field)


def _skip_named_tuple_fields(  # noqa: PLR0913, PLR0917
    app: sphinx.application.Sphinx,  # noqa: ARG001
    what: str,  # noqa: ARG001
    name: str,  # noqa: ARG001
    obj: object,
    skip: bool,  # noqa: FBT001
    options: dict[str, object],  # noqa: ARG001
) -> bool:
    # A NamedTuple's numpy "Attributes" section already describes each field, and napoleon renders it.
    # autodoc would document every field a second time as "Alias for field number N".
    return skip or isinstance(obj, _NAMED_TUPLE_FIELD_TYPE)


def setup(app: sphinx.application.Sphinx) -> None:
    """Register the `historia-action` tag substitution and the skipping of NamedTuple field members."""
    app.connect("source-read", _substitute_historia_action_tag)
    app.connect("autodoc-skip-member", _skip_named_tuple_fields)


project = "historia"
author = "Cody Baker"
copyright = f"{datetime.datetime.now(tz=datetime.timezone.utc).astimezone().year}, {author}"

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

exclude_patterns = ["_build", "Thumbs.db", ".DS_Store", "README.md", "reviews"]

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
html_favicon = "assets/historia-favicon.svg"
html_sidebars: dict[str, list[str]] = {
    "installation/index": [],
    "tutorial/index": [],
    "development/index": [],
}
html_theme_options = {
    "logo": {
        "image_light": "assets/historia-icon-transparent.svg",
        "image_dark": "assets/historia-icon-dark-transparent.svg",
        "text": "historia",
        "alt_text": "Historia - Home",
    },
    "icon_links": [
        {
            "name": "GitHub",
            "url": "https://github.com/CodyCBakerPhD/historia",
            "icon": "fa-brands fa-github",
            "type": "fontawesome",
        },
    ],
}
