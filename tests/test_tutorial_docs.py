import pathlib

import pytest

_TUTORIAL_PATH = pathlib.Path(__file__).resolve().parents[1] / "docs/tutorial/index.md"


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    "snippet",
    [
        """```bash
historia update github --directory ./history --username $PROJECT_OWNER --recency 3 --start 2026-05-10
```""",
        """```python
import pathlib
import historia

historia.github.update(
    directory=pathlib.Path("./history"),
    username=project_owner,
    past_number_of_days=3,
    start_date="2026-05-10",
)
```""",
    ],
)
def test_tutorial_update_examples_use_fixed_start_date(snippet: str) -> None:
    tutorial_text = _TUTORIAL_PATH.read_text(encoding="utf-8")

    assert tutorial_text.count(snippet) == 1
