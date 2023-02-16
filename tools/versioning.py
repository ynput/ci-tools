import re
import click
from semver import VersionInfo
from repository import GithubConnect

from utils import Printer

printer = Printer()


def remove_prefix(text, prefix):
    return text[text.startswith(prefix) and len(prefix):]


def get_last_version(type):
    repo = GithubConnect().remote_repo

    version_types = {
        "CI": "^CI/[0-9\.]*",
        "release": "^[0-9\.]*"
    }

    pattern = re.compile(version_types[type])

    tags = []
    for tag in repo.get_tags():
        match_obj = pattern.match(tag.name)
        # QUESTION: didn't find better way to do this
        if not match_obj:
            continue
        match = match_obj.group(0)
        if not match:
            continue
        tags.append(tag.name)

    tag = tags[0]

    if type == "CI":
        return remove_prefix(tag, "CI/"), tag
    else:
        return tag, tag


def file_regex_replace(filename, regex, version):
    with open(filename, 'r+') as f:
        text = f.read()
        text = re.sub(regex, version, text)

        f.seek(0)
        f.write(text)
        f.truncate()


def bump_file_versions(version, version_path, pyproject_path):

    regex = "(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(-((0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(\.(0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?"
    file_regex_replace(version_path, regex, version)

    # bump pyproject.toml
    regex = "version = \"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(\+((0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*)(\.(0|[1-9]\d*|\d*[a-zA-Z-][0-9a-zA-Z-]*))*))?(\+([0-9a-zA-Z-]+(\.[0-9a-zA-Z-]+)*))?\""
    pyproject_version = f"version = \"{version}\""
    file_regex_replace(pyproject_path, regex, pyproject_version)


@click.command(
    name="bump-file-version",
    help=(
        "Bump version number inside of version.py and pyproject.toml."
    )
)
@click.option(
    "--version", required=True,
    help="Version SemVer string"
)
@click.option(
    "--pyproject-path", required=True,
    help="Relative/absolute path to pyproject.toml from project root"
)
@click.option(
    "--version-path", required=True,
    help="Relative/absolute path to version.py from project root"
)
def bump_file_versions_cli(version, version_path, pyproject_path):
    bump_file_versions(version, version_path, pyproject_path)


def current_version(type):
    last_release, _ = get_last_version(type)
    return last_release


def bump_version(type, part):
    current_version_ = current_version(type)
    last_release_v = VersionInfo.parse(current_version_)
    return last_release_v.next_version(part)


@click.command(
    name="bump-version",
    help=(
        "Bump version number from latest found tag in repository."
    )
)
@click.option(
    "--type", required=True,
    help="Type of version tag (CI or release)"
)
@click.option(
    "--part", required=True,
    help=(
        "SemVer part of version should be bumped. \n"
        "Example: major, minor, patch"
    )
)
def bump_version_cli(type, part):
    new_version = bump_version(type, part)
    print(new_version)



@click.command(
    name="current-version",
    help=(
        "Current version number from latest found tag in repository."
    )
)
@click.option(
    "--type", required=True,
    help="Type of version tag (CI or release)"
)
def current_version_cli(type):
    print(
        current_version(type)
    )