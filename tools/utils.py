import click


class Printer:
    ctx: click.Context

    def __init__(self):
        pass

    def echo(self, message):
        if self.ctx.obj["DEBUG"]:
            click.echo(message)

    @classmethod
    def set_context(cls, ctx):
        cls.ctx = ctx