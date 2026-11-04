import collections.abc
import datetime
import json
import os
import pathlib
import time
import types

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

    def _mock_fetch_info_for_date(*, info_type: str, date: str, username: str) -> tuple[list[str], bool]:
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


def _user_directory(directory: pathlib.Path, /) -> pathlib.Path:
    return directory / f"version-{historia.data.github.CACHE_LAYOUT_VERSION}" / "username-codycbakerphd"


@pytest.mark.ai_generated
def test_dump_info_for_date_records_empty_results_without_day_folders(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    def _mock_fetch_info_for_date(**_kwargs: object) -> tuple[list[str], bool]:
        return ([], False)

    monkeypatch.setattr("historia.data.github._dump.fetch_info_for_date", _mock_fetch_info_for_date)

    test_directory = tmp_path / "test_dump"
    test_directory.mkdir()

    historia.data.github.dump_info_for_date(
        directory=test_directory,
        date="2026-01-05",
        username="codycbakerphd",
    )

    assert list(test_directory.rglob(pattern="*.json")) == []
    assert list(test_directory.rglob(pattern="year-*")) == []
    empty_results_text = (_user_directory(test_directory) / "empty-results.txt").read_text(encoding="utf-8")
    assert empty_results_text.splitlines() == [
        "2026-01-05 issues_assigned",
        "2026-01-05 issues_opened",
        "2026-01-05 prs_assigned",
        "2026-01-05 prs_opened",
        "2026-01-05 prs_review_requested",
        "2026-01-05 prs_reviewed",
    ]


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("overwrite", "expected_fetch_count"),
    [
        pytest.param(False, 0, id="overwrite-false-skips"),
        pytest.param(True, 1, id="overwrite-true-fetches"),
    ],
)
def test_dump_specific_info_does_not_fetch_a_recorded_empty_result_again(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    overwrite: bool,
    expected_fetch_count: int,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    fetch_count = 0

    def _mock_fetch_info_for_date(**_kwargs: object) -> tuple[list[str], bool]:
        nonlocal fetch_count
        fetch_count += 1
        return ([], False)

    monkeypatch.setattr("historia.data.github._dump.fetch_info_for_date", _mock_fetch_info_for_date)
    user_directory = _user_directory(tmp_path)
    user_directory.mkdir(parents=True)
    (user_directory / "empty-results.txt").write_text(data="2026-01-05 prs_assigned\n", encoding="utf-8")

    historia.data.github.dump_specific_info(
        directory=tmp_path,
        info_type="prs_assigned",
        date="2026-01-05",
        username="codycbakerphd",
        overwrite=overwrite,
    )

    assert fetch_count == expected_fetch_count
    assert (user_directory / "empty-results.txt").read_text(encoding="utf-8") == "2026-01-05 prs_assigned\n"


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("initial_lines", "expected_lines"),
    [
        pytest.param(["2026-01-05 prs_assigned"], None, id="last-entry-removes-file"),
        pytest.param(
            ["2026-01-04 prs_opened", "2026-01-05 prs_assigned"],
            ["2026-01-04 prs_opened"],
            id="other-entries-kept",
        ),
    ],
)
def test_dump_specific_info_drops_a_recorded_empty_result_once_items_are_saved(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    initial_lines: list[str],
    expected_lines: list[str] | None,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    def _mock_fetch_info_for_date(**_kwargs: object) -> tuple[list[str], bool]:
        return (["https://github.com/con/nwb2bids/pull/1"], False)

    monkeypatch.setattr("historia.data.github._dump.fetch_info_for_date", _mock_fetch_info_for_date)
    user_directory = _user_directory(tmp_path)
    user_directory.mkdir(parents=True)
    empty_results_path = user_directory / "empty-results.txt"
    empty_results_path.write_text(data="".join(f"{line}\n" for line in initial_lines), encoding="utf-8")

    historia.data.github.dump_specific_info(
        directory=tmp_path,
        info_type="prs_assigned",
        date="2026-01-05",
        username="codycbakerphd",
        overwrite=True,
    )

    saved_file_path = user_directory / "year-2026" / "month-01" / "day-05" / "info-prs+assigned_date-2026+01+05.json"
    assert json.loads(saved_file_path.read_text(encoding="utf-8")) == ["https://github.com/con/nwb2bids/pull/1"]
    actual_lines = empty_results_path.read_text(encoding="utf-8").splitlines() if empty_results_path.exists() else None
    assert actual_lines == expected_lines


@pytest.mark.ai_generated
def test_dump_specific_info_keeps_a_saved_file_on_an_empty_answer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    def _mock_fetch_info_for_date(**_kwargs: object) -> tuple[list[str], bool]:
        return ([], False)

    monkeypatch.setattr("historia.data.github._dump.fetch_info_for_date", _mock_fetch_info_for_date)
    user_directory = _user_directory(tmp_path)
    day_directory = user_directory / "year-2026" / "month-01" / "day-05"
    day_directory.mkdir(parents=True)
    saved_file_path = day_directory / "info-prs+assigned_date-2026+01+05.json"
    saved_file_path.write_text(data='["https://github.com/con/nwb2bids/pull/1"]', encoding="utf-8")

    historia.data.github.dump_specific_info(
        directory=tmp_path,
        info_type="prs_assigned",
        date="2026-01-05",
        username="codycbakerphd",
        overwrite=True,
    )

    assert saved_file_path.read_text(encoding="utf-8") == '["https://github.com/con/nwb2bids/pull/1"]'
    assert not (user_directory / "empty-results.txt").exists()


@pytest.mark.ai_generated
def test_update_fetches_an_empty_older_day_only_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    fetched_dates: list[str] = []

    def _mock_fetch_info_for_date(
        *,
        info_type: str,
        date: str,
        username: str,  # noqa: ARG001
    ) -> tuple[list[str], bool]:
        if info_type == "prs_assigned":
            fetched_dates.append(date)
        return ([], False)

    monkeypatch.setattr("historia.data.github._dump.fetch_info_for_date", _mock_fetch_info_for_date)

    for _ in range(2):
        historia.data.github.update(
            directory=tmp_path,
            username="codycbakerphd",
            past_number_of_days=3,
            start_date="2026-01-05",
        )

    first_run_dates = ["2026-01-05", "2026-01-04", "2026-01-03", "2026-01-02"]
    second_run_dates = ["2026-01-05", "2026-01-04"]
    assert fetched_dates == first_run_dates + second_run_dates


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

    def _mock_fetch_info_for_date(**_kwargs: object) -> tuple[list[str], bool]:
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
def test_dump_specific_info_ignores_other_cache_layout_version(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    fetched_urls = ["https://github.com/con/nwb2bids/issues/252"]
    fetch_call_count = 0

    def _mock_fetch_info_for_date(**_kwargs: object) -> tuple[list[str], bool]:
        nonlocal fetch_call_count
        fetch_call_count += 1
        return (fetched_urls, False)

    monkeypatch.setattr("historia.data.github._dump.fetch_info_for_date", _mock_fetch_info_for_date)

    username = "codycbakerphd"
    date = "2026-01-05"
    year, month, day = date.split("-")
    test_directory = tmp_path / "test_dump"
    other_layout_directory = (
        test_directory / f"version-{historia.data.github.CACHE_LAYOUT_VERSION + 1}" / f"username-{username}"
    )
    other_layout_subdir = other_layout_directory / f"year-{year}" / f"month-{month}" / f"day-{day}"
    other_layout_subdir.mkdir(parents=True)
    other_layout_file_path = other_layout_subdir / f'info-issues+opened_date-{date.replace("-", "+")}.json'
    other_layout_contents = '["stale-other-layout"]'
    other_layout_file_path.write_text(data=other_layout_contents, encoding="utf-8")

    historia.data.github.dump_specific_info(
        directory=test_directory,
        info_type="issues_opened",
        date=date,
        username=username,
        overwrite=False,
    )

    current_layout_file_path = (
        test_directory
        / f"version-{historia.data.github.CACHE_LAYOUT_VERSION}"
        / f"username-{username}"
        / f"year-{year}"
        / f"month-{month}"
        / f"day-{day}"
        / f'info-issues+opened_date-{date.replace("-", "+")}.json'
    )
    with current_layout_file_path.open(mode="r") as file_stream:
        current_layout_content = json.load(file_stream)
    assert current_layout_content == fetched_urls
    assert other_layout_file_path.read_text(encoding="utf-8") == other_layout_contents
    assert fetch_call_count == 1


@pytest.mark.ai_generated
def test_update_iterates_over_expected_dates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    fetched_dates: list[str] = []

    def _mock_fetch_info_for_date(
        *,
        info_type: str,
        date: str,
        username: str,  # noqa: ARG001
    ) -> tuple[list[str], bool]:
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


@pytest.fixture
def set_local_timezone() -> collections.abc.Iterator[collections.abc.Callable[[str], None]]:
    original_timezone = os.environ.get("TZ")

    def _set_local_timezone(timezone: str, /) -> None:
        os.environ["TZ"] = timezone
        time.tzset()

    yield _set_local_timezone

    if original_timezone is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = original_timezone
    time.tzset()


def _frozen_datetime_module(instant: datetime.datetime, /) -> types.SimpleNamespace:
    class _FrozenDatetime(datetime.datetime):
        @classmethod
        def now(cls, tz: datetime.tzinfo | None = None) -> "_FrozenDatetime":
            return cls.fromtimestamp(instant.timestamp(), tz=tz)

    return types.SimpleNamespace(
        datetime=_FrozenDatetime,
        date=datetime.date,
        timedelta=datetime.timedelta,
        timezone=datetime.timezone,
    )


@pytest.mark.ai_generated
@pytest.mark.skipif(not hasattr(time, "tzset"), reason="time.tzset is only available on Unix")
@pytest.mark.parametrize(
    ("local_timezone", "instant", "expected_dates"),
    [
        # POSIX zone strings invert the sign, so `<+14>-14` is 14 hours ahead of UTC
        pytest.param(
            "<+14>-14",
            datetime.datetime(2026, 1, 5, 23, 30, tzinfo=datetime.timezone.utc),
            ["2026-01-05", "2026-01-04"],
            id="utc-plus-14",
        ),
        pytest.param(
            "<-12>+12",
            datetime.datetime(2026, 1, 6, 0, 30, tzinfo=datetime.timezone.utc),
            ["2026-01-06", "2026-01-05"],
            id="utc-minus-12",
        ),
    ],
)
def test_update_anchors_on_the_utc_date(  # noqa: PLR0913, PLR0917
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    set_local_timezone: collections.abc.Callable[[str], None],
    local_timezone: str,
    instant: datetime.datetime,
    expected_dates: list[str],
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")
    set_local_timezone(local_timezone)
    monkeypatch.setattr("historia.data.github._update.datetime", _frozen_datetime_module(instant))

    fetched_dates: list[str] = []

    def _mock_fetch_info_for_date(
        *,
        info_type: str,
        date: str,
        username: str,  # noqa: ARG001
    ) -> tuple[list[str], bool]:
        if info_type == "prs_opened":
            fetched_dates.append(date)
        return ([], False)

    monkeypatch.setattr("historia.data.github._dump.fetch_info_for_date", _mock_fetch_info_for_date)

    historia.data.github.update(directory=tmp_path, username="codycbakerphd", past_number_of_days=1)

    assert fetched_dates == expected_dates


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("rate_limited_info_type", "expected_hit_rate_limit", "expected_fetched_info_types"),
    [
        pytest.param(
            None,
            False,
            [
                "prs_opened",
                "prs_assigned",
                "prs_review_requested",
                "prs_reviewed",
                "issues_opened",
                "issues_assigned",
            ],
            id="no-rate-limit",
        ),
        pytest.param("prs_assigned", True, ["prs_opened", "prs_assigned"], id="rate-limited"),
    ],
)
def test_dump_info_for_date_returns_whether_rate_limit_was_hit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    rate_limited_info_type: str | None,
    expected_hit_rate_limit: bool,
    expected_fetched_info_types: list[str],
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    fetched_info_types: list[str] = []

    def _mock_fetch_info_for_date(
        *,
        info_type: str,
        date: str,  # noqa: ARG001
        username: str,  # noqa: ARG001
    ) -> tuple[list[str], bool]:
        fetched_info_types.append(info_type)
        return ([], info_type == rate_limited_info_type)

    monkeypatch.setattr("historia.data.github._dump.fetch_info_for_date", _mock_fetch_info_for_date)

    hit_rate_limit = historia.data.github.dump_info_for_date(
        directory=tmp_path,
        date="2026-01-05",
        username="codycbakerphd",
    )

    assert hit_rate_limit is expected_hit_rate_limit
    assert fetched_info_types == expected_fetched_info_types


@pytest.mark.ai_generated
@pytest.mark.parametrize(
    ("rate_limited_date", "expected_hit_rate_limit"),
    [
        pytest.param(None, False, id="no-rate-limit"),
        pytest.param("2026-01-04", True, id="rate-limited"),
    ],
)
def test_update_returns_whether_rate_limit_was_hit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    rate_limited_date: str | None,
    expected_hit_rate_limit: bool,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake-token")

    fetched_dates: list[str] = []

    def _mock_fetch_info_for_date(
        *,
        info_type: str,
        date: str,
        username: str,  # noqa: ARG001
    ) -> tuple[list[str], bool]:
        if info_type == "prs_opened":
            fetched_dates.append(date)
        return ([], date == rate_limited_date)

    monkeypatch.setattr("historia.data.github._dump.fetch_info_for_date", _mock_fetch_info_for_date)

    hit_rate_limit = historia.data.github.update(
        directory=tmp_path,
        username="codycbakerphd",
        past_number_of_days=2,
        start_date="2026-01-05",
    )

    assert hit_rate_limit is expected_hit_rate_limit
    assert fetched_dates == ["2026-01-05", "2026-01-04", "2026-01-03"]
