import importlib.metadata
import json
import pathlib
import typing

from ._fetch_info import fetch_info_for_date
from ..._globals import INFO_TYPES


def dump_specific_info(
    *,
    directory: pathlib.Path,
    info_type: typing.Literal["prs_opened", "prs_assigned", "issues_opened", "issues_assigned"],
    date: str,
    username: str,
    overwrite: bool = False,
) -> bool:
    """
    Fetch and save a specific type of GitHub info for a given date.

    Parameters
    ----------
    directory : pathlib.Path
        The base directory to save the data to.
    info_type : "prs_opened", "prs_assigned", "issues_opened", or "issues_assigned"
        The type of information to fetch and save.
    date : str
        The date to fetch information for, in the format "YYYY-MM-DD".
    username : str
        The GitHub username to fetch information about.
    overwrite : bool, default=False
        Whether to overwrite existing files.
        If False, existing files will be left unchanged.
        Use of True is recommended for the most recent days (since API fetches may not be 100% accurate).

    Returns
    -------
    bool
        Whether the GitHub API rate limit was hit during the query.

    """
    year, month, day = date.split("-")
    version = importlib.metadata.distribution("historia").version
    major, minor, _ = version.split(".")

    subdir = (
        directory
        / f"version-{major}+{minor}"
        / f"username-{username}"
        / "request-graphql"
        / f"year-{year}"
        / f"month-{month}"
        / f"day-{day}"
    )
    filename = f'info-{info_type.replace("_", "+")}_date-{date.replace("-", "+")}.json'
    file_path = subdir / filename
    if overwrite is False and file_path.exists():
        return False

    info, hit_rate_limit = fetch_info_for_date(info_type=info_type, date=date, username=username)

    if hit_rate_limit:
        return hit_rate_limit
    if len(info) == 0:
        return False

    subdir.mkdir(parents=True, exist_ok=True)
    with file_path.open(mode="w") as file_stream:
        json.dump(obj=info, fp=file_stream, indent=1)

    return False


def dump_info_for_date(
    *,
    directory: pathlib.Path,
    date: str,
    username: str,
    overwrite: bool = False,
) -> None:
    """
    Fetch and save all GitHub info types for a given date.

    Parameters
    ----------
    directory : pathlib.Path
        The base directory to save the data to.
    date : str
        The date to fetch information for, in the format "YYYY-MM-DD".
    username : str
        The GitHub username to fetch information about.
    overwrite : bool, default=False
        Whether to overwrite existing files.
        If False, existing files will be left unchanged.
        Use of True is recommended for the most recent days (since API fetches may not be 100% accurate).

    Returns
    -------
    bool
        Whether the GitHub API rate limit was hit during the query.

    """
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
