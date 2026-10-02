import typing

# Increment this only when the on-disk cache layout changes incompatibly.
CACHE_LAYOUT_VERSION: typing.Final[int] = 1

InfoType = typing.Literal[
    "prs_opened",
    "prs_assigned",
    "prs_review_requested",
    "prs_reviewed",
    "issues_opened",
    "issues_assigned",
]
INFO_TYPES: list[InfoType] = [
    "prs_opened",
    "prs_assigned",
    "prs_review_requested",
    "prs_reviewed",
    "issues_opened",
    "issues_assigned",
]
