import pathlib

from .._update import update as _update_github


def github(
    directory: pathlib.Path,
    username: str,
    past_number_of_days: int,
) -> None:
    _update_github(directory=directory, username=username, past_number_of_days=past_number_of_days)


__all__ = ["github"]
