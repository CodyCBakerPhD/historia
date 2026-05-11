import datetime
import pathlib

import tqdm

from ._dump import dump_info_for_date
from ..._input_validation import ensure_directory_path, ensure_int, ensure_optional_str, ensure_str


def update(
    *,
    directory: pathlib.Path,
    username: str,
    past_number_of_days: int,
    start_date: str | None = None,
) -> None:
    """
    Fetch and save GitHub info for the most recent ``past_number_of_days`` days.

    Parameters
    ----------
    directory : pathlib.Path
        The base directory to save the data to.
    username : str
        The GitHub username to fetch information about.
    past_number_of_days : int
        Number of days (in addition to the anchor date) to fetch backwards from.
    start_date : str, optional
        Anchor date to count backwards from, in the format "YYYY-MM-DD".
        Defaults to today's date in the local timezone.
        Primarily intended to make the iteration deterministic for testing.

    """
    directory = ensure_directory_path(value=directory, name="directory")
    username = ensure_str(value=username, name="username")
    past_number_of_days = ensure_int(value=past_number_of_days, name="past_number_of_days")
    start_date = ensure_optional_str(value=start_date, name="start_date")

    if start_date is None:
        anchor = datetime.datetime.now(tz=datetime.timezone.utc).astimezone().date()
    else:
        anchor = datetime.date.fromisoformat(start_date)

    with tqdm.tqdm(
        iterable=range(past_number_of_days + 1),
        desc="Fetching work history",
        unit="days",
        dynamic_ncols=True,
    ) as progress_bar:
        for day in progress_bar:
            date = (anchor - datetime.timedelta(days=day)).strftime("%Y-%m-%d")
            progress_bar.set_postfix(date=date)
            overwrite = day < 2
            dump_info_for_date(directory=directory, date=date, username=username, overwrite=overwrite)
