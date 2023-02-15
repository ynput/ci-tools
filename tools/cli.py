import os
import click
from dotenv import load_dotenv
from utils import Printer


from changelog import (
    generate_milestone_changelog_cli,
    assign_milestone_to_issue_cli
)
from environment import set_pyenv_python_version
from milestones import (
    get_commit_from_milestone_description_cli,
    set_commit_to_milestone_description_cli,
    set_changelog_to_milestone_description_cli,
    set_new_milestone_title_cli
)
from versioning import (
    bump_version_cli,
    bump_file_versions_cli
)
from repository import (
    GithubConnect,
    get_latest_commit_cli
)

load_dotenv()

printer = Printer()


@click.group()
def changelog():
    printer.echo("Changelog commands activated...")

changelog.add_command(generate_milestone_changelog_cli)
changelog.add_command(assign_milestone_to_issue_cli)


@click.group()
def env():
    printer.echo("Environment commands activated...")

env.add_command(set_pyenv_python_version)

@click.group()
def repo():
    printer.echo("repository commands activated...")

repo.add_command(get_latest_commit_cli)


@click.group()
def milestones():
    printer.echo("milestones commands activated...")

milestones.add_command(get_commit_from_milestone_description_cli)
milestones.add_command(set_commit_to_milestone_description_cli)
milestones.add_command(set_changelog_to_milestone_description_cli)
milestones.add_command(set_new_milestone_title_cli)


@click.group()
def versioning():
    printer.echo("Versioning commands activated...")

versioning.add_command(bump_version_cli)
versioning.add_command(bump_file_versions_cli)


@click.group()
@click.option("--debug/--no-debug", default=False)
@click.option(
    "--repo-owner", required=False,
    help="Repo organization or owner",
)
@click.option(
    "--repo-name", required=False,
    help="Repository name"
)
@click.option(
    "--github-token", required=False, hide_input=True,
    help="Github Token"
)
@click.pass_context
def cli(ctx, debug, github_token=None, repo_owner=None, repo_name=None):
    # ensure that ctx.obj exists and is a dict (in case `cli()` is called
    # by means other than the `if` block below)
    ctx.ensure_object(dict)

    ctx.obj["DEBUG"] = debug
    Printer.set_context(ctx)

    github_token = github_token or os.getenv("GITHUB_TOKEN")
    repo_owner = repo_owner or os.getenv("GITHUB_REPOSITORY_OWNER")
    repo_name = repo_name or os.getenv("GITHUB_REPOSITORY_NAME")
    # connect to repo
    GithubConnect.set_attributes(repo_owner, repo_name, github_token)

cli.add_command(changelog)
cli.add_command(env)
cli.add_command(repo)
cli.add_command(versioning)
cli.add_command(milestones)

if __name__ == '__main__':
    cli()