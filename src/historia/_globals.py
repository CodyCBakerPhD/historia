from typing import Literal

InfoType = Literal["prs_opened", "prs_assigned", "issues_opened", "issues_assigned"]

INFO_TYPES: list[InfoType] = [
    "prs_opened",
    "prs_assigned",
    "issues_opened",
    "issues_assigned",
]
