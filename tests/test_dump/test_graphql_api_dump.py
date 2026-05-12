import json
import pathlib

import pytest

import historia


@pytest.mark.ai_generated
def test_dump_info_for_date_graphql(monkeypatch: pytest.MonkeyPatch, tmp_path: pathlib.Path) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    username = "codycbakerphd"

    test_directory = tmp_path / "test_dump"
    test_directory.mkdir(exist_ok=True)
    test_version_directory = test_directory / f"version-{historia.data.github.CACHE_LAYOUT_VERSION}"
    test_username_directory = test_version_directory / f"username-{username}"

    expected_directory = pathlib.Path(__file__).parent / "expected_dumps"
    expected_version_directory = expected_directory / f"version-{historia.data.github.CACHE_LAYOUT_VERSION}"
    expected_username_directory = expected_version_directory / f"username-{username}"

    def _mock_fetch_info_for_date(info_type: str, date: str, username: str) -> tuple[list[str], bool]:
        assert date == "2026-01-05"
        assert username == "codycbakerphd"
        if info_type == "issues_opened":
            return (["https://github.com/con/nwb2bids/issues/252"], False)
        if info_type == "prs_opened":
            return (
                [
                    "https://github.com/con/nwb2bids/pull/254",
                    "https://github.com/con/nwb2bids/pull/253",
                    "https://github.com/con/nwb2bids/pull/251",
                ],
                False,
            )
        return ([], False)

    monkeypatch.setattr("historia.data.github._dump.fetch_info_for_date", _mock_fetch_info_for_date)

    historia.data.github.dump_info_for_date(
        directory=test_directory,
        date="2026-01-05",
        username=username,
    )

    test_file_paths = sorted(test_username_directory.rglob(pattern="*.json"))
    relative_test_file_paths = {path.relative_to(test_version_directory) for path in test_file_paths}
    expected_file_paths = sorted(expected_username_directory.rglob(pattern="*.json"))
    relative_expected_file_paths = {path.relative_to(expected_version_directory) for path in expected_file_paths}
    assert relative_test_file_paths == relative_expected_file_paths

    for test_file_path, expected_file_path in zip(test_file_paths, expected_file_paths, strict=True):
        with test_file_path.open(mode="r") as file_stream:
            test_content = json.load(file_stream)
        with expected_file_path.open(mode="r") as file_stream:
            expected_content = json.load(file_stream)
        assert test_content == expected_content


@pytest.mark.ai_generated
def test_dump_specific_info_does_not_create_folder_when_empty(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    def _mock_fetch_info_for_date(info_type: str, date: str, username: str) -> tuple[list[str], bool]:
        return ([], False)

    monkeypatch.setattr("historia.data.github._dump.fetch_info_for_date", _mock_fetch_info_for_date)

    test_directory = tmp_path / "test_dump"
    test_directory.mkdir()

    historia.data.github.dump_info_for_date(
        directory=test_directory,
        date="2026-01-05",
        username="codycbakerphd",
    )

    # No nested day folders or files should have been created when there were no results.
    assert list(test_directory.rglob(pattern="*.json")) == []
    assert not any(child.is_dir() for child in test_directory.iterdir())


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("overwrite", "expected_contents"),
    [
        pytest.param(True, '["https://github.com/con/nwb2bids/issues/252"]', id="overwrite-true-replaces"),
        pytest.param(False, '["stale-but-preserved"]', id="overwrite-false-preserves"),
    ],
)
def test_dump_specific_info_overwrite_behavior(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    overwrite: bool,
    expected_contents: str,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    fetched_urls = ["https://github.com/con/nwb2bids/issues/252"]

    def _mock_fetch_info_for_date(info_type: str, date: str, username: str) -> tuple[list[str], bool]:
        if not overwrite:
            pytest.fail("fetch_info_for_date should not be called when the file already exists and overwrite=False")
        return (fetched_urls, False)

    monkeypatch.setattr("historia.data.github._dump.fetch_info_for_date", _mock_fetch_info_for_date)

    username = "codycbakerphd"
    date = "2026-01-05"
    year, month, day = date.split("-")
    test_directory = tmp_path / "test_dump"
    versioned_username_directory = (
        test_directory / f"version-{historia.data.github.CACHE_LAYOUT_VERSION}" / f"username-{username}"
    )
    subdir = versioned_username_directory / f"year-{year}" / f"month-{month}" / f"day-{day}"
    subdir.mkdir(parents=True)
    file_path = subdir / f'info-issues+opened_date-{date.replace("-", "+")}.json'
    initial_contents = '["stale-but-preserved"]'
    file_path.write_text(data=initial_contents, encoding="utf-8")

    historia.data.github.dump_specific_info(
        directory=test_directory,
        info_type="issues_opened",
        date=date,
        username=username,
        overwrite=overwrite,
    )

    with file_path.open(mode="r") as file_stream:
        actual_content = json.load(file_stream)
    assert actual_content == json.loads(expected_contents)


@pytest.mark.ai_generated
def test_update_iterates_over_expected_dates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    fetched_dates: list[str] = []

    def _mock_fetch_info_for_date(info_type: str, date: str, username: str) -> tuple[list[str], bool]:
        if info_type == "issues_opened":
            fetched_dates.append(date)
        return ([], False)

    monkeypatch.setattr("historia.data.github._dump.fetch_info_for_date", _mock_fetch_info_for_date)

    historia.data.github.update(
        directory=tmp_path,
        username="codycbakerphd",
        past_number_of_days=2,
        start_date="2026-01-05",
    )

    assert fetched_dates == ["2026-01-05", "2026-01-04", "2026-01-03"]
