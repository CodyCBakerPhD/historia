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


# historia
@rich_click.group(name="historia")
@rich_click.version_option(
    version=importlib.metadata.distribution("historia").version,
    prog_name="historia",
)
def historia_cli() -> None:
    pass


# historia update
@historia_cli.group(name="update")
def historia_data_update_cli() -> None:
    pass


# historia update github
@historia_data_update_cli.command(name="github")
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
        "Defaults to today's date in the local timezone. "
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
    pass


# historia project create
@_historia_project_cli.command(name="create")
@rich_click.option("--owner", type=str, required=True, help="GitHub user or organization login to own the project.")
@rich_click.option("--title", type=str, required=True, help="Title of the new GitHub Project.")
def _historia_project_create_cli(*, owner: str, title: str) -> None:
    project = create_project_page(owner=owner, title=title)
    if project:
        message = f"Project created successfully!\nID: {project['id']}\nURL: {project['url']}"
        rich_click.echo(rich_click.style(message, fg="green"))
    else:
        message = "Project creation failed due to rate limiting. Please check the warnings above and try again later."
        rich_click.echo(rich_click.style(message, fg="red"))


# historia project populate
@_historia_project_cli.command(name="populate")
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
@rich_click.option(
    "--url",
    "project_url",
    type=str,
    required=True,
    help=(
        "The URL of the GitHub Project v2 to populate. "
        "E.g., `https://github.com/users/username/projects/1` "
        "or `https://github.com/orgs/orgname/projects/1`."
    ),
)
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
@rich_click.option(
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
@rich_click.option(
    "--members",
    "assign_members",
    is_flag=True,
    default=False,
    required=False,
    help="Assign the custom 'Members' field based on username directories.",
)
@rich_click.option(
    "--yes",
    "auto_accept",
    is_flag=True,
    default=False,
    required=False,
    help=(
        "Automatically proceed with populate when closing workflows are detected, "
        "skipping the confirmation prompt (for headless/non-interactive use)."
    ),
)
def _historia_project_populate_cli(  # noqa: PLR0913
    *,
    directory: str,
    project_url: str,
    status: str | None,
    end_date_placeholder_days: int,
    assign_members: bool,
    auto_accept: bool,
) -> None:
    try:
        closing_workflows = get_project_closing_workflows(project_url)
        if closing_workflows:
            workflow_list = ", ".join(f"'{w}'" for w in closing_workflows)
            status_description = f"the specified status '{status}'" if status is not None else "derived status values"
            warning = (
                f"\nWarning: This project has the following enabled workflow(s) that may close "
                f"the underlying GitHub items when their status is modified: {workflow_list}.\n"
                f"Populating this project with {status_description} may cause unintended changes "
                f"to source issues and pull requests.\n"
            )
            rich_click.echo(rich_click.style(warning, fg="yellow"))
            if not auto_accept and not rich_click.confirm("Do you want to proceed with populating this project?"):
                raise SystemExit(0)
        add_to_project(
            directory=pathlib.Path(directory),
            project_url=project_url,
            status=status,
            end_date_placeholder_days=end_date_placeholder_days,
            assign_members=assign_members,
        )
    except (ValueError, RuntimeError) as exception:
        rich_click.echo(rich_click.style(str(exception), fg="red"))
        raise SystemExit(1) from exception


# historia project update
@_historia_project_cli.group(name="update")
def _historia_project_update_cli() -> None:
    pass


# historia project update dates
@_historia_project_update_cli.command(name="dates")
@rich_click.option(
    "--url",
    "project_url",
    type=str,
    required=True,
    help=(
        "The URL of the GitHub Project v2 whose item dates should be updated. "
        "E.g., `https://github.com/users/username/projects/1` "
        "or `https://github.com/orgs/orgname/projects/1`."
    ),
)
@rich_click.option(
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
def _historia_project_update_dates_cli(*, project_url: str, end_date_placeholder_days: int) -> None:
    try:
        update_project_item_dates(project_url=project_url, end_date_placeholder_days=end_date_placeholder_days)
    except (ValueError, RuntimeError) as exception:
        rich_click.echo(rich_click.style(str(exception), fg="red"))
        raise SystemExit(1) from exception


# historia project update members
@_historia_project_update_cli.command(name="members")
@rich_click.option(
    "--url",
    "project_url",
    type=str,
    required=True,
    help=(
        "The URL of the GitHub Project v2 whose item member attribution should be updated. "
        "E.g., `https://github.com/users/username/projects/1` "
        "or `https://github.com/orgs/orgname/projects/1`."
    ),
)
def _historia_project_update_members_cli(*, project_url: str) -> None:
    try:
        update_project_item_members(project_url=project_url)
    except (ValueError, RuntimeError) as exception:
        rich_click.echo(rich_click.style(str(exception), fg="red"))
        raise SystemExit(1) from exception


# historia project transition
@_historia_project_cli.command(name="transition")
@rich_click.option(
    "--url",
    "project_url",
    type=str,
    required=True,
    help=(
        "The URL of the GitHub Project v2 whose items should be transitioned. "
        "E.g., `https://github.com/users/username/projects/1` "
        "or `https://github.com/orgs/orgname/projects/1`."
    ),
)
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
@rich_click.option(
    "--yes",
    "auto_accept",
    is_flag=True,
    default=False,
    required=False,
    help=(
        "Automatically proceed with transition when closing workflows are detected, "
        "skipping the confirmation prompt (for headless/non-interactive use)."
    ),
)
def _historia_project_transition_cli(
    *,
    project_url: str,
    current_status: str,
    new_status: str,
    auto_accept: bool,
) -> None:
    try:
        closing_workflows = get_project_closing_workflows(project_url)
        if closing_workflows:
            workflow_list = ", ".join(f"'{w}'" for w in closing_workflows)
            warning = (
                f"\nWarning: This project has the following enabled workflow(s) that may close "
                f"the underlying GitHub items when their status is modified: {workflow_list}.\n"
                f"Proceeding with this transition may cause unintended closures.\n"
            )
            rich_click.echo(rich_click.style(warning, fg="yellow"))
            if not auto_accept and not rich_click.confirm("Do you want to proceed with the transition?"):
                raise SystemExit(0)
        transition_status(project_url=project_url, current_status=current_status, new_status=new_status)
    except (ValueError, RuntimeError) as exception:
        rich_click.echo(rich_click.style(str(exception), fg="red"))
        raise SystemExit(1) from exception
