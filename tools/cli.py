import click

from changelog import (
    generate_milestone_changelog,
    assign_milestone_to_issue
)


@click.group()
def changelog():
    click.echo("Changelog command activated...")

changelog.add_command(generate_milestone_changelog)
changelog.add_command(assign_milestone_to_issue)


@click.group()
@click.option("--debug/--no-debug", default=False)
@click.pass_context
def cli(ctx, debug):
    # ensure that ctx.obj exists and is a dict (in case `cli()` is called
    # by means other than the `if` block below)
    ctx.ensure_object(dict)

    ctx.obj["DEBUG"] = debug

cli.add_command(changelog)

if __name__ == '__main__':
    cli()
