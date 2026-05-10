import pathlib

import rich_click

from . import data
from .data import minify as _minify
from .project import add_to_project, create_project_page, move_done_to_history, update_project_item_dates


# historia
@rich_click.group(name="historia")
def historia_cli():
    pass


# historia data
@historia_cli.group(name="data")
def _historia_data_cli():
    pass


# historia data update
@_historia_data_cli.group(name="update")
def historia_data_update_cli():
    pass


# historia data update github
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
def _historia_data_update_github_cli(
    directory: str,
    username: str,
    past_number_of_days: int,
) -> None:
    directory_path = pathlib.Path(directory)

    data.github.update(directory=directory_path, username=username, past_number_of_days=past_number_of_days)


# historia data minify
@_historia_data_cli.command(name="minify")
@rich_click.option(
    "--directory",
    type=str,
    required=True,
    help=(
        "The specific subdirectory to minify; should be for a specific version and username. "
        "E.g., `/path/to/version-0+1/username-codycbakerphd/request-graphql`."
    ),
)
def _historia_data_minify_cli(directory: str) -> None:
    directory_path = pathlib.Path(directory)

    _minify(directory=directory_path)


# historia project
@historia_cli.group(name="project")
def _historia_project_cli():
    pass


# historia project create
@_historia_project_cli.command(name="create")
@rich_click.option("--owner", type=str, required=True, help="GitHub user or organization login to own the project.")
@rich_click.option("--title", type=str, required=True, help="Title of the new GitHub Project.")
def _historia_project_create_cli(owner: str, title: str) -> None:
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
        "E.g., `/path/to/version-0+1/username-codycbakerphd/request-graphql`."
    ),
)
@rich_click.option(
    "--projecturl",
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
    "--enddateplaceholderdays",
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
def _historia_project_populate_cli(
    directory: str, project_url: str, status: str | None, end_date_placeholder_days: int
) -> None:
    try:
        add_to_project(
            directory=pathlib.Path(directory),
            project_url=project_url,
            status=status,
            end_date_placeholder_days=end_date_placeholder_days,
        )
    except (ValueError, RuntimeError) as e:
        rich_click.echo(rich_click.style(str(e), fg="red"))
        raise SystemExit(1)


# historia project update
@_historia_project_cli.group(name="update")
def _historia_project_update_cli():
    pass


# historia project update dates
@_historia_project_update_cli.command(name="dates")
@rich_click.option(
    "--projecturl",
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
    "--enddateplaceholderdays",
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
def _historia_project_update_dates_cli(project_url: str, end_date_placeholder_days: int) -> None:
    try:
        update_project_item_dates(project_url=project_url, end_date_placeholder_days=end_date_placeholder_days)
    except (ValueError, RuntimeError) as e:
        rich_click.echo(rich_click.style(str(e), fg="red"))
        raise SystemExit(1)


# historia project transition
@_historia_project_cli.command(name="transition")
@rich_click.option(
    "--projecturl",
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
    type=rich_click.Choice(["DONE"], case_sensitive=True),
    required=True,
    help="The current status of items to transition. Currently only 'DONE' is supported.",
)
def _historia_project_transition_cli(project_url: str, status: str) -> None:
    try:
        if status == "DONE":
            move_done_to_history(project_url=project_url)
    except (ValueError, RuntimeError) as e:
        rich_click.echo(rich_click.style(str(e), fg="red"))
        raise SystemExit(1)


_mywork_cli = historia_cli
