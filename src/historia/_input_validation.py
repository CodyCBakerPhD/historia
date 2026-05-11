import pathlib
import typing

import beartype.door
import beartype.roar


def _validate_type_with_beartype(*, value: object, hint: object, name: str, expected_type_description: str) -> None:
    try:
        beartype.door.die_if_unbearable(value, hint)
    except beartype.roar.BeartypeDoorHintViolation as exception:
        message = f"`{name}` must be {expected_type_description}."
        raise TypeError(message) from exception


def ensure_directory_path(*, value: object, name: str) -> pathlib.Path:
    """Validate that ``value`` is a directory path argument."""
    _validate_type_with_beartype(value=value, hint=pathlib.Path, name=name, expected_type_description="a pathlib.Path")
    path_value = typing.cast("pathlib.Path", value)
    if path_value.exists() and not path_value.is_dir():
        message = f"`{name}` must point to a directory, not a file: `{value}`."
        raise NotADirectoryError(message)
    return path_value


def ensure_int(*, value: object, name: str) -> int:
    """Validate that ``value`` is a non-bool int."""
    _validate_type_with_beartype(value=value, hint=int, name=name, expected_type_description="an int")
    if isinstance(value, bool):
        message = f"`{name}` must be an int."
        raise TypeError(message)
    return typing.cast("int", value)


def ensure_str(*, value: object, name: str) -> str:
    """Validate that ``value`` is a string."""
    _validate_type_with_beartype(value=value, hint=str, name=name, expected_type_description="a str")
    return typing.cast("str", value)


def ensure_optional_str(*, value: object, name: str) -> str | None:
    """Validate that ``value`` is either a string or ``None``."""
    _validate_type_with_beartype(value=value, hint=str | None, name=name, expected_type_description="a str or None")
    return typing.cast("str | None", value)
