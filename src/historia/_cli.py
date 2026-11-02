"""Command-line interface for historia."""

import collections.abc
import contextlib
import importlib.metadata
import pathlib

import rich_click

from . import data
from .project import (
    add_to_project,
    create_project_page,
    get_project_closing_workflows,
    transition_status,
    update_project_item_dates,
    update_project_item_members,
)

_OptionDecorator = collections.abc.Callable[[collections.abc.Callable[..., None]], collections.abc.Callable[..., None]]

_placeholder_option = rich_click.option(
    "--placeholder",
    "end_date_placeholder_days",
    type=int,
    default=180,
    show_default=True,
    required=False,
    help=(
        "Number of days after an item's creation date to use as the placeholder end date "
        "when the item has not yet been closed. Default is 180 (approximately 6 months)."
    ),
)


def _url_option(purpose: str, /) -> _OptionDecorator:
    return rich_click.option(
        "--url",
        "project_url",
        type=str,
        required=True,
        help=(
            f"The URL of the GitHub Project v2 {purpose}. "
            "E.g., `https://github.com/users/username/projects/1` "
            "or `https://github.com/orgs/orgname/projects/1`."
        ),
    )


def _yes_option(action: str, /) -> _OptionDecorator:
    return rich_click.option(
        "--yes",
        "auto_accept",
        is_flag=True,
        default=False,
        required=False,
        help=(
            f"Automatically proceed with {action} when closing workflows are detected, "
            "skipping the confirmation prompt (for headless/non-interactive use)."
        ),
    )


def _confirm_closing_workflows(*, project_url: str, consequence: str, prompt: str, auto_accept: bool) -> None:
    """Warn about enabled workflows that close items on a status change, then exit unless the user proceeds."""
    closing_workflows = get_project_closing_workflows(project_url)
    if not closing_workflows:
        return
    workflow_list = ", ".join(f"'{workflow}'" for workflow in closing_workflows)
    warning = (
        f"\nWarning: This project has the following enabled workflow(s) that may close "
        f"the underlying GitHub items when their status is modified: {workflow_list}.\n"
        f"{consequence}\n"
    )
    rich_click.echo(rich_click.style(warning, fg="yellow"))
    if not (auto_accept or rich_click.confirm(prompt)):
        raise SystemExit(0)


@contextlib.contextmanager
def _exit_on_api_error() -> collections.abc.Iterator[None]:
    """Report a ``ValueError`` or ``RuntimeError`` in red and exit with code 1."""
    try:
        yield
    except (ValueError, RuntimeError) as exception:
        rich_click.echo(rich_click.style(str(exception), fg="red"))
        raise SystemExit(1) from exception


# historia
@rich_click.group(name="historia")
@rich_click.version_option(
    version=importlib.metadata.distribution("historia").version,
    prog_name="historia",
)
def historia_cli() -> None:
    """Collect GitHub activity for use in project dashboards."""


# historia update
@historia_cli.group(name="update")
def historia_data_update_cli() -> None:
    """Fetch and save recent activity from a data source."""


# historia update github
@historia_data_update_cli.command(name="github", no_args_is_help=True)
@rich_click.option("--directory", type=str, required=True, help="Directory to save the data to.")
@rich_click.option("--username", type=str, required=True, help="GitHub username to fetch information about.")
@rich_click.option(
    "--recency",
    "past_number_of_days",
    type=int,
    required=True,
    help="Number of most recent days to fetch. Smart updating still applies.",
)
@rich_click.option(
    "--start",
    "start_date",
    type=str,
    default=None,
    required=False,
    help=(
        "Optional anchor date to count backwards from, in the format `YYYY-MM-DD`. "
        "Defaults to today's date in UTC, the calendar GitHub's timestamps and search dates use. "
        "Primarily intended to make iteration deterministic for backfills and testing."
    ),
)
def _historia_data_update_github_cli(
    *,
    directory: str,
    username: str,
    past_number_of_days: int,
    start_date: str | None,
) -> None:
    """Fetch and save a user's GitHub issues and pull requests by day."""
    directory_path = pathlib.Path(directory)

    data.github.update(
        directory=directory_path,
        username=username,
        past_number_of_days=past_number_of_days,
        start_date=start_date,
    )


# historia project
@historia_cli.group(name="project")
def _historia_project_cli() -> None:
    """Create and maintain a GitHub Project from the saved activity."""


