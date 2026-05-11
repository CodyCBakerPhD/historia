import pathlib

import pytest


_TUTORIAL_PATH = pathlib.Path(__file__).resolve().parents[1] / "docs/tutorial/index.md"


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "snippet",
    [
        "--start 2026-05-10",
        'start_date="2026-05-10"',
    ],
)
def test_tutorial_update_examples_use_fixed_start_date(snippet: str) -> None:
    tutorial_text = _TUTORIAL_PATH.read_text(encoding="utf-8")

    assert tutorial_text.count(snippet) == 1
