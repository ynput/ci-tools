
import click
from github.Repository import Repository
from github import Github
from git import Repo
from utils import Printer

printer = Printer()


class GithubConnect:
    _remote_repo: Repository
    _github: Github
    _owner: str
    _name: str
    _path: str
    _token: str

    def __init__(self):
        pass

    @property
    def remote_repo(self):
        return self._remote_repo

    @property
    def name(self):
        return self._name

    @property
    def owner(self):
        return self._owner

    @property
    def repo_path(self):
        return self._path

    @property
    def token(self):
        return self._token

    @property
    def github(self):
        return self._github

    @classmethod
    def set_attributes(cls, owner, name, token):
        cls._github = Github(token)
        cls._owner = owner
        cls._name = name
        cls._token = token
        cls._path = f"{owner}/{name}"
        cls._remote_repo = cls._github.get_repo(cls._path)


def get_local_git_repo(repo_path):
    return Repo(repo_path)

def get_latest_commit(branch):
    repo_connect = GithubConnect()
    repo = repo_connect.remote_repo

    branches = repo.get_branches()
    for branch_ in branches:
        if branch_.name == branch:
            HEAD = repo.get_commit( str(branch_.commit.sha))
            return HEAD.sha


@click.command(
    name="get-latest-commit",
    help=(
        "get latest commit."
    )
)
@click.option(
    "--branch", required=True,
    help="branch name"
)
def get_latest_commit_cli(branch):
    printer.echo(f"Branch activated '{branch}'..")
    commit_sha = get_latest_commit(branch)
    printer.echo(f"Latest commit '{commit_sha}'..")
    print(commit_sha)