# historia project create
@_historia_project_cli.command(name="create", no_args_is_help=True)
@rich_click.option("--owner", type=str, required=True, help="GitHub user or organization login to own the project.")
@rich_click.option("--title", type=str, required=True, help="Title of the new GitHub Project.")
@rich_click.option(
    "--public",
    is_flag=True,
    default=False,
    required=False,
    help="Make the project publicly visible. Projects are created private by default.",
)
def _historia_project_create_cli(*, owner: str, title: str, public: bool) -> None:
    """Create a GitHub Project with Start date and End date fields."""
    project = create_project_page(owner=owner, title=title, public=public)
    if project:
        message = f"Project created successfully!\nID: {project['id']}\nURL: {project['url']}"
        rich_click.echo(rich_click.style(message, fg="green"))
    else:
        message = "Project creation failed due to rate limiting. Please check the warnings above and try again later."
        rich_click.echo(rich_click.style(message, fg="red"))


# historia project populate
@_historia_project_cli.command(name="populate", no_args_is_help=True)
@rich_click.option(
    "--directory",
    type=str,
    required=True,
    help=(
        "The specific subdirectory containing derivatives JSON files; should be for a specific version and username. "
        "E.g., `/path/to/version-1/username-codycbakerphd`. If a parent directory containing multiple "
        "`version-*` subdirectories is provided, only the latest version is used."
    ),
)
@_url_option("to populate")
@rich_click.option(
    "--status",
    type=str,
    default=None,
    required=False,
    help=(
        "Optional custom status value to apply to all items added to the project. "
        "When omitted, the status is derived from each item's type and state."
    ),
)
@_placeholder_option
@rich_click.option(
    "--members",
    "assign_members",
    is_flag=True,
    default=False,
    required=False,
    help="Assign the custom 'Members' field based on username directories.",
)
@_yes_option("populate")
def _historia_project_populate_cli(  # noqa: PLR0913
    *,
    directory: str,
    project_url: str,
    status: str | None,
    end_date_placeholder_days: int,
    assign_members: bool,
    auto_accept: bool,
) -> None:
    """Add the saved issues and pull requests to a GitHub Project."""
    status_description = f"the specified status '{status}'" if status is not None else "derived status values"
    with _exit_on_api_error():
        _confirm_closing_workflows(
            project_url=project_url,
            consequence=(
                f"Populating this project with {status_description} may cause unintended changes "
                "to source issues and pull requests."
            ),
            prompt="Do you want to proceed with populating this project?",
            auto_accept=auto_accept,
        )
        add_to_project(
            directory=pathlib.Path(directory),
            project_url=project_url,
            status=status,
            end_date_placeholder_days=end_date_placeholder_days,
            assign_members=assign_members,
        )


# historia project update
@_historia_project_cli.group(name="update")
def _historia_project_update_cli() -> None:
    """Refresh fields on items already in the project."""


# historia project update dates
@_historia_project_update_cli.command(name="dates", no_args_is_help=True)
@_url_option("whose item dates should be updated")
@_placeholder_option
@rich_click.option(
    "--recency",
    "past_number_of_days",
    type=int,
    default=None,
    required=False,
    help=(
        "Only update items created or closed within this many most recent days. "
        "Every item is updated when this is not specified, which is what a first run "
        "or a backfill needs."
    ),
)
def _historia_project_update_dates_cli(
    *,
    project_url: str,
    end_date_placeholder_days: int,
    past_number_of_days: int | None,
) -> None:
    """Recompute the Start and End dates of items in the project."""
    with _exit_on_api_error():
        update_project_item_dates(
            project_url=project_url,
            end_date_placeholder_days=end_date_placeholder_days,
            past_number_of_days=past_number_of_days,
        )


# historia project update members
@_historia_project_update_cli.command(name="members", no_args_is_help=True)
@_url_option("whose item member attribution should be updated")
def _historia_project_update_members_cli(*, project_url: str) -> None:
    """Refresh the Members field of items in the project."""
    with _exit_on_api_error():
        update_project_item_members(project_url=project_url)


# historia project transition
@_historia_project_cli.command(name="transition", no_args_is_help=True)
@_url_option("whose items should be transitioned")
@rich_click.option(
    "--status",
    "--current",
    "current_status",
    type=str,
    required=True,
    help="The current status of items to transition.",
)
@rich_click.option(
    "--new",
    "new_status",
    type=str,
    required=True,
    help="The status to assign to matching items.",
)
@_yes_option("transition")
def _historia_project_transition_cli(
    *,
    project_url: str,
    current_status: str,
    new_status: str,
    auto_accept: bool,
) -> None:
    """Move every project item with the given status to a new status."""
    with _exit_on_api_error():
        _confirm_closing_workflows(
            project_url=project_url,
            consequence="Proceeding with this transition may cause unintended closures.",
            prompt="Do you want to proceed with the transition?",
            auto_accept=auto_accept,
        )
        transition_status(project_url=project_url, current_status=current_status, new_status=new_status)
