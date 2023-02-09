import click
from dotenv import load_dotenv
from utils import Printer


from changelog import (
    generate_milestone_changelog,
    assign_milestone_to_issue
)
from environment import set_pyenv_python_version


load_dotenv()
printer = Printer()


@click.group()
def changelog():
    printer.echo("Changelog command activated...")

changelog.add_command(generate_milestone_changelog)
changelog.add_command(assign_milestone_to_issue)


@click.group()
def env():
    printer.echo("Environment command activated...")

env.add_command(set_pyenv_python_version)

@click.group()
@click.option("--debug/--no-debug", default=False)
@click.pass_context
def cli(ctx, debug):
    # ensure that ctx.obj exists and is a dict (in case `cli()` is called
    # by means other than the `if` block below)
    ctx.ensure_object(dict)

    ctx.obj["DEBUG"] = debug
    Printer.set_context(ctx)

cli.add_command(changelog)
cli.add_command(env)

if __name__ == '__main__':
    cli()