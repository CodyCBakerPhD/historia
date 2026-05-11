import json
import pathlib

import pytest

from historia._add_to_project import _collect_unique_urls


@pytest.mark.ai_generated
def test_collect_unique_urls_reads_graphql_json_files(tmp_path: pathlib.Path) -> None:
    urls_a = ["https://github.com/owner/repo/pull/1", "https://github.com/owner/repo/pull/2"]
    urls_b = ["https://github.com/owner/repo/pull/2", "https://github.com/owner/repo/issues/3"]
    non_graphql_json = {"unexpected": "format"}

    sub = tmp_path / "sub"
    sub.mkdir()
    (tmp_path / "a.json").write_text(json.dumps(urls_a))
    (sub / "b.json").write_text(json.dumps(urls_b))
    (tmp_path / "other.json").write_text(json.dumps(non_graphql_json))

    result = _collect_unique_urls(tmp_path)

    assert set(result) == {
        "https://github.com/owner/repo/pull/1",
        "https://github.com/owner/repo/pull/2",
        "https://github.com/owner/repo/issues/3",
    }
