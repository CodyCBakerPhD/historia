import pathlib

from .._dump import dump_info_for_date, dump_specific_info
from .._fetch_info import fetch_info_for_date
from .._update import update as _update_github

__all__ = ["dump_info_for_date", "dump_specific_info", "fetch_info_for_date", "update"]


def update(
    directory: pathlib.Path,
    username: str,
    past_number_of_days: int,
) -> None:
    _update_github(directory=directory, username=username, past_number_of_days=past_number_of_days)
