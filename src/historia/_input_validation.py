import pathlib


def ensure_directory_path(*, value: object, name: str) -> pathlib.Path:
    """Validate that ``value`` is a directory path argument."""
    if not isinstance(value, pathlib.Path):
        message = f"`{name}` must be a pathlib.Path."
        raise TypeError(message)
    if value.exists() and not value.is_dir():
        message = f"`{name}` must point to a directory, not a file: `{value}`."
        raise NotADirectoryError(message)
    return value


def ensure_int(*, value: object, name: str) -> int:
    """Validate that ``value`` is a non-bool int."""
    if isinstance(value, bool) or not isinstance(value, int):
        message = f"`{name}` must be an int."
        raise TypeError(message)
    return value


def ensure_str(*, value: object, name: str) -> str:
    """Validate that ``value`` is a string."""
    if not isinstance(value, str):
        message = f"`{name}` must be a str."
        raise TypeError(message)
    return value


def ensure_optional_str(*, value: object, name: str) -> str | None:
    """Validate that ``value`` is either a string or ``None``."""
    if value is None:
        return None
    return ensure_str(value=value, name=name)
