"""Save fetched GitHub activity to the on-disk cache."""

import json
import pathlib

import beartype

from ._fetch_info import fetch_info_for_date
from ..._globals import CACHE_LAYOUT_VERSION, INFO_TYPES, InfoType

_EMPTY_RESULTS_FILENAME = "empty-results.txt"


@beartype.beartype
def dump_specific_info(
    *,
    directory: pathlib.Path,
    info_type: InfoType,
    date: str,
    username: str,
    overwrite: bool = False,
) -> bool:
    """
    Fetch and save a specific type of GitHub info for a given date.

    An answer with no items writes no file, so a day without activity gets no folder. Instead, the date and info
    type are listed in ``empty-results.txt`` in the user's folder, one ``YYYY-MM-DD info_type`` per line. A later
    call without ``overwrite`` then does not fetch them again. An existing file is never replaced by an empty answer.

    Parameters
    ----------
    directory : pathlib.Path
        The base directory to save the data to.
    info_type : InfoType
        The type of information to fetch and save. One of "prs_opened", "prs_assigned", "prs_review_requested",
        "prs_reviewed", "issues_opened", or "issues_assigned".
    date : str
        The date to fetch information for, in the format "YYYY-MM-DD". It is a day in UTC.
    username : str
        The GitHub username to fetch information about.
    overwrite : bool, default=False
        Whether to fetch again a date and info type that was already saved or recorded as empty.
        If False, existing files will be left unchanged.
        Use of True is recommended for the most recent days (since API fetches may not be 100% accurate).

    Returns
    -------
    bool
        Whether the GitHub API rate limit was hit during the query.

    """
    year, month, day = date.split("-")
    user_directory = directory / f"version-{CACHE_LAYOUT_VERSION}" / f"username-{username}"
    subdir = user_directory / f"year-{year}" / f"month-{month}" / f"day-{day}"
    filename = f'info-{info_type.replace("_", "+")}_date-{date.replace("-", "+")}.json'
    file_path = subdir / filename
    empty_results_path = user_directory / _EMPTY_RESULTS_FILENAME
    empty_results = _read_empty_results(empty_results_path)
    empty_result = f"{date} {info_type}"
    if overwrite is False and (file_path.exists() or empty_result in empty_results):
        return False

    info, hit_rate_limit = fetch_info_for_date(info_type=info_type, date=date, username=username)

    if hit_rate_limit:
        return hit_rate_limit
    if len(info) == 0:
        # A day that already has a file keeps it, so only a day with nothing saved is recorded as empty
        if not file_path.exists() and empty_result not in empty_results:
            _write_empty_results(path=empty_results_path, empty_results=empty_results | {empty_result})
        return False

    subdir.mkdir(parents=True, exist_ok=True)
    with file_path.open(mode="w") as file_stream:
        json.dump(obj=info, fp=file_stream, indent=1)
    if empty_result in empty_results:
        _write_empty_results(path=empty_results_path, empty_results=empty_results - {empty_result})

    return False


def _read_empty_results(path: pathlib.Path, /) -> set[str]:
    """Read the ``YYYY-MM-DD info_type`` lines of a user's record of empty answers."""
    if not path.exists():
        return set()
    return set(path.read_text(encoding="utf-8").splitlines()) - {""}


def _write_empty_results(*, path: pathlib.Path, empty_results: set[str]) -> None:
    """Write a user's record of empty answers in sorted order, removing the file once it would be empty."""
    if len(empty_results) == 0:
        path.unlink(missing_ok=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data="".join(f"{empty_result}\n" for empty_result in sorted(empty_results)), encoding="utf-8")


@beartype.beartype
def dump_info_for_date(
    *,
    directory: pathlib.Path,
    date: str,
    username: str,
    overwrite: bool = False,
) -> bool:
    """
    Fetch and save all GitHub info types for a given date.

    Stops at the first info type that hits the GitHub API rate limit.

    Parameters
    ----------
    directory : pathlib.Path
        The base directory to save the data to.
    date : str
        The date to fetch information for, in the format "YYYY-MM-DD". It is a day in UTC.
    username : str
        The GitHub username to fetch information about.
    overwrite : bool, default=False
        Whether to fetch again an info type that was already saved or recorded as empty for the date.
        If False, existing files will be left unchanged.
        Use of True is recommended for the most recent days (since API fetches may not be 100% accurate).

    Returns
    -------
    bool
        Whether the GitHub API rate limit was hit during the query.

    """
    hit_rate_limit = False
    for info_type in INFO_TYPES:
        hit_rate_limit = dump_specific_info(
            directory=directory,
            info_type=info_type,
            date=date,
            username=username,
            overwrite=overwrite,
        )
        if hit_rate_limit:
            break

    return hit_rate_limit